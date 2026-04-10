"""Deep Agents 使用的 retrieval tool 與 payload mapper。"""

from __future__ import annotations

from dataclasses import dataclass, asdict

from sqlalchemy import select

from app.auth.verifier import CurrentPrincipal
from app.chat.contracts.types import ChatCitation, ChatCitationRegion
from app.core.settings import AppSettings
from app.db.models import Document, EvaluationQueryType
from app.services.retrieval import retrieve_area_candidates
from app.services.retrieval_routing import DocumentScope, SummaryStrategy, build_query_routing_decision
from app.services.retrieval_assembler import AssembledContext, AssembledRetrievalResult, assemble_retrieval_result


@dataclass(slots=True)
class RetrievalToolResult:
    """retrieval pipeline 封裝為單一 tool 的輸出。"""

    # chat-ready contexts。
    assembled_contexts: list[AssembledContext]
    # assembled-context reference metadata。
    citations: list[ChatCitation]
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

    回傳：
    - `RetrievalToolResult`：contexts、citations 與 trace。

    前置條件：
    - 此 tool 必須始終維持 SQL gate、same-404 與 ready-only。
    """

    explicit_query_type = _coerce_optional_query_type(task_type=task_type)
    retrieval_result = retrieve_area_candidates(
        session=session,
        principal=principal,
        settings=settings,
        area_id=area_id,
        query=question,
        document_scope=document_scope,
        summary_strategy=summary_strategy,
        query_type=explicit_query_type,
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
    return {
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
        "query_focus_applied": retrieval_trace.get("query_focus_applied"),
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
