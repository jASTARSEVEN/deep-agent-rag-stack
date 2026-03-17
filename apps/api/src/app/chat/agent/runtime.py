"""Chat runtime：Deep Agents 正式路徑與 deterministic 測試 adapter。"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable, Iterator
from contextlib import nullcontext
from dataclasses import asdict, dataclass
from typing import Any

from app.auth.verifier import CurrentPrincipal
from app.chat.agent.deep_agents import build_main_agent
from app.chat.tools.retrieval import (
    RetrievalToolResult,
    build_agent_tool_context_payload,
    build_assembled_context_payload,
    build_tool_call_output_summary,
    retrieve_area_contexts_tool,
)
from app.core.settings import AppSettings
from app.services.retrieval_assembler import AssembledContext

try:
    from langchain_core.tools import tool
except ImportError:  # pragma: no cover - 依賴缺失時於執行期明確失敗。
    tool = None  # type: ignore[assignment]

try:
    from langchain_openai import ChatOpenAI
except ImportError:  # pragma: no cover - 依賴缺失時於執行期明確失敗。
    ChatOpenAI = None  # type: ignore[assignment]

try:
    from langsmith import tracing_context
except ImportError:  # pragma: no cover - 依賴缺失時於執行期明確失敗。
    tracing_context = None  # type: ignore[assignment]


# chat streaming debug 使用的模組 logger。
LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class AgentTrace:
    """answer layer 與 Deep Agents 的最小 trace。"""

    # 使用的 provider 名稱。
    provider: str
    # 使用的模型名稱。
    model: str
    # 傳入 answer layer 的 context 數量。
    contexts_count: int
    # 此次是否使用 fallback。
    used_fallback: bool
    # 本輪保留的 agent 執行摘要；目前未額外拆 task。
    agent_tasks: list[str]
    # 此次是否實際執行 retrieval。
    retrieval_invoked: bool
    # 實際啟用的 sub-agent 名稱。
    sub_agents_invoked: list[str]


class DeterministicChatRuntime:
    """供測試與離線環境使用的穩定 answer runtime。"""

    def __init__(self, *, model: str) -> None:
        """初始化 deterministic chat runtime。

        參數：
        - `model`：用於 trace 的模型名稱。

        回傳：
        - `None`：此建構子只保存設定。
        """

        self.provider_name = "deterministic"
        self.model = model

    def generate_answer(self, *, question: str, assembled_contexts: list[AssembledContext]) -> tuple[str, AgentTrace]:
        """根據 contexts 產生穩定回答。

        參數：
        - `question`：使用者提問。
        - `assembled_contexts`：已組裝的 contexts。

        回傳：
        - `tuple[str, AgentTrace]`：回答文字與 trace。
        """

        if not assembled_contexts:
            return (
                "目前可用的已授權文件中沒有足夠內容可以回答這個問題。",
                AgentTrace(
                    provider=self.provider_name,
                    model=self.model,
                    contexts_count=0,
                    used_fallback=False,
                    agent_tasks=[],
                    retrieval_invoked=True,
                    sub_agents_invoked=[],
                ),
            )

        context_text = " ".join(context.assembled_text.replace("\n", " ").strip() for context in assembled_contexts[:2]).strip()
        headings = [context.heading for context in assembled_contexts if context.heading]
        heading_text = "、".join(dict.fromkeys(headings[:3])) if headings else "相關段落"
        return (
            f"根據目前已授權且完成索引的內容，問題「{question}」可參考 {heading_text}。重點如下：{context_text[:320]}",
            AgentTrace(
                provider=self.provider_name,
                model=self.model,
                contexts_count=len(assembled_contexts),
                used_fallback=False,
                agent_tasks=[],
                retrieval_invoked=True,
                sub_agents_invoked=[],
            ),
        )

    def stream_answer(self, *, question: str, assembled_contexts: list[AssembledContext]) -> Iterator[str]:
        """以穩定回答模擬串流輸出。

        參數：
        - `question`：使用者提問。
        - `assembled_contexts`：已組裝的 contexts。

        回傳：
        - `Iterator[str]`：單段回答文字。
        """

        answer, _ = self.generate_answer(question=question, assembled_contexts=assembled_contexts)
        yield answer


class DeepAgentsChatRuntime:
    """使用 Deep Agents 執行正式 area-scoped chat 的 runtime。"""

    def __init__(self, *, model: str, api_key: str, max_output_tokens: int, timeout_seconds: int) -> None:
        """初始化 Deep Agents runtime。

        參數：
        - `model`：要使用的 chat model 名稱。
        - `api_key`：OpenAI API key。
        - `max_output_tokens`：回答輸出上限。
        - `timeout_seconds`：OpenAI API timeout 秒數。

        回傳：
        - `None`：此建構子只保存設定。
        """

        self.provider_name = "deepagents"
        self.model = model
        self._api_key = api_key
        self._max_output_tokens = max_output_tokens
        self._timeout_seconds = timeout_seconds

    def _build_langsmith_tags(self, *, settings: AppSettings) -> list[str]:
        """建立本次 chat invocation 的 LangSmith tags。

        參數：
        - `settings`：API 執行期設定。

        回傳：
        - `list[str]`：LangSmith UI 可篩選的 tags。
        """

        return [
            "deepagents",
            "langgraph",
            f"chat_provider:{self.provider_name}",
            f"chat_model:{settings.chat_model}",
        ]

    def _build_langsmith_metadata(
        self,
        *,
        principal: CurrentPrincipal,
        settings: AppSettings,
        area_id: str,
        question: str,
    ) -> dict[str, object]:
        """建立本次 chat invocation 的 LangSmith metadata。

        參數：
        - `principal`：目前已驗證使用者。
        - `settings`：API 執行期設定。
        - `area_id`：目標 area。
        - `question`：使用者提問。

        回傳：
        - `dict[str, object]`：供 LangSmith trace 篩選與除錯使用的 metadata。
        """

        return {
            "area_id": area_id,
            "principal_sub": principal.sub,
            "principal_groups_count": len(principal.groups),
            "chat_provider": self.provider_name,
            "chat_model": settings.chat_model,
            "question_length": len(question),
        }

    def run(
        self,
        *,
        session,
        principal: CurrentPrincipal,
        settings: AppSettings,
        area_id: str,
        question: str,
        conversation_messages: list[object] | None = None,
        writer: Callable[[dict[str, object]], None] | None = None,
    ) -> dict[str, object]:
        """執行 Deep Agents 回答，並回傳最終 graph state payload。

        參數：
        - `session`：目前資料庫 session。
        - `principal`：目前已驗證使用者。
        - `settings`：API 執行期設定。
        - `area_id`：目標 area。
        - `question`：使用者提問。
        - `conversation_messages`：目前 thread 已累積的對話訊息；若無則回退為單輪輸入。
        - `writer`：LangGraph custom event writer。

        回傳：
        - `dict[str, object]`：最終回答、references 與 trace。
        """

        if ChatOpenAI is None or tool is None:  # pragma: no cover - 依賴缺失時於執行期明確失敗。
            raise RuntimeError("缺少 langchain-openai 或 langchain-core 依賴，無法建立 Deep Agents runtime。")

        retrieval_invoked = False
        retrieval_result: RetrievalToolResult | None = None
        citations_payload: list[dict[str, object]] = []
        assembled_contexts_payload: list[dict[str, object]] = []
        llm_tool_contexts_payload: list[dict[str, object]] = []
        stream_started_at = time.perf_counter()
        first_token_emitted = False

        def log_stream_debug(*, event: str, **fields: object) -> None:
            """在啟用 debug 時記錄 chat stream 關鍵時間點。

            參數：
            - `event`：事件名稱。
            - `**fields`：附帶欄位。

            回傳：
            - `None`：僅記錄 debug log。
            """

            if not settings.chat_stream_debug:
                return
            elapsed_ms = round((time.perf_counter() - stream_started_at) * 1000, 1)
            LOGGER.info(
                "chat_stream_debug event=%s elapsed_ms=%s area_id=%s question=%r fields=%s",
                event,
                elapsed_ms,
                area_id,
                question,
                fields,
            )

        def emit_phase(*, phase: str, status: str, message: str) -> None:
            """透過 LangGraph custom stream 發送高層 chat 階段事件。"""

            log_stream_debug(event="phase", phase=phase, status=status, message=message)
            if writer is None:
                return
            writer({"type": "phase", "phase": phase, "status": status, "message": message})

        def emit_tool_call(
            *,
            name: str,
            status: str,
            input_payload: dict[str, object],
            output_payload: dict[str, object] | None = None,
        ) -> None:
            """透過 LangGraph custom stream 發送工具呼叫事件。"""

            log_stream_debug(event="tool_call", name=name, status=status)
            if writer is None:
                return
            writer(
                {
                    "type": "tool_call",
                    "name": name,
                    "status": status,
                    "input": input_payload,
                    "output": output_payload,
                }
            )

        @tool
        def retrieve_area_contexts(focus_query: str | None = None) -> str:
            """回傳目前 area 與問題的 assembled contexts、references 與 trace。"""

            nonlocal retrieval_invoked, retrieval_result, citations_payload, assembled_contexts_payload, llm_tool_contexts_payload

            if retrieval_result is None:
                tool_input = {
                    "area_id": area_id,
                    "question": focus_query.strip() if isinstance(focus_query, str) and focus_query.strip() else question,
                }
                emit_phase(phase="tool_calling", status="started", message="正在呼叫知識庫工具")
                emit_phase(phase="searching", status="started", message="正在搜尋知識庫內容")
                emit_tool_call(name="retrieve_area_contexts", status="started", input_payload=tool_input)
                retrieval_result = retrieve_area_contexts_tool(
                    session=session,
                    principal=principal,
                    settings=settings,
                    area_id=area_id,
                    question=str(tool_input["question"]),
                )
                citations_payload = [item.model_dump(mode="json") for item in retrieval_result.citations]
                assembled_contexts_payload = build_assembled_context_payload(retrieval_result)
                llm_tool_contexts_payload = build_agent_tool_context_payload(retrieval_result)
                retrieval_invoked = True
                log_stream_debug(
                    event="retrieval_complete",
                    contexts_count=len(retrieval_result.assembled_contexts),
                    citations_count=len(retrieval_result.citations),
                )
                emit_phase(phase="searching", status="completed", message="知識庫搜尋完成")
                emit_phase(phase="tool_calling", status="completed", message="知識庫工具呼叫完成")
                emit_tool_call(
                    name="retrieve_area_contexts",
                    status="completed",
                    input_payload=tool_input,
                    output_payload=build_tool_call_output_summary(retrieval_result),
                )

            return json.dumps(
                {
                    "assembled_contexts": llm_tool_contexts_payload,
                },
                ensure_ascii=False,
            )

        llm = ChatOpenAI(
            model=self.model,
            api_key=self._api_key,
            timeout=self._timeout_seconds,
            max_tokens=self._max_output_tokens,
            streaming=True,
        )
        tracing_manager = nullcontext()
        if settings.langsmith_tracing:
            if tracing_context is None:  # pragma: no cover - 依賴缺失時於執行期明確失敗。
                raise RuntimeError("缺少 langsmith 依賴，無法啟用 LangSmith tracing。")
            if not settings.langsmith_api_key:
                raise ValueError("啟用 LangSmith tracing 前必須提供 LANGSMITH_API_KEY。")
            tracing_manager = tracing_context(
                enabled=True,
                project_name=settings.langsmith_project,
                tags=self._build_langsmith_tags(settings=settings),
                metadata=self._build_langsmith_metadata(
                    principal=principal,
                    settings=settings,
                    area_id=area_id,
                    question=question,
                ),
            )

        emit_phase(phase="thinking", status="started", message="正在思考如何回答")
        main_agent = build_main_agent(model=llm, retrieve_area_contexts_tool=retrieve_area_contexts)
        log_stream_debug(event="agent_stream_start")

        result: object | None = None
        streamed_answer_parts: list[str] = []
        with tracing_manager:
            for stream_item in main_agent.stream(
                {
                    "messages": _build_agent_input_messages(
                        question=question,
                        conversation_messages=conversation_messages,
                    )
                },
                stream_mode=["messages", "values"],
            ):
                stream_mode, stream_payload = _normalize_agent_stream_item(stream_item)
                if stream_mode == "messages":
                    text_delta = _extract_stream_message_text(stream_payload)
                    if text_delta:
                        if not first_token_emitted:
                            first_token_emitted = True
                            log_stream_debug(
                                event="first_answer_token",
                                delta_preview=text_delta[:80],
                                delta_length=len(text_delta),
                            )
                        streamed_answer_parts.append(text_delta)
                    continue
                if stream_mode == "values" and isinstance(stream_payload, dict):
                    log_stream_debug(
                        event="agent_values",
                        message_count=(
                            len(stream_payload.get("messages", []))
                            if isinstance(stream_payload.get("messages"), list)
                            else 0
                        ),
                        has_answer=bool(_extract_final_answer_text(stream_payload)),
                    )
                    result = stream_payload

        answer = _extract_final_answer_text(result) or "".join(streamed_answer_parts).strip() or "目前無法根據現有內容生成穩定回答。"
        log_stream_debug(
            event="answer_complete",
            token_events=len(streamed_answer_parts),
            answer_length=len(answer),
            retrieval_invoked=retrieval_invoked,
        )
        emit_phase(phase="thinking", status="completed", message="回答內容已整理完成")

        trace = {
            "retrieval": retrieval_result.trace["retrieval"] if retrieval_result is not None else {},
            "assembler": retrieval_result.trace["assembler"] if retrieval_result is not None else {"contexts": []},
            "agent": asdict(
                AgentTrace(
                    provider=self.provider_name,
                    model=self.model,
                    contexts_count=len(retrieval_result.assembled_contexts) if retrieval_result is not None else 0,
                    used_fallback=False,
                    agent_tasks=[],
                    retrieval_invoked=retrieval_invoked,
                    sub_agents_invoked=[],
                )
            ),
        }
        return {
            "answer": answer,
            "citations": citations_payload,
            "assembled_contexts": assembled_contexts_payload,
            "trace": trace,
            "raw_result": result,
        }


def build_chat_runtime(settings: AppSettings) -> DeterministicChatRuntime | DeepAgentsChatRuntime:
    """依照設定建立 chat runtime。

    參數：
    - `settings`：API 執行期設定。

    回傳：
    - runtime：deterministic 或 Deep Agents runtime。
    """

    provider_name = settings.chat_provider.strip().lower()
    if provider_name == "deterministic":
        return DeterministicChatRuntime(model=settings.chat_model)
    if provider_name == "deepagents":
        if not settings.openai_api_key:
            raise ValueError("使用 Deep Agents runtime 前必須提供 OPENAI_API_KEY。")
        return DeepAgentsChatRuntime(
            model=settings.chat_model,
            api_key=settings.openai_api_key,
            max_output_tokens=settings.chat_max_output_tokens,
            timeout_seconds=settings.chat_timeout_seconds,
        )
    raise ValueError(f"不支援的 chat provider：{settings.chat_provider}；僅支援 deterministic 與 deepagents。")


def _build_agent_input_messages(*, question: str, conversation_messages: list[object] | None) -> list[object]:
    """建立送進 Deep Agents 的對話訊息列表。

    參數：
    - `question`：目前這一輪的使用者問題。
    - `conversation_messages`：thread 內已累積的訊息列表。

    回傳：
    - `list[object]`：可直接送入 Deep Agents 的 message payload。
    """

    if isinstance(conversation_messages, list) and conversation_messages:
        return conversation_messages
    return [{"role": "user", "content": question}]


def _extract_final_answer_text(result: object) -> str:
    """依官方建議，從 agent 最終 `messages` 取最後一則回答文字。"""

    if not isinstance(result, dict):
        return ""
    messages = result.get("messages")
    if not isinstance(messages, list) or not messages:
        return ""
    final_message = messages[-1]
    if isinstance(final_message, dict):
        content = final_message.get("content")
    else:
        content = getattr(final_message, "content", None)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        return _flatten_message_content(content)
    return ""


def extract_final_assistant_message(result: object) -> dict[str, Any] | None:
    """從 Deep Agents 最終結果擷取最後一則助理訊息。

    參數：
    - `result`：Deep Agents `values` stream 最終 payload。

    回傳：
    - `dict[str, Any] | None`：可回寫到 LangGraph thread state 的助理訊息；若不存在則回傳 `None`。
    """

    if not isinstance(result, dict):
        return None
    messages = result.get("messages")
    if not isinstance(messages, list) or not messages:
        return None
    final_message = messages[-1]
    if isinstance(final_message, dict):
        message_type = final_message.get("type")
        role = final_message.get("role")
        if message_type == "ai" or role == "assistant":
            return final_message
        return None

    message_type = getattr(final_message, "type", None)
    message_content = getattr(final_message, "content", None)
    if message_type != "ai":
        return None
    return {
        "type": "ai",
        "role": "assistant",
        "content": message_content,
    }


def _normalize_agent_stream_item(stream_item: object) -> tuple[str | None, object]:
    """將 Deep Agents stream item 正規化為 `(stream_mode, payload)`。"""

    if isinstance(stream_item, tuple) and len(stream_item) == 2 and isinstance(stream_item[0], str):
        return stream_item[0], stream_item[1]
    return None, stream_item


def _extract_stream_message_text(stream_payload: object) -> str:
    """從 Deep Agents `messages` stream payload 擷取本次文字增量。"""

    if not isinstance(stream_payload, tuple) or not stream_payload:
        return ""
    message_like = stream_payload[0]
    if isinstance(message_like, dict):
        content = message_like.get("content")
    else:
        content = getattr(message_like, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return _flatten_message_content(content)
    return ""


def _flatten_message_content(content: list[object]) -> str:
    """將最後一則 message 的 content block 列表展平成純文字。"""

    text_parts: list[str] = []
    for item in content:
        if isinstance(item, str):
            text_parts.append(item)
            continue
        if not isinstance(item, dict):
            continue
        text_value = item.get("text")
        if isinstance(text_value, str):
            text_parts.append(text_value)
            continue
        if item.get("type") == "text" and isinstance(item.get("content"), str):
            text_parts.append(str(item["content"]))
    return "".join(text_parts)
