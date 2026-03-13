"""Chat runtime 與 Deep Agents 路徑測試。"""

from dataclasses import dataclass
from types import SimpleNamespace

from app.auth.verifier import CurrentPrincipal
from app.core.settings import AppSettings
from app.db.models import ChunkStructureKind
from app.chat.agent.runtime import DeepAgentsChatRuntime, DeterministicChatRuntime, build_chat_runtime
from app.services.retrieval_assembler import AssembledContext


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


def test_deepagents_runtime_emits_phase_and_tool_call_custom_events(monkeypatch) -> None:
    """Deep Agents 應透過 writer 發出階段與工具呼叫事件。

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
        "thinking",
        "tool_calling",
        "searching",
        "searching",
        "tool_calling",
        "thinking",
    ]
    assert [event["status"] for event in tool_events] == ["started", "completed"]
    assert tool_events[0]["name"] == "retrieve_area_contexts"
    assert tool_events[0]["input"] == {"area_id": "area-1", "question": "reader policy"}
    assert tool_events[1]["output"] == {
        "contexts_count": 0,
        "citations_count": 0,
        "contexts": [],
    }


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
        document_id: str
        excerpt: str

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
                "document_id": self.document_id,
                "excerpt": self.excerpt,
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
            citations=[FakeCitation(context_index=0, document_id="doc-1", excerpt="這是一段組裝後的內容。")],
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
