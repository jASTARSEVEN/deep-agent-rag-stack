"""Deep Agents 使用的 retrieval tool 與 payload mapper。"""

from __future__ import annotations

from base64 import urlsafe_b64decode, urlsafe_b64encode
import binascii
from dataclasses import dataclass, asdict

from sqlalchemy import select

from app.auth.verifier import CurrentPrincipal
from app.chat.contracts.types import ChatCitation, ChatCitationRegion
from app.core.settings import AppSettings
from app.db.models import Document, DocumentStatus, EvaluationQueryType
from app.services.access import require_area_access
from app.services.retrieval import retrieve_area_candidates
from app.services.retrieval_routing import DocumentScope, SummaryStrategy, build_query_routing_decision
from app.services.retrieval_assembler import AssembledContext, AssembledRetrievalResult, assemble_retrieval_result


# agent follow-up retrieval 每次最多回傳的 planning 文件數。
MAX_PLANNING_DOCUMENTS = 5
# agent 可見的 synopsis hint 最長字元數。
MAX_SYNOPSIS_HINT_CHARS = 500
# query-time evidence cue 最長字元數。
MAX_EVIDENCE_CUE_CHARS = 220
# compare 題固定回答模板。
COMPARE_ANSWER_TEMPLATE = [
    "先逐一說明每份文件的直接證據與立場。",
    "再整理共同點與差異；只有雙方都有直接證據時才能寫成共同點。",
    "若目前已具備雙邊直接證據，直接完成比較，不要加入 required documents 或 tool coverage 狀態前言；只有真的缺少其中一方證據時，才簡短說明證據不足。",
]


@dataclass(slots=True)
class RetrievalPlanningDocument:
    """agent 可見的單一文件規劃資訊。"""

    # 後端核發給 agent 的文件 handle。
    handle: str
    # 文件名稱。
    document_name: str
    # 此文件是否由 query mention resolver 命中。
    mentioned_by_query: bool
    # 此文件是否在本輪 retrieval 命中。
    hit_in_current_round: bool
    # 此文件是否有可供規劃的 synopsis。
    synopsis_available: bool


@dataclass(slots=True)
class RetrievalEvidenceCue:
    """agent / debug UI 可見的 evidence cue。"""

    # 對應的 context label。
    context_label: str
    # cue 所屬文件名稱。
    document_name: str
    # 從 assembled evidence 擷取的短摘錄。
    cue_text: str


@dataclass(slots=True)
class RetrievalSynopsisHint:
    """agent 可見的 synopsis planning hint。"""

    # 對應的文件 handle。
    handle: str
    # 文件名稱。
    document_name: str
    # 摘錄後的 synopsis 文字。
    synopsis_text: str


@dataclass(slots=True)
class RetrievalCoverageSignals:
    """summary/compare follow-up 用的 coverage 訊號。"""

    # 目前缺少 citation-ready evidence 的文件名稱。
    missing_document_names: list[str]
    # 是否已具備至少兩份文件的 compare evidence。
    supports_compare: bool
    # 目前是否仍應視為證據不足。
    insufficient_evidence: bool
    # 仍缺少的 compare 面向。
    missing_compare_axes: list[str]
    # 本輪是否有新增 evidence。
    new_evidence_found: bool


@dataclass(slots=True)
class RetrievalToolResult:
    """retrieval pipeline 封裝為單一 tool 的輸出。"""

    # chat-ready contexts。
    assembled_contexts: list[AssembledContext]
    # assembled-context reference metadata。
    citations: list[ChatCitation]
    # agent follow-up 規劃可見的文件資訊。
    planning_documents: list[RetrievalPlanningDocument]
    # compare / multi-document 題的 coverage 訊號。
    coverage_signals: RetrievalCoverageSignals | None
    # 建議 agent 下一步如何補查。
    next_best_followups: list[str]
    # 供 agent / debug UI 快速理解的短 cue。
    evidence_cue_texts: list[RetrievalEvidenceCue]
    # agent 要求檢視時回傳的 synopsis hints。
    synopsis_hints: list[RetrievalSynopsisHint]
    # 單回合 follow-up trace 增量。
    loop_trace_delta: dict[str, object]
    # retrieval 與 assembler trace。
    trace: dict[str, object]


def retrieve_area_contexts_tool(
    *,
    session,
    principal: CurrentPrincipal,
    settings: AppSettings,
    area_id: str,
    question: str,
    task_type: EvaluationQueryType | str | None = None,
    document_scope: DocumentScope | str | None = None,
    summary_strategy: SummaryStrategy | str | None = None,
    query_variant: str | None = None,
    document_handles: list[str] | tuple[str, ...] | None = None,
    inspect_synopsis_handles: list[str] | tuple[str, ...] | None = None,
    followup_reason: str | None = None,
) -> RetrievalToolResult:
    """將 retrieval、rerank 與 assembler 包成單一 tool-shaped capability。

    參數：
    - `session`：目前資料庫 session。
    - `principal`：目前已驗證使用者。
    - `settings`：API 執行期設定。
    - `area_id`：檢索所屬 area。
    - `question`：使用者提問。
    - `task_type`：可選的任務類型提示；不提供時由後端自動 routing。
    - `document_scope`：可選的文件範圍提示；不得攜帶 document ids，實際 ids 仍由後端解析。
    - `summary_strategy`：可選的摘要策略提示；只在 `document_summary` 下有效。
    - `query_variant`：agent follow-up 使用的單一 query variant。
    - `document_handles`：agent follow-up 使用的安全文件 handles。
    - `inspect_synopsis_handles`：要查看 synopsis hint 的安全文件 handles。
    - `followup_reason`：本次 follow-up 的簡短原因。

    回傳：
    - `RetrievalToolResult`：contexts、citations 與 trace。

    前置條件：
    - 此 tool 必須始終維持 SQL gate、same-404 與 ready-only。
    """

    return _retrieve_area_contexts_internal(
        session=session,
        principal=principal,
        settings=settings,
        area_id=area_id,
        question=question,
        task_type=task_type,
        document_scope=document_scope,
        summary_strategy=summary_strategy,
        query_variant=query_variant,
        document_handles=document_handles,
        inspect_synopsis_handles=inspect_synopsis_handles,
        followup_reason=followup_reason,
        allowed_document_ids_override=None,
    )


def _retrieve_area_contexts_internal(
    *,
    session,
    principal: CurrentPrincipal,
    settings: AppSettings,
    area_id: str,
    question: str,
    task_type: EvaluationQueryType | str | None = None,
    document_scope: DocumentScope | str | None = None,
    summary_strategy: SummaryStrategy | str | None = None,
    query_variant: str | None = None,
    document_handles: list[str] | tuple[str, ...] | None = None,
    inspect_synopsis_handles: list[str] | tuple[str, ...] | None = None,
    followup_reason: str | None = None,
    allowed_document_ids_override: tuple[str, ...] | None = None,
) -> RetrievalToolResult:
    """建立供 runtime 與 benchmark 共用的 internal retrieval helper。

    參數：
    - `session`：目前資料庫 session。
    - `principal`：目前已驗證使用者。
    - `settings`：API 執行期設定。
    - `area_id`：檢索所屬 area。
    - `question`：使用者提問。
    - `task_type`：可選的任務類型提示。
    - `document_scope`：可選的文件範圍提示。
    - `summary_strategy`：可選的摘要策略提示。
    - `query_variant`：agent follow-up 使用的單一 query variant。
    - `document_handles`：agent follow-up 使用的安全文件 handles。
    - `inspect_synopsis_handles`：要求檢視 synopsis hint 的安全文件 handles。
    - `followup_reason`：本次 follow-up 的簡短原因。
    - `allowed_document_ids_override`：benchmark/test 專用文件白名單；public tool 不應傳入。

    回傳：
    - `RetrievalToolResult`：contexts、citations 與 trace。

    前置條件：
    - benchmark/test 若傳入 `allowed_document_ids_override`，必須先完成權限與 `ready` 驗證。
    """

    authorized_ready_documents = _load_authorized_ready_documents(
        session=session,
        principal=principal,
        area_id=area_id,
    )
    document_name_by_id = {
        str(document.id): str(document.file_name)
        for document in authorized_ready_documents
    }
    authorized_document_ids = tuple(document_name_by_id.keys())
    normalized_query_variant = _normalize_query_variant(
        query_variant=query_variant,
        settings=settings,
    )
    scoped_document_ids = _resolve_document_handles(
        handles=document_handles,
        authorized_document_ids=authorized_document_ids,
        settings=settings,
    )
    synopsis_document_ids = _resolve_document_handles(
        handles=inspect_synopsis_handles,
        authorized_document_ids=authorized_document_ids,
        settings=settings,
        max_items=settings.chat_agentic_max_synopsis_inspections_per_turn,
    )
    effective_query = normalized_query_variant or question
    explicit_query_type = _coerce_optional_query_type(task_type=task_type)
    retrieval_result = retrieve_area_candidates(
        session=session,
        principal=principal,
        settings=settings,
        area_id=area_id,
        query=effective_query,
        document_scope=document_scope,
        summary_strategy=summary_strategy,
        query_type=explicit_query_type,
        allowed_document_ids_override=allowed_document_ids_override or scoped_document_ids,
    )
    effective_settings = build_query_routing_decision(
        settings=settings,
        query=question,
        explicit_document_scope=document_scope,
        explicit_summary_strategy=summary_strategy,
        explicit_query_type=EvaluationQueryType(retrieval_result.trace.query_type),
        session=session,
        principal=principal,
        area_id=area_id,
    ).effective_settings
    assembled_result = assemble_retrieval_result(
        session=session,
        settings=effective_settings,
        retrieval_result=retrieval_result,
    )
    return RetrievalToolResult(
        assembled_contexts=assembled_result.assembled_contexts,
        citations=build_chat_citations(
            session=session,
            assembled_result=assembled_result,
            max_items=effective_settings.assembler_max_contexts,
        ),
        planning_documents=_build_planning_documents(
            authorized_ready_documents=authorized_ready_documents,
            retrieval_trace=retrieval_result.trace,
            assembled_contexts=assembled_result.assembled_contexts,
        ),
        coverage_signals=_build_coverage_signals(
            retrieval_trace=asdict(assembled_result.trace.retrieval),
            assembled_contexts=assembled_result.assembled_contexts,
            document_name_by_id=document_name_by_id,
        ),
        next_best_followups=_build_next_best_followups(
            retrieval_trace=asdict(assembled_result.trace.retrieval),
            assembled_contexts=assembled_result.assembled_contexts,
            document_name_by_id=document_name_by_id,
        ),
        evidence_cue_texts=_build_evidence_cue_texts(
            assembled_contexts=assembled_result.assembled_contexts,
            document_name_by_id=document_name_by_id,
        ),
        synopsis_hints=_build_synopsis_hints(
            authorized_ready_documents=authorized_ready_documents,
            synopsis_document_ids=synopsis_document_ids,
        ),
        loop_trace_delta={
            "base_question": question,
            "effective_query": effective_query,
            "query_variant": normalized_query_variant or "",
            "scoped_document_ids": list(scoped_document_ids or ()),
            "inspect_synopsis_document_ids": list(synopsis_document_ids or ()),
            "followup_reason": (followup_reason or "").strip(),
        },
        trace={
            "retrieval": asdict(assembled_result.trace.retrieval),
            "assembler": asdict(assembled_result.trace.assembler),
        },
    )


def _coerce_optional_query_type(*, task_type: EvaluationQueryType | str | None) -> EvaluationQueryType | None:
    """將 tool task type hint 轉成正式 enum。

    參數：
    - `task_type`：agent 或內部呼叫提供的任務類型提示。

    回傳：
    - `EvaluationQueryType | None`：成功解析後的 query type；未提供時回傳空值。
    """

    if task_type is None:
        return None
    if isinstance(task_type, EvaluationQueryType):
        return task_type
    normalized = str(task_type).strip()
    if not normalized:
        return None
    return EvaluationQueryType(normalized)


def build_assembled_context_payload(
    session,
    retrieval_result: RetrievalToolResult | None,
) -> list[dict[str, object]]:
    """將 retrieval tool result 轉成前端可直接顯示的 assembled context payload。

    參數：
    - `session`：目前資料庫 session。
    - `retrieval_result`：單次 retrieval tool 執行結果。

    回傳：
    - `list[dict[str, object]]`：assembled context 列表。
    """

    if retrieval_result is None:
        return []

    fallback_document_names = _collect_document_names_from_citations(retrieval_result.citations)
    document_name_by_id = _load_document_names(
        session=session,
        document_ids=[str(context.document_id) for context in retrieval_result.assembled_contexts],
        fallback_names=fallback_document_names,
    )
    truncated_by_index = {
        item["context_index"]: item["truncated"]
        for item in retrieval_result.trace["assembler"]["contexts"]
    }
    return [
        {
            "context_index": index,
            "context_label": _build_context_label(index),
            "document_id": str(context.document_id),
            "document_name": document_name_by_id.get(str(context.document_id), ""),
            "parent_chunk_id": str(context.parent_chunk_id) if context.parent_chunk_id is not None else None,
            "child_chunk_ids": [str(chunk_id) for chunk_id in context.chunk_ids],
            "structure_kind": context.structure_kind.value,
            "heading": context.heading,
            "excerpt": context.assembled_text,
            "assembled_text": context.assembled_text,
            "source": context.source,
            "start_offset": context.start_offset,
            "end_offset": context.end_offset,
            "page_start": min((region.page_number for region in context.regions), default=None),
            "page_end": max((region.page_number for region in context.regions), default=None),
            "regions": [
                {
                    "page_number": region.page_number,
                    "region_order": region.region_order,
                    "bbox_left": region.bbox_left,
                    "bbox_bottom": region.bbox_bottom,
                    "bbox_right": region.bbox_right,
                    "bbox_top": region.bbox_top,
                }
                for region in context.regions
            ],
            "truncated": truncated_by_index.get(index, False),
        }
        for index, context in enumerate(retrieval_result.assembled_contexts)
    ]


def build_agent_tool_context_payload(
    session,
    retrieval_result: RetrievalToolResult | None,
) -> list[dict[str, object]]:
    """建立回傳給 LLM 的最小 assembled context payload。

    參數：
    - `session`：目前資料庫 session。
    - `retrieval_result`：單次 retrieval tool 執行結果。

    回傳：
    - `list[dict[str, object]]`：僅含回答所需最小欄位的 context 列表。
    """

    if retrieval_result is None:
        return []

    fallback_document_names = _collect_document_names_from_citations(retrieval_result.citations)
    document_name_by_id = _load_document_names(
        session=session,
        document_ids=[str(context.document_id) for context in retrieval_result.assembled_contexts],
        fallback_names=fallback_document_names,
    )

    return [
        {
            "context_label": _build_context_label(index),
            "context_index": index,
            "document_name": document_name_by_id.get(str(context.document_id), ""),
            "heading": context.heading,
            "assembled_text": context.assembled_text,
        }
        for index, context in enumerate(retrieval_result.assembled_contexts)
    ]


def build_agent_tool_payload(
    session,
    retrieval_result: RetrievalToolResult | None,
    *,
    assembled_contexts_payload: list[dict[str, object]] | None = None,
    loop_trace_delta: dict[str, object] | None = None,
    tool_call_count: int,
    followup_call_count: int,
    synopsis_inspection_count: int,
    latency_budget_status: str,
    stop_reason: str,
) -> dict[str, object]:
    """建立 `retrieve_area_contexts` 回傳給 LLM 的正式 payload。

    參數：
    - `session`：目前資料庫 session。
    - `retrieval_result`：單次 retrieval tool 執行結果。
    - `assembled_contexts_payload`：可選的累積 context payload；未提供時使用本次 round 結果。
    - `loop_trace_delta`：可選的 runtime 級 loop trace 覆寫。
    - `tool_call_count`：目前回合已執行的 tool call 次數。
    - `followup_call_count`：目前回合的 follow-up 次數。
    - `synopsis_inspection_count`：目前回合已檢視的 synopsis 次數。
    - `latency_budget_status`：目前 latency budget 狀態。
    - `stop_reason`：目前 agentic loop stop reason。

    回傳：
    - `dict[str, object]`：提供給 LLM 的單一 tool payload。
    """

    tool_contexts_payload = (
        list(assembled_contexts_payload)
        if assembled_contexts_payload is not None
        else build_agent_tool_context_payload(session, retrieval_result)
    )
    effective_loop_trace_delta = (
        dict(loop_trace_delta)
        if loop_trace_delta is not None
        else dict(retrieval_result.loop_trace_delta)
        if retrieval_result is not None
        else {}
    )
    include_loop_trace = bool(
        effective_loop_trace_delta
        or followup_call_count > 0
        or synopsis_inspection_count > 0
        or latency_budget_status != "normal"
        or stop_reason not in {"not_started", "continue"}
    )
    payload: dict[str, object] = {
        "assembled_contexts": tool_contexts_payload,
        "coverage_signals": _build_agent_coverage_signals_payload(retrieval_result),
        "planning_documents": _build_agent_planning_documents_payload(retrieval_result),
        "next_best_followups": list(retrieval_result.next_best_followups) if retrieval_result is not None else [],
        "evidence_cue_texts": _build_agent_evidence_cue_payload(retrieval_result),
        "synopsis_hints": _build_agent_synopsis_hints_payload(retrieval_result),
        "loop_trace_delta": (
            {
                **effective_loop_trace_delta,
                "tool_call_count": tool_call_count,
                "followup_call_count": followup_call_count,
                "synopsis_inspection_count": synopsis_inspection_count,
                "latency_budget_status": latency_budget_status,
                "stop_reason": stop_reason,
            }
            if include_loop_trace
            else {}
        ),
    }
    response_contract = build_agent_response_contract_payload(session, retrieval_result)
    if response_contract is not None:
        payload["response_contract"] = response_contract
    return payload


def build_agent_response_contract_payload(
    session,
    retrieval_result: RetrievalToolResult | None,
) -> dict[str, object] | None:
    """建立給 LLM 的回答契約提示。

    參數：
    - `session`：目前資料庫 session。
    - `retrieval_result`：單次 retrieval tool 執行結果。

    回傳：
    - `dict[str, object] | None`：僅在需要額外回答 guardrail 時回傳契約 payload。
    """

    if retrieval_result is None:
        return None

    retrieval_trace = retrieval_result.trace["retrieval"] if retrieval_result is not None else {}
    if retrieval_trace.get("query_type") != EvaluationQueryType.cross_document_compare.value:
        return None

    required_document_names = list(
        dict.fromkeys(
            document.document_name
            for document in retrieval_result.planning_documents
            if document.mentioned_by_query or document.hit_in_current_round
        )
    )
    return {
        "task_type": EvaluationQueryType.cross_document_compare.value,
        "required_document_names": required_document_names,
        "compare_answer_template": list(COMPARE_ANSWER_TEMPLATE),
    }


def build_tool_call_output_summary(
    session,
    retrieval_result: RetrievalToolResult | None,
) -> dict[str, object]:
    """建立 custom `tool_call.completed` 事件的 debug-safe 摘要。

    參數：
    - `session`：目前資料庫 session。
    - `retrieval_result`：單次 retrieval tool 執行結果。

    回傳：
    - `dict[str, object]`：前端工具檢視可使用的摘要。
    """

    assembled_contexts_payload = build_assembled_context_payload(session, retrieval_result)
    retrieval_trace = retrieval_result.trace["retrieval"] if retrieval_result is not None else {}
    response_contract = build_agent_response_contract_payload(session, retrieval_result)
    payload = {
        "contexts_count": len(assembled_contexts_payload),
        "citations_count": len(retrieval_result.citations) if retrieval_result is not None else 0,
        "query_type": retrieval_trace.get("query_type"),
        "query_type_language": retrieval_trace.get("query_type_language"),
        "query_type_source": retrieval_trace.get("query_type_source"),
        "query_type_confidence": retrieval_trace.get("query_type_confidence"),
        "query_type_matched_rules": retrieval_trace.get("query_type_matched_rules", []),
        "query_type_rule_hits": retrieval_trace.get("query_type_rule_hits", []),
        "query_type_embedding_scores": retrieval_trace.get("query_type_embedding_scores", []),
        "query_type_top_label": retrieval_trace.get("query_type_top_label"),
        "query_type_runner_up_label": retrieval_trace.get("query_type_runner_up_label"),
        "query_type_embedding_margin": retrieval_trace.get("query_type_embedding_margin"),
        "query_type_fallback_used": retrieval_trace.get("query_type_fallback_used"),
        "query_type_fallback_reason": retrieval_trace.get("query_type_fallback_reason"),
        "summary_scope": retrieval_trace.get("summary_scope"),
        "summary_strategy": retrieval_trace.get("summary_strategy"),
        "summary_strategy_source": retrieval_trace.get("summary_strategy_source"),
        "summary_strategy_confidence": retrieval_trace.get("summary_strategy_confidence"),
        "summary_strategy_rule_hits": retrieval_trace.get("summary_strategy_rule_hits", []),
        "summary_strategy_embedding_scores": retrieval_trace.get("summary_strategy_embedding_scores", []),
        "summary_strategy_top_label": retrieval_trace.get("summary_strategy_top_label"),
        "summary_strategy_runner_up_label": retrieval_trace.get("summary_strategy_runner_up_label"),
        "summary_strategy_embedding_margin": retrieval_trace.get("summary_strategy_embedding_margin"),
        "summary_strategy_fallback_used": retrieval_trace.get("summary_strategy_fallback_used"),
        "summary_strategy_fallback_reason": retrieval_trace.get("summary_strategy_fallback_reason"),
        "document_scope": retrieval_trace.get("document_scope"),
        "resolved_document_ids": retrieval_trace.get("resolved_document_ids", []),
        "document_mention_source": retrieval_trace.get("document_mention_source"),
        "document_mention_confidence": retrieval_trace.get("document_mention_confidence"),
        "document_mention_candidates": retrieval_trace.get("document_mention_candidates", []),
        "selected_profile": retrieval_trace.get("selected_profile"),
        "fallback_reason": retrieval_trace.get("fallback_reason"),
        "selection_applied": retrieval_trace.get("selection_applied"),
        "selection_strategy": retrieval_trace.get("selection_strategy"),
        "selected_document_count": retrieval_trace.get("selected_document_count"),
        "selected_parent_count": retrieval_trace.get("selected_parent_count"),
        "selected_document_ids": retrieval_trace.get("selected_document_ids", []),
        "selected_parent_ids": retrieval_trace.get("selected_parent_ids", []),
        "dropped_by_diversity": retrieval_trace.get("dropped_by_diversity", []),
        "profile_settings": retrieval_trace.get("profile_settings", {}),
        "coverage_signals": (
            asdict(retrieval_result.coverage_signals)
            if retrieval_result is not None and retrieval_result.coverage_signals is not None
            else None
        ),
        "planning_documents": [
            {
                "document_name": item.document_name,
                "mentioned_by_query": item.mentioned_by_query,
                "hit_in_current_round": item.hit_in_current_round,
                "synopsis_available": item.synopsis_available,
            }
            for item in (retrieval_result.planning_documents if retrieval_result is not None else [])
        ],
        "next_best_followups": retrieval_result.next_best_followups if retrieval_result is not None else [],
        "evidence_cue_texts": [
            asdict(item)
            for item in (retrieval_result.evidence_cue_texts if retrieval_result is not None else [])
        ],
        "synopsis_hints": [
            {
                "document_name": item.document_name,
                "synopsis_text": item.synopsis_text,
            }
            for item in (retrieval_result.synopsis_hints if retrieval_result is not None else [])
        ],
        "loop_trace_delta": retrieval_result.loop_trace_delta if retrieval_result is not None else {},
        "contexts": [
            {
                "context_index": item["context_index"],
                "context_label": item["context_label"],
                "document_id": item["document_id"],
                "document_name": item["document_name"],
                "parent_chunk_id": item["parent_chunk_id"],
                "child_chunk_ids": item["child_chunk_ids"],
                "heading": item["heading"],
                "structure_kind": item["structure_kind"],
                "source": item["source"],
                "truncated": item["truncated"],
                "excerpt": item["excerpt"],
            }
            for item in assembled_contexts_payload
        ],
    }
    if response_contract is not None:
        payload["response_contract"] = response_contract
    return payload


def build_chat_citations(
    *,
    session,
    assembled_result: AssembledRetrievalResult,
    max_items: int,
) -> list[ChatCitation]:
    """將 assembler 輸出轉成 context-level references。

    參數：
    - `session`：目前資料庫 session。
    - `assembled_result`：assembler 的完整輸出。
    - `max_items`：允許保留的最大 context 數量。

    回傳：
    - `list[ChatCitation]`：一筆對應一個 assembled context 的 reference 列表。
    """

    if max_items <= 0 or not assembled_result.assembled_contexts:
        return []

    truncated_by_index = {
        context_trace.context_index: context_trace.truncated
        for context_trace in assembled_result.trace.assembler.contexts
    }
    document_name_by_id = _load_document_names(
        session=session,
        document_ids=[str(context.document_id) for context in assembled_result.assembled_contexts[:max_items]],
    )
    references: list[ChatCitation] = []
    for index, context in enumerate(assembled_result.assembled_contexts[:max_items]):
        references.append(
            ChatCitation(
                context_index=index,
                context_label=_build_context_label(index),
                document_id=str(context.document_id),
                document_name=document_name_by_id.get(str(context.document_id), ""),
                parent_chunk_id=str(context.parent_chunk_id) if context.parent_chunk_id is not None else None,
                child_chunk_ids=[str(chunk_id) for chunk_id in context.chunk_ids],
                heading=context.heading,
                structure_kind=context.structure_kind,
                start_offset=context.start_offset,
                end_offset=context.end_offset,
                excerpt=context.assembled_text,
                source=context.source,
                truncated=truncated_by_index.get(index, False),
                page_start=min((region.page_number for region in context.regions), default=None),
                page_end=max((region.page_number for region in context.regions), default=None),
                regions=[
                    ChatCitationRegion(
                        page_number=region.page_number,
                        region_order=region.region_order,
                        bbox_left=region.bbox_left,
                        bbox_bottom=region.bbox_bottom,
                        bbox_right=region.bbox_right,
                        bbox_top=region.bbox_top,
                    )
                    for region in context.regions
                ],
            )
        )
    return references


def _build_agent_planning_documents_payload(
    retrieval_result: RetrievalToolResult | None,
) -> list[dict[str, object]]:
    """建立提供給 LLM 的 planning documents 欄位。

    參數：
    - `retrieval_result`：單次 retrieval tool 執行結果。

    回傳：
    - `list[dict[str, object]]`：不暴露 raw document id 的 planning documents。
    """

    if retrieval_result is None:
        return []

    payload: list[dict[str, object]] = []
    for item in retrieval_result.planning_documents:
        planning_document = {
            "document_name": str(getattr(item, "document_name", "") or ""),
            "mentioned_by_query": bool(getattr(item, "mentioned_by_query", False)),
            "hit_in_current_round": bool(getattr(item, "hit_in_current_round", False)),
            "synopsis_available": bool(getattr(item, "synopsis_available", False)),
        }
        handle = getattr(item, "handle", None)
        if isinstance(handle, str) and handle:
            planning_document["handle"] = handle
        payload.append(planning_document)
    return payload


def _build_agent_coverage_signals_payload(
    retrieval_result: RetrievalToolResult | None,
) -> dict[str, object] | None:
    """建立提供給 LLM 的 coverage signals 欄位。

    參數：
    - `retrieval_result`：單次 retrieval tool 執行結果。

    回傳：
    - `dict[str, object] | None`：compare / multi-document planning 訊號。
    """

    if retrieval_result is None or retrieval_result.coverage_signals is None:
        return None

    coverage_signals = retrieval_result.coverage_signals
    if isinstance(coverage_signals, dict):
        return {
            "missing_document_names": list(coverage_signals.get("missing_document_names", [])),
            "supports_compare": bool(coverage_signals.get("supports_compare", False)),
            "insufficient_evidence": bool(coverage_signals.get("insufficient_evidence", False)),
            "missing_compare_axes": list(coverage_signals.get("missing_compare_axes", [])),
            "new_evidence_found": bool(coverage_signals.get("new_evidence_found", False)),
        }

    return {
        "missing_document_names": list(getattr(coverage_signals, "missing_document_names", [])),
        "supports_compare": bool(getattr(coverage_signals, "supports_compare", False)),
        "insufficient_evidence": bool(getattr(coverage_signals, "insufficient_evidence", False)),
        "missing_compare_axes": list(getattr(coverage_signals, "missing_compare_axes", [])),
        "new_evidence_found": bool(getattr(coverage_signals, "new_evidence_found", False)),
    }


def _build_agent_evidence_cue_payload(
    retrieval_result: RetrievalToolResult | None,
) -> list[dict[str, object]]:
    """建立提供給 LLM 的 evidence cues 欄位。

    參數：
    - `retrieval_result`：單次 retrieval tool 執行結果。

    回傳：
    - `list[dict[str, object]]`：簡短 evidence cue 清單。
    """

    if retrieval_result is None:
        return []

    return [
        {
            "context_label": str(getattr(item, "context_label", "") or ""),
            "document_name": str(getattr(item, "document_name", "") or ""),
            "cue_text": str(getattr(item, "cue_text", "") or ""),
        }
        for item in retrieval_result.evidence_cue_texts
    ]


def _build_agent_synopsis_hints_payload(
    retrieval_result: RetrievalToolResult | None,
) -> list[dict[str, object]]:
    """建立提供給 LLM 的 synopsis hints 欄位。

    參數：
    - `retrieval_result`：單次 retrieval tool 執行結果。

    回傳：
    - `list[dict[str, object]]`：可選的 synopsis hints。
    """

    if retrieval_result is None:
        return []

    payload: list[dict[str, object]] = []
    for item in retrieval_result.synopsis_hints:
        synopsis_hint = {
            "document_name": str(getattr(item, "document_name", "") or ""),
            "synopsis_text": str(getattr(item, "synopsis_text", "") or ""),
        }
        handle = getattr(item, "handle", None)
        if isinstance(handle, str) and handle:
            synopsis_hint["handle"] = handle
        payload.append(synopsis_hint)
    return payload


def _build_context_label(context_index: int) -> str:
    """建立穩定的 context 引用標籤。

    參數：
    - `context_index`：assembled context 在回傳列表中的索引。

    回傳：
    - `str`：提供給回答與 UI 使用的標籤，例如 `C1`。
    """

    return f"C{context_index + 1}"


def _collect_document_names_from_citations(citations: list[object]) -> dict[str, str]:
    """從既有 citation payload 擷取文件名稱對照。

    參數：
    - `citations`：目前回合的 citation 清單。

    回傳：
    - `dict[str, str]`：以文件識別碼為鍵的檔名對照表。
    """

    document_name_by_id: dict[str, str] = {}
    for citation in citations:
        document_id = getattr(citation, "document_id", None)
        document_name = getattr(citation, "document_name", None)
        if isinstance(citation, dict):
            document_id = citation.get("document_id")
            document_name = citation.get("document_name")
        if isinstance(document_id, str) and isinstance(document_name, str) and document_name:
            document_name_by_id[document_id] = document_name
    return document_name_by_id


def _load_document_names(
    *,
    session,
    document_ids: list[str],
    fallback_names: dict[str, str] | None = None,
) -> dict[str, str]:
    """依文件識別碼讀取檔名對照表。

    參數：
    - `session`：目前資料庫 session。
    - `document_ids`：要查詢檔名的文件識別碼列表。
    - `fallback_names`：當前 context 已知的檔名對照表。

    回傳：
    - `dict[str, str]`：以文件識別碼為鍵的檔名對照表。
    """

    unique_ids = list(dict.fromkeys(document_ids))
    if not unique_ids:
        return {}
    if session is None:
        return {
            document_id: document_name
            for document_id, document_name in (fallback_names or {}).items()
            if document_id in unique_ids
        }

    rows = session.execute(select(Document.id, Document.file_name).where(Document.id.in_(unique_ids))).all()
    document_name_by_id = {str(document_id): str(file_name) for document_id, file_name in rows}
    for document_id, document_name in (fallback_names or {}).items():
        document_name_by_id.setdefault(document_id, document_name)
    return document_name_by_id


def _load_authorized_ready_documents(
    *,
    session,
    principal: CurrentPrincipal,
    area_id: str,
) -> list[Document]:
    """讀取目前 area 內已授權且 ready 的文件清單。

    參數：
    - `session`：目前資料庫 session。
    - `principal`：目前已驗證使用者。
    - `area_id`：目標 area。

    回傳：
    - `list[Document]`：已授權且 `status=ready` 的文件。
    """

    require_area_access(session=session, principal=principal, area_id=area_id)
    return list(
        session.scalars(
            select(Document)
            .where(Document.area_id == area_id, Document.status == DocumentStatus.ready)
            .order_by(Document.created_at.asc(), Document.file_name.asc())
        ).all()
    )


def _normalize_query_variant(
    *,
    query_variant: str | None,
    settings: AppSettings,
) -> str | None:
    """清理並限制 agent follow-up 的單一 query variant。

    參數：
    - `query_variant`：原始 query variant。
    - `settings`：應用程式設定。

    回傳：
    - `str | None`：正規化後的單一 query variant；若未提供則回傳空值。
    """

    if query_variant is None:
        return None

    normalized = str(query_variant).strip()
    if not normalized:
        return None
    return normalized[: settings.chat_agentic_max_query_variant_chars]


def _resolve_document_handles(
    *,
    handles: list[str] | tuple[str, ...] | None,
    authorized_document_ids: tuple[str, ...],
    settings: AppSettings,
    max_items: int | None = None,
) -> tuple[str, ...] | None:
    """將 agent 提供的安全文件 handles 解析回已授權的文件識別碼。

    參數：
    - `handles`：agent 提供的安全文件 handles。
    - `authorized_document_ids`：目前 area 內已授權且 ready 的文件識別碼。
    - `settings`：應用程式設定。
    - `max_items`：本次最多允許解析的 handle 數量。

    回傳：
    - `tuple[str, ...] | None`：驗證通過後的文件識別碼白名單。
    """

    if not handles:
        return None

    normalized_handles = [str(handle).strip() for handle in handles if str(handle).strip()]
    if not normalized_handles:
        return None

    limit = max_items or settings.chat_agentic_max_scoped_documents_per_call
    if len(normalized_handles) > limit:
        raise ValueError("document_handles 超出單次 tool call 允許上限。")

    authorized_document_id_set = set(authorized_document_ids)
    resolved_ids: list[str] = []
    for handle in normalized_handles:
        document_id = _decode_document_handle(handle=handle)
        if document_id not in authorized_document_id_set:
            raise ValueError("document_handles 含有未授權或不存在的文件。")
        if document_id not in resolved_ids:
            resolved_ids.append(document_id)
    return tuple(resolved_ids)


def _encode_document_handle(*, document_id: str) -> str:
    """將文件識別碼編碼為 agent 可見的安全 handle。

    參數：
    - `document_id`：原始文件識別碼。

    回傳：
    - `str`：不可直接看出原始識別碼的 handle。
    """

    encoded = urlsafe_b64encode(document_id.encode("utf-8")).decode("ascii").rstrip("=")
    return f"doc_{encoded}"


def _decode_document_handle(*, handle: str) -> str:
    """將安全文件 handle 解回原始文件識別碼。

    參數：
    - `handle`：agent 提供的文件 handle。

    回傳：
    - `str`：解碼後的文件識別碼。
    """

    normalized = str(handle).strip()
    if not normalized.startswith("doc_"):
        raise ValueError("document_handles 只能使用後端核發的安全 handle。")
    payload = normalized.removeprefix("doc_")
    try:
        padding = "=" * (-len(payload) % 4)
        return urlsafe_b64decode(f"{payload}{padding}".encode("ascii")).decode("utf-8")
    except (ValueError, binascii.Error, UnicodeDecodeError) as exc:
        raise ValueError("document_handles 格式無效。") from exc


def _build_planning_documents(
    *,
    authorized_ready_documents: list[Document],
    retrieval_trace,
    assembled_contexts: list[AssembledContext],
) -> list[RetrievalPlanningDocument]:
    """建立 agent follow-up 規劃使用的文件清單。

    參數：
    - `authorized_ready_documents`：目前 area 內已授權且 ready 的文件。
    - `retrieval_trace`：本輪 retrieval trace。
    - `assembled_contexts`：本輪 assembled contexts。

    回傳：
    - `list[RetrievalPlanningDocument]`：規劃文件清單。
    """

    mention_candidates = retrieval_trace.document_mention_candidates or []
    mentioned_document_ids = {
        str(candidate.get("document_id"))
        for candidate in mention_candidates
        if isinstance(candidate, dict) and isinstance(candidate.get("document_id"), str)
    }
    hit_document_ids = {str(context.document_id) for context in assembled_contexts}
    candidate_documents = [
        document
        for document in authorized_ready_documents
        if document.id in mentioned_document_ids or document.id in hit_document_ids
    ]
    if not candidate_documents:
        candidate_documents = authorized_ready_documents[:MAX_PLANNING_DOCUMENTS]

    return [
        RetrievalPlanningDocument(
            handle=_encode_document_handle(document_id=str(document.id)),
            document_name=str(document.file_name),
            mentioned_by_query=document.id in mentioned_document_ids,
            hit_in_current_round=document.id in hit_document_ids,
            synopsis_available=bool((document.synopsis_text or "").strip()),
        )
        for document in candidate_documents[:MAX_PLANNING_DOCUMENTS]
    ]


def _build_coverage_signals(
    *,
    retrieval_trace: dict[str, object],
    assembled_contexts: list[AssembledContext],
    document_name_by_id: dict[str, str],
) -> RetrievalCoverageSignals | None:
    """建立 compare / multi-document follow-up 需要的 coverage 訊號。

    參數：
    - `retrieval_trace`：本輪 retrieval trace。
    - `assembled_contexts`：本輪 assembled contexts。
    - `document_name_by_id`：文件名稱對照表。

    回傳：
    - `RetrievalCoverageSignals | None`：本輪 coverage 訊號。
    """

    query_type = str(retrieval_trace.get("query_type", ""))
    summary_scope = str(retrieval_trace.get("summary_scope") or "")
    if query_type != EvaluationQueryType.cross_document_compare.value and summary_scope != "multi_document":
        return None

    resolved_document_ids = [
        str(document_id)
        for document_id in (retrieval_trace.get("resolved_document_ids") or [])
        if isinstance(document_id, str)
    ]
    cited_document_ids = list(dict.fromkeys(str(context.document_id) for context in assembled_contexts))
    missing_document_names = [
        document_name_by_id[document_id]
        for document_id in resolved_document_ids
        if document_id in document_name_by_id and document_id not in cited_document_ids
    ]
    supports_compare = len(cited_document_ids) >= 2
    return RetrievalCoverageSignals(
        missing_document_names=missing_document_names,
        supports_compare=supports_compare,
        insufficient_evidence=bool(missing_document_names) or not supports_compare,
        missing_compare_axes=[] if supports_compare else ["共同點與差異都缺少雙邊直接證據"],
        new_evidence_found=bool(assembled_contexts),
    )


def _build_next_best_followups(
    *,
    retrieval_trace: dict[str, object],
    assembled_contexts: list[AssembledContext],
    document_name_by_id: dict[str, str],
) -> list[str]:
    """建立 agent 下一步 follow-up 建議。

    參數：
    - `retrieval_trace`：本輪 retrieval trace。
    - `assembled_contexts`：本輪 assembled contexts。
    - `document_name_by_id`：文件名稱對照表。

    回傳：
    - `list[str]`：下一步 follow-up 建議。
    """

    coverage_signals = _build_coverage_signals(
        retrieval_trace=retrieval_trace,
        assembled_contexts=assembled_contexts,
        document_name_by_id=document_name_by_id,
    )
    if coverage_signals is None:
        return []

    followups = [
        f"補查文件「{document_name}」的直接 compare 證據。"
        for document_name in coverage_signals.missing_document_names
    ]
    if not coverage_signals.supports_compare:
        followups.append("優先找出每份文件對同一 compare 面向的直接引文，再整理共同點與差異。")
    return followups


def _build_evidence_cue_texts(
    *,
    assembled_contexts: list[AssembledContext],
    document_name_by_id: dict[str, str],
) -> list[RetrievalEvidenceCue]:
    """從 assembled contexts 建立短 evidence cues。

    參數：
    - `assembled_contexts`：本輪 assembled contexts。
    - `document_name_by_id`：文件名稱對照表。

    回傳：
    - `list[RetrievalEvidenceCue]`：短 cue 清單。
    """

    cues: list[RetrievalEvidenceCue] = []
    for index, context in enumerate(assembled_contexts[:3]):
        cues.append(
            RetrievalEvidenceCue(
                context_label=_build_context_label(index),
                document_name=document_name_by_id.get(str(context.document_id), ""),
                cue_text=context.assembled_text.replace("\n", " ").strip()[:MAX_EVIDENCE_CUE_CHARS],
            )
        )
    return cues


def _build_synopsis_hints(
    *,
    authorized_ready_documents: list[Document],
    synopsis_document_ids: tuple[str, ...] | None,
) -> list[RetrievalSynopsisHint]:
    """建立 agent 可見的 synopsis planning hints。

    參數：
    - `authorized_ready_documents`：目前 area 內已授權且 ready 的文件。
    - `synopsis_document_ids`：要求查看 synopsis 的文件識別碼。

    回傳：
    - `list[RetrievalSynopsisHint]`：synopsis hint 清單。
    """

    if not synopsis_document_ids:
        return []

    documents_by_id = {str(document.id): document for document in authorized_ready_documents}
    hints: list[RetrievalSynopsisHint] = []
    for document_id in synopsis_document_ids:
        document = documents_by_id.get(document_id)
        if document is None:
            continue
        synopsis_text = (document.synopsis_text or "").strip()
        if not synopsis_text:
            continue
        hints.append(
            RetrievalSynopsisHint(
                handle=_encode_document_handle(document_id=document_id),
                document_name=str(document.file_name),
                synopsis_text=synopsis_text[:MAX_SYNOPSIS_HINT_CHARS],
            )
        )
    return hints
