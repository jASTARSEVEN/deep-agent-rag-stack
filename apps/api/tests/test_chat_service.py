"""Chat runtime 與 Deep Agents 路徑測試。"""

import json
from contextlib import contextmanager
from dataclasses import dataclass
from types import SimpleNamespace
from uuid import uuid4

from app.auth.verifier import CurrentPrincipal
from app.core.settings import AppSettings
from app.db.models import (
    Area,
    AreaUserRole,
    ChunkStructureKind,
    ChunkType,
    Document,
    DocumentChunk,
    DocumentStatus,
    EvaluationQueryType,
    Role,
)
from app.chat.agent.runtime import (
    DeepAgentsChatRuntime,
    DeterministicChatRuntime,
    _build_answer_blocks_from_markers,
    _build_agent_input_messages,
    build_chat_runtime,
)
from app.services.retrieval_assembler import AssembledContext


def _uuid() -> str:
    """建立測試用 UUID 字串。

    參數：
    - 無

    回傳：
    - `str`：新的 UUID 字串。
    """

    return str(uuid4())


def test_deterministic_runtime_factory_returns_deterministic_runtime() -> None:
    """`CHAT_PROVIDER=deterministic` 應建立 deterministic runtime。

    參數：
    - 無

    回傳：
    - `None`：僅驗證 provider factory 結果型別。
    """

    settings = AppSettings(
        CHAT_PROVIDER="deterministic",
        CHAT_MODEL="deterministic-answer",
    )

    provider = build_chat_runtime(settings)

    assert isinstance(provider, DeterministicChatRuntime)
    assert provider.provider_name == "deterministic"


def test_deepagents_runtime_factory_returns_real_deepagents_runtime() -> None:
    """`CHAT_PROVIDER=deepagents` 應建立真正的 Deep Agents runtime。

    參數：
    - 無

    回傳：
    - `None`：僅驗證 provider factory 結果型別。
    """

    settings = AppSettings(
        CHAT_PROVIDER="deepagents",
        CHAT_MODEL="gpt-5-mini",
        CHAT_MAX_OUTPUT_TOKENS=1024,
        CHAT_TIMEOUT_SECONDS=60,
        OPENAI_API_KEY="test-key",
    )

    provider = build_chat_runtime(settings)

    assert isinstance(provider, DeepAgentsChatRuntime)
    assert provider.provider_name == "deepagents"


def test_deepagents_runtime_exposes_single_retrieval_tool_without_keyword_gate(monkeypatch) -> None:
    """Deep Agents 主 agent 應自行決定是否呼叫單一 retrieval tool。

    參數：
    - `monkeypatch`：pytest monkeypatch fixture。

    回傳：
    - `None`：僅驗證單一 tool 暴露與無 keyword gate 強制檢索。
    """

    captured_tools: list[object] = []

    class FakeChatOpenAI:
        """模擬 Deep Agents 使用的 ChatOpenAI。"""

        def __init__(self, **kwargs) -> None:
            """初始化假 LLM。

            參數：
            - `**kwargs`：LLM 初始化參數。

            回傳：
            - `None`：僅保存初始化參數。
            """

            self.kwargs = kwargs

    class FakeAgent:
        """模擬主 agent，且本案例刻意不呼叫 retrieval tool。"""

        def stream(self, _input, *, stream_mode):
            """輸出固定串流結果，模擬 agent 自行決定不查知識庫。

            參數：
            - `_input`：agent 輸入。
            - `stream_mode`：要求的 stream modes。

            回傳：
            - `list[tuple[str, object]]`：固定的 messages/values 串流片段。
            """

            assert stream_mode == ["messages", "values"]
            return iter(
                [
                    ("messages", ({"content": "這是直接回答。"}, {"tags": []})),
                    ("values", {"messages": [{"role": "assistant", "content": "這是直接回答。"}]}),
                ]
            )

    def fake_create_deep_agent(**kwargs):
        """記錄主 agent 暴露的 tools，並回傳假 agent。

        參數：
        - `**kwargs`：建立 agent 的參數。

        回傳：
        - `FakeAgent`：固定輸出回答的假 agent。
        """

        captured_tools.extend(kwargs.get("tools", []))
        return FakeAgent()

    monkeypatch.setattr("app.chat.agent.runtime.ChatOpenAI", FakeChatOpenAI)
    monkeypatch.setattr("app.chat.agent.deep_agents.create_deep_agent", fake_create_deep_agent)

    provider = DeepAgentsChatRuntime(
        model="gpt-5-mini",
        api_key="test-key",
        max_output_tokens=512,
        timeout_seconds=30,
    )
    settings = AppSettings(
        CHAT_PROVIDER="deepagents",
        CHAT_MODEL="gpt-5-mini",
        CHAT_MAX_OUTPUT_TOKENS=512,
        CHAT_TIMEOUT_SECONDS=30,
        OPENAI_API_KEY="test-key",
    )

    result = provider.run(
        session=None,
        principal=CurrentPrincipal(sub="user-1", groups=("/group/reader",), authenticated=True),
        settings=settings,
        area_id="area-1",
        question="請根據上傳文件回答知識區域是做什麼的？",
    )

    assert len(captured_tools) == 1
    assert result["answer"] == "這是直接回答。"
    assert result["trace"]["agent"]["retrieval_invoked"] is False


def test_build_agent_input_messages_prefers_thread_history() -> None:
    """Deep Agents 輸入應優先使用 LangGraph thread 已累積的歷史訊息。

    參數：
    - 無

    回傳：
    - `None`：僅驗證歷史訊息優先順序。
    """

    history_messages = [
        {"role": "user", "content": "第一輪問題"},
        {"role": "assistant", "content": "第一輪回答"},
        {"role": "user", "content": "第二輪追問"},
    ]

    assert (
        _build_agent_input_messages(
            question="這個欄位不應被拿來覆蓋 history",
            conversation_messages=history_messages,
        )
        == history_messages
    )


def test_build_answer_blocks_from_markers_parses_context_labels() -> None:
    """回答 marker 應被解析為 answer blocks 與 display citations。

    參數：
    - 無

    回傳：
    - `None`：以斷言驗證 marker parse 結果。
    """

    clean_answer, answer_blocks = _build_answer_blocks_from_markers(
        answer="第一段重點 [[C1]]\n\n第二段綜合整理 [[C1,C2]]",
        citations_payload=[
            {
                "context_index": 0,
                "context_label": "C1",
                "document_id": "doc-1",
                "document_name": "policy.md",
                "heading": "Section A",
                "parent_chunk_id": "parent-1",
                "child_chunk_ids": ["child-1"],
                "structure_kind": "text",
                "start_offset": 0,
                "end_offset": 10,
                "excerpt": "alpha",
                "source": "hybrid",
                "truncated": False,
            },
            {
                "context_index": 1,
                "context_label": "C2",
                "document_id": "doc-1",
                "document_name": "policy.md",
                "heading": "Section B",
                "parent_chunk_id": "parent-2",
                "child_chunk_ids": ["child-2"],
                "structure_kind": "text",
                "start_offset": 20,
                "end_offset": 30,
                "excerpt": "beta",
                "source": "hybrid",
                "truncated": False,
            },
        ],
    )

    assert clean_answer == "第一段重點\n\n第二段綜合整理"
    assert [block.text for block in answer_blocks] == ["第一段重點", "第二段綜合整理"]
    assert answer_blocks[0].citation_context_indices == [0]
    assert [item.context_label for item in answer_blocks[1].display_citations] == ["C1", "C2"]


def test_deepagents_runtime_uses_conversation_history_as_agent_input(monkeypatch) -> None:
    """Deep Agents runtime 應把 LangGraph thread 累積的 messages 傳給主 agent。

    參數：
    - `monkeypatch`：pytest monkeypatch fixture。

    回傳：
    - `None`：僅驗證多輪對話輸入來源。
    """

    captured_inputs: list[object] = []

    class FakeChatOpenAI:
        """模擬 Deep Agents 使用的 ChatOpenAI。"""

        def __init__(self, **kwargs) -> None:
            """初始化假 LLM。

            參數：
            - `**kwargs`：LLM 初始化參數。

            回傳：
            - `None`：僅保存初始化參數。
            """

            self.kwargs = kwargs

    class FakeAgent:
        """記錄 agent 輸入並回傳固定答案。"""

        def stream(self, agent_input, *, stream_mode):
            """記錄主 agent 取得的輸入內容。

            參數：
            - `agent_input`：主 agent 的輸入 payload。
            - `stream_mode`：要求的 stream modes。

            回傳：
            - `list[tuple[str, object]]`：固定串流結果。
            """

            captured_inputs.append(agent_input)
            assert stream_mode == ["messages", "values"]
            return iter(
                [
                    ("messages", ({"content": "這是多輪回答。"}, {"tags": []})),
                    ("values", {"messages": [{"role": "assistant", "content": "這是多輪回答。"}]}),
                ]
            )

    monkeypatch.setattr("app.chat.agent.runtime.ChatOpenAI", FakeChatOpenAI)
    monkeypatch.setattr("app.chat.agent.deep_agents.create_deep_agent", lambda **kwargs: FakeAgent())

    provider = DeepAgentsChatRuntime(
        model="gpt-5-mini",
        api_key="test-key",
        max_output_tokens=512,
        timeout_seconds=30,
    )
    settings = AppSettings(
        CHAT_PROVIDER="deepagents",
        CHAT_MODEL="gpt-5-mini",
        CHAT_MAX_OUTPUT_TOKENS=512,
        CHAT_TIMEOUT_SECONDS=30,
        OPENAI_API_KEY="test-key",
    )
    conversation_messages = [
        {"role": "user", "content": "第一輪：知識區域是什麼？"},
        {"role": "assistant", "content": "第一輪：知識區域是文件集合。"},
        {"role": "user", "content": "第二輪：那它的權限怎麼控管？"},
    ]

    result = provider.run(
        session=None,
        principal=CurrentPrincipal(sub="user-1", groups=("/group/reader",), authenticated=True),
        settings=settings,
        area_id="area-1",
        question="第二輪：那它的權限怎麼控管？",
        conversation_messages=conversation_messages,
    )

    assert result["answer"] == "這是多輪回答。"
    assert captured_inputs == [{"messages": conversation_messages}]


def test_deepagents_runtime_emits_phase_tool_call_and_token_custom_events(monkeypatch) -> None:
    """Deep Agents 應透過 writer 發出階段、工具呼叫與 token 事件。

    參數：
    - `monkeypatch`：pytest monkeypatch fixture。

    回傳：
    - `None`：僅驗證 custom phase event contract。
    """

    emitted_events: list[dict[str, object]] = []

    class FakeChatOpenAI:
        """模擬 Deep Agents 使用的 ChatOpenAI。"""

        def __init__(self, **kwargs) -> None:
            """初始化假 LLM。

            參數：
            - `**kwargs`：LLM 初始化參數。

            回傳：
            - `None`：僅保存初始化參數。
            """

            self.kwargs = kwargs

    monkeypatch.setattr("app.chat.agent.runtime.ChatOpenAI", FakeChatOpenAI)
    monkeypatch.setattr("app.chat.agent.runtime.tool", lambda func: func)

    def fake_retrieve_area_contexts_tool(**kwargs):
        """模擬 retrieval tool 結果。

        參數：
        - `**kwargs`：retrieval tool 參數。

        回傳：
        - `SimpleNamespace`：最小 retrieval 結果。
        """

        return SimpleNamespace(
            assembled_contexts=[],
            citations=[],
            trace={"retrieval": {"query": kwargs["question"]}, "assembler": {"contexts": []}},
        )

    monkeypatch.setattr("app.chat.agent.runtime.retrieve_area_contexts_tool", fake_retrieve_area_contexts_tool)

    class FakeAgent:
        """模擬主 agent，並主動呼叫 retrieval tool。"""

        def __init__(self, tools) -> None:
            """初始化假 agent。

            參數：
            - `tools`：主 agent 可用的工具列表。

            回傳：
            - `None`：僅保存工具列表。
            """

            self.tools = tools

        def stream(self, _input, *, stream_mode):
            """先呼叫 retrieval tool，再回傳固定串流回答。

            參數：
            - `_input`：agent 輸入。
            - `stream_mode`：要求的 stream modes。

            回傳：
            - `list[tuple[str, object]]`：固定的 messages/values 串流片段。
            """

            assert stream_mode == ["messages", "values"]
            self.tools[0]("reader policy")
            return iter(
                [
                    ("messages", ({"content": "這是帶搜尋流程的回答。"}, {"tags": []})),
                    ("values", {"messages": [{"role": "assistant", "content": "這是帶搜尋流程的回答。"}]}),
                ]
            )

    def fake_create_deep_agent(**kwargs):
        """回傳會主動呼叫 retrieval tool 的假 agent。

        參數：
        - `**kwargs`：建立 agent 的參數。

        回傳：
        - `FakeAgent`：固定輸出的假 agent。
        """

        return FakeAgent(kwargs.get("tools", []))

    monkeypatch.setattr("app.chat.agent.deep_agents.create_deep_agent", fake_create_deep_agent)

    provider = DeepAgentsChatRuntime(
        model="gpt-5-mini",
        api_key="test-key",
        max_output_tokens=512,
        timeout_seconds=30,
    )
    settings = AppSettings(
        CHAT_PROVIDER="deepagents",
        CHAT_MODEL="gpt-5-mini",
        CHAT_MAX_OUTPUT_TOKENS=512,
        CHAT_TIMEOUT_SECONDS=30,
        OPENAI_API_KEY="test-key",
    )

    result = provider.run(
        session=None,
        principal=CurrentPrincipal(sub="user-1", groups=("/group/reader",), authenticated=True),
        settings=settings,
        area_id="area-1",
        question="請根據文件回答 reader policy",
        writer=emitted_events.append,
    )

    assert result["answer"] == "這是帶搜尋流程的回答。"
    phase_events = [event for event in emitted_events if event["type"] == "phase"]
    tool_events = [event for event in emitted_events if event["type"] == "tool_call"]
    assert [event["phase"] for event in phase_events] == [
        "preparing",
        "preparing",
        "thinking",
        "tool_calling",
        "searching",
        "searching",
        "tool_calling",
        "thinking",
        "drafting",
        "drafting",
        "thinking",
    ]
    assert [event["status"] for event in tool_events] == ["started", "completed"]
    assert tool_events[0]["name"] == "retrieve_area_contexts"
    assert tool_events[0]["input"] == {"area_id": "area-1", "question": "請根據文件回答 reader policy"}
    assert tool_events[1]["output"] == {
        "contexts_count": 0,
        "citations_count": 0,
        "query_type": None,
        "query_type_language": None,
        "query_type_source": None,
        "query_type_confidence": None,
        "query_type_matched_rules": [],
        "query_type_rule_hits": [],
        "query_type_embedding_scores": [],
        "query_type_top_label": None,
        "query_type_runner_up_label": None,
        "query_type_embedding_margin": None,
        "query_type_fallback_used": None,
        "query_type_fallback_reason": None,
        "summary_scope": None,
        "summary_strategy": None,
        "summary_strategy_source": None,
        "summary_strategy_confidence": None,
        "summary_strategy_rule_hits": [],
        "summary_strategy_embedding_scores": [],
        "summary_strategy_top_label": None,
        "summary_strategy_runner_up_label": None,
        "summary_strategy_embedding_margin": None,
        "summary_strategy_fallback_used": None,
        "summary_strategy_fallback_reason": None,
        "resolved_document_ids": [],
        "document_mention_source": None,
        "document_mention_confidence": None,
        "document_mention_candidates": [],
        "selected_profile": None,
        "fallback_reason": None,
        "selection_applied": None,
        "selection_strategy": None,
        "selected_document_count": None,
        "selected_parent_count": None,
        "selected_document_ids": [],
        "selected_parent_ids": [],
        "dropped_by_diversity": [],
        "query_focus_applied": None,
        "profile_settings": {},
        "contexts": [],
    }
    reference_events = [event for event in emitted_events if event["type"] == "references"]
    assert reference_events == [{"type": "references", "references": []}]
    token_events = [event for event in emitted_events if event["type"] == "token"]
    assert token_events == [{"type": "token", "delta": "這是帶搜尋流程的回答。"}]


def test_deepagents_runtime_summary_queries_use_unified_answer_path(monkeypatch) -> None:
    """summary query 應不再分 lane，而是統一走 Deep Agents answer path。"""

    captured_llm_kwargs: list[dict[str, object]] = []
    captured_inputs: list[object] = []

    class FakeChatOpenAI:
        """模擬 Deep Agents 使用的 ChatOpenAI。"""

        def __init__(self, **kwargs) -> None:
            """初始化假 LLM。"""

            self.kwargs = kwargs
            captured_llm_kwargs.append(dict(kwargs))

    class FakeAgent:
        """模擬主 agent，會主動呼叫 retrieval tool。"""

        def __init__(self, tools) -> None:
            """初始化假 agent。"""

            self.tools = tools

        def stream(self, agent_input, *, stream_mode):
            """先執行 retrieval tool，再回傳固定回答。"""

            captured_inputs.append(agent_input)
            assert stream_mode == ["messages", "values"]
            self.tools[0]("summary question")
            return iter(
                [
                    ("messages", ({"content": "這是統一路徑摘要回答。"}, {"tags": []})),
                    ("values", {"messages": [{"role": "assistant", "content": "這是統一路徑摘要回答。"}]}),
                ]
            )

    def fake_create_deep_agent(**kwargs):
        """建立固定假 agent。"""

        return FakeAgent(kwargs.get("tools", []))

    def fake_retrieve_area_contexts_tool(**kwargs):
        """回傳最小 retrieval 結果。"""

        return SimpleNamespace(
            assembled_contexts=[],
            citations=[],
            trace={"retrieval": {"query": kwargs["question"]}, "assembler": {"contexts": []}},
        )

    monkeypatch.setattr("app.chat.agent.runtime.ChatOpenAI", FakeChatOpenAI)
    monkeypatch.setattr("app.chat.agent.runtime.tool", lambda func: func)
    monkeypatch.setattr("app.chat.agent.runtime.retrieve_area_contexts_tool", fake_retrieve_area_contexts_tool)
    monkeypatch.setattr("app.chat.agent.deep_agents.create_deep_agent", fake_create_deep_agent)

    provider = DeepAgentsChatRuntime(
        model="gpt-5-mini",
        api_key="test-key",
        max_output_tokens=512,
        timeout_seconds=30,
    )
    settings = AppSettings(
        CHAT_PROVIDER="deepagents",
        CHAT_MODEL="gpt-5-mini",
        CHAT_MAX_OUTPUT_TOKENS=512,
        CHAT_TIMEOUT_SECONDS=30,
        OPENAI_API_KEY="test-key",
    )

    result_false = provider.run(
        session=None,
        principal=CurrentPrincipal(sub="user-1", groups=("/group/reader",), authenticated=True),
        settings=settings,
        area_id="area-1",
        question="Summarize the document",
        thinking_mode=False,
    )
    result_true = provider.run(
        session=None,
        principal=CurrentPrincipal(sub="user-1", groups=("/group/reader",), authenticated=True),
        settings=settings,
        area_id="area-1",
        question="Summarize the section",
        thinking_mode=True,
    )

    assert result_false["answer"] == "這是統一路徑摘要回答。"
    assert result_true["answer"] == "這是統一路徑摘要回答。"
    assert result_false["trace"]["agent"]["answer_path"] == "deepagents_unified"
    assert result_true["trace"]["agent"]["answer_path"] == "deepagents_unified"
    assert result_false["trace"]["agent"]["thinking_mode"] is False
    assert result_true["trace"]["agent"]["thinking_mode"] is True
    assert result_false["trace"]["agent"]["thinking_mode_ignored"] is False
    assert result_true["trace"]["agent"]["thinking_mode_ignored"] is True
    assert captured_llm_kwargs[0]["reasoning_effort"] == "minimal"
    assert all(item == {"messages": [{"role": "user", "content": "Summarize the document"}]} or item == {"messages": [{"role": "user", "content": "Summarize the section"}]} for item in captured_inputs)


def test_deepagents_tool_call_completed_event_includes_context_excerpt(monkeypatch) -> None:
    """有 retrieval context 時，tool completed 事件應包含 excerpt 與 assembled_text。

    參數：
    - `monkeypatch`：pytest monkeypatch fixture。

    回傳：
    - `None`：僅驗證 tool output 的 context payload shape。
    """

    emitted_events: list[dict[str, object]] = []

    class FakeChatOpenAI:
        """模擬 Deep Agents 使用的 ChatOpenAI。"""

        def __init__(self, **kwargs) -> None:
            """初始化假 LLM。

            參數：
            - `**kwargs`：LLM 初始化參數。

            回傳：
            - `None`：僅保存初始化參數。
            """

            self.kwargs = kwargs

    @dataclass
    class FakeCitation:
        """模擬 citation 的最小 `model_dump` 介面。"""

        context_index: int
        context_label: str
        document_id: str
        document_name: str
        parent_chunk_id: str | None
        child_chunk_ids: list[str]
        heading: str | None
        structure_kind: str
        start_offset: int
        end_offset: int
        excerpt: str
        source: str
        truncated: bool
        page_start: int | None = None
        page_end: int | None = None
        regions: list[dict[str, object]] | None = None

        def model_dump(self, *, mode: str = "json") -> dict[str, object]:
            """回傳與 Pydantic model 類似的 dump 結果。

            參數：
            - `mode`：序列化模式。

            回傳：
            - `dict[str, object]`：序列化後字典。
            """

            assert mode == "json"
            return {
                "context_index": self.context_index,
                "context_label": self.context_label,
                "document_id": self.document_id,
                "document_name": self.document_name,
                "parent_chunk_id": self.parent_chunk_id,
                "child_chunk_ids": self.child_chunk_ids,
                "heading": self.heading,
                "structure_kind": self.structure_kind,
                "start_offset": self.start_offset,
                "end_offset": self.end_offset,
                    "excerpt": self.excerpt,
                    "source": self.source,
                    "truncated": self.truncated,
                    "page_start": self.page_start,
                    "page_end": self.page_end,
                    "regions": self.regions or [],
                }

    monkeypatch.setattr("app.chat.agent.runtime.ChatOpenAI", FakeChatOpenAI)
    monkeypatch.setattr("app.chat.agent.runtime.tool", lambda func: func)

    def fake_retrieve_area_contexts_tool(**kwargs):
        """回傳包含單一 assembled context 的 retrieval 結果。"""

        return SimpleNamespace(
            assembled_contexts=[
                AssembledContext(
                    document_id="doc-1",
                    parent_chunk_id="parent-1",
                    chunk_ids=["child-1", "child-2"],
                        structure_kind=ChunkStructureKind.text,
                    heading="Reader Policy",
                    assembled_text="這是一段組裝後的內容。",
                    source="業務規格書.md",
                    start_offset=10,
                    end_offset=40,
                )
            ],
            citations=[
                FakeCitation(
                    context_index=0,
                    context_label="C1",
                    document_id="doc-1",
                    document_name="reader-policy.md",
                    parent_chunk_id="parent-1",
                    child_chunk_ids=["child-1", "child-2"],
                    heading="Reader Policy",
                    structure_kind="text",
                    start_offset=10,
                    end_offset=40,
                    excerpt="這是一段組裝後的內容。",
                    source="hybrid",
                    truncated=False,
                )
            ],
            trace={
                "retrieval": {"query": kwargs["question"]},
                "assembler": {"contexts": [{"context_index": 0, "truncated": False}]},
            },
        )

    monkeypatch.setattr("app.chat.agent.runtime.retrieve_area_contexts_tool", fake_retrieve_area_contexts_tool)

    class FakeAgent:
        """模擬主 agent，並主動呼叫 retrieval tool。"""

        def __init__(self, tools) -> None:
            """初始化假 agent。"""

            self.tools = tools

        def stream(self, _input, *, stream_mode):
            """先執行 retrieval，再回傳固定回答。"""

            assert stream_mode == ["messages", "values"]
            self.tools[0]("reader policy")
            return iter(
                [
                    ("messages", ({"content": "這是回答。"}, {"tags": []})),
                    ("values", {"messages": [{"role": "assistant", "content": "這是回答。"}]}),
                ]
            )

    monkeypatch.setattr("app.chat.agent.deep_agents.create_deep_agent", lambda **kwargs: FakeAgent(kwargs.get("tools", [])))

    provider = DeepAgentsChatRuntime(
        model="gpt-5-mini",
        api_key="test-key",
        max_output_tokens=512,
        timeout_seconds=30,
    )
    settings = AppSettings(
        CHAT_PROVIDER="deepagents",
        CHAT_MODEL="gpt-5-mini",
        CHAT_MAX_OUTPUT_TOKENS=512,
        CHAT_TIMEOUT_SECONDS=30,
        OPENAI_API_KEY="test-key",
    )

    provider.run(
        session=None,
        principal=CurrentPrincipal(sub="user-1", groups=("/group/reader",), authenticated=True),
        settings=settings,
        area_id="area-1",
        question="請根據文件回答 reader policy",
        writer=emitted_events.append,
    )

    completed_tool_event = [
        event for event in emitted_events if event["type"] == "tool_call" and event["status"] == "completed"
    ][0]
    context_payload = completed_tool_event["output"]["contexts"][0]

    assert context_payload["excerpt"] == "這是一段組裝後的內容。"
    assert "assembled_text" not in context_payload


def test_deepagents_runtime_returns_slim_tool_payload_to_llm(monkeypatch) -> None:
    """Deep Agents tool 回傳給 LLM 時應只包含最小 assembled contexts。

    參數：
    - `monkeypatch`：pytest monkeypatch fixture。

    回傳：
    - `None`：僅驗證餵給 LLM 的 tool payload 已瘦身。
    """

    captured_tool_result: dict[str, object] = {}

    class FakeChatOpenAI:
        """模擬 Deep Agents 使用的 ChatOpenAI。"""

        def __init__(self, **kwargs) -> None:
            """初始化假 LLM。

            參數：
            - `**kwargs`：LLM 初始化參數。

            回傳：
            - `None`：僅保存初始化參數。
            """

            self.kwargs = kwargs

    @dataclass
    class FakeCitation:
        """模擬 citation 的最小 `model_dump` 介面。"""

        context_index: int
        context_label: str
        document_id: str
        document_name: str
        parent_chunk_id: str | None
        child_chunk_ids: list[str]
        heading: str | None
        structure_kind: str
        start_offset: int
        end_offset: int
        excerpt: str
        source: str
        truncated: bool
        page_start: int | None = None
        page_end: int | None = None
        regions: list[dict[str, object]] | None = None

        def model_dump(self, *, mode: str = "json") -> dict[str, object]:
            """回傳與 Pydantic model 類似的 dump 結果。

            參數：
            - `mode`：序列化模式。

            回傳：
            - `dict[str, object]`：序列化後字典。
            """

            assert mode == "json"
            return {
                "context_index": self.context_index,
                "context_label": self.context_label,
                "document_id": self.document_id,
                "document_name": self.document_name,
                "parent_chunk_id": self.parent_chunk_id,
                "child_chunk_ids": self.child_chunk_ids,
                "heading": self.heading,
                "structure_kind": self.structure_kind,
                "start_offset": self.start_offset,
                "end_offset": self.end_offset,
                    "excerpt": self.excerpt,
                    "source": self.source,
                    "truncated": self.truncated,
                    "page_start": self.page_start,
                    "page_end": self.page_end,
                    "regions": self.regions or [],
                }

    monkeypatch.setattr("app.chat.agent.runtime.ChatOpenAI", FakeChatOpenAI)
    monkeypatch.setattr("app.chat.agent.runtime.tool", lambda func: func)

    def fake_retrieve_area_contexts_tool(**kwargs):
        """回傳包含單一 assembled context 的 retrieval 結果。"""

        return SimpleNamespace(
            assembled_contexts=[
                AssembledContext(
                    document_id="doc-1",
                    parent_chunk_id="parent-1",
                    chunk_ids=["child-1"],
                    structure_kind=ChunkStructureKind.text,
                    heading="Reader Policy",
                    assembled_text="這是一段組裝後的內容。",
                    source="業務規格書.md",
                    start_offset=10,
                    end_offset=40,
                )
            ],
            citations=[
                FakeCitation(
                    context_index=0,
                    context_label="C1",
                    document_id="doc-1",
                    document_name="reader-policy.md",
                    parent_chunk_id="parent-1",
                    child_chunk_ids=["child-1"],
                    heading="Reader Policy",
                    structure_kind="text",
                    start_offset=10,
                    end_offset=40,
                    excerpt="這是一段組裝後的內容。",
                    source="hybrid",
                    truncated=False,
                )
            ],
            trace={
                "retrieval": {"query": kwargs["question"]},
                "assembler": {"contexts": [{"context_index": 0, "truncated": False}]},
            },
        )

    monkeypatch.setattr("app.chat.agent.runtime.retrieve_area_contexts_tool", fake_retrieve_area_contexts_tool)

    class FakeAgent:
        """模擬主 agent，並擷取 tool 回傳字串。"""

        def __init__(self, tools) -> None:
            """初始化假 agent。"""

            self.tools = tools

        def stream(self, _input, *, stream_mode):
            """先執行 retrieval，再回傳固定回答。"""

            assert stream_mode == ["messages", "values"]
            captured_tool_result.update(json.loads(self.tools[0]("reader policy")))
            return iter(
                [
                    ("messages", ({"content": "這是回答。"}, {"tags": []})),
                    ("values", {"messages": [{"role": "assistant", "content": "這是回答。"}]}),
                ]
            )

    monkeypatch.setattr("app.chat.agent.deep_agents.create_deep_agent", lambda **kwargs: FakeAgent(kwargs.get("tools", [])))

    provider = DeepAgentsChatRuntime(
        model="gpt-5-mini",
        api_key="test-key",
        max_output_tokens=512,
        timeout_seconds=30,
    )
    settings = AppSettings(
        CHAT_PROVIDER="deepagents",
        CHAT_MODEL="gpt-5-mini",
        CHAT_MAX_OUTPUT_TOKENS=512,
        CHAT_TIMEOUT_SECONDS=30,
        OPENAI_API_KEY="test-key",
    )

    provider.run(
        session=None,
        principal=CurrentPrincipal(sub="user-1", groups=("/group/reader",), authenticated=True),
        settings=settings,
        area_id="area-1",
        question="請根據文件回答 reader policy",
    )

    assert list(captured_tool_result.keys()) == ["assembled_contexts"]
    assert captured_tool_result["assembled_contexts"] == [
        {
            "context_label": "C1",
            "context_index": 0,
            "document_name": "reader-policy.md",
            "heading": "Reader Policy",
            "assembled_text": "這是一段組裝後的內容。",
        }
    ]


def test_deepagents_runtime_runs_real_retrieval_tool_and_returns_context_contract(
    db_session,
    app_settings,
    monkeypatch,
) -> None:
    """Deep Agents runtime 應可走真實 retrieval tool 並回傳 assembled-context contract。

    參數：
    - `db_session`：測試資料庫 session fixture。
    - `app_settings`：測試設定 fixture。
    - `monkeypatch`：pytest monkeypatch fixture。

    回傳：
    - `None`：以斷言驗證 Deep Agents 與 retrieval tool 的整合契約。
    """

    area = Area(id=_uuid(), name="Deep Agents Tool Integration")
    document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="reader-policy.md",
        content_type="text/markdown",
        file_size=100,
        storage_key="area/document-reader-policy/reader-policy.md",
        status=DocumentStatus.ready,
    )
    parent = DocumentChunk(
        id=_uuid(),
        document_id=document.id,
        parent_chunk_id=None,
        chunk_type=ChunkType.parent,
        structure_kind=ChunkStructureKind.text,
        position=0,
        section_index=0,
        child_index=None,
        heading="Reader Policy",
        content="alpha intro\n\nalpha details",
        content_preview="alpha intro",
        char_count=27,
        start_offset=0,
        end_offset=27,
    )
    child_one = DocumentChunk(
        id=_uuid(),
        document_id=document.id,
        parent_chunk_id=parent.id,
        chunk_type=ChunkType.child,
        structure_kind=ChunkStructureKind.text,
        position=1,
        section_index=0,
        child_index=0,
        heading="Reader Policy",
        content="alpha intro",
        content_preview="alpha intro",
        char_count=11,
        start_offset=0,
        end_offset=11,
        embedding=[0.1] * app_settings.embedding_dimensions,
    )
    child_two = DocumentChunk(
        id=_uuid(),
        document_id=document.id,
        parent_chunk_id=parent.id,
        chunk_type=ChunkType.child,
        structure_kind=ChunkStructureKind.text,
        position=2,
        section_index=0,
        child_index=1,
        heading="Reader Policy",
        content="alpha details",
        content_preview="alpha details",
        char_count=13,
        start_offset=13,
        end_offset=26,
        embedding=[0.1] * app_settings.embedding_dimensions,
    )
    db_session.add_all(
        [
            area,
            AreaUserRole(area_id=area.id, user_sub="user-reader", role=Role.reader),
            document,
            parent,
            child_one,
            child_two,
        ]
    )
    db_session.commit()

    captured_tool_result: dict[str, object] = {}
    emitted_events: list[dict[str, object]] = []

    class FakeChatOpenAI:
        """模擬 Deep Agents 使用的 ChatOpenAI。"""

        def __init__(self, **kwargs) -> None:
            """初始化假 LLM。

            參數：
            - `**kwargs`：LLM 初始化參數。

            回傳：
            - `None`：僅保存初始化參數。
            """

            self.kwargs = kwargs

    class FakeAgent:
        """模擬主 agent，並主動呼叫真實 retrieval tool。"""

        def __init__(self, tools) -> None:
            """初始化假 agent。

            參數：
            - `tools`：主 agent 可用工具列表。

            回傳：
            - `None`：僅保存工具列表。
            """

            self.tools = tools

        def stream(self, _input, *, stream_mode):
            """先執行 retrieval tool，再回傳固定回答。

            參數：
            - `_input`：agent 輸入。
            - `stream_mode`：要求的 stream modes。

            回傳：
            - `Iterator[tuple[str, object]]`：固定 messages/values 串流片段。
            """

            assert stream_mode == ["messages", "values"]
            captured_tool_result.update(json.loads(self.tools[0]("alpha")))
            return iter(
                [
                    ("messages", ({"content": "這是帶真實檢索的回答。"}, {"tags": []})),
                    ("values", {"messages": [{"role": "assistant", "content": "這是帶真實檢索的回答。"}]}),
                ]
            )

    monkeypatch.setattr("app.chat.agent.runtime.ChatOpenAI", FakeChatOpenAI)
    monkeypatch.setattr("app.chat.agent.runtime.tool", lambda func: func)
    monkeypatch.setattr("app.chat.agent.deep_agents.create_deep_agent", lambda **kwargs: FakeAgent(kwargs.get("tools", [])))

    provider = DeepAgentsChatRuntime(
        model="gpt-5-mini",
        api_key="test-key",
        max_output_tokens=512,
        timeout_seconds=30,
    )
    settings = app_settings.model_copy(
        update={
            "chat_provider": "deepagents",
            "chat_model": "gpt-5-mini",
            "chat_max_output_tokens": 512,
            "chat_timeout_seconds": 30,
            "openai_api_key": "test-key",
        }
    )

    result = provider.run(
        session=db_session,
        principal=CurrentPrincipal(sub="user-reader", groups=("/group/reader",), authenticated=True),
        settings=settings,
        area_id=area.id,
        question="請根據文件回答 alpha",
        writer=emitted_events.append,
    )

    assert result["answer"] == "這是帶真實檢索的回答。"
    assert result["answer_blocks"] == [
        {
            "text": "這是帶真實檢索的回答。",
            "citation_context_indices": [],
            "display_citations": [],
        }
    ]
    assert result["citations"] == [
        {
            "context_index": 0,
            "context_label": "C1",
            "document_id": document.id,
            "document_name": "reader-policy.md",
            "parent_chunk_id": parent.id,
            "child_chunk_ids": [child_one.id, child_two.id],
            "heading": "Reader Policy",
            "structure_kind": "text",
            "start_offset": 0,
            "end_offset": 27,
            "excerpt": "alpha intro\n\nalpha details",
            "source": "hybrid",
            "truncated": False,
            "page_start": None,
            "page_end": None,
            "regions": [],
        }
    ]
    assert result["assembled_contexts"] == [
        {
            "context_index": 0,
            "context_label": "C1",
            "document_id": document.id,
            "document_name": "reader-policy.md",
            "parent_chunk_id": parent.id,
            "child_chunk_ids": [child_one.id, child_two.id],
            "structure_kind": "text",
            "heading": "Reader Policy",
            "excerpt": "alpha intro\n\nalpha details",
            "assembled_text": "alpha intro\n\nalpha details",
            "source": "hybrid",
            "start_offset": 0,
            "end_offset": 27,
            "page_start": None,
            "page_end": None,
            "regions": [],
            "truncated": False,
        }
    ]
    assert result["trace"]["retrieval"]["query"] == "請根據文件回答 alpha"
    assert result["trace"]["assembler"]["kept_chunk_ids"] == [child_one.id, child_two.id]
    assert result["trace"]["agent"]["retrieval_invoked"] is True
    assert result["trace"]["agent"]["contexts_count"] == 1
    assert result["used_knowledge_base"] is True
    assert result["message_artifact"]["assistant_turn_index"] == 0
    assert result["message_artifact"]["used_knowledge_base"] is True
    assert captured_tool_result == {
        "assembled_contexts": [
            {
                "context_label": "C1",
                "context_index": 0,
                "document_name": "reader-policy.md",
                "heading": "Reader Policy",
                "assembled_text": "alpha intro\n\nalpha details",
            }
        ]
    }
    completed_tool_event = [
        event for event in emitted_events if event["type"] == "tool_call" and event["status"] == "completed"
    ][0]
    reference_event = [event for event in emitted_events if event["type"] == "references"][0]
    assert reference_event["references"] == [
        {
            "context_index": 0,
            "context_label": "C1",
            "document_id": document.id,
            "document_name": "reader-policy.md",
            "parent_chunk_id": parent.id,
            "child_chunk_ids": [child_one.id, child_two.id],
            "structure_kind": "text",
            "heading": "Reader Policy",
            "excerpt": "alpha intro\n\nalpha details",
            "assembled_text": "alpha intro\n\nalpha details",
            "source": "hybrid",
            "start_offset": 0,
            "end_offset": 27,
            "page_start": None,
            "page_end": None,
            "regions": [],
            "truncated": False,
        }
    ]
    assert completed_tool_event["output"]["contexts_count"] == 1
    assert completed_tool_event["output"]["citations_count"] == 1
    assert completed_tool_event["output"]["query_type"] == "fact_lookup"
    assert completed_tool_event["output"]["query_type_language"] == "mixed"
    assert completed_tool_event["output"]["query_type_source"] == "fallback"
    assert completed_tool_event["output"]["query_type_confidence"] == 0.0
    assert completed_tool_event["output"]["query_type_matched_rules"] == []
    assert completed_tool_event["output"]["query_type_rule_hits"] == []
    assert completed_tool_event["output"]["query_type_embedding_scores"]
    assert completed_tool_event["output"]["query_type_embedding_margin"] >= 0.0
    assert completed_tool_event["output"]["query_type_fallback_used"] is False
    assert completed_tool_event["output"]["query_type_fallback_reason"] == "llm_fallback_unavailable"
    assert completed_tool_event["output"]["summary_scope"] is None
    assert completed_tool_event["output"]["resolved_document_ids"] == []
    assert completed_tool_event["output"]["document_mention_source"] == "none"
    assert completed_tool_event["output"]["document_mention_confidence"] == 0.0
    assert completed_tool_event["output"]["document_mention_candidates"] == []
    assert completed_tool_event["output"]["selected_profile"] == "fact_lookup_precision_v1"
    assert completed_tool_event["output"]["selection_applied"] is False
    assert completed_tool_event["output"]["selection_strategy"] == "disabled"
    assert completed_tool_event["output"]["selected_document_count"] == 1
    assert completed_tool_event["output"]["selected_parent_count"] == 1
    assert completed_tool_event["output"]["selected_document_ids"] == [document.id]
    assert completed_tool_event["output"]["selected_parent_ids"] == [parent.id]
    assert completed_tool_event["output"]["dropped_by_diversity"] == []
    assert completed_tool_event["output"]["query_focus_applied"] is False
    assert completed_tool_event["output"]["summary_strategy"] is None
    assert completed_tool_event["output"]["summary_strategy_source"] == "not_applicable"
    assert completed_tool_event["output"]["summary_strategy_confidence"] == 0.0
    assert completed_tool_event["output"]["summary_strategy_rule_hits"] == []
    assert completed_tool_event["output"]["summary_strategy_embedding_scores"] == []
    assert completed_tool_event["output"]["summary_strategy_top_label"] is None
    assert completed_tool_event["output"]["summary_strategy_runner_up_label"] is None
    assert completed_tool_event["output"]["summary_strategy_embedding_margin"] == 0.0
    assert completed_tool_event["output"]["summary_strategy_fallback_used"] is False
    assert completed_tool_event["output"]["summary_strategy_fallback_reason"] is None
    assert completed_tool_event["output"]["fallback_reason"] is None
    assert completed_tool_event["output"]["profile_settings"]["vector_top_k"] == settings.retrieval_vector_top_k
    assert completed_tool_event["output"]["profile_settings"]["task_type_embedding_scores"]
    assert completed_tool_event["output"]["contexts"] == [
        {
            "context_index": 0,
            "context_label": "C1",
            "document_id": document.id,
            "document_name": "reader-policy.md",
            "parent_chunk_id": parent.id,
            "child_chunk_ids": [child_one.id, child_two.id],
            "heading": "Reader Policy",
            "structure_kind": "text",
            "source": "hybrid",
            "truncated": False,
            "excerpt": "alpha intro\n\nalpha details",
        }
    ]


def test_deepagents_runtime_wraps_invocation_in_langsmith_tracing_context(monkeypatch) -> None:
    """啟用 LangSmith tracing 時，Deep Agents invocation 應包在 tracing context 內。

    參數：
    - `monkeypatch`：pytest monkeypatch fixture。

    回傳：
    - `None`：僅驗證 tracing context 參數與包覆範圍。
    """

    captured_context: dict[str, object] = {}

    class FakeChatOpenAI:
        """模擬 Deep Agents 使用的 ChatOpenAI。"""

        def __init__(self, **kwargs) -> None:
            """初始化假 LLM。

            參數：
            - `**kwargs`：LLM 初始化參數。

            回傳：
            - `None`：僅保存初始化參數。
            """

            self.kwargs = kwargs

    @contextmanager
    def fake_tracing_context(**kwargs):
        """記錄 tracing context 參數，並模擬 context manager。

        參數：
        - `**kwargs`：傳入 tracing context 的設定。

        回傳：
        - context manager：供測試包覆 Deep Agents invocation。
        """

        captured_context["kwargs"] = kwargs
        captured_context["entered"] = True
        try:
            yield
        finally:
            captured_context["exited"] = True

    class FakeAgent:
        """模擬主 agent。"""

        def stream(self, _input, *, stream_mode):
            """回傳固定串流回答。

            參數：
            - `_input`：agent 輸入。
            - `stream_mode`：要求的 stream modes。

            回傳：
            - `Iterator[tuple[str, object]]`：固定的 messages/values 串流片段。
            """

            assert stream_mode == ["messages", "values"]
            assert captured_context.get("entered") is True
            return iter(
                [
                    ("messages", ({"content": "這是 traced 回答。"}, {"tags": []})),
                    ("values", {"messages": [{"role": "assistant", "content": "這是 traced 回答。"}]}),
                ]
            )

    monkeypatch.setattr("app.chat.agent.runtime.ChatOpenAI", FakeChatOpenAI)
    monkeypatch.setattr("app.chat.agent.runtime.tracing_context", fake_tracing_context)
    monkeypatch.setattr("app.chat.agent.deep_agents.create_deep_agent", lambda **kwargs: FakeAgent())

    provider = DeepAgentsChatRuntime(
        model="gpt-5-mini",
        api_key="test-key",
        max_output_tokens=512,
        timeout_seconds=30,
    )
    settings = AppSettings(
        CHAT_PROVIDER="deepagents",
        CHAT_MODEL="gpt-5-mini",
        CHAT_MAX_OUTPUT_TOKENS=512,
        CHAT_TIMEOUT_SECONDS=30,
        OPENAI_API_KEY="test-key",
        LANGSMITH_TRACING=True,
        LANGSMITH_API_KEY="langsmith-test-key",
        LANGSMITH_PROJECT="deep-agent-rag-stack-test",
    )

    result = provider.run(
        session=None,
        principal=CurrentPrincipal(sub="user-1", groups=("/group/reader",), authenticated=True),
        settings=settings,
        area_id="area-1",
        question="請根據文件回答 reader policy",
    )

    assert result["answer"] == "這是 traced 回答。"
    assert captured_context["kwargs"] == {
        "enabled": True,
        "project_name": "deep-agent-rag-stack-test",
        "tags": [
            "deepagents",
            "langgraph",
            "chat_provider:deepagents",
            "chat_model:gpt-5-mini",
        ],
        "metadata": {
            "area_id": "area-1",
            "principal_sub": "user-1",
            "principal_groups_count": 1,
            "chat_provider": "deepagents",
            "chat_model": "gpt-5-mini",
            "question_length": len("請根據文件回答 reader policy"),
        },
    }
    assert captured_context["exited"] is True


def test_deepagents_runtime_rejects_langsmith_tracing_without_api_key(monkeypatch) -> None:
    """啟用 LangSmith tracing 但未提供 API key 時應提早失敗。

    參數：
    - `monkeypatch`：pytest monkeypatch fixture。

    回傳：
    - `None`：僅驗證缺少必要設定時的錯誤訊息。
    """

    class FakeChatOpenAI:
        """模擬 Deep Agents 使用的 ChatOpenAI。"""

        def __init__(self, **kwargs) -> None:
            """初始化假 LLM。

            參數：
            - `**kwargs`：LLM 初始化參數。

            回傳：
            - `None`：僅保存初始化參數。
            """

            self.kwargs = kwargs

    monkeypatch.setattr("app.chat.agent.runtime.ChatOpenAI", FakeChatOpenAI)

    provider = DeepAgentsChatRuntime(
        model="gpt-5-mini",
        api_key="test-key",
        max_output_tokens=512,
        timeout_seconds=30,
    )
    settings = AppSettings(
        CHAT_PROVIDER="deepagents",
        CHAT_MODEL="gpt-5-mini",
        CHAT_MAX_OUTPUT_TOKENS=512,
        CHAT_TIMEOUT_SECONDS=30,
        OPENAI_API_KEY="test-key",
        LANGSMITH_TRACING=True,
        LANGSMITH_API_KEY="",
    )

    try:
        provider.run(
            session=None,
            principal=CurrentPrincipal(sub="user-1", groups=("/group/reader",), authenticated=True),
            settings=settings,
            area_id="area-1",
            question="請根據文件回答 reader policy",
        )
    except ValueError as exc:
        assert "LANGSMITH_API_KEY" in str(exc)
    else:
        raise AssertionError("預期缺少 LANGSMITH_API_KEY 時應拋出 ValueError。")
