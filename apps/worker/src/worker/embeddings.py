"""Worker 使用的 embedding provider abstraction 與 OpenAI 實作。"""

from __future__ import annotations

import hashlib
import math
import time
from abc import ABC, abstractmethod

from worker.core.settings import WorkerSettings
from worker.db_types import DEFAULT_EMBEDDING_DIMENSIONS


class EmbeddingProvider(ABC):
    """Embedding provider 抽象介面。"""

    @abstractmethod
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """將多筆文字轉成 embeddings。

        參數：
        - `texts`：要嵌入的文字清單。

        回傳：
        - `list[list[float]]`：與輸入順序一致的向量結果。
        """


class DeterministicEmbeddingProvider(EmbeddingProvider):
    """供測試與離線環境使用的穩定假 embedding provider。"""

    def __init__(self, dimensions: int) -> None:
        """初始化 deterministic embedding provider。

        參數：
        - `dimensions`：輸出向量維度。

        回傳：
        - `None`：此建構子只負責保存設定。
        """

        self._dimensions = dimensions

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """將文字轉成可重現的假向量。

        參數：
        - `texts`：要嵌入的文字清單。

        回傳：
        - `list[list[float]]`：可重現且已正規化的向量清單。
        """

        return [_build_deterministic_embedding(text=text, dimensions=self._dimensions) for text in texts]


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """使用 OpenAI embeddings API 的 provider。"""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        dimensions: int,
        max_batch_texts: int,
        retry_max_attempts: int,
        retry_base_delay_seconds: float,
    ) -> None:
        """初始化 OpenAI embedding provider。

        參數：
        - `api_key`：OpenAI API key。
        - `model`：要使用的 embedding model 名稱。
        - `dimensions`：預期輸出向量維度。
        - `max_batch_texts`：每批最多送出的文字筆數。
        - `retry_max_attempts`：暫時性失敗時的最大重試次數。
        - `retry_base_delay_seconds`：暫時性失敗的 retry 初始等待秒數。

        回傳：
        - `None`：此建構子只負責建立 client 與保存設定。
        """

        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - 依賴缺失時於執行期明確失敗。
            raise RuntimeError("缺少 openai 套件，無法建立 OpenAI embedding provider。") from exc

        self._client = OpenAI(api_key=api_key)
        self._model = model
        self._dimensions = dimensions
        self._max_batch_texts = max(1, max_batch_texts)
        self._retry_max_attempts = max(1, retry_max_attempts)
        self._retry_base_delay_seconds = max(0.0, retry_base_delay_seconds)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """呼叫 OpenAI API 產生 embeddings。

        參數：
        - `texts`：要嵌入的文字清單。

        回傳：
        - `list[list[float]]`：與輸入順序一致的向量結果。
        """

        embeddings: list[list[float]] = []
        for offset in range(0, len(texts), self._max_batch_texts):
            batch_texts = texts[offset : offset + self._max_batch_texts]
            embeddings.extend(self._embed_batch(batch_texts))

        for embedding in embeddings:
            if len(embedding) != self._dimensions:
                raise ValueError(f"embedding 維度不符，預期 {self._dimensions}，實際 {len(embedding)}。")
        return embeddings

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        """以單一 batch 呼叫 embeddings API，必要時自動拆分過大的 request。"""

        try:
            response = self._request_embeddings_with_retry(texts)
        except Exception as exc:
            if _is_openai_request_too_large_error(exc) and len(texts) > 1:
                midpoint = max(1, len(texts) // 2)
                return self._embed_batch(texts[:midpoint]) + self._embed_batch(texts[midpoint:])
            raise _normalize_openai_embedding_error(exc) from exc

        return [list(item.embedding) for item in response.data]

    def _request_embeddings_with_retry(self, texts: list[str]):
        """在暫時性失敗時以有限次 backoff 重試 embeddings request。"""

        last_error: Exception | None = None
        for attempt in range(1, self._retry_max_attempts + 1):
            try:
                return self._client.embeddings.create(model=self._model, input=texts)
            except Exception as exc:
                last_error = exc
                if _is_openai_request_too_large_error(exc):
                    raise
                if not _is_transient_openai_error(exc) or attempt >= self._retry_max_attempts:
                    raise
                sleep_seconds = self._retry_base_delay_seconds * (2 ** (attempt - 1))
                if sleep_seconds > 0:
                    time.sleep(sleep_seconds)

        raise RuntimeError("embedding request retry 流程未回傳結果。") from last_error


def build_embedding_provider(settings: WorkerSettings) -> EmbeddingProvider:
    """依照設定建立 embedding provider。

    參數：
    - `settings`：worker 執行期設定。

    回傳：
    - `EmbeddingProvider`：可供 ingest/indexing 使用的 provider。
    """

    if settings.embedding_dimensions != DEFAULT_EMBEDDING_DIMENSIONS:
        raise ValueError(
            f"目前 schema 固定使用 {DEFAULT_EMBEDDING_DIMENSIONS} 維 embedding，"
            f"不支援設定為 {settings.embedding_dimensions}。"
        )

    provider = settings.embedding_provider.strip().lower()
    if provider == "deterministic":
        return DeterministicEmbeddingProvider(dimensions=settings.embedding_dimensions)
    if provider == "openai":
        if not settings.openai_api_key:
            raise ValueError("使用 OpenAI embeddings 前必須提供 OPENAI_API_KEY。")
        return OpenAIEmbeddingProvider(
            api_key=settings.openai_api_key,
            model=settings.embedding_model,
            dimensions=settings.embedding_dimensions,
            max_batch_texts=settings.embedding_max_batch_texts,
            retry_max_attempts=settings.embedding_retry_max_attempts,
            retry_base_delay_seconds=settings.embedding_retry_base_delay_seconds,
        )
    raise ValueError(f"不支援的 embedding provider：{settings.embedding_provider}")


def _is_transient_openai_error(error: Exception) -> bool:
    """判定目前 OpenAI 例外是否屬於適合重試的暫時性失敗。"""

    status_code = getattr(error, "status_code", None)
    if isinstance(status_code, int) and status_code in {408, 409, 429}:
        return True
    if isinstance(status_code, int) and status_code >= 500:
        return True

    error_name = error.__class__.__name__
    return error_name in {"APIConnectionError", "APITimeoutError", "InternalServerError", "RateLimitError"}


def _is_openai_request_too_large_error(error: Exception) -> bool:
    """判定目前 OpenAI 例外是否為 request size 超限。"""

    message = str(error).lower()
    return "maximum request size" in message and "tokens per request" in message


def _normalize_openai_embedding_error(error: Exception) -> ValueError:
    """將 OpenAI embedding 例外轉為 worker ingest 可受控處理的錯誤。"""

    if _is_openai_request_too_large_error(error):
        return ValueError("OpenAI embeddings request 超過單次上限；請檢查 batch 切分與 chunk 大小設定。")
    return ValueError(f"OpenAI embeddings 失敗：{error}")


def _build_deterministic_embedding(*, text: str, dimensions: int) -> list[float]:
    """根據文字內容建立穩定且已正規化的假向量。

    參數：
    - `text`：輸入文字。
    - `dimensions`：輸出向量維度。

    回傳：
    - `list[float]`：可重現的單位向量。
    """

    raw_values: list[float] = []
    counter = 0
    while len(raw_values) < dimensions:
        digest = hashlib.sha256(f"{text}\0{counter}".encode("utf-8")).digest()
        for offset in range(0, len(digest), 4):
            block = digest[offset : offset + 4]
            integer = int.from_bytes(block, byteorder="big", signed=False)
            raw_values.append((integer / 0xFFFFFFFF) * 2.0 - 1.0)
            if len(raw_values) == dimensions:
                break
        counter += 1

    norm = math.sqrt(sum(value * value for value in raw_values)) or 1.0
    return [value / norm for value in raw_values]
