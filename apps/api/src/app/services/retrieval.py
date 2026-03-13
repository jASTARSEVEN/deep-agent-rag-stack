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
    # RRF 合併後分數。
    rrf_score: float


@dataclass(slots=True)
class RankedChunkMatch:
    """合併 vector / FTS recall 前使用的中間結構。"""

    # 命中的 chunk ORM 物件。
    chunk: DocumentChunk
    # vector recall 排名；未命中時為空值。
    vector_rank: int | None = None
    # FTS recall 排名；未命中時為空值。
    fts_rank: int | None = None
    # RRF 合併後分數。
    rrf_score: float = 0.0


def retrieve_area_candidates(
    *,
    session: Session,
    principal: CurrentPrincipal,
    settings: AppSettings,
    area_id: str,
    query: str,
) -> list[RetrievalCandidate]:
    """在指定 area 內取得 ready-only 的 hybrid recall candidates。

    參數：
    - `session`：目前資料庫 session。
    - `principal`：目前已驗證使用者。
    - `settings`：API 執行期設定。
    - `area_id`：要檢索的 area 識別碼。
    - `query`：使用者查詢文字。

    回傳：
    - `list[RetrievalCandidate]`：已完成 SQL gate、vector recall、FTS recall 與 RRF merge 的 candidates。
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
    return [
        RetrievalCandidate(
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
            rrf_score=match.rrf_score,
        )
        for match in merged_matches
    ]


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

    return sorted(
        merged_by_chunk_id.values(),
        key=lambda item: (-item.rrf_score, item.chunk.position),
    )[:max_candidates]


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
