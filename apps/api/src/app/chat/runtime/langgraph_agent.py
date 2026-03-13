"""LangGraph public graph，僅負責將輸入交給 Deep Agents chat runtime。"""

from __future__ import annotations

from typing import NotRequired, TypedDict

from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph

from app.auth.verifier import CurrentPrincipal
from app.chat.agent.runtime import DeepAgentsChatRuntime, build_chat_runtime
from app.chat.tools.retrieval import retrieve_area_contexts_tool
from app.core.settings import get_settings
from app.db.session import create_database_engine, create_session_factory


# LangGraph default endpoint 使用的全域 settings。
GRAPH_SETTINGS = get_settings()
# LangGraph default endpoint 使用的全域資料庫 engine。
GRAPH_ENGINE = create_database_engine(GRAPH_SETTINGS)
# LangGraph default endpoint 使用的全域 session factory。
GRAPH_SESSION_FACTORY = create_session_factory(GRAPH_ENGINE)


class ChatGraphState(TypedDict):
    """單輪 chat graph state。"""

    # 要提問的 area 識別碼。
    area_id: str
    # 使用者提問。
    question: str
    # 目前已驗證使用者。
    principal: dict[str, object]
    # 最終回答文字。
    answer: str
    # 最終 context references。
    citations: list[dict]
    # 最終 assembled contexts。
    assembled_contexts: list[dict]
    # 最終 trace。
    trace: dict
    # 測試與本機覆寫用的可選 settings。
    settings: NotRequired[object]
    # 測試與本機覆寫用的可選 session factory。
    session_factory: NotRequired[object]


def _run_chat_node(state: ChatGraphState) -> ChatGraphState:
    """Graph 節點：執行單輪 chat 並回填輸出。"""

    runtime_settings = state.get("settings", GRAPH_SETTINGS)
    session_factory = state.get("session_factory", GRAPH_SESSION_FACTORY)
    principal_payload = state["principal"]
    principal = CurrentPrincipal(
        sub=str(principal_payload["sub"]),
        groups=tuple(str(group) for group in principal_payload.get("groups", [])),
        authenticated=bool(principal_payload.get("authenticated", True)),
    )
    session = session_factory()
    try:
        runtime = build_chat_runtime(runtime_settings)
        if isinstance(runtime, DeepAgentsChatRuntime):
            result = runtime.run(
                session=session,
                principal=principal,
                settings=runtime_settings,
                area_id=state["area_id"],
                question=state["question"],
                writer=get_stream_writer(),
            )
            return {
                **state,
                "answer": str(result.get("answer", "")),
                "citations": list(result.get("citations", [])),
                "assembled_contexts": list(result.get("assembled_contexts", [])),
                "trace": dict(result.get("trace", {})),
            }

        retrieval_tool_result = retrieve_area_contexts_tool(
            session=session,
            principal=principal,
            settings=runtime_settings,
            area_id=state["area_id"],
            question=state["question"],
        )
        answer, _ = runtime.generate_answer(
            question=state["question"],
            assembled_contexts=retrieval_tool_result.assembled_contexts,
        )
        return {
            **state,
            "answer": answer,
            "citations": [item.model_dump(mode="json") for item in retrieval_tool_result.citations],
            "assembled_contexts": [
                {
                    "context_index": index,
                    "document_id": context.document_id,
                    "parent_chunk_id": context.parent_chunk_id,
                    "child_chunk_ids": context.chunk_ids,
                    "structure_kind": context.structure_kind.value,
                    "heading": context.heading,
                    "assembled_text": context.assembled_text,
                    "source": context.source,
                    "start_offset": context.start_offset,
                    "end_offset": context.end_offset,
                    "truncated": next(
                        (
                            item["truncated"]
                            for item in retrieval_tool_result.trace["assembler"]["contexts"]
                            if item["context_index"] == index
                        ),
                        False,
                    ),
                }
                for index, context in enumerate(retrieval_tool_result.assembled_contexts)
            ],
            "trace": {
                "retrieval": retrieval_tool_result.trace["retrieval"],
                "assembler": retrieval_tool_result.trace["assembler"],
                "agent": {
                    "provider": runtime.provider_name,
                    "model": runtime.model,
                    "contexts_count": len(retrieval_tool_result.assembled_contexts),
                    "used_fallback": len(retrieval_tool_result.assembled_contexts) == 0,
                },
            },
        }
    finally:
        session.close()


def build_graph(_config=None):
    """建立 LangGraph public graph。"""

    workflow = StateGraph(ChatGraphState)
    workflow.add_node("run_chat", _run_chat_node)
    workflow.add_edge(START, "run_chat")
    workflow.add_edge("run_chat", END)
    return workflow.compile()


# 對外匯出的 compiled graph。
graph = build_graph()
