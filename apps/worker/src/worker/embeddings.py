"""Worker 使用的 embedding provider abstraction 與 hosted embedding 實作。"""

from __future__ import annotations

import hashlib
import math
import time
from abc import ABC, abstractmethod

from worker.core.settings import WorkerSettings
from worker.db_types import DEFAULT_EMBEDDING_DIMENSIONS


# OpenRouter 的 OpenAI-compatible embeddings API base URL。
OPENROUTER_EMBEDDINGS_BASE_URL = "https://openrouter.ai/api/v1"


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


class HostedEmbeddingProvider(EmbeddingProvider):
    """使用 OpenAI-compatible embeddings API 的 hosted provider 基底類別。"""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        dimensions: int,
        max_batch_texts: int,
        retry_max_attempts: int,
        retry_base_delay_seconds: float,
        provider_name: str,
        base_url: str | None = None,
        default_headers: dict[str, str] | None = None,
        send_dimensions: bool = False,
        encoding_format: str | None = None,
    ) -> None:
        """初始化 hosted embedding provider。

        參數：
        - `api_key`：對應 provider 的 API key。
        - `model`：要使用的 embedding model 名稱。
        - `dimensions`：預期輸出向量維度。
        - `max_batch_texts`：每批最多送出的文字筆數。
        - `retry_max_attempts`：暫時性失敗時的最大重試次數。
        - `retry_base_delay_seconds`：暫時性失敗的 retry 初始等待秒數。
        - `provider_name`：目前 provider 的顯示名稱。
        - `base_url`：若需改用 OpenAI-compatible endpoint 時的 base URL。
        - `default_headers`：每次 request 都要帶上的額外 headers。
        - `send_dimensions`：是否在 request 中明確帶上 `dimensions`。
        - `encoding_format`：若 provider 需要指定 encoding format 時使用的值。

        回傳：
        - `None`：此建構子只負責建立 client 與保存設定。
        """

        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - 依賴缺失時於執行期明確失敗。
            raise RuntimeError(f"缺少 openai 套件，無法建立 {provider_name} embedding provider。") from exc

        client_kwargs: dict[str, object] = {"api_key": api_key}
        if base_url is not None:
            client_kwargs["base_url"] = base_url
        if default_headers:
            client_kwargs["default_headers"] = default_headers

        self._client = OpenAI(**client_kwargs)
        self._model = model
        self._dimensions = dimensions
        self._max_batch_texts = max(1, max_batch_texts)
        self._retry_max_attempts = max(1, retry_max_attempts)
        self._retry_base_delay_seconds = max(0.0, retry_base_delay_seconds)
        self._provider_name = provider_name
        self._send_dimensions = send_dimensions
        self._encoding_format = encoding_format

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """呼叫 hosted embeddings API 產生 embeddings。

        參數：
        - `texts`：要嵌入的文字清單。

        回傳：
        - `list[list[float]]`：與輸入順序一致的向量結果。
        """

        embeddings: list[list[float]] = []
        for offset in range(0, len(texts), self._max_batch_texts):
            batch_texts = texts[offset : offset + self._max_batch_texts]
            embeddings.extend(self._embed_batch(batch_texts))

        return [
            _normalize_embedding_dimensions(
                embedding=embedding,
                target_dimensions=self._dimensions,
                provider_name=self._provider_name,
            )
            for embedding in embeddings
        ]

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        """以單一 batch 呼叫 embeddings API，必要時自動拆分過大的 request。"""

        try:
            response = self._request_embeddings_with_retry(texts)
        except Exception as exc:
            if _is_hosted_request_too_large_error(exc) and len(texts) > 1:
                midpoint = max(1, len(texts) // 2)
                return self._embed_batch(texts[:midpoint]) + self._embed_batch(texts[midpoint:])
            raise _normalize_hosted_embedding_error(error=exc, provider_name=self._provider_name) from exc

        return [list(item.embedding) for item in response.data]

    def _request_embeddings_with_retry(self, texts: list[str]):
        """在暫時性失敗時以有限次 backoff 重試 embeddings request。"""

        last_error: Exception | None = None
        for attempt in range(1, self._retry_max_attempts + 1):
            try:
                request_kwargs: dict[str, object] = {"model": self._model, "input": texts}
                if self._send_dimensions:
                    request_kwargs["dimensions"] = self._dimensions
                if self._encoding_format is not None:
                    request_kwargs["encoding_format"] = self._encoding_format
                return self._client.embeddings.create(**request_kwargs)
            except Exception as exc:
                last_error = exc
                if _is_hosted_request_too_large_error(exc):
                    raise
                if not _is_transient_hosted_error(exc) or attempt >= self._retry_max_attempts:
                    raise
                sleep_seconds = self._retry_base_delay_seconds * (2 ** (attempt - 1))
                if sleep_seconds > 0:
                    time.sleep(sleep_seconds)

        raise RuntimeError("embedding request retry 流程未回傳結果。") from last_error


class OpenAIEmbeddingProvider(HostedEmbeddingProvider):
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
        - `None`：此建構子只負責轉接到 hosted provider 基底類別。
        """

        super().__init__(
            api_key=api_key,
            model=model,
            dimensions=dimensions,
            max_batch_texts=max_batch_texts,
            retry_max_attempts=retry_max_attempts,
            retry_base_delay_seconds=retry_base_delay_seconds,
            provider_name="OpenAI",
        )


class OpenRouterEmbeddingProvider(HostedEmbeddingProvider):
    """使用 OpenRouter embeddings API 的 provider。"""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        dimensions: int,
        max_batch_texts: int,
        retry_max_attempts: int,
        retry_base_delay_seconds: float,
        http_referer: str | None,
        title: str | None,
    ) -> None:
        """初始化 OpenRouter embedding provider。

        參數：
        - `api_key`：OpenRouter API key。
        - `model`：要使用的 embedding model 名稱。
        - `dimensions`：預期輸出向量維度；會一併送進 OpenRouter request。
        - `max_batch_texts`：每批最多送出的文字筆數。
        - `retry_max_attempts`：暫時性失敗時的最大重試次數。
        - `retry_base_delay_seconds`：暫時性失敗的 retry 初始等待秒數。
        - `http_referer`：可選的 `HTTP-Referer` header。
        - `title`：可選的 `X-OpenRouter-Title` header。

        回傳：
        - `None`：此建構子只負責轉接到 hosted provider 基底類別。
        """

        default_headers: dict[str, str] = {}
        if http_referer:
            default_headers["HTTP-Referer"] = http_referer
        if title:
            default_headers["X-OpenRouter-Title"] = title

        super().__init__(
            api_key=api_key,
            model=model,
            dimensions=dimensions,
            max_batch_texts=max_batch_texts,
            retry_max_attempts=retry_max_attempts,
            retry_base_delay_seconds=retry_base_delay_seconds,
            provider_name="OpenRouter",
            base_url=OPENROUTER_EMBEDDINGS_BASE_URL,
            default_headers=default_headers or None,
            send_dimensions=True,
            encoding_format="float",
        )


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
    if provider == "openrouter":
        if not settings.openrouter_api_key:
            raise ValueError("使用 OpenRouter embeddings 前必須提供 OPENROUTER_API_KEY。")
        return OpenRouterEmbeddingProvider(
            api_key=settings.openrouter_api_key,
            model=settings.embedding_model,
            dimensions=settings.embedding_dimensions,
            max_batch_texts=settings.embedding_max_batch_texts,
            retry_max_attempts=settings.embedding_retry_max_attempts,
            retry_base_delay_seconds=settings.embedding_retry_base_delay_seconds,
            http_referer=settings.openrouter_http_referer,
            title=settings.openrouter_title,
        )
    raise ValueError(f"不支援的 embedding provider：{settings.embedding_provider}")


def _is_transient_hosted_error(error: Exception) -> bool:
    """判定目前 hosted embeddings 例外是否屬於適合重試的暫時性失敗。

    參數：
    - `error`：目前捕捉到的 provider 例外。

    回傳：
    - `bool`：若屬於暫時性錯誤則回傳 `True`。
    """

    status_code = getattr(error, "status_code", None)
    if isinstance(status_code, int) and status_code in {408, 409, 429}:
        return True
    if isinstance(status_code, int) and status_code >= 500:
        return True

    error_name = error.__class__.__name__
    return error_name in {"APIConnectionError", "APITimeoutError", "InternalServerError", "RateLimitError"}


def _is_hosted_request_too_large_error(error: Exception) -> bool:
    """判定目前 hosted embeddings 例外是否為 request size 超限。

    參數：
    - `error`：目前捕捉到的 provider 例外。

    回傳：
    - `bool`：若錯誤訊息對應 request size 超限則回傳 `True`。
    """

    message = str(error).lower()
    return "maximum request size" in message and "tokens per request" in message


def _normalize_hosted_embedding_error(*, error: Exception, provider_name: str) -> ValueError:
    """將 hosted embedding 例外轉為 worker ingest 可受控處理的錯誤。

    參數：
    - `error`：原始 provider 例外。
    - `provider_name`：要寫入錯誤訊息的 provider 名稱。

    回傳：
    - `ValueError`：可供 ingest 任務受控處理的錯誤。
    """

    if _is_hosted_request_too_large_error(error):
        return ValueError(f"{provider_name} embeddings request 超過單次上限；請檢查 batch 切分與 chunk 大小設定。")
    return ValueError(f"{provider_name} embeddings 失敗：{error}")


def _normalize_embedding_dimensions(
    *,
    embedding: list[float],
    target_dimensions: int,
    provider_name: str,
) -> list[float]:
    """將 provider 回傳向量正規化為 schema 固定維度。

    參數：
    - `embedding`：provider 原始回傳向量。
    - `target_dimensions`：目前 schema 固定要求的向量維度。
    - `provider_name`：目前 provider 名稱，供錯誤訊息使用。

    回傳：
    - `list[float]`：可直接寫入 schema 的固定維度向量。
    """

    current_dimensions = len(embedding)
    if current_dimensions == target_dimensions:
        return embedding
    if current_dimensions > target_dimensions:
        raise ValueError(
            f"{provider_name} embeddings 維度超出 schema 上限，預期最多 {target_dimensions}，實際 {current_dimensions}。"
        )
    return embedding + [0.0] * (target_dimensions - current_dimensions)


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
