"""Retrieval evaluation dataset、review 與報表讀取 service。"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.auth.verifier import CurrentPrincipal
from app.core.settings import AppSettings
from app.db.models import (
    ChunkType,
    Document,
    DocumentChunk,
    DocumentStatus,
    EvaluationQueryType,
    RetrievalEvalDataset,
    RetrievalEvalItem,
    RetrievalEvalItemSpan,
    RetrievalEvalRun,
    RetrievalEvalRunArtifact,
    Role,
    utc_now,
)
from app.schemas.evaluation import (
    CreateEvaluationItemRequest,
    EvaluationCandidatePreviewResponse,
    EvaluationCandidateStageResponse,
    EvaluationDatasetDetailResponse,
    EvaluationDatasetListResponse,
    EvaluationDatasetSummary,
    EvaluationDocumentSearchHit,
    EvaluationItemSpanResponse,
    EvaluationItemSummary,
    EvaluationPreviewDebugRequest,
    EvaluationQueryRoutingDetail,
    EvaluationRunReportResponse,
    EvaluationRunSummary,
    EvaluationSelectionDetail,
    EvaluationStageCandidate,
)
from app.services.access import require_area_access, require_minimum_area_role
from app.services.evaluation_mapping import CandidateWindow, GoldSpan, first_hit_rank, match_gold_relevance, match_gold_relevance_for_windows
from app.services.retrieval_routing import QueryRoutingDecision, build_query_routing_decision
from app.services.retrieval_selection import RetrievalSelectionResult, apply_scope_aware_selection
from app.services.retrieval import (
    RetrievalResult,
    RetrievalTrace,
    _apply_python_rrf,
    _apply_ranking_policy,
    _apply_rerank,
    _build_retrieval_candidate,
    _recall_ranked_candidates,
)
from app.services.retrieval_assembler import assemble_retrieval_result


@dataclass(slots=True)
class ItemStageEvaluationResult:
    """單題 retrieval evaluation 的共用 stage 計算結果。"""

    item: RetrievalEvalItem
    gold_spans: list[GoldSpan]
    query_routing: EvaluationQueryRoutingDetail
    selection: EvaluationSelectionDetail
    recall_stage: EvaluationCandidateStageResponse
    rerank_stage: EvaluationCandidateStageResponse
    assembled_stage: EvaluationCandidateStageResponse


def list_area_evaluation_datasets(
    *,
    session: Session,
    principal: CurrentPrincipal,
    area_id: str,
) -> EvaluationDatasetListResponse:
    """列出指定 area 的 evaluation datasets。

    參數：
    - `session`：目前資料庫 session。
    - `principal`：目前已驗證使用者。
    - `area_id`：目標 area。

    回傳：
    - `EvaluationDatasetListResponse`：可存取 datasets 清單。
    """

    require_minimum_area_role(session=session, principal=principal, area_id=area_id, minimum_role=Role.maintainer)
    datasets = session.scalars(
        select(RetrievalEvalDataset)
        .where(RetrievalEvalDataset.area_id == area_id)
        .order_by(RetrievalEvalDataset.created_at.desc())
    ).all()
    return EvaluationDatasetListResponse(items=[build_dataset_summary(session=session, dataset=dataset) for dataset in datasets])


def create_area_evaluation_dataset(
    *,
    session: Session,
    principal: CurrentPrincipal,
    area_id: str,
    name: str,
    query_type: EvaluationQueryType,
) -> EvaluationDatasetSummary:
    """建立新的 evaluation dataset。

    參數：
    - `session`：目前資料庫 session。
    - `principal`：目前已驗證使用者。
    - `area_id`：目標 area。
    - `name`：dataset 名稱。
    - `query_type`：dataset 題型。

    回傳：
    - `EvaluationDatasetSummary`：新建立的 dataset。
    """

    require_minimum_area_role(session=session, principal=principal, area_id=area_id, minimum_role=Role.maintainer)
    dataset = RetrievalEvalDataset(area_id=area_id, name=name, query_type=query_type, created_by_sub=principal.sub)
    session.add(dataset)
    session.commit()
    session.refresh(dataset)
    return build_dataset_summary(session=session, dataset=dataset)


def get_evaluation_dataset_detail(
    *,
    session: Session,
    principal: CurrentPrincipal,
    dataset_id: str,
) -> EvaluationDatasetDetailResponse:
    """讀取 dataset 詳細資料。

    參數：
    - `session`：目前資料庫 session。
    - `principal`：目前已驗證使用者。
    - `dataset_id`：目標 dataset。

    回傳：
    - `EvaluationDatasetDetailResponse`：dataset 詳細資料。
    """

    dataset = _get_authorized_dataset(session=session, principal=principal, dataset_id=dataset_id)
    items = session.scalars(
        select(RetrievalEvalItem).where(RetrievalEvalItem.dataset_id == dataset.id).order_by(RetrievalEvalItem.created_at.asc())
    ).all()
    runs = session.scalars(
        select(RetrievalEvalRun).where(RetrievalEvalRun.dataset_id == dataset.id).order_by(RetrievalEvalRun.created_at.desc())
    ).all()
    spans_by_item_id = _load_spans_by_item_id(session=session, item_ids=[item.id for item in items])
    return EvaluationDatasetDetailResponse(
        dataset=build_dataset_summary(session=session, dataset=dataset),
        items=[build_item_summary(item=item, spans=spans_by_item_id.get(item.id, [])) for item in items],
        runs=[build_run_summary(run) for run in runs],
    )


def delete_evaluation_dataset(
    *,
    session: Session,
    principal: CurrentPrincipal,
    dataset_id: str,
) -> None:
    """刪除單一 evaluation dataset。

    參數：
    - `session`：目前資料庫 session。
    - `principal`：目前已驗證使用者。
    - `dataset_id`：目標 dataset。

    回傳：
    - `None`：刪除成功時不回傳內容。
    """

    dataset = _get_authorized_dataset(session=session, principal=principal, dataset_id=dataset_id)
    session.delete(dataset)
    session.commit()


def create_evaluation_item(
    *,
    session: Session,
    principal: CurrentPrincipal,
    dataset_id: str,
    payload: CreateEvaluationItemRequest,
) -> EvaluationItemSummary:
    """在 dataset 內新增題目。

    參數：
    - `session`：目前資料庫 session。
    - `principal`：目前已驗證使用者。
    - `dataset_id`：目標 dataset。
    - `payload`：建立題目 payload。

    回傳：
    - `EvaluationItemSummary`：新題目摘要。
    """

    dataset = _get_authorized_dataset(session=session, principal=principal, dataset_id=dataset_id)
    if payload.query_type is not None and payload.query_type != dataset.query_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="item query_type 必須與 dataset query_type 一致。",
        )
    item = RetrievalEvalItem(
        dataset_id=dataset.id,
        query_type=dataset.query_type,
        query_text=payload.query_text,
        language=payload.language,
        notes=payload.notes,
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    return build_item_summary(item=item, spans=[])


def delete_evaluation_item(
    *,
    session: Session,
    principal: CurrentPrincipal,
    item_id: str,
) -> None:
    """刪除單一 evaluation 題目。

    參數：
    - `session`：目前資料庫 session。
    - `principal`：目前已驗證使用者。
    - `item_id`：目標題目。

    回傳：
    - `None`：刪除成功時不回傳內容。
    """

    item, _dataset = _get_authorized_item(session=session, principal=principal, item_id=item_id)
    session.delete(item)
    session.commit()


def add_item_span(
    *,
    session: Session,
    principal: CurrentPrincipal,
    item_id: str,
    document_id: str,
    start_offset: int,
    end_offset: int,
    relevance_grade: int,
) -> EvaluationItemSummary:
    """為題目新增 gold source span。

    參數：
    - `session`：目前資料庫 session。
    - `principal`：目前已驗證使用者。
    - `item_id`：目標題目。
    - `document_id`：來源文件。
    - `start_offset`：起始 offset。
    - `end_offset`：結束 offset。
    - `relevance_grade`：relevance 分級。

    回傳：
    - `EvaluationItemSummary`：更新後題目摘要。
    """

    item, dataset = _get_authorized_item(session=session, principal=principal, item_id=item_id)
    document = _get_authorized_ready_document(
        session=session,
        principal=principal,
        area_id=dataset.area_id,
        document_id=document_id,
    )
    if not document.display_text or end_offset > len(document.display_text):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="span 超出 display_text 範圍。")
    session.execute(
        delete(RetrievalEvalItemSpan).where(
            RetrievalEvalItemSpan.item_id == item.id,
            RetrievalEvalItemSpan.is_retrieval_miss.is_(True),
        )
    )
    existing_span = session.scalars(
        select(RetrievalEvalItemSpan).where(
            RetrievalEvalItemSpan.item_id == item.id,
            RetrievalEvalItemSpan.document_id == document.id,
            RetrievalEvalItemSpan.start_offset == start_offset,
            RetrievalEvalItemSpan.end_offset == end_offset,
            RetrievalEvalItemSpan.is_retrieval_miss.is_(False),
        )
    ).one_or_none()
    if existing_span is None:
        session.add(
            RetrievalEvalItemSpan(
                item_id=item.id,
                document_id=document.id,
                start_offset=start_offset,
                end_offset=end_offset,
                relevance_grade=relevance_grade,
                is_retrieval_miss=False,
                created_by_sub=principal.sub,
            )
        )
    else:
        existing_span.relevance_grade = relevance_grade
        existing_span.updated_at = utc_now()
    session.commit()
    session.refresh(item)
    spans = _load_spans_by_item_id(session=session, item_ids=[item.id]).get(item.id, [])
    return build_item_summary(item=item, spans=spans)


def mark_item_retrieval_miss(
    *,
    session: Session,
    principal: CurrentPrincipal,
    item_id: str,
) -> EvaluationItemSummary:
    """將題目標記為 retrieval miss。

    參數：
    - `session`：目前資料庫 session。
    - `principal`：目前已驗證使用者。
    - `item_id`：目標題目。

    回傳：
    - `EvaluationItemSummary`：更新後題目摘要。
    """

    item, _dataset = _get_authorized_item(session=session, principal=principal, item_id=item_id)
    session.execute(delete(RetrievalEvalItemSpan).where(RetrievalEvalItemSpan.item_id == item.id))
    session.add(
        RetrievalEvalItemSpan(
            item_id=item.id,
            document_id=None,
            start_offset=0,
            end_offset=0,
            relevance_grade=None,
            is_retrieval_miss=True,
            created_by_sub=principal.sub,
        )
    )
    session.commit()
    session.refresh(item)
    spans = _load_spans_by_item_id(session=session, item_ids=[item.id]).get(item.id, [])
    return build_item_summary(item=item, spans=spans)


def preview_evaluation_candidates(
    *,
    session: Session,
    principal: CurrentPrincipal,
    settings: AppSettings,
    item_id: str,
    payload: EvaluationPreviewDebugRequest,
) -> EvaluationCandidatePreviewResponse:
    """讀取單題的 recall/rerank/assembled candidate preview。

    參數：
    - `session`：目前資料庫 session。
    - `principal`：目前已驗證使用者。
    - `settings`：應用程式設定。
    - `item_id`：目標題目。
    - `payload`：preview 臨時調參 payload。

    回傳：
    - `EvaluationCandidatePreviewResponse`：三階段 candidate preview。
    """

    item, dataset = _get_authorized_item(session=session, principal=principal, item_id=item_id)
    spans = _load_spans_by_item_id(session=session, item_ids=[item.id]).get(item.id, [])
    stage_result = evaluate_item_stage_outputs(
        session=session,
        principal=principal,
        settings=_apply_preview_debug_overrides(settings=settings, payload=payload),
        area_id=dataset.area_id,
        item=item,
        spans=spans,
        top_k=payload.top_k,
        apply_rerank=payload.apply_rerank,
    )
    return EvaluationCandidatePreviewResponse(
        dataset=build_dataset_summary(session=session, dataset=dataset),
        item=build_item_summary(item=item, spans=spans),
        query_routing=stage_result.query_routing,
        selection=stage_result.selection,
        recall=stage_result.recall_stage,
        rerank=stage_result.rerank_stage,
        assembled=stage_result.assembled_stage,
        document_search_hits=_search_document_hits(
            session=session,
            principal=principal,
            area_id=dataset.area_id,
            query=item.query_text,
        ),
    )


def evaluate_item_stage_outputs(
    *,
    session: Session,
    principal: CurrentPrincipal,
    settings: AppSettings,
    area_id: str,
    item: RetrievalEvalItem,
    spans: list[RetrievalEvalItemSpan],
    top_k: int,
    apply_rerank: bool = True,
    allowed_document_ids_override: tuple[str, ...] | None = None,
) -> ItemStageEvaluationResult:
    """建立單題共用的 recall/rerank/assembled stage 結果。

    參數：
    - `session`：目前資料庫 session。
    - `principal`：目前已驗證使用者。
    - `settings`：應用程式設定。
    - `area_id`：目標 area。
    - `item`：目前題目。
    - `spans`：該題 gold spans。
    - `top_k`：stage 回傳上限。
    - `apply_rerank`：是否套用 rerank stage。
    - `allowed_document_ids_override`：benchmark-only 文件白名單；用於具備原始文件上下文的資料集。

    回傳：
    - `ItemStageEvaluationResult`：可供 preview 與 benchmark 共用的 stage 結果。
    """

    routing_decision = build_query_routing_decision(
        settings=settings,
        query=item.query_text,
        explicit_query_type=item.query_type,
        session=session,
        principal=principal,
        area_id=area_id,
    )
    effective_settings = routing_decision.effective_settings
    retrieval_query = item.query_text
    scoped_document_ids = allowed_document_ids_override or routing_decision.resolved_document_ids or None

    recall_matches = _apply_ranking_policy(
        matches=_apply_python_rrf(
            matches=_recall_ranked_candidates(
                session=session,
                settings=effective_settings,
                area_id=area_id,
                query=retrieval_query,
                allowed_document_ids=scoped_document_ids,
                allowed_parent_ids=None,
            ),
            settings=effective_settings,
        ),
        query=item.query_text,
        settings=effective_settings,
    )
    rerank_matches = (
        _apply_rerank(matches=recall_matches, query=item.query_text, settings=effective_settings)
        if apply_rerank
        else recall_matches
    )
    reranked_candidates = [_build_retrieval_candidate(match) for match in rerank_matches]
    selection_result = apply_scope_aware_selection(
        candidates=reranked_candidates,
        selected_profile=routing_decision.selected_profile,
        resolved_document_ids=scoped_document_ids or (),
        max_contexts=effective_settings.assembler_max_contexts,
    )
    retrieval_result = RetrievalResult(
        candidates=selection_result.candidates,
        trace=_build_empty_trace(
            query=item.query_text,
            settings=effective_settings,
            total_candidates=len(rerank_matches),
            routing_decision=routing_decision,
            selection_result=selection_result,
        ),
    )
    assembled_result = assemble_retrieval_result(session=session, settings=effective_settings, retrieval_result=retrieval_result)
    gold_spans = [
        GoldSpan(
            document_id=span.document_id,
            start_offset=span.start_offset,
            end_offset=span.end_offset,
            relevance_grade=span.relevance_grade,
            is_retrieval_miss=span.is_retrieval_miss,
        )
        for span in spans
    ]
    document_names = _load_document_names(session=session, area_id=area_id)
    return ItemStageEvaluationResult(
        item=item,
        gold_spans=gold_spans,
        query_routing=_build_query_routing_detail(routing_decision=routing_decision),
        selection=_build_selection_detail(selection_result=selection_result),
        recall_stage=_build_recall_stage(
            matches=recall_matches,
            gold_spans=gold_spans,
            document_names=document_names,
            top_k=top_k,
        ),
        rerank_stage=_build_rerank_stage(
            candidates=retrieval_result.candidates,
            gold_spans=gold_spans,
            document_names=document_names,
            top_k=top_k,
            apply_rerank=apply_rerank,
        ),
        assembled_stage=_build_assembled_stage(
            session=session,
            contexts=assembled_result.assembled_contexts,
            gold_spans=gold_spans,
            document_names=document_names,
            top_k=top_k,
        ),
    )


def _apply_preview_debug_overrides(*, settings: AppSettings, payload: EvaluationPreviewDebugRequest) -> AppSettings:
    """將 preview 臨時調參套用到單題 evaluation。"""

    updates: dict[str, int] = {}
    if payload.retrieval_vector_top_k is not None:
        updates["retrieval_vector_top_k"] = payload.retrieval_vector_top_k
    if payload.retrieval_fts_top_k is not None:
        updates["retrieval_fts_top_k"] = payload.retrieval_fts_top_k
    if payload.retrieval_max_candidates is not None:
        updates["retrieval_max_candidates"] = payload.retrieval_max_candidates
    if payload.rerank_top_n is not None:
        updates["rerank_top_n"] = payload.rerank_top_n
    return settings.model_copy(update=updates) if updates else settings


def create_evaluation_run(
    *,
    session: Session,
    principal: CurrentPrincipal,
    settings: AppSettings,
    dataset_id: str,
    top_k: int,
    evaluation_profile: str = "production_like_v1",
) -> EvaluationRunReportResponse:
    """執行 dataset benchmark。

    參數：
    - `session`：目前資料庫 session。
    - `principal`：目前已驗證使用者。
    - `settings`：應用程式設定。
    - `dataset_id`：目標 dataset。
    - `top_k`：指標截斷排名。

    回傳：
    - `EvaluationRunReportResponse`：完整 run 報表。
    """

    dataset = _get_authorized_dataset(session=session, principal=principal, dataset_id=dataset_id)
    items = session.scalars(select(RetrievalEvalItem).where(RetrievalEvalItem.dataset_id == dataset.id)).all()
    spans_by_item_id = _load_spans_by_item_id(session=session, item_ids=[item.id for item in items])
    from app.services.evaluation_runner import run_evaluation_dataset

    return run_evaluation_dataset(
        session=session,
        principal=principal,
        settings=settings,
        dataset=dataset,
        items=items,
        spans_by_item_id=spans_by_item_id,
        top_k=top_k,
        evaluation_profile=evaluation_profile,
    )


def get_evaluation_run_report(
    *,
    session: Session,
    principal: CurrentPrincipal,
    run_id: str,
) -> EvaluationRunReportResponse:
    """讀取既有 benchmark run 報表。

    參數：
    - `session`：目前資料庫 session。
    - `principal`：目前已驗證使用者。
    - `run_id`：目標 run。

    回傳：
    - `EvaluationRunReportResponse`：完整 run 報表。
    """

    run, dataset = _get_authorized_run(session=session, principal=principal, run_id=run_id)
    artifact = session.scalars(
        select(RetrievalEvalRunArtifact).where(RetrievalEvalRunArtifact.run_id == run.id)
    ).one_or_none()
    if artifact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到指定的 evaluation run。")
    payload = json.loads(artifact.report_json)
    baseline_compare = json.loads(artifact.baseline_compare_json) if artifact.baseline_compare_json else None
    return EvaluationRunReportResponse(
        run=build_run_summary(run),
        dataset=build_dataset_summary(session=session, dataset=dataset),
        summary_metrics=payload["summary_metrics"],
        breakdowns=payload["breakdowns"],
        per_query=payload["per_query"],
        baseline_compare=baseline_compare,
    )


def build_dataset_summary(*, session: Session, dataset: RetrievalEvalDataset) -> EvaluationDatasetSummary:
    """建立 dataset summary。

    參數：
    - `session`：目前資料庫 session。
    - `dataset`：ORM dataset。

    回傳：
    - `EvaluationDatasetSummary`：API summary。
    """

    item_count = session.scalar(
        select(func.count(RetrievalEvalItem.id)).where(RetrievalEvalItem.dataset_id == dataset.id)
    ) or 0
    return EvaluationDatasetSummary(
        id=dataset.id,
        area_id=dataset.area_id,
        name=dataset.name,
        query_type=dataset.query_type,
        baseline_run_id=dataset.baseline_run_id,
        created_by_sub=dataset.created_by_sub,
        created_at=dataset.created_at,
        updated_at=dataset.updated_at,
        item_count=int(item_count),
    )


def build_item_summary(*, item: RetrievalEvalItem, spans: list[RetrievalEvalItemSpan]) -> EvaluationItemSummary:
    """建立 item summary。

    參數：
    - `item`：ORM item。
    - `spans`：該題的 spans。

    回傳：
    - `EvaluationItemSummary`：API summary。
    """

    return EvaluationItemSummary(
        id=item.id,
        dataset_id=item.dataset_id,
        query_type=item.query_type,
        query_text=item.query_text,
        language=item.language,
        notes=item.notes,
        created_at=item.created_at,
        updated_at=item.updated_at,
        spans=[build_span_response(span) for span in spans],
    )


def build_span_response(span: RetrievalEvalItemSpan) -> EvaluationItemSpanResponse:
    """建立 span response。

    參數：
    - `span`：ORM span。

    回傳：
    - `EvaluationItemSpanResponse`：API span response。
    """

    return EvaluationItemSpanResponse.model_validate(span)


def build_run_summary(run: RetrievalEvalRun) -> EvaluationRunSummary:
    """建立 run summary。

    參數：
    - `run`：ORM run。

    回傳：
    - `EvaluationRunSummary`：API run summary。
    """

    payload = {
        "id": run.id,
        "dataset_id": run.dataset_id,
        "status": run.status,
        "baseline_run_id": run.baseline_run_id,
        "created_by_sub": run.created_by_sub,
        "total_items": run.total_items,
        "evaluation_profile": run.evaluation_profile,
        "config_snapshot": json.loads(run.config_snapshot) if run.config_snapshot else {},
        "error_message": run.error_message,
        "created_at": run.created_at,
        "completed_at": run.completed_at,
    }
    return EvaluationRunSummary.model_validate(payload)


def _get_authorized_dataset(
    *,
    session: Session,
    principal: CurrentPrincipal,
    dataset_id: str,
) -> RetrievalEvalDataset:
    """讀取並驗證 dataset 存取權。

    參數：
    - `session`：目前資料庫 session。
    - `principal`：目前已驗證使用者。
    - `dataset_id`：目標 dataset。

    回傳：
    - `RetrievalEvalDataset`：已授權 dataset。
    """

    dataset = session.get(RetrievalEvalDataset, dataset_id)
    if dataset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到指定的 evaluation dataset。")
    try:
        require_minimum_area_role(session=session, principal=principal, area_id=dataset.area_id, minimum_role=Role.maintainer)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_404_NOT_FOUND:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到指定的 evaluation dataset。") from exc
        raise
    return dataset


def _get_authorized_item(
    *,
    session: Session,
    principal: CurrentPrincipal,
    item_id: str,
) -> tuple[RetrievalEvalItem, RetrievalEvalDataset]:
    """讀取並驗證題目存取權。

    參數：
    - `session`：目前資料庫 session。
    - `principal`：目前已驗證使用者。
    - `item_id`：目標題目。

    回傳：
    - `tuple[RetrievalEvalItem, RetrievalEvalDataset]`：已授權題目與 dataset。
    """

    item = session.get(RetrievalEvalItem, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到指定的 evaluation item。")
    dataset = _get_authorized_dataset(session=session, principal=principal, dataset_id=item.dataset_id)
    return item, dataset


def _get_authorized_run(
    *,
    session: Session,
    principal: CurrentPrincipal,
    run_id: str,
) -> tuple[RetrievalEvalRun, RetrievalEvalDataset]:
    """讀取並驗證 run 存取權。

    參數：
    - `session`：目前資料庫 session。
    - `principal`：目前已驗證使用者。
    - `run_id`：目標 run。

    回傳：
    - `tuple[RetrievalEvalRun, RetrievalEvalDataset]`：已授權 run 與 dataset。
    """

    run = session.get(RetrievalEvalRun, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到指定的 evaluation run。")
    dataset = _get_authorized_dataset(session=session, principal=principal, dataset_id=run.dataset_id)
    return run, dataset


def _load_spans_by_item_id(*, session: Session, item_ids: list[str]) -> dict[str, list[RetrievalEvalItemSpan]]:
    """批次載入題目的 spans。

    參數：
    - `session`：目前資料庫 session。
    - `item_ids`：題目 id 列表。

    回傳：
    - `dict[str, list[RetrievalEvalItemSpan]]`：依 item_id 分組的 spans。
    """

    if not item_ids:
        return {}
    spans = session.scalars(
        select(RetrievalEvalItemSpan)
        .where(RetrievalEvalItemSpan.item_id.in_(item_ids))
        .order_by(RetrievalEvalItemSpan.created_at.asc())
    ).all()
    grouped: dict[str, list[RetrievalEvalItemSpan]] = defaultdict(list)
    for span in spans:
        grouped[span.item_id].append(span)
    return grouped


def _get_authorized_ready_document(
    *,
    session: Session,
    principal: CurrentPrincipal,
    area_id: str,
    document_id: str,
) -> Document:
    """讀取已授權且 ready 的文件。

    參數：
    - `session`：目前資料庫 session。
    - `principal`：目前已驗證使用者。
    - `area_id`：目標 area。
    - `document_id`：文件 id。

    回傳：
    - `Document`：已授權且 ready 文件。
    """

    require_minimum_area_role(session=session, principal=principal, area_id=area_id, minimum_role=Role.maintainer)
    document = session.get(Document, document_id)
    if document is None or document.area_id != area_id or document.status != DocumentStatus.ready:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到指定的文件。")
    return document


def _build_empty_trace(
    *,
    query: str,
    settings: AppSettings,
    total_candidates: int,
    routing_decision: QueryRoutingDecision,
    selection_result: RetrievalSelectionResult,
 ) -> RetrievalTrace:
    """建立 assembler 需要的最小 trace 物件。

    參數：
    - `query`：題目 query。
    - `settings`：應用程式設定。
    - `total_candidates`：候選總數。
    - `routing_decision`：本次 query routing 決策。
    - `selection_result`：本次 diversified selection 結果。

    回傳：
    - `RetrievalTrace`：最小 retrieval trace dataclass。
    """

    return RetrievalTrace(
        query=query,
        vector_top_k=settings.retrieval_vector_top_k,
        fts_top_k=settings.retrieval_fts_top_k,
        max_candidates=settings.retrieval_max_candidates,
        rerank_top_n=min(settings.rerank_top_n, total_candidates),
        query_type=routing_decision.query_type.value,
        query_type_language=routing_decision.language,
        query_type_source=routing_decision.source,
        query_type_confidence=routing_decision.confidence,
        query_type_matched_rules=list(routing_decision.matched_rules),
        query_type_rule_hits=[
            {
                "label": hit.label,
                "reason": hit.reason,
                "confidence": hit.confidence,
            }
            for hit in routing_decision.query_type_rule_hits
        ],
        query_type_embedding_scores=[
            {
                "label": score.label,
                "score": score.score,
            }
            for score in routing_decision.query_type_embedding_scores
        ],
        query_type_top_label=routing_decision.query_type_top_label,
        query_type_runner_up_label=routing_decision.query_type_runner_up_label,
        query_type_embedding_margin=routing_decision.query_type_embedding_margin,
        query_type_fallback_used=routing_decision.query_type_fallback_used,
        query_type_fallback_reason=routing_decision.query_type_fallback_reason,
        summary_scope=routing_decision.summary_scope,
        summary_strategy=routing_decision.summary_strategy,
        summary_strategy_source=routing_decision.summary_strategy_source,
        summary_strategy_confidence=routing_decision.summary_strategy_confidence,
        summary_strategy_rule_hits=[
            {
                "label": hit.label,
                "reason": hit.reason,
                "confidence": hit.confidence,
            }
            for hit in routing_decision.summary_strategy_rule_hits
        ],
        summary_strategy_embedding_scores=[
            {
                "label": score.label,
                "score": score.score,
            }
            for score in routing_decision.summary_strategy_embedding_scores
        ],
        summary_strategy_top_label=routing_decision.summary_strategy_top_label,
        summary_strategy_runner_up_label=routing_decision.summary_strategy_runner_up_label,
        summary_strategy_embedding_margin=routing_decision.summary_strategy_embedding_margin,
        summary_strategy_fallback_used=routing_decision.summary_strategy_fallback_used,
        summary_strategy_fallback_reason=routing_decision.summary_strategy_fallback_reason,
        resolved_document_ids=list(routing_decision.resolved_document_ids),
        document_mention_source=routing_decision.document_mention_source,
        document_mention_confidence=routing_decision.document_mention_confidence,
        document_mention_candidates=[dict(candidate) for candidate in routing_decision.document_mention_candidates],
        selected_profile=routing_decision.selected_profile,
        profile_settings=routing_decision.resolved_settings,
        selection_applied=selection_result.applied,
        selection_strategy=selection_result.strategy,
        selected_document_count=len(selection_result.selected_document_ids),
        selected_parent_count=len(selection_result.selected_parent_ids),
        selected_document_ids=list(selection_result.selected_document_ids),
        selected_parent_ids=list(selection_result.selected_parent_ids),
        dropped_by_diversity=[
            {
                "document_id": entry.document_id,
                "parent_chunk_id": entry.parent_chunk_id,
                "chunk_id": entry.chunk_id,
                "drop_reason": entry.drop_reason,
            }
            for entry in selection_result.dropped_by_diversity
        ],
        candidates=[],
    )


def _build_query_routing_detail(
    *,
    routing_decision: QueryRoutingDecision,
) -> EvaluationQueryRoutingDetail:
    """將 query routing 決策轉為 evaluation API detail。

    參數：
    - `routing_decision`：本次 query routing 決策。
    回傳：
    - `EvaluationQueryRoutingDetail`：preview 與 benchmark 共用的 routing detail。
    """

    return EvaluationQueryRoutingDetail(
        query_type=routing_decision.query_type,
        language=routing_decision.language,
        confidence=routing_decision.confidence,
        source=routing_decision.source,
        matched_rules=list(routing_decision.matched_rules),
        query_type_rule_hits=[
            {
                "label": hit.label,
                "reason": hit.reason,
                "confidence": hit.confidence,
            }
            for hit in routing_decision.query_type_rule_hits
        ],
        query_type_embedding_scores=[
            {
                "label": score.label,
                "score": score.score,
            }
            for score in routing_decision.query_type_embedding_scores
        ],
        query_type_top_label=routing_decision.query_type_top_label,
        query_type_runner_up_label=routing_decision.query_type_runner_up_label,
        query_type_embedding_margin=routing_decision.query_type_embedding_margin,
        query_type_fallback_used=routing_decision.query_type_fallback_used,
        query_type_fallback_reason=routing_decision.query_type_fallback_reason,
        summary_scope=routing_decision.summary_scope,
        summary_strategy=routing_decision.summary_strategy,
        summary_strategy_source=routing_decision.summary_strategy_source,
        summary_strategy_confidence=routing_decision.summary_strategy_confidence,
        summary_strategy_rule_hits=[
            {
                "label": hit.label,
                "reason": hit.reason,
                "confidence": hit.confidence,
            }
            for hit in routing_decision.summary_strategy_rule_hits
        ],
        summary_strategy_embedding_scores=[
            {
                "label": score.label,
                "score": score.score,
            }
            for score in routing_decision.summary_strategy_embedding_scores
        ],
        summary_strategy_top_label=routing_decision.summary_strategy_top_label,
        summary_strategy_runner_up_label=routing_decision.summary_strategy_runner_up_label,
        summary_strategy_embedding_margin=routing_decision.summary_strategy_embedding_margin,
        summary_strategy_fallback_used=routing_decision.summary_strategy_fallback_used,
        summary_strategy_fallback_reason=routing_decision.summary_strategy_fallback_reason,
        resolved_document_ids=list(routing_decision.resolved_document_ids),
        document_mention_source=routing_decision.document_mention_source,
        document_mention_confidence=routing_decision.document_mention_confidence,
        document_mention_candidates=[dict(candidate) for candidate in routing_decision.document_mention_candidates],
        selected_profile=routing_decision.selected_profile,
        resolved_settings=routing_decision.resolved_settings,
    )


def _build_selection_detail(*, selection_result: RetrievalSelectionResult) -> EvaluationSelectionDetail:
    """將 selection 結果轉為 evaluation API detail。

    參數：
    - `selection_result`：本次 diversified selection 結果。

    回傳：
    - `EvaluationSelectionDetail`：preview 與 benchmark 共用的 selection detail。
    """

    return EvaluationSelectionDetail(
        applied=selection_result.applied,
        strategy=selection_result.strategy,
        selected_document_count=len(selection_result.selected_document_ids),
        selected_parent_count=len(selection_result.selected_parent_ids),
        selected_document_ids=list(selection_result.selected_document_ids),
        selected_parent_ids=list(selection_result.selected_parent_ids),
        dropped_by_diversity=[
            {
                "document_id": entry.document_id,
                "parent_chunk_id": entry.parent_chunk_id,
                "chunk_id": entry.chunk_id,
                "drop_reason": entry.drop_reason,
            }
            for entry in selection_result.dropped_by_diversity
        ],
    )


def _load_document_names(*, session: Session, area_id: str) -> dict[str, str]:
    """載入 area 內文件名稱映射。

    參數：
    - `session`：目前資料庫 session。
    - `area_id`：目標 area。

    回傳：
    - `dict[str, str]`：文件名稱映射。
    """

    rows = session.execute(select(Document.id, Document.file_name).where(Document.area_id == area_id)).all()
    return {row.id: row.file_name for row in rows}


def _build_recall_stage(
    *,
    matches,
    gold_spans: list[GoldSpan],
    document_names: dict[str, str],
    top_k: int,
) -> EvaluationCandidateStageResponse:
    """建立 recall stage response。"""

    items: list[EvaluationStageCandidate] = []
    relevances: list[int | None] = []
    full_relevances = [
        match_gold_relevance(
            gold_spans,
            CandidateWindow(
                document_id=match.chunk.document_id,
                start_offset=match.chunk.start_offset,
                end_offset=match.chunk.end_offset,
            ),
        )
        for match in matches
    ]
    for rank, match in enumerate(matches[:top_k], start=1):
        relevance = match_gold_relevance(
            gold_spans,
            CandidateWindow(
                document_id=match.chunk.document_id,
                start_offset=match.chunk.start_offset,
                end_offset=match.chunk.end_offset,
            ),
        )
        relevances.append(relevance)
        items.append(
            EvaluationStageCandidate(
                document_id=match.chunk.document_id,
                document_name=document_names.get(match.chunk.document_id, "Unknown"),
                parent_chunk_id=match.chunk.parent_chunk_id,
                child_chunk_ids=[match.chunk.id],
                heading=match.chunk.heading,
                start_offset=match.chunk.start_offset,
                end_offset=match.chunk.end_offset,
                excerpt=match.chunk.content[:240],
                source="hybrid",
                rank=rank,
                vector_rank=match.vector_rank,
                fts_rank=match.fts_rank,
                rrf_rank=match.rrf_rank,
                rerank_rank=None,
                matched_relevance=relevance,
            )
        )
    return EvaluationCandidateStageResponse(
        stage="recall",
        first_hit_rank=first_hit_rank(relevances),
        full_hit_rank=first_hit_rank(full_relevances),
        rerank_applied=None,
        fallback_reason=None,
        items=items,
    )


def _build_rerank_stage(
    *,
    candidates,
    gold_spans: list[GoldSpan],
    document_names: dict[str, str],
    top_k: int,
    apply_rerank: bool,
) -> EvaluationCandidateStageResponse:
    """建立 rerank stage response。"""

    items: list[EvaluationStageCandidate] = []
    relevances: list[int | None] = []
    rerank_applied = any(candidate.rerank_applied for candidate in candidates) if apply_rerank else None
    fallback_reason = next(
        (candidate.rerank_fallback_reason for candidate in candidates if candidate.rerank_fallback_reason),
        None,
    )
    grouped_candidates: dict[tuple[str, str | None], list[object]] = defaultdict(list)
    order: list[tuple[str, str | None]] = []
    for candidate in candidates:
        group_key = (str(candidate.document_id), str(candidate.parent_chunk_id) if candidate.parent_chunk_id is not None else None)
        if group_key not in grouped_candidates:
            order.append(group_key)
        grouped_candidates[group_key].append(candidate)

    full_relevances: list[int | None] = []
    for group_key in order:
        group = grouped_candidates[group_key]
        full_relevances.append(
            match_gold_relevance_for_windows(
                gold_spans,
                [
                    CandidateWindow(
                        document_id=str(candidate.document_id),
                        start_offset=candidate.start_offset,
                        end_offset=candidate.end_offset,
                    )
                    for candidate in group
                ],
            )
        )

    for rank, group_key in enumerate(order[:top_k], start=1):
        group = grouped_candidates[group_key]
        relevance = match_gold_relevance_for_windows(
            gold_spans,
            [
                CandidateWindow(
                    document_id=str(candidate.document_id),
                    start_offset=candidate.start_offset,
                    end_offset=candidate.end_offset,
                )
                for candidate in group
            ],
        )
        relevances.append(relevance)
        items.append(
            EvaluationStageCandidate(
                document_id=group[0].document_id,
                document_name=document_names.get(group[0].document_id, "Unknown"),
                parent_chunk_id=group[0].parent_chunk_id,
                child_chunk_ids=[candidate.chunk_id for candidate in group],
                heading=group[0].heading,
                start_offset=min(candidate.start_offset for candidate in group),
                end_offset=max(candidate.end_offset for candidate in group),
                excerpt="\n\n".join(candidate.content for candidate in group)[:240],
                source=group[0].source,
                rank=rank,
                vector_rank=min((candidate.vector_rank for candidate in group if candidate.vector_rank is not None), default=None),
                fts_rank=min((candidate.fts_rank for candidate in group if candidate.fts_rank is not None), default=None),
                rrf_rank=min((candidate.rrf_rank for candidate in group if candidate.rrf_rank is not None), default=None),
                rerank_rank=min(
                    (candidate.rerank_rank for candidate in group if candidate.rerank_rank is not None),
                    default=(rank if apply_rerank else None),
                ),
                matched_relevance=relevance,
            )
        )
    return EvaluationCandidateStageResponse(
        stage="rerank",
        first_hit_rank=first_hit_rank(relevances) if apply_rerank else None,
        full_hit_rank=first_hit_rank(full_relevances) if apply_rerank else None,
        rerank_applied=rerank_applied,
        fallback_reason=fallback_reason if apply_rerank else None,
        items=items if apply_rerank else [],
    )


def _build_assembled_stage(
    *,
    session: Session,
    contexts,
    gold_spans: list[GoldSpan],
    document_names: dict[str, str],
    top_k: int,
) -> EvaluationCandidateStageResponse:
    """建立 assembled stage response。"""

    items: list[EvaluationStageCandidate] = []
    relevances: list[int | None] = []
    chunk_ids = [str(chunk_id) for context in contexts for chunk_id in context.chunk_ids]
    chunks = session.scalars(select(DocumentChunk).where(DocumentChunk.id.in_(chunk_ids))).all() if chunk_ids else []
    chunk_by_id = {str(chunk.id): chunk for chunk in chunks}
    full_relevances: list[int | None] = []
    for context in contexts:
        windows = [
            CandidateWindow(
                document_id=str(chunk.document_id),
                start_offset=chunk.start_offset,
                end_offset=chunk.end_offset,
            )
            for chunk_id in context.chunk_ids
            if (chunk := chunk_by_id.get(str(chunk_id))) is not None
        ]
        if not windows:
            windows = [
                CandidateWindow(
                    document_id=str(context.document_id),
                    start_offset=context.start_offset,
                    end_offset=context.end_offset,
                )
            ]
        full_relevances.append(match_gold_relevance_for_windows(gold_spans, windows))

    for rank, context in enumerate(contexts[:top_k], start=1):
        windows = [
            CandidateWindow(
                document_id=str(chunk.document_id),
                start_offset=chunk.start_offset,
                end_offset=chunk.end_offset,
            )
            for chunk_id in context.chunk_ids
            if (chunk := chunk_by_id.get(str(chunk_id))) is not None
        ]
        if not windows:
            windows = [
                CandidateWindow(
                    document_id=str(context.document_id),
                    start_offset=context.start_offset,
                    end_offset=context.end_offset,
                )
            ]
        relevance = match_gold_relevance_for_windows(gold_spans, windows)
        relevances.append(relevance)
        items.append(
            EvaluationStageCandidate(
                document_id=context.document_id,
                document_name=document_names.get(context.document_id, "Unknown"),
                parent_chunk_id=context.parent_chunk_id,
                child_chunk_ids=context.chunk_ids,
                heading=context.heading,
                start_offset=context.start_offset,
                end_offset=context.end_offset,
                excerpt=context.assembled_text[:240],
                source=context.source,
                rank=rank,
                vector_rank=None,
                fts_rank=None,
                rrf_rank=None,
                rerank_rank=rank,
                matched_relevance=relevance,
            )
        )
    return EvaluationCandidateStageResponse(
        stage="assembled",
        first_hit_rank=first_hit_rank(relevances),
        full_hit_rank=first_hit_rank(full_relevances),
        rerank_applied=None,
        fallback_reason=None,
        items=items,
    )


def _search_document_hits(
    *,
    session: Session,
    principal: CurrentPrincipal,
    area_id: str,
    query: str,
) -> list[EvaluationDocumentSearchHit]:
    """在 ready 文件內做簡化全文搜尋。

    參數：
    - `session`：目前資料庫 session。
    - `principal`：目前已驗證使用者。
    - `area_id`：目標 area。
    - `query`：搜尋關鍵字。

    回傳：
    - `list[EvaluationDocumentSearchHit]`：搜尋命中結果。
    """

    require_minimum_area_role(session=session, principal=principal, area_id=area_id, minimum_role=Role.maintainer)
    rows = session.execute(
        select(DocumentChunk, Document.file_name)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(
            Document.area_id == area_id,
            Document.status == DocumentStatus.ready,
            DocumentChunk.chunk_type == ChunkType.child,
            DocumentChunk.content.ilike(f"%{query}%"),
        )
        .order_by(Document.file_name.asc(), DocumentChunk.position.asc())
        .limit(10)
    ).all()
    return [
        EvaluationDocumentSearchHit(
            document_id=row[0].document_id,
            document_name=row[1],
            chunk_id=row[0].id,
            heading=row[0].heading,
            start_offset=row[0].start_offset,
            end_offset=row[0].end_offset,
            excerpt=row[0].content[:240],
        )
        for row in rows
    ]
