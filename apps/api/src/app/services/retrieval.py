"""Area 範圍內的 internal retrieval service。"""

from __future__ import annotations

import math
from dataclasses import dataclass

from sqlalchemy import Float, Select, func, select, text
from sqlalchemy.orm import Session

from app.auth.verifier import CurrentPrincipal
from app.core.settings import AppSettings
from app.db.models import ChunkStructureKind, ChunkType, Document, DocumentChunk, DocumentStatus
from app.services.access import require_area_access
from app.services.embeddings import build_embedding_provider
from app.services.reranking import RerankInputDocument, RerankScore, build_rerank_provider


@dataclass(slots=True)
class RetrievalCandidate:
    """內部 retrieval candidate 結構。"""

    # candidate 所屬文件識別碼。
    document_id: str
    # candidate 對應的 child chunk 識別碼。
    chunk_id: str
    # candidate 對應的 parent chunk 識別碼。
    parent_chunk_id: str | None
    # candidate 的內容結構型別。
    structure_kind: ChunkStructureKind
    # candidate 所屬段落標題。
    heading: str | None
    # candidate 內容文字。
    content: str
    # candidate 在 normalized 文字中的起始 offset。
    start_offset: int
    # candidate 在 normalized 文字中的結束 offset。
    end_offset: int
    # candidate 來源，可能為 vector、fts 或 hybrid。
    source: str
    # vector recall 排名；未命中時為空值。
    vector_rank: int | None
    # FTS recall 排名；未命中時為空值。
    fts_rank: int | None
    # RRF 排名。
    rrf_rank: int
    # RRF 合併後分數。
    rrf_score: float
    # rerank 排名；未套用或未命中時為空值。
    rerank_rank: int | None
    # rerank 分數；未套用或未命中時為空值。
    rerank_score: float | None
    # 此 candidate 是否成功套用 rerank 結果。
    rerank_applied: bool


@dataclass(slots=True)
class RetrievalTraceEntry:
    """單一 retrieval candidate 的 trace metadata。"""

    # candidate 對應的 chunk 識別碼。
    chunk_id: str
    # candidate 來源。
    source: str
    # vector recall 排名。
    vector_rank: int | None
    # FTS recall 排名。
    fts_rank: int | None
    # RRF 排名。
    rrf_rank: int
    # RRF 分數。
    rrf_score: float
    # rerank 排名。
    rerank_rank: int | None
    # rerank 分數。
    rerank_score: float | None
    # 是否成功套用 rerank。
    rerank_applied: bool


@dataclass(slots=True)
class RetrievalTrace:
    """單次 retrieval 的 trace metadata。"""

    # 使用者查詢文字。
    query: str
    # vector recall top-k。
    vector_top_k: int
    # FTS recall top-k。
    fts_top_k: int
    # RRF 後最多保留的 candidates 數量。
    max_candidates: int
    # 實際送進 rerank 的前幾名 candidates。
    rerank_top_n: int
    # 此次 retrieval 的 candidate traces。
    candidates: list[RetrievalTraceEntry]


@dataclass(slots=True)
class RetrievalResult:
    """internal retrieval service 的回傳結構。"""

    # retrieval 後的最終 candidates。
    candidates: list[RetrievalCandidate]
    # 供後續 chat / citations 使用的 trace metadata。
    trace: RetrievalTrace


@dataclass(slots=True)
class RankedChunkMatch:
    """合併 vector / FTS recall 與 rerank 前使用的中間結構。"""

    # 命中的 chunk ORM 物件。
    chunk: DocumentChunk
    # vector recall 排名；未命中時為空值。
    vector_rank: int | None = None
    # FTS recall 排名；未命中時為空值。
    fts_rank: int | None = None
    # RRF 排名。
    rrf_rank: int | None = None
    # RRF 合併後分數。
    rrf_score: float = 0.0
    # rerank 排名；未套用或未命中時為空值。
    rerank_rank: int | None = None
    # rerank 分數；未套用或未命中時為空值。
    rerank_score: float | None = None
    # 此 candidate 是否成功套用 rerank。
    rerank_applied: bool = False


def retrieve_area_candidates(
    *,
    session: Session,
    principal: CurrentPrincipal,
    settings: AppSettings,
    area_id: str,
    query: str,
) -> RetrievalResult:
    """在指定 area 內取得 ready-only 的 hybrid recall 與 rerank candidates。

    參數：
    - `session`：目前資料庫 session。
    - `principal`：目前已驗證使用者。
    - `settings`：API 執行期設定。
    - `area_id`：要檢索的 area 識別碼。
    - `query`：使用者查詢文字。

    回傳：
    - `RetrievalResult`：已完成 SQL gate、vector recall、FTS recall、RRF 與 rerank 的結果與 trace。
    """

    require_area_access(session=session, principal=principal, area_id=area_id)
    vector_matches = _run_vector_recall(session=session, settings=settings, area_id=area_id, query=query)
    fts_matches = _run_fts_recall(session=session, settings=settings, area_id=area_id, query=query)
    merged_matches = _merge_ranked_matches(
        vector_matches=vector_matches,
        fts_matches=fts_matches,
        rrf_k=settings.retrieval_rrf_k,
        max_candidates=settings.retrieval_max_candidates,
    )
    reranked_matches = _apply_rerank(matches=merged_matches, query=query, settings=settings)
    candidates = [_build_retrieval_candidate(match) for match in reranked_matches]
    return RetrievalResult(
        candidates=candidates,
        trace=RetrievalTrace(
            query=query,
            vector_top_k=settings.retrieval_vector_top_k,
            fts_top_k=settings.retrieval_fts_top_k,
            max_candidates=settings.retrieval_max_candidates,
            rerank_top_n=min(settings.rerank_top_n, len(reranked_matches)),
            candidates=[
                RetrievalTraceEntry(
                    chunk_id=candidate.chunk_id,
                    source=candidate.source,
                    vector_rank=candidate.vector_rank,
                    fts_rank=candidate.fts_rank,
                    rrf_rank=candidate.rrf_rank,
                    rrf_score=candidate.rrf_score,
                    rerank_rank=candidate.rerank_rank,
                    rerank_score=candidate.rerank_score,
                    rerank_applied=candidate.rerank_applied,
                )
                for candidate in candidates
            ],
        ),
    )


def build_postgres_fts_recall_statement(*, settings: AppSettings, area_id: str, query: str) -> Select:
    """建立 PostgreSQL 專用的 FTS recall statement。

    參數：
    - `settings`：API 執行期設定。
    - `area_id`：要檢索的 area 識別碼。
    - `query`：使用者查詢文字。

    回傳：
    - `Select`：可直接給 PostgreSQL 執行的 FTS recall query。
    """

    ts_query = build_postgres_fts_query(settings=settings, query=query)
    rank_expr = func.ts_rank_cd(DocumentChunk.fts_document, ts_query).label("fts_score")
    return (
        select(DocumentChunk, rank_expr)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(
            Document.area_id == area_id,
            Document.status == DocumentStatus.ready,
            DocumentChunk.chunk_type == ChunkType.child,
            DocumentChunk.fts_document.is_not(None),
            DocumentChunk.fts_document.op("@@")(ts_query),
        )
        .order_by(rank_expr.desc(), DocumentChunk.position.asc())
        .limit(settings.retrieval_fts_top_k)
    )


def build_postgres_fts_query(*, settings: AppSettings, query: str):
    """建立 PostgreSQL 專用的 `websearch_to_tsquery` expression。

    參數：
    - `settings`：API 執行期設定。
    - `query`：使用者查詢文字。

    回傳：
    - SQLAlchemy expression：對應 PostgreSQL `websearch_to_tsquery()` 的查詢 expression。
    """

    return func.websearch_to_tsquery(settings.text_search_config, query)


def _run_vector_recall(*, session: Session, settings: AppSettings, area_id: str, query: str) -> list[RankedChunkMatch]:
    """執行 vector recall，並回傳帶 rank 的 chunk 結果。

    參數：
    - `session`：目前資料庫 session。
    - `settings`：API 執行期設定。
    - `area_id`：要檢索的 area 識別碼。
    - `query`：使用者查詢文字。

    回傳：
    - `list[RankedChunkMatch]`：依向量相似度排序後的結果。
    """

    dialect_name = session.get_bind().dialect.name
    provider = build_embedding_provider(settings)
    query_embedding = provider.embed_texts([query])[0]

    if dialect_name == "postgresql":
        _configure_postgres_hnsw_search(session=session, settings=settings)
        distance_expr = DocumentChunk.embedding.op("<=>")(query_embedding).cast(Float).label("vector_distance")
        rows = session.execute(
            select(DocumentChunk, distance_expr)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(
                Document.area_id == area_id,
                Document.status == DocumentStatus.ready,
                DocumentChunk.chunk_type == ChunkType.child,
                DocumentChunk.embedding.is_not(None),
            )
            .order_by(distance_expr.asc(), DocumentChunk.position.asc())
            .limit(settings.retrieval_vector_top_k)
        ).all()
        return [RankedChunkMatch(chunk=chunk, vector_rank=index) for index, (chunk, _) in enumerate(rows, start=1)]

    chunks = _load_sql_gated_ready_child_chunks(session=session, area_id=area_id)
    scored_chunks = sorted(
        (
            (_cosine_distance(query_embedding, chunk.embedding), chunk)
            for chunk in chunks
            if chunk.embedding is not None
        ),
        key=lambda item: (item[0], item[1].position),
    )[: settings.retrieval_vector_top_k]
    return [RankedChunkMatch(chunk=chunk, vector_rank=index) for index, (_, chunk) in enumerate(scored_chunks, start=1)]


def _configure_postgres_hnsw_search(*, session: Session, settings: AppSettings) -> None:
    """設定 PostgreSQL HNSW 查詢期參數。

    參數：
    - `session`：目前資料庫 session。
    - `settings`：API 執行期設定。

    回傳：
    - `None`：僅在目前 transaction 內設定 HNSW 搜尋參數。

    前置條件：
    - 目前資料庫需為 PostgreSQL，且 `pgvector >= 0.8.0` 支援 `hnsw.iterative_scan`。

    風險：
    - 若日後 pgvector 版本降級，這些參數可能失效，需在 infra 升降版時同步驗證。
    """

    session.execute(text("SET LOCAL hnsw.iterative_scan = 'strict_order'"))
    session.execute(text("SET LOCAL hnsw.ef_search = :ef_search"), {"ef_search": settings.retrieval_hnsw_ef_search})


def _run_fts_recall(*, session: Session, settings: AppSettings, area_id: str, query: str) -> list[RankedChunkMatch]:
    """執行 FTS recall，並回傳帶 rank 的 chunk 結果。

    參數：
    - `session`：目前資料庫 session。
    - `settings`：API 執行期設定。
    - `area_id`：要檢索的 area 識別碼。
    - `query`：使用者查詢文字。

    回傳：
    - `list[RankedChunkMatch]`：依 FTS 分數排序後的結果。
    """

    dialect_name = session.get_bind().dialect.name
    if dialect_name == "postgresql":
        rows = session.execute(build_postgres_fts_recall_statement(settings=settings, area_id=area_id, query=query)).all()
        return [RankedChunkMatch(chunk=chunk, fts_rank=index) for index, (chunk, _) in enumerate(rows, start=1)]

    chunks = _load_sql_gated_ready_child_chunks(session=session, area_id=area_id)
    scored_chunks = sorted(
        (
            (_sqlite_fts_score(query=query, content=chunk.content), chunk)
            for chunk in chunks
            if chunk.fts_document
        ),
        key=lambda item: (-item[0], item[1].position),
    )
    scored_chunks = [item for item in scored_chunks if item[0] > 0][: settings.retrieval_fts_top_k]
    return [RankedChunkMatch(chunk=chunk, fts_rank=index) for index, (_, chunk) in enumerate(scored_chunks, start=1)]


def _load_sql_gated_ready_child_chunks(*, session: Session, area_id: str) -> list[DocumentChunk]:
    """在 SQLite fallback 路徑載入已套 SQL gate 的 ready child chunks。

    參數：
    - `session`：目前資料庫 session。
    - `area_id`：要檢索的 area 識別碼。

    回傳：
    - `list[DocumentChunk]`：指定 area 內 ready-only 的 child chunks。
    """

    return session.scalars(
        select(DocumentChunk)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(
            Document.area_id == area_id,
            Document.status == DocumentStatus.ready,
            DocumentChunk.chunk_type == ChunkType.child,
        )
        .order_by(DocumentChunk.position.asc())
    ).all()


def _merge_ranked_matches(
    *,
    vector_matches: list[RankedChunkMatch],
    fts_matches: list[RankedChunkMatch],
    rrf_k: int,
    max_candidates: int,
) -> list[RankedChunkMatch]:
    """將 vector 與 FTS recall 結果以 RRF 合併。

    參數：
    - `vector_matches`：vector recall 結果。
    - `fts_matches`：FTS recall 結果。
    - `rrf_k`：RRF 使用的平滑常數。
    - `max_candidates`：最多保留的候選數量。

    回傳：
    - `list[RankedChunkMatch]`：依 RRF 分數排序後的結果。
    """

    merged_by_chunk_id: dict[str, RankedChunkMatch] = {}

    for match in vector_matches:
        current = merged_by_chunk_id.setdefault(match.chunk.id, RankedChunkMatch(chunk=match.chunk))
        current.vector_rank = match.vector_rank
        current.rrf_score += 1.0 / (rrf_k + (match.vector_rank or 0))

    for match in fts_matches:
        current = merged_by_chunk_id.setdefault(match.chunk.id, RankedChunkMatch(chunk=match.chunk))
        current.fts_rank = match.fts_rank
        current.rrf_score += 1.0 / (rrf_k + (match.fts_rank or 0))

    merged_matches = sorted(
        merged_by_chunk_id.values(),
        key=lambda item: (-item.rrf_score, item.chunk.position),
    )[:max_candidates]
    for index, match in enumerate(merged_matches, start=1):
        match.rrf_rank = index
    return merged_matches


def _apply_rerank(*, matches: list[RankedChunkMatch], query: str, settings: AppSettings) -> list[RankedChunkMatch]:
    """將 RRF 後的 candidates 再送入 rerank，並保留 fail-open fallback。

    參數：
    - `matches`：RRF 後的候選結果。
    - `query`：使用者查詢文字。
    - `settings`：API 執行期設定。

    回傳：
    - `list[RankedChunkMatch]`：套用 rerank 或 fallback 後的最終排序結果。

    風險：
    - rerank 僅可重排已通過 SQL gate 的結果，不得擴大可見資料集合。
    """

    rerank_limit = min(settings.rerank_top_n, len(matches))
    if rerank_limit <= 0:
        return matches

    rerank_inputs = [
        RerankInputDocument(
            candidate_id=match.chunk.id,
            text=_build_rerank_document_text(content=match.chunk.content, max_chars=settings.rerank_max_chars_per_doc),
        )
        for match in matches[:rerank_limit]
    ]

    try:
        rerank_provider = build_rerank_provider(settings)
        rerank_scores = rerank_provider.rerank(query=query, documents=rerank_inputs, top_n=rerank_limit)
    except Exception:
        return matches

    rerank_score_by_chunk_id = {item.candidate_id: item for item in rerank_scores}
    top_matches = matches[:rerank_limit]
    for match in top_matches:
        score = rerank_score_by_chunk_id.get(match.chunk.id)
        if score is None:
            match.rerank_applied = False
            match.rerank_score = None
            match.rerank_rank = None
            continue
        match.rerank_applied = True
        match.rerank_score = score.score

    reranked_top_matches = sorted(
        top_matches,
        key=lambda item: (
            0 if item.rerank_applied else 1,
            -(item.rerank_score if item.rerank_score is not None else float("-inf")),
            item.rrf_rank or 0,
        ),
    )
    for index, match in enumerate(reranked_top_matches, start=1):
        if match.rerank_applied:
            match.rerank_rank = index
    return reranked_top_matches + matches[rerank_limit:]


def _build_rerank_document_text(*, content: str, max_chars: int) -> str:
    """建立送進 rerank 的文件文字。

    參數：
    - `content`：child chunk 原始內容。
    - `max_chars`：每筆 rerank 文件允許的最大字元數。

    回傳：
    - `str`：已套成本上限的 rerank 文件文字。
    """

    normalized_content = content.strip()
    if len(normalized_content) <= max_chars:
        return normalized_content
    return normalized_content[:max_chars]


def _build_retrieval_candidate(match: RankedChunkMatch) -> RetrievalCandidate:
    """將中間結構轉為對外使用的 retrieval candidate。

    參數：
    - `match`：合併與 rerank 後的 chunk match。

    回傳：
    - `RetrievalCandidate`：供 internal caller 使用的 candidate。
    """

    return RetrievalCandidate(
        document_id=match.chunk.document_id,
        chunk_id=match.chunk.id,
        parent_chunk_id=match.chunk.parent_chunk_id,
        structure_kind=match.chunk.structure_kind,
        heading=match.chunk.heading,
        content=match.chunk.content,
        start_offset=match.chunk.start_offset,
        end_offset=match.chunk.end_offset,
        source=_resolve_candidate_source(match),
        vector_rank=match.vector_rank,
        fts_rank=match.fts_rank,
        rrf_rank=match.rrf_rank or 0,
        rrf_score=match.rrf_score,
        rerank_rank=match.rerank_rank,
        rerank_score=match.rerank_score,
        rerank_applied=match.rerank_applied,
    )


def _resolve_candidate_source(match: RankedChunkMatch) -> str:
    """根據 rank 來源決定 candidate source 欄位。

    參數：
    - `match`：合併後的 chunk match。

    回傳：
    - `str`：`vector`、`fts` 或 `hybrid`。
    """

    if match.vector_rank is not None and match.fts_rank is not None:
        return "hybrid"
    if match.vector_rank is not None:
        return "vector"
    return "fts"


def _cosine_distance(left: list[float], right: list[float] | None) -> float:
    """計算兩個向量的 cosine distance。

    參數：
    - `left`：左側向量。
    - `right`：右側向量。

    回傳：
    - `float`：cosine distance，數值越小越相近。
    """

    if right is None:
        return 1.0
    dot_product = sum(left_value * right_value for left_value, right_value in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left)) or 1.0
    right_norm = math.sqrt(sum(value * value for value in right)) or 1.0
    cosine_similarity = dot_product / (left_norm * right_norm)
    return 1.0 - cosine_similarity


def _sqlite_fts_score(*, query: str, content: str) -> int:
    """SQLite 測試 fallback 的簡化 FTS 分數。

    參數：
    - `query`：使用者查詢文字。
    - `content`：chunk 內容。

    回傳：
    - `int`：命中的 token 次數總和。
    """

    tokens = [token.strip().lower() for token in query.split() if token.strip()]
    if not tokens:
        tokens = [query.strip().lower()]
    lowered_content = content.lower()
    return sum(lowered_content.count(token) for token in tokens if token)
