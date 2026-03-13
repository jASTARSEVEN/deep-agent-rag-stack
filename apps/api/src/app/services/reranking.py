"""API 使用的 rerank provider abstraction 與 Cohere / deterministic 實作。"""

from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.settings import AppSettings


@dataclass(slots=True)
class RerankInputDocument:
    """rerank provider 使用的輸入文件結構。"""

    # 對應 retrieval candidate 的識別碼。
    candidate_id: str
    # 傳給 rerank provider 的文字內容。
    text: str


@dataclass(slots=True)
class RerankScore:
    """rerank provider 回傳的單筆分數結果。"""

    # 對應 retrieval candidate 的識別碼。
    candidate_id: str
    # rerank relevance score。
    score: float


class RerankProvider(ABC):
    """Rerank provider 抽象介面。"""

    @abstractmethod
    def rerank(self, *, query: str, documents: list[RerankInputDocument], top_n: int) -> list[RerankScore]:
        """依照 query 對文件清單做 rerank。

        參數：
        - `query`：使用者查詢文字。
        - `documents`：要送進 rerank 的候選文件。
        - `top_n`：最多回傳前幾名結果。

        回傳：
        - `list[RerankScore]`：依 provider 排序後的分數結果。
        """


class DeterministicRerankProvider(RerankProvider):
    """供測試與離線環境使用的穩定 rerank provider。"""

    def rerank(self, *, query: str, documents: list[RerankInputDocument], top_n: int) -> list[RerankScore]:
        """以 query token overlap 與穩定雜湊建立可重現的 rerank 結果。

        參數：
        - `query`：使用者查詢文字。
        - `documents`：要送進 rerank 的候選文件。
        - `top_n`：最多回傳前幾名結果。

        回傳：
        - `list[RerankScore]`：依 deterministic 分數排序後的結果。
        """

        query_tokens = [token.strip().lower() for token in query.split() if token.strip()]
        scored_documents: list[RerankScore] = []
        for document in documents:
            normalized_text = document.text.lower()
            overlap_score = float(sum(normalized_text.count(token) for token in query_tokens))
            tie_breaker = _build_stable_fraction(seed=f"{query}\0{document.candidate_id}\0{document.text}")
            scored_documents.append(RerankScore(candidate_id=document.candidate_id, score=overlap_score + tie_breaker))

        return sorted(
            scored_documents,
            key=lambda item: (-item.score, item.candidate_id),
        )[:top_n]


class CohereRerankProvider(RerankProvider):
    """使用 Cohere Rerank v4 HTTP API 的 provider。"""

    _endpoint = "https://api.cohere.com/v2/rerank"

    def __init__(self, *, api_key: str, model: str) -> None:
        """初始化 Cohere rerank provider。

        參數：
        - `api_key`：Cohere API key。
        - `model`：要使用的 rerank model 名稱。

        回傳：
        - `None`：此建構子只負責保存設定。
        """

        self._api_key = api_key
        self._model = model

    def rerank(self, *, query: str, documents: list[RerankInputDocument], top_n: int) -> list[RerankScore]:
        """呼叫 Cohere HTTP API 產生 rerank 結果。

        參數：
        - `query`：使用者查詢文字。
        - `documents`：要送進 rerank 的候選文件。
        - `top_n`：最多回傳前幾名結果。

        回傳：
        - `list[RerankScore]`：依 Cohere relevance score 排序後的結果。

        風險：
        - 此方法會呼叫外部 API，timeout、5xx 或網路中斷需由上層以 fail-open fallback 處理。
        """

        payload = json.dumps(
            {
                "model": self._model,
                "query": query,
                "documents": [document.text for document in documents],
                "top_n": top_n,
            }
        ).encode("utf-8")
        request = Request(
            self._endpoint,
            data=payload,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )

        try:
            with urlopen(request, timeout=10) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError) as exc:
            raise RuntimeError("Cohere rerank API 呼叫失敗。") from exc

        raw_results = response_payload.get("results", [])
        rerank_scores: list[RerankScore] = []
        for item in raw_results:
            index = item.get("index")
            relevance_score = item.get("relevance_score")
            if not isinstance(index, int) or not isinstance(relevance_score, (int, float)):
                continue
            if index < 0 or index >= len(documents):
                continue
            rerank_scores.append(RerankScore(candidate_id=documents[index].candidate_id, score=float(relevance_score)))
        return rerank_scores


def build_rerank_provider(settings: AppSettings) -> RerankProvider:
    """依照設定建立 rerank provider。

    參數：
    - `settings`：API 執行期設定。

    回傳：
    - `RerankProvider`：可供 internal retrieval 使用的 rerank provider。
    """

    provider = settings.rerank_provider.strip().lower()
    if provider == "deterministic":
        return DeterministicRerankProvider()
    if provider == "cohere":
        if not settings.cohere_api_key:
            raise ValueError("使用 Cohere rerank 前必須提供 COHERE_API_KEY。")
        return CohereRerankProvider(api_key=settings.cohere_api_key, model=settings.rerank_model)
    raise ValueError(f"不支援的 rerank provider：{settings.rerank_provider}")


def _build_stable_fraction(*, seed: str) -> float:
    """根據 seed 建立穩定且可重現的小數分數。

    參數：
    - `seed`：用來產生穩定分數的字串。

    回傳：
    - `float`：介於 0 與 1 之間的小數。
    """

    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    integer = int.from_bytes(digest[:8], byteorder="big", signed=False)
    return integer / float(2**64 - 1)
