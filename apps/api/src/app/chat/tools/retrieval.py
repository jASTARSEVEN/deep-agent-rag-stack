"""Deep Agents 使用的 retrieval tool 與 payload mapper。"""

from __future__ import annotations

from dataclasses import dataclass, asdict

from app.auth.verifier import CurrentPrincipal
from app.chat.contracts.types import ChatCitation
from app.core.settings import AppSettings
from app.services.retrieval import retrieve_area_candidates
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
) -> RetrievalToolResult:
    """將 retrieval、rerank 與 assembler 包成單一 tool-shaped capability。

    參數：
    - `session`：目前資料庫 session。
    - `principal`：目前已驗證使用者。
    - `settings`：API 執行期設定。
    - `area_id`：檢索所屬 area。
    - `question`：使用者提問。

    回傳：
    - `RetrievalToolResult`：contexts、citations 與 trace。

    前置條件：
    - 此 tool 必須始終維持 SQL gate、same-404 與 ready-only。
    """

    retrieval_result = retrieve_area_candidates(
        session=session,
        principal=principal,
        settings=settings,
        area_id=area_id,
        query=question,
    )
    assembled_result = assemble_retrieval_result(
        session=session,
        settings=settings,
        retrieval_result=retrieval_result,
    )
    return RetrievalToolResult(
        assembled_contexts=assembled_result.assembled_contexts,
        citations=build_chat_citations(assembled_result=assembled_result, max_items=settings.assembler_max_contexts),
        trace={
            "retrieval": asdict(assembled_result.trace.retrieval),
            "assembler": asdict(assembled_result.trace.assembler),
        },
    )


def build_assembled_context_payload(retrieval_result: RetrievalToolResult | None) -> list[dict[str, object]]:
    """將 retrieval tool result 轉成前端可直接顯示的 assembled context payload。

    參數：
    - `retrieval_result`：單次 retrieval tool 執行結果。

    回傳：
    - `list[dict[str, object]]`：assembled context 列表。
    """

    if retrieval_result is None:
        return []

    truncated_by_index = {
        item["context_index"]: item["truncated"]
        for item in retrieval_result.trace["assembler"]["contexts"]
    }
    return [
        {
            "context_index": index,
            "document_id": context.document_id,
            "parent_chunk_id": context.parent_chunk_id,
            "child_chunk_ids": context.chunk_ids,
            "structure_kind": context.structure_kind.value,
            "heading": context.heading,
            "excerpt": context.assembled_text,
            "assembled_text": context.assembled_text,
            "source": context.source,
            "start_offset": context.start_offset,
            "end_offset": context.end_offset,
            "truncated": truncated_by_index.get(index, False),
        }
        for index, context in enumerate(retrieval_result.assembled_contexts)
    ]


def build_tool_call_output_summary(retrieval_result: RetrievalToolResult | None) -> dict[str, object]:
    """建立 custom `tool_call.completed` 事件的 debug-safe 摘要。

    參數：
    - `retrieval_result`：單次 retrieval tool 執行結果。

    回傳：
    - `dict[str, object]`：前端工具檢視可使用的摘要。
    """

    assembled_contexts_payload = build_assembled_context_payload(retrieval_result)
    return {
        "contexts_count": len(assembled_contexts_payload),
        "citations_count": len(retrieval_result.citations) if retrieval_result is not None else 0,
        "contexts": [
            {
                "context_index": item["context_index"],
                "document_id": item["document_id"],
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


def build_chat_citations(*, assembled_result: AssembledRetrievalResult, max_items: int) -> list[ChatCitation]:
    """將 assembler 輸出轉成 context-level references。

    參數：
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
    references: list[ChatCitation] = []
    for index, context in enumerate(assembled_result.assembled_contexts[:max_items]):
        references.append(
            ChatCitation(
                context_index=index,
                document_id=context.document_id,
                parent_chunk_id=context.parent_chunk_id,
                child_chunk_ids=context.chunk_ids,
                heading=context.heading,
                structure_kind=context.structure_kind,
                start_offset=context.start_offset,
                end_offset=context.end_offset,
                excerpt=context.assembled_text,
                source=context.source,
                truncated=truncated_by_index.get(index, False),
            )
        )
    return references
