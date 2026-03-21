"""Embedding provider 行為測試。"""

from types import SimpleNamespace

from worker.embeddings import OpenAIEmbeddingProvider


class _FakeTooLargeError(Exception):
    """模擬 OpenAI request size 超限錯誤。"""

    status_code = 400


class _FakeRateLimitError(Exception):
    """模擬 OpenAI rate limit 暫時性錯誤。"""

    status_code = 429


class _FakeEmbeddingsClient:
    """模擬 OpenAI embeddings.create 行為。"""

    def __init__(self, responder) -> None:
        """建立測試用 embeddings client。

        參數：
        - `responder`：根據輸入批次決定回傳或拋錯的 callable。

        回傳：
        - `None`：此建構子只負責保存 responder。
        """

        self._responder = responder
        self.calls: list[list[str]] = []
        self.embeddings = SimpleNamespace(create=self.create)

    def create(self, *, model: str, input: list[str]):
        """記錄呼叫批次，並回傳 responder 指定結果。

        參數：
        - `model`：本次呼叫的 model 名稱。
        - `input`：本次送出的文字批次。

        回傳：
        - 任意：模擬 OpenAI embeddings API response。
        """

        del model
        batch = list(input)
        self.calls.append(batch)
        return self._responder(batch)


def _build_response(batch: list[str], *, dimensions: int):
    """建立與 OpenAI SDK 相容的假 response 物件。"""

    return SimpleNamespace(
        data=[SimpleNamespace(embedding=[float(index)] * dimensions) for index, _ in enumerate(batch, start=1)]
    )


def _build_provider(*, client, dimensions: int = 4, max_batch_texts: int = 64) -> OpenAIEmbeddingProvider:
    """建立不經 OpenAI 真實 client 初始化的 provider 測試實例。"""

    provider = object.__new__(OpenAIEmbeddingProvider)
    provider._client = client
    provider._model = "text-embedding-3-small"
    provider._dimensions = dimensions
    provider._max_batch_texts = max_batch_texts
    provider._retry_max_attempts = 3
    provider._retry_base_delay_seconds = 0.0
    return provider


def test_openai_embedding_provider_splits_oversized_batch_recursively() -> None:
    """當單批請求超過上限時，provider 應自動拆小後重送。"""

    def responder(batch: list[str]):
        if len(batch) > 1:
            raise _FakeTooLargeError("Invalid 'input': maximum request size is 300000 tokens per request.")
        return _build_response(batch, dimensions=4)

    client = _FakeEmbeddingsClient(responder)
    provider = _build_provider(client=client, max_batch_texts=8)

    embeddings = provider.embed_texts(["alpha", "beta", "gamma"])

    assert client.calls == [
        ["alpha", "beta", "gamma"],
        ["alpha"],
        ["beta", "gamma"],
        ["beta"],
        ["gamma"],
    ]
    assert embeddings == [
        [1.0, 1.0, 1.0, 1.0],
        [1.0, 1.0, 1.0, 1.0],
        [1.0, 1.0, 1.0, 1.0],
    ]


def test_openai_embedding_provider_retries_transient_error() -> None:
    """暫時性 OpenAI 失敗應在 provider 內重試後成功。"""

    attempts = {"count": 0}

    def responder(batch: list[str]):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise _FakeRateLimitError("rate limit")
        return _build_response(batch, dimensions=4)

    client = _FakeEmbeddingsClient(responder)
    provider = _build_provider(client=client, max_batch_texts=8)

    embeddings = provider.embed_texts(["alpha"])

    assert attempts["count"] == 2
    assert client.calls == [["alpha"], ["alpha"]]
    assert embeddings == [[1.0, 1.0, 1.0, 1.0]]
