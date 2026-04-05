"""API embedding provider 測試。"""

from __future__ import annotations

import sys
from types import SimpleNamespace

from app.core.settings import AppSettings
from app.services.embeddings import OpenAIEmbeddingProvider, build_embedding_provider


def _build_response(batch: list[str], *, dimensions: int):
    """建立與 OpenAI SDK 相容的假 response 物件。

    參數：
    - `batch`：本次回應對應的輸入批次。
    - `dimensions`：每筆向量的維度。

    回傳：
    - 任意：帶有 `data[].embedding` 結構的假 response。
    """

    return SimpleNamespace(
        data=[SimpleNamespace(embedding=[float(index)] * dimensions) for index, _ in enumerate(batch, start=1)]
    )


def test_openai_embedding_provider_zero_pads_shorter_vectors() -> None:
    """OpenAI-compatible provider 回傳較短向量時應自動零補齊到 schema 維度。

    參數：
    - 無

    回傳：
    - `None`：以斷言驗證升維後的相容行為。
    """

    provider = object.__new__(OpenAIEmbeddingProvider)
    provider._client = SimpleNamespace(
        embeddings=SimpleNamespace(create=lambda **request_kwargs: _build_response(list(request_kwargs["input"]), dimensions=3))
    )
    provider._model = "text-embedding-3-small"
    provider._dimensions = 5
    provider._provider_name = "OpenAI"
    provider._send_dimensions = False
    provider._encoding_format = None

    embeddings = provider.embed_texts(["alpha"])

    assert embeddings == [[1.0, 1.0, 1.0, 0.0, 0.0]]


def test_build_embedding_provider_openrouter_uses_openrouter_client_options(monkeypatch) -> None:
    """OpenRouter provider factory 應注入 base URL、headers 與 4096 維 request。

    參數：
    - `monkeypatch`：pytest 提供的 monkeypatch fixture。

    回傳：
    - `None`：以斷言驗證 OpenRouter provider factory 行為。
    """

    openai_init_calls: list[dict[str, object]] = []
    request_calls: list[dict[str, object]] = []

    class FakeOpenAI:
        """模擬 `openai.OpenAI` client。"""

        def __init__(self, **kwargs) -> None:
            """記錄 client 初始化參數。

            參數：
            - `**kwargs`：傳入 `OpenAI(...)` 的建構參數。

            回傳：
            - `None`：此建構子只負責記錄參數。
            """

            openai_init_calls.append(dict(kwargs))
            self.embeddings = SimpleNamespace(create=self.create)

        def create(self, **kwargs):
            """記錄 embeddings request，並回傳 4096 維向量。

            參數：
            - `**kwargs`：傳入 `embeddings.create(...)` 的 request 參數。

            回傳：
            - 任意：模擬 OpenRouter embeddings response。
            """

            request_calls.append(dict(kwargs))
            return _build_response(list(kwargs["input"]), dimensions=4096)

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeOpenAI))

    settings = AppSettings(
        _env_file=None,
        EMBEDDING_PROVIDER="openrouter",
        EMBEDDING_MODEL="qwen/qwen3-embedding-8b",
        EMBEDDING_DIMENSIONS=4096,
        OPENROUTER_API_KEY="openrouter-key",
        OPENROUTER_HTTP_REFERER="https://example.com",
        OPENROUTER_TITLE="Deep Agent",
    )

    provider = build_embedding_provider(settings)
    embeddings = provider.embed_texts(["alpha"])

    assert openai_init_calls == [
        {
            "api_key": "openrouter-key",
            "base_url": "https://openrouter.ai/api/v1",
            "default_headers": {
                "HTTP-Referer": "https://example.com",
                "X-OpenRouter-Title": "Deep Agent",
            },
        }
    ]
    assert request_calls == [
        {
            "model": "qwen/qwen3-embedding-8b",
            "input": ["alpha"],
            "dimensions": 4096,
            "encoding_format": "float",
        }
    ]
    assert len(embeddings[0]) == 4096
