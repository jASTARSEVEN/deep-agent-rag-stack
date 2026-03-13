"""API 使用的 embedding provider abstraction 與 OpenAI 實作。"""

from __future__ import annotations

import hashlib
import math
from abc import ABC, abstractmethod

from app.core.settings import AppSettings
from app.db.sql_types import DEFAULT_EMBEDDING_DIMENSIONS


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

    def __init__(self, *, api_key: str, model: str, dimensions: int) -> None:
        """初始化 OpenAI embedding provider。

        參數：
        - `api_key`：OpenAI API key。
        - `model`：要使用的 embedding model 名稱。
        - `dimensions`：預期輸出向量維度。

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

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """呼叫 OpenAI API 產生 embeddings。

        參數：
        - `texts`：要嵌入的文字清單。

        回傳：
        - `list[list[float]]`：與輸入順序一致的向量結果。
        """

        response = self._client.embeddings.create(model=self._model, input=texts)
        embeddings = [list(item.embedding) for item in response.data]
        for embedding in embeddings:
            if len(embedding) != self._dimensions:
                raise ValueError(f"embedding 維度不符，預期 {self._dimensions}，實際 {len(embedding)}。")
        return embeddings


def build_embedding_provider(settings: AppSettings) -> EmbeddingProvider:
    """依照設定建立 embedding provider。

    參數：
    - `settings`：API 執行期設定。

    回傳：
    - `EmbeddingProvider`：可供 retrieval 與 inline ingest 使用的 provider。
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
        )
    raise ValueError(f"不支援的 embedding provider：{settings.embedding_provider}")


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
