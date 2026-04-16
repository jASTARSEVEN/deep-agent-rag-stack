"""啟動 Playwright E2E 專用 API server，並注入可觀測的 fake Deep Agents runtime。"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import Request
from fastapi.responses import JSONResponse, StreamingResponse
import uvicorn


# `apps/api` 模組根目錄。
API_ROOT_DIRECTORY = Path(__file__).resolve().parents[4] / "api"
# `apps/api/src` 目錄，供 E2E wrapper 匯入正式 API 模組。
API_SRC_DIRECTORY = API_ROOT_DIRECTORY / "src"

if str(API_SRC_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(API_SRC_DIRECTORY))

from app.auth.verifier import CurrentPrincipal
from app.chat.agent.runtime import DeepAgentsChatRuntime


# E2E wrapper 內記錄已建立的 assistant ids。
REGISTERED_ASSISTANT_IDS: set[str] = set()
# E2E wrapper 內記錄 thread state。
THREAD_STATE_BY_ID: dict[str, dict[str, Any]] = {}
# E2E wrapper 內記錄已失效 thread。
STALE_THREAD_IDS: set[str] = set()


def _resolve_principal_from_request(request: Request) -> CurrentPrincipal:
    """從目前 request 的 Bearer token 解析 principal。

    參數：
    - `request`：目前 HTTP request。

    回傳：
    - `CurrentPrincipal`：由 Bearer token 或 fallback 建立的 principal。
    """

    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        return CurrentPrincipal(sub="e2e-user", groups=(), authenticated=True)
    token = authorization.removeprefix("Bearer ").strip()
    verifier = request.app.state.token_verifier
    return verifier.verify(token)


def _build_answer_block(
    *,
    text: str,
    context_index: int | None = None,
    context_label: str | None = None,
    document_id: str | None = None,
    document_name: str | None = None,
    heading: str | None = None,
) -> dict[str, Any]:
    """建立 assistant answer block payload。

    參數：
    - `text`：區塊文字。
    - `context_index`：引用 context index；若為空則不產生 citation。
    - `context_label`：顯示用 citation label。
    - `document_id`：引用文件識別碼。
    - `document_name`：引用文件名稱。
    - `heading`：引用段落標題。

    回傳：
    - `dict[str, Any]`：符合前端 answer block contract 的字典。
    """

    if context_index is None or context_label is None or document_id is None or document_name is None:
        return {
            "text": text,
            "citation_context_indices": [],
            "display_citations": [],
        }

    return {
        "text": text,
        "citation_context_indices": [context_index],
        "display_citations": [
            {
                "context_index": context_index,
                "context_label": context_label,
                "document_id": document_id,
                "document_name": document_name,
                "heading": heading,
                "page_start": None,
                "page_end": None,
            }
        ],
    }


def _build_context_reference(
    *,
    context_index: int,
    context_label: str,
    document_id: str,
    document_name: str,
    parent_chunk_id: str,
    child_chunk_ids: list[str],
    heading: str,
    excerpt: str,
) -> dict[str, Any]:
    """建立 assembled context / reference payload。

    參數：
    - `context_index`：context 順序。
    - `context_label`：顯示用 citation label。
    - `document_id`：文件識別碼。
    - `document_name`：文件名稱。
    - `parent_chunk_id`：parent chunk 識別碼。
    - `child_chunk_ids`：child chunk 識別碼列表。
    - `heading`：段落標題。
    - `excerpt`：context 摘要文字。

    回傳：
    - `dict[str, Any]`：符合前端 citation / references contract 的字典。
    """

    return {
        "context_index": context_index,
        "context_label": context_label,
        "document_id": document_id,
        "document_name": document_name,
        "parent_chunk_id": parent_chunk_id,
        "child_chunk_ids": child_chunk_ids,
        "structure_kind": "text",
        "heading": heading,
        "excerpt": excerpt,
        "assembled_text": excerpt,
        "source": "hybrid",
        "start_offset": 0,
        "end_offset": len(excerpt),
        "page_start": None,
        "page_end": None,
        "regions": [],
        "truncated": False,
    }


def _build_message_artifact(
    *,
    answer: str,
    answer_blocks: list[dict[str, Any]],
    citations: list[dict[str, Any]],
    assistant_turn_index: int,
    used_knowledge_base: bool,
) -> dict[str, Any]:
    """建立 LangGraph thread state 使用的 assistant artifact。

    參數：
    - `answer`：最終回答文字。
    - `answer_blocks`：回答區塊。
    - `citations`：引用列表。
    - `assistant_turn_index`：目前 assistant turn index。
    - `used_knowledge_base`：本輪是否使用知識庫。

    回傳：
    - `dict[str, Any]`：可持久化到 thread state 的 artifact。
    """

    return {
        "assistant_turn_index": assistant_turn_index,
        "answer": answer,
        "answer_blocks": answer_blocks,
        "citations": citations,
        "used_knowledge_base": used_knowledge_base,
    }


def _emit_phase(writer, *, phase: str, status: str, message: str) -> None:
    """發送 LangGraph custom phase event。

    參數：
    - `writer`：LangGraph stream writer。
    - `phase`：高層 phase 名稱。
    - `status`：phase 狀態。
    - `message`：顯示訊息。

    回傳：
    - `None`：僅透過 writer 輸出事件。
    """

    if writer is None:
        return
    writer({"type": "phase", "phase": phase, "status": status, "message": message})


def _emit_tool_call(writer, *, status: str, output: dict[str, Any] | None = None) -> None:
    """發送 LangGraph custom tool_call event。

    參數：
    - `writer`：LangGraph stream writer。
    - `status`：tool call 狀態。
    - `output`：可選的 tool output 摘要。

    回傳：
    - `None`：僅透過 writer 輸出事件。
    """

    if writer is None:
        return
    writer(
        {
            "type": "tool_call",
            "name": "retrieve_area_contexts",
            "status": status,
            "input": {"area_id": "e2e-area", "question": "e2e-question"},
            "output": output,
        }
    )


def _emit_references(writer, references: list[dict[str, Any]]) -> None:
    """發送 LangGraph custom references event。

    參數：
    - `writer`：LangGraph stream writer。
    - `references`：references payload。

    回傳：
    - `None`：僅透過 writer 輸出事件。
    """

    if writer is None:
        return
    writer({"type": "references", "references": references})


def _to_sse_event(*, event: str, data: dict[str, Any]) -> str:
    """將單筆事件編碼為 LangGraph SDK 可讀的 SSE 片段。

    參數：
    - `event`：SSE event 名稱。
    - `data`：可 JSON 序列化的 payload。

    回傳：
    - `str`：SSE 文字片段。
    """

    import json

    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


class FakeE2EDeepAgentsRuntime(DeepAgentsChatRuntime):
    """Playwright E2E 專用的 fake Deep Agents runtime。"""

    def __init__(self) -> None:
        """初始化 fake runtime。

        參數：
        - 無。

        回傳：
        - `None`：僅保存 provider/model metadata。
        """

        self.provider_name = "deepagents"
        self.model = os.getenv("CHAT_MODEL", "gpt-5.4-mini")

    def run(
        self,
        *,
        session,
        principal: CurrentPrincipal,
        settings,
        area_id: str,
        question: str,
        thinking_mode: bool = False,
        conversation_messages: list[object] | None = None,
        writer=None,
        benchmark_document_ids=None,
    ) -> dict[str, Any]:
        """執行 E2E 專用 fake chat runtime。

        參數：
        - `session`：目前資料庫 session；此 runtime 不直接使用。
        - `principal`：目前登入的 principal。
        - `settings`：目前 API 設定。
        - `area_id`：當前 area 識別碼。
        - `question`：使用者提問。
        - `thinking_mode`：thinking mode 旗標。
        - `conversation_messages`：目前 thread 已累積的對話訊息。
        - `writer`：LangGraph custom event writer。
        - `benchmark_document_ids`：benchmark 專用覆寫；E2E 不使用。

        回傳：
        - `dict[str, Any]`：符合 LangGraph chat node 預期的結果 payload。
        """

        del session, benchmark_document_ids

        assistant_turn_index = sum(
            1
            for message in (conversation_messages or [])
            if isinstance(message, dict) and (message.get("role") == "assistant" or message.get("type") == "ai")
        )

        _emit_phase(writer, phase="preparing", status="started", message="正在建立回答流程")
        _emit_phase(writer, phase="preparing", status="completed", message="回答流程建立完成")
        _emit_phase(writer, phase="thinking", status="started", message="正在理解問題")
        _emit_phase(writer, phase="tool_calling", status="started", message="正在呼叫知識庫工具")
        _emit_phase(writer, phase="searching", status="started", message="正在搜尋知識庫內容")
        _emit_tool_call(writer, status="started")

        if "maintainer guide" in question.lower():
            references = [
                _build_context_reference(
                    context_index=0,
                    context_label="C1",
                    document_id="00000000-0000-0000-0000-000000000101",
                    document_name="reader-handbook.md",
                    parent_chunk_id="00000000-0000-0000-0000-000000000201",
                    child_chunk_ids=["00000000-0000-0000-0000-000000000202"],
                    heading="Reader Intro",
                    excerpt="Reader handbook 只提到 reader policy，沒有未授權文件的直接證據。",
                )
            ]
            tool_output = {
                "contexts_count": 1,
                "citations_count": 1,
                "tool_call_count": 1,
                "followup_call_count": 0,
                "latency_budget_status": "within_budget",
                "stop_reason": "insufficient_visible_evidence",
                "coverage_signals": {
                    "missing_document_names": [],
                    "supports_compare": False,
                    "insufficient_evidence": True,
                    "missing_compare_axes": ["unauthorized_document_evidence"],
                    "new_evidence_found": False,
                },
                "planning_documents": [
                    {
                        "handle": "reader-visible-handle",
                        "document_name": "reader-handbook.md",
                        "mentioned_by_query": True,
                        "hit_in_current_round": True,
                        "synopsis_available": True,
                    }
                ],
                "next_best_followups": ["僅能在已授權且 ready 的文件內補查"],
                "contexts": references,
            }
            answer = "目前引用內容只涵蓋已授權且 ready 的 Reader Handbook，證據不足以比較你提到的其他文件。"
            answer_blocks = [
                _build_answer_block(
                    text=answer,
                    context_index=0,
                    context_label="C1",
                    document_id="00000000-0000-0000-0000-000000000101",
                    document_name="reader-handbook.md",
                    heading="Reader Intro",
                )
            ]
            trace = {
                "agent": {
                    "provider": self.provider_name,
                    "model": self.model,
                    "contexts_count": 1,
                    "used_fallback": False,
                    "retrieval_invoked": True,
                    "answer_path": "deepagents_unified",
                    "thinking_mode": thinking_mode,
                    "thinking_mode_ignored": False,
                }
            }
        elif "travel policy" in question.lower() or "比較" in question:
            references = [
                _build_context_reference(
                    context_index=0,
                    context_label="C1",
                    document_id="00000000-0000-0000-0000-000000000301",
                    document_name="travel-policy.md",
                    parent_chunk_id="00000000-0000-0000-0000-000000000401",
                    child_chunk_ids=["00000000-0000-0000-0000-000000000402"],
                    heading="Approval Rule",
                    excerpt="Travel Policy 明確要求出差前需取得主管同意。",
                )
            ]
            _emit_phase(writer, phase="searching", status="completed", message="首輪搜尋已找到 1 個候選片段")
            _emit_phase(writer, phase="tool_calling", status="completed", message="首輪工具呼叫完成")
            _emit_tool_call(
                writer,
                status="completed",
                output={
                    "contexts_count": 1,
                    "citations_count": 1,
                    "tool_call_count": 1,
                    "followup_call_count": 0,
                    "latency_budget_status": "within_budget",
                    "stop_reason": "followup_requested",
                    "coverage_signals": {
                        "missing_document_names": ["expense-guidelines.md"],
                        "supports_compare": True,
                        "insufficient_evidence": True,
                        "missing_compare_axes": ["approval requirement"],
                        "new_evidence_found": True,
                    },
                    "planning_documents": [
                        {
                            "handle": "travel-policy-handle",
                            "document_name": "travel-policy.md",
                            "mentioned_by_query": True,
                            "hit_in_current_round": True,
                            "synopsis_available": True,
                        }
                    ],
                    "next_best_followups": ["補查 expense-guidelines.md 是否明示 approval requirement"],
                    "contexts": references,
                },
            )
            _emit_phase(writer, phase="tool_calling", status="started", message="正在進行 follow-up 工具呼叫")
            _emit_phase(writer, phase="searching", status="started", message="正在補查比較缺口")
            _emit_tool_call(writer, status="started")
            tool_output = {
                "contexts_count": 1,
                "citations_count": 1,
                "tool_call_count": 2,
                "followup_call_count": 1,
                "synopsis_inspection_count": 1,
                "latency_budget_status": "degraded",
                "stop_reason": "latency_budget_soft_limit",
                "coverage_signals": {
                    "missing_document_names": ["expense-guidelines.md"],
                    "supports_compare": True,
                    "insufficient_evidence": True,
                    "missing_compare_axes": ["approval requirement"],
                    "new_evidence_found": False,
                },
                "planning_documents": [
                    {
                        "handle": "travel-policy-handle",
                        "document_name": "travel-policy.md",
                        "mentioned_by_query": True,
                        "hit_in_current_round": True,
                        "synopsis_available": True,
                    }
                ],
                "next_best_followups": ["目前已達 latency soft limit，停止繼續補查"],
                "contexts": references,
            }
            answer = "目前只有 Travel Policy 有直接引用證據，Expense Guidelines 的現有引用內容未明示 approval requirement，因此證據不足以完成完整比較。"
            answer_blocks = [
                _build_answer_block(
                    text=answer,
                    context_index=0,
                    context_label="C1",
                    document_id="00000000-0000-0000-0000-000000000301",
                    document_name="travel-policy.md",
                    heading="Approval Rule",
                )
            ]
            trace = {
                "agent": {
                    "provider": self.provider_name,
                    "model": self.model,
                    "contexts_count": 1,
                    "used_fallback": False,
                    "retrieval_invoked": True,
                    "answer_path": "deepagents_unified",
                    "thinking_mode": thinking_mode,
                    "thinking_mode_ignored": False,
                },
                "loop": {
                    "tool_call_count": 2,
                    "followup_call_count": 1,
                    "latency_budget_status": "degraded",
                    "stop_reason": "latency_budget_soft_limit",
                },
            }
        else:
            references = [
                _build_context_reference(
                    context_index=0,
                    context_label="C1",
                    document_id="00000000-0000-0000-0000-000000000101",
                    document_name="reader-handbook.md",
                    parent_chunk_id="00000000-0000-0000-0000-000000000201",
                    child_chunk_ids=["00000000-0000-0000-0000-000000000202"],
                    heading="Reader Intro",
                    excerpt="Reader handbook 說明 reader policy 與 citation 行為。",
                )
            ]
            tool_output = {
                "contexts_count": 1,
                "citations_count": 1,
                "tool_call_count": 1,
                "followup_call_count": 0,
                "latency_budget_status": "within_budget",
                "stop_reason": "evidence_sufficient",
                "coverage_signals": {
                    "missing_document_names": [],
                    "supports_compare": False,
                    "insufficient_evidence": False,
                    "missing_compare_axes": [],
                    "new_evidence_found": True,
                },
                "planning_documents": [
                    {
                        "handle": "reader-visible-handle",
                        "document_name": "reader-handbook.md",
                        "mentioned_by_query": True,
                        "hit_in_current_round": True,
                        "synopsis_available": True,
                    }
                ],
                "next_best_followups": [],
                "contexts": references,
            }
            answer = "Reader Handbook 說明 reader policy 與 citations 會綁定在已授權且 ready 的內容。"
            answer_blocks = [
                _build_answer_block(
                    text=answer,
                    context_index=0,
                    context_label="C1",
                    document_id="00000000-0000-0000-0000-000000000101",
                    document_name="reader-handbook.md",
                    heading="Reader Intro",
                )
            ]
            trace = {
                "agent": {
                    "provider": self.provider_name,
                    "model": self.model,
                    "contexts_count": 1,
                    "used_fallback": False,
                    "retrieval_invoked": True,
                    "answer_path": "deepagents_unified",
                    "thinking_mode": thinking_mode,
                    "thinking_mode_ignored": False,
                }
            }

        _emit_references(writer, references)
        _emit_phase(writer, phase="searching", status="completed", message="知識庫搜尋完成")
        _emit_phase(writer, phase="tool_calling", status="completed", message="知識庫工具呼叫完成")
        _emit_tool_call(writer, status="completed", output=tool_output)
        _emit_phase(writer, phase="drafting", status="started", message="正在整理回答")
        if writer is not None:
            writer({"type": "token", "delta": answer})
        _emit_phase(writer, phase="drafting", status="completed", message="回答整理完成")
        _emit_phase(writer, phase="thinking", status="completed", message="回答完成")

        message_artifact = _build_message_artifact(
            answer=answer,
            answer_blocks=answer_blocks,
            citations=references,
            assistant_turn_index=assistant_turn_index,
            used_knowledge_base=bool(references),
        )
        raw_result = {"messages": [{"role": "assistant", "content": answer}]}

        return {
            "answer": answer,
            "answer_blocks": answer_blocks,
            "citations": references,
            "assembled_contexts": references,
            "message_artifact": message_artifact,
            "used_knowledge_base": bool(references),
            "trace": trace,
            "raw_result": raw_result,
        }


def _build_e2e_runtime(_settings) -> FakeE2EDeepAgentsRuntime:
    """建立 E2E 專用 fake runtime。

    參數：
    - `_settings`：目前 API 設定；此 runtime 不直接使用。

    回傳：
    - `FakeE2EDeepAgentsRuntime`：E2E 專用 runtime。
    """

    return FakeE2EDeepAgentsRuntime()


def main() -> None:
    """啟動注入 fake runtime 的 E2E API server。

    參數：
    - 無。

    回傳：
    - `None`：此函式會直接啟動 uvicorn。
    """

    import app.chat.runtime.langgraph_agent as langgraph_agent

    langgraph_agent.build_chat_runtime = _build_e2e_runtime

    from app.chat.runtime.langgraph_http_app import app

    @app.post("/assistants")
    async def create_assistant(request: Request) -> dict[str, Any]:
        """建立 E2E 專用 assistant 註冊紀錄。

        參數：
        - `request`：HTTP request；內含 assistant create payload。

        回傳：
        - `dict[str, Any]`：最小 assistant payload。
        """

        payload = await request.json()
        assistant_id = str(payload.get("assistant_id") or uuid4())
        REGISTERED_ASSISTANT_IDS.add(assistant_id)
        return {
            "assistant_id": assistant_id,
            "graph_id": payload.get("graph_id"),
            "name": payload.get("name"),
        }

    @app.post("/threads")
    async def create_thread(request: Request) -> dict[str, Any]:
        """建立 E2E 專用 thread state。

        參數：
        - `request`：HTTP request；內含 thread create payload。

        回傳：
        - `dict[str, Any]`：最小 thread payload。
        """

        payload = await request.json()
        principal = _resolve_principal_from_request(request)
        thread_id = str(payload.get("thread_id") or uuid4())
        metadata = dict(payload.get("metadata", {}) or {})
        metadata["owner"] = principal.sub
        THREAD_STATE_BY_ID.setdefault(
            thread_id,
            {
                "messages": [],
                "message_artifacts": [],
                "metadata": metadata,
            },
        )
        return {"thread_id": thread_id}

    @app.get("/threads/{thread_id}")
    async def get_thread(thread_id: str) -> JSONResponse:
        """回傳 E2E thread metadata。

        參數：
        - `thread_id`：目標 thread 識別碼。

        回傳：
        - `JSONResponse`：最小 thread payload；找不到時回 404。
        """

        if thread_id in STALE_THREAD_IDS:
            return JSONResponse({"detail": "Thread not found"}, status_code=404)
        state = THREAD_STATE_BY_ID.get(thread_id)
        if state is None:
            return JSONResponse({"detail": "Thread not found"}, status_code=404)
        return JSONResponse(
            {
                "thread_id": thread_id,
                "created_at": "2026-04-16T00:00:00Z",
                "updated_at": "2026-04-16T00:00:00Z",
                "metadata": state.get("metadata", {}),
                "status": "idle",
                "values": state,
                "interrupts": {},
            }
        )

    @app.get("/threads/{thread_id}/state")
    async def get_thread_state(thread_id: str) -> JSONResponse:
        """回傳 E2E thread state。

        參數：
        - `thread_id`：目標 thread 識別碼。

        回傳：
        - `JSONResponse`：LangGraph thread state 相容 payload。
        """

        if thread_id in STALE_THREAD_IDS:
            return JSONResponse({"detail": "Thread not found"}, status_code=404)
        state = THREAD_STATE_BY_ID.get(thread_id)
        if state is None:
            return JSONResponse({"detail": "Thread not found"}, status_code=404)
        return JSONResponse({"values": state})

    @app.post("/__e2e/threads/{thread_id}/mark-stale")
    async def mark_thread_stale(thread_id: str) -> dict[str, Any]:
        """將指定 thread 標記為 stale，讓後續 metadata/state 查詢回 404。"""

        STALE_THREAD_IDS.add(thread_id)
        return {"thread_id": thread_id, "stale": True}

    @app.post("/threads/{thread_id}/runs/stream", response_model=None)
    async def stream_thread_run(thread_id: str, request: Request) -> Any:
        """執行 E2E 專用 fake run 並以 SSE 回傳。

        參數：
        - `thread_id`：目標 thread 識別碼。
        - `request`：HTTP request；內含 run payload。

        回傳：
        - `JSONResponse | StreamingResponse`：assistant/thread 驗證失敗時回 404，否則回 SSE stream。
        """

        payload = await request.json()
        assistant_id = str(payload.get("assistant_id") or "")
        if assistant_id not in REGISTERED_ASSISTANT_IDS:
            return JSONResponse({"detail": "Assistant not found"}, status_code=404)

        state = THREAD_STATE_BY_ID.get(thread_id)
        if state is None:
            return JSONResponse({"detail": "Thread not found"}, status_code=404)

        input_payload = payload.get("input", {})
        area_id = str(input_payload.get("area_id") or state.get("metadata", {}).get("area_id") or "")
        question = str(input_payload.get("question") or "")
        runtime_events: list[dict[str, Any]] = []
        runtime = FakeE2EDeepAgentsRuntime()
        result = runtime.run(
            session=None,
            principal=CurrentPrincipal(sub="e2e-user", groups=(), authenticated=True),
            settings=getattr(app.state, "settings", None),
            area_id=area_id,
            question=question,
            thinking_mode=bool(input_payload.get("thinking_mode", False)),
            conversation_messages=list(state.get("messages", [])),
            writer=runtime_events.append,
        )

        state["messages"] = [
            *list(state.get("messages", [])),
            {"role": "user", "content": question},
            {"role": "assistant", "content": result["answer"]},
        ]
        state["message_artifacts"] = [
            *list(state.get("message_artifacts", [])),
            result["message_artifact"],
        ]

        async def event_stream():
            """逐筆輸出 SSE 事件。

            參數：
            - 無。

            回傳：
            - `AsyncIterator[str]`：SSE 文字片段。
            """

            for event in runtime_events:
                yield _to_sse_event(event="custom", data=event)
            yield _to_sse_event(
                event="values",
                data={
                    "area_id": area_id,
                    "question": question,
                    "answer": result["answer"],
                    "answer_blocks": result["answer_blocks"],
                    "citations": result["citations"],
                    "assembled_contexts": result["assembled_contexts"],
                    "used_knowledge_base": result["used_knowledge_base"],
                    "trace": result["trace"],
                    "messages": state["messages"],
                    "message_artifacts": state["message_artifacts"],
                },
            )

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    uvicorn.run(
        app,
        host=os.getenv("API_HOST", "127.0.0.1"),
        port=int(os.getenv("API_PORT", "18001")),
    )


if __name__ == "__main__":
    main()
