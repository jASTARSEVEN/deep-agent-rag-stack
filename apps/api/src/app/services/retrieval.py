"""Area 範圍內的 internal retrieval service。"""

from __future__ import annotations

import logging
import math
from collections import OrderedDict
from dataclasses import dataclass

from sqlalchemy import Integer, String, bindparam, select, text
from sqlalchemy.orm import Session

from app.auth.verifier import CurrentPrincipal
from app.core.settings import AppSettings
from app.db.models import ChunkStructureKind, ChunkType, Document, DocumentChunk, DocumentStatus
from app.db.sql_types import DEFAULT_EMBEDDING_DIMENSIONS, Vector
from app.services.access import require_area_access
from app.services.embeddings import build_embedding_provider
from app.services.retrieval_query import (
    QueryFocusPlan,
    build_query_focus_plan_from_settings,
    extract_query_tokens,
    get_query_focus_boost_terms,
)
from app.services.reranking import RerankInputDocument, build_rerank_provider
from app.services.retrieval_text import build_evidence_synopsis, build_rerank_document_text, merge_chunk_contents

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class RetrievalCandidate:
    """內部 retrieval candidate 結構。"""

    document_id: str
    chunk_id: str
    parent_chunk_id: str | None
    structure_kind: ChunkStructureKind
    heading: str | None
    content: str
    start_offset: int
    end_offset: int
    source: str
    vector_rank: int | None
    fts_rank: int | None
    rrf_rank: int
    rrf_score: float
    rerank_rank: int | None
    rerank_score: float | None
    rerank_applied: bool
    rerank_fallback_reason: str | None


@dataclass(slots=True)
class RetrievalTraceEntry:
    """單一 retrieval candidate 的 trace metadata。"""

    chunk_id: str
    source: str
    vector_rank: int | None
    fts_rank: int | None
    rrf_rank: int
    rrf_score: float
    rerank_rank: int | None
    rerank_score: float | None
    rerank_applied: bool
    rerank_fallback_reason: str | None


@dataclass(slots=True)
class RetrievalTrace:
    """單次 retrieval 的 trace metadata。"""

    query: str
    vector_top_k: int
    fts_top_k: int
    max_candidates: int
    rerank_top_n: int
    candidates: list[RetrievalTraceEntry]
    query_focus_applied: bool = False
    query_focus_language: str = "en"
    query_focus_intents: list[str] | None = None
    query_focus_slots: dict[str, str] | None = None
    focus_query: str = ""
    rerank_query: str = ""


@dataclass(slots=True)
class RetrievalResult:
    """Internal retrieval service 的回傳結構。"""

    candidates: list[RetrievalCandidate]
    trace: RetrievalTrace


@dataclass(slots=True)
class RankedChunkMatch:
    """合併與 rerank 前使用的中間結構。"""

    chunk: DocumentChunk
    vector_rank: int | None = None
    fts_rank: int | None = None
    rrf_rank: int | None = None
    rrf_score: float = 0.0
    rerank_rank: int | None = None
    rerank_score: float | None = None
    rerank_applied: bool = False
    rerank_fallback_reason: str | None = None


@dataclass(slots=True)
class _RerankParentGroup:
    """rerank 前依 parent 聚合的候選群組。"""

    candidate_id: str
    heading: str | None
    content: str
    matches: list[RankedChunkMatch]
    order: int


def _build_match_chunks_rpc_statement():
    """建立具備 PostgreSQL 明確 bind type 的 `match_chunks` RPC statement。

    參數：
    - 無

    回傳：
    - `TextClause`：已綁定 vector/text/varchar/int 型別的 SQL statement。
    """

    if Vector is None:  # pragma: no cover - PostgreSQL 正式路徑應固定安裝 pgvector。
        raise RuntimeError("PostgreSQL retrieval 路徑需要 `pgvector` SQLAlchemy 型別支援。")

    return text(
        "SELECT * FROM match_chunks(:query_embedding, :query_text, :area_id, :vector_top_k, :fts_top_k)"
    ).bindparams(
        bindparam("query_embedding", type_=Vector(DEFAULT_EMBEDDING_DIMENSIONS)),
        bindparam("query_text", type_=String()),
        bindparam("area_id", type_=String()),
        bindparam("vector_top_k", type_=Integer()),
        bindparam("fts_top_k", type_=Integer()),
    )


def retrieve_area_candidates(
    *,
    session: Session,
    principal: CurrentPrincipal,
    settings: AppSettings,
    area_id: str,
    query: str,
) -> RetrievalResult:
    """在指定 area 內取得 hybrid recall、Python RRF 與 rerank candidates。

    參數：
    - `session`：目前資料庫 session。
    - `principal`：目前已驗證使用者。
    - `settings`：API 執行期設定。
    - `area_id`：要檢索的 area 識別碼。
    - `query`：使用者查詢文字。

    回傳：
    - `RetrievalResult`：已完成 recall、RRF、ranking hook 與 rerank 的候選集合。
    """

    require_area_access(session=session, principal=principal, area_id=area_id)

    query_focus_plan = build_query_focus_plan_from_settings(settings=settings, query=query)
    recalled_matches = _recall_ranked_candidates(
        session=session,
        settings=settings,
        area_id=area_id,
        query=query_focus_plan.focus_query if query_focus_plan.applied else query,
    )
    rrf_matches = _apply_python_rrf(matches=recalled_matches, settings=settings)
    ranked_matches = _apply_ranking_policy(
        matches=rrf_matches,
        query=query,
        settings=settings,
        focus_query=query_focus_plan.focus_query if query_focus_plan.applied else None,
        query_focus_plan=query_focus_plan,
    )
    reranked_matches = _apply_rerank(
        matches=ranked_matches,
        query=query_focus_plan.rerank_query if query_focus_plan.applied else query,
        settings=settings,
    )
    candidates = [_build_retrieval_candidate(match) for match in reranked_matches]

    return RetrievalResult(
        candidates=candidates,
        trace=RetrievalTrace(
            query=query,
            vector_top_k=settings.retrieval_vector_top_k,
            fts_top_k=settings.retrieval_fts_top_k,
            max_candidates=settings.retrieval_max_candidates,
            rerank_top_n=min(settings.rerank_top_n, len(reranked_matches)),
            query_focus_applied=query_focus_plan.applied,
            query_focus_language=query_focus_plan.language,
            query_focus_intents=list(query_focus_plan.intents),
            query_focus_slots=dict(query_focus_plan.slots),
            focus_query=query_focus_plan.focus_query,
            rerank_query=query_focus_plan.rerank_query,
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
                    rerank_fallback_reason=candidate.rerank_fallback_reason,
                )
                for candidate in candidates
            ],
        ),
    )


def _recall_ranked_candidates(
    *,
    session: Session,
    settings: AppSettings,
    area_id: str,
    query: str,
) -> list[RankedChunkMatch]:
    """依資料庫方言取得已套用 area/ready 邊界的 ranked candidates。"""

    dialect_name = session.get_bind().dialect.name
    if dialect_name == "postgresql":
        return _run_postgres_candidate_generation(
            session=session,
            settings=settings,
            area_id=area_id,
            query=query,
        )
    return _run_sqlite_candidate_generation(
        session=session,
        settings=settings,
        area_id=area_id,
        query=query,
    )


def _run_postgres_candidate_generation(
    *,
    session: Session,
    settings: AppSettings,
    area_id: str,
    query: str,
) -> list[RankedChunkMatch]:
    """透過 PostgreSQL RPC 取得 recall 候選與其排序輸入。

    參數：
    - `session`：目前資料庫 session。
    - `settings`：API 執行期設定。
    - `area_id`：受 SQL gate 保護的 area 識別碼。
    - `query`：使用者查詢文字。

    回傳：
    - `list[RankedChunkMatch]`：已帶回 vector / FTS rank 的 recall 候選。
    """

    provider = build_embedding_provider(settings)
    query_embedding = provider.embed_texts([query])[0]
    rpc_stmt = _build_match_chunks_rpc_statement()
    rows = session.execute(
        rpc_stmt,
        {
            "query_embedding": query_embedding,
            "query_text": query,
            "area_id": area_id,
            "vector_top_k": settings.retrieval_vector_top_k,
            "fts_top_k": settings.retrieval_fts_top_k,
        },
    ).all()

    matches: list[RankedChunkMatch] = []
    for row in rows:
        chunk = session.get(DocumentChunk, str(row.id))
        if chunk is None:
            continue
        matches.append(
            RankedChunkMatch(
                chunk=chunk,
                vector_rank=row.vector_rank,
                fts_rank=row.fts_rank,
            )
        )
    return matches


def _run_sqlite_candidate_generation(
    *,
    session: Session,
    settings: AppSettings,
    area_id: str,
    query: str,
) -> list[RankedChunkMatch]:
    """SQLite 本機測試專用的 candidate generation 路徑。"""

    provider = build_embedding_provider(settings)
    query_embedding = provider.embed_texts([query])[0]
    chunks = session.scalars(
        select(DocumentChunk)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(
            Document.area_id == area_id,
            Document.status == DocumentStatus.ready,
            DocumentChunk.chunk_type == ChunkType.child,
        )
        .order_by(DocumentChunk.position.asc())
    ).all()

    merged_by_chunk_id: dict[str, RankedChunkMatch] = {}

    vector_scored = sorted(
        (
            (_cosine_distance(query_embedding, chunk.embedding), chunk)
            for chunk in chunks
            if chunk.embedding is not None
        ),
        key=lambda item: (item[0], item[1].position),
    )[: settings.retrieval_vector_top_k]
    for index, (_, chunk) in enumerate(vector_scored, start=1):
        current = merged_by_chunk_id.setdefault(chunk.id, RankedChunkMatch(chunk=chunk))
        current.vector_rank = index

    fts_scored = sorted(
        (
            (_sqlite_fts_score(query=query, content=chunk.content), chunk)
            for chunk in chunks
            if chunk.content
        ),
        key=lambda item: (-item[0], item[1].position),
    )
    for index, (_, chunk) in enumerate((item for item in fts_scored if item[0] > 0), start=1):
        if index > settings.retrieval_fts_top_k:
            break
        current = merged_by_chunk_id.setdefault(chunk.id, RankedChunkMatch(chunk=chunk))
        current.fts_rank = index

    return list(merged_by_chunk_id.values())


def _apply_python_rrf(*, matches: list[RankedChunkMatch], settings: AppSettings) -> list[RankedChunkMatch]:
    """在 Python 層對 recall 候選套用 RRF。"""

    for match in matches:
        match.rrf_score = _compute_rrf_score(match=match, rrf_k=settings.retrieval_rrf_k)

    merged_matches = sorted(
        matches,
        key=lambda item: (
            -item.rrf_score,
            _best_rank(item),
            item.chunk.position,
            item.chunk.id,
        ),
    )[: settings.retrieval_max_candidates]

    for index, match in enumerate(merged_matches, start=1):
        match.rrf_rank = index
    return merged_matches


def _apply_ranking_policy(
    *,
    matches: list[RankedChunkMatch],
    query: str,
    settings: AppSettings,
    focus_query: str | None = None,
    query_focus_plan: QueryFocusPlan | None = None,
) -> list[RankedChunkMatch]:
    """套用最小 ranking policy，降低目錄噪音並保留商品名命中優勢。

    參數：
    - `matches`：已完成 Python RRF 的候選。
    - `query`：使用者查詢文字。
    - `settings`：API 執行期設定。
    - `focus_query`：若 query focus 已套用，供 token-based ranking 使用的 focus query。
    - `query_focus_plan`：本次 retrieval 的 query focus plan；未套用時可為空值。

    回傳：
    - `list[RankedChunkMatch]`：已套用最小 ranking rules 的候選排序。
    """
    del settings
    token_query = focus_query or query
    query_tokens = _extract_query_tokens(token_query)
    intent_boost_terms = (
        get_query_focus_boost_terms(
            intents=query_focus_plan.intents,
            language=query_focus_plan.language,
        )
        if query_focus_plan is not None and query_focus_plan.applied
        else ()
    )
    scored_matches = [
        (
            _ranking_policy_score(
                match=match,
                query=query,
                query_tokens=query_tokens,
                intent_boost_terms=intent_boost_terms,
            ),
            index,
            match,
        )
        for index, match in enumerate(matches)
    ]
    scored_matches.sort(
        key=lambda item: (
            -item[0],
            item[2].rrf_rank or 1_000_000,
            _best_rank(item[2]),
            item[1],
        )
    )
    return [item[2] for item in scored_matches]


def _extract_query_tokens(query: str) -> list[str]:
    """抽出 ranking policy 使用的 query tokens。"""

    return extract_query_tokens(query=query)


def _ranking_policy_score(
    *,
    match: RankedChunkMatch,
    query: str,
    query_tokens: list[str],
    intent_boost_terms: tuple[str, ...] = (),
) -> float:
    """計算最小 ranking policy 分數。"""

    score = match.rrf_score
    heading = (match.chunk.heading or "").strip().lower()
    content = (match.chunk.content or "").strip().lower()
    normalized_query = query.strip().lower()

    if normalized_query and normalized_query in content:
        score += 0.08
    if normalized_query and normalized_query in heading:
        score += 0.12

    if query_tokens:
        heading_token_hits = sum(1 for token in query_tokens if token and token in heading)
        content_token_hits = sum(1 for token in query_tokens if token and token in content)
        score += min(heading_token_hits, 4) * 0.025
        score += min(content_token_hits, 6) * 0.008

    if intent_boost_terms:
        normalized_boost_terms = [term.strip().lower() for term in intent_boost_terms if term.strip()]
        boost_heading_hits = sum(1 for term in normalized_boost_terms if term in heading)
        boost_content_hits = sum(1 for term in normalized_boost_terms if term in content)
        score += min(boost_heading_hits, 3) * 0.02
        score += min(boost_content_hits, 3) * 0.006

    if _is_table_of_contents_chunk(match):
        score -= 0.12
        if normalized_query and normalized_query in heading:
            score += 0.03

    return score


def _is_table_of_contents_chunk(match: RankedChunkMatch) -> bool:
    """判斷候選是否屬於帶有 leader dots 的目錄類噪音。"""

    content = (match.chunk.content or "").strip().lower()
    if "................................................................" in content:
        return True
    return False


def _compute_rrf_score(*, match: RankedChunkMatch, rrf_k: int) -> float:
    """依 vector/FTS rank 計算單一候選的 RRF 分數。"""

    score = 0.0
    if match.vector_rank is not None:
        score += 1.0 / (rrf_k + match.vector_rank)
    if match.fts_rank is not None:
        score += 1.0 / (rrf_k + match.fts_rank)
    return score


def _best_rank(match: RankedChunkMatch) -> int:
    """回傳候選可用 rank 中最好的那個，用於 tie-break。"""

    available_ranks = [rank for rank in (match.vector_rank, match.fts_rank) if rank is not None]
    return min(available_ranks) if available_ranks else 1_000_000


def _cosine_distance(left: list[float], right: list[float] | None) -> float:
    """計算兩個向量的 cosine distance。"""

    if right is None:
        return 1.0
    dot_product = sum(left_value * right_value for left_value, right_value in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left)) or 1.0
    right_norm = math.sqrt(sum(value * value for value in right)) or 1.0
    cosine_similarity = dot_product / (left_norm * right_norm)
    return 1.0 - cosine_similarity


def _sqlite_fts_score(*, query: str, content: str) -> int:
    """SQLite 測試 fallback 的簡化 FTS 分數。"""

    tokens = [token.strip().lower() for token in query.split() if token.strip()]
    if not tokens:
        tokens = [query.strip().lower()]
    lowered_content = content.lower()
    return sum(lowered_content.count(token) for token in tokens if token)


def _apply_rerank(*, matches: list[RankedChunkMatch], query: str, settings: AppSettings) -> list[RankedChunkMatch]:
    """將 RRF 後的 candidates 再送入 rerank，並保留 fail-open fallback。"""

    rerank_groups = _group_matches_for_parent_rerank(matches=matches)
    rerank_limit = min(settings.rerank_top_n, len(rerank_groups))
    if rerank_limit <= 0:
        return matches

    rerank_inputs = [
        RerankInputDocument(
            candidate_id=group.candidate_id,
            text=build_rerank_document_text(
                heading=group.heading,
                content=group.content,
                max_chars=settings.rerank_max_chars_per_doc,
                evidence_synopsis=(
                    build_evidence_synopsis(
                        heading=group.heading,
                        content=group.content,
                        variant=settings.retrieval_evidence_synopsis_variant,
                    )
                    if settings.retrieval_evidence_synopsis_enabled
                    else None
                ),
            ),
        )
        for group in rerank_groups[:rerank_limit]
    ]

    try:
        rerank_provider = build_rerank_provider(settings)
        rerank_scores = rerank_provider.rerank(query=query, documents=rerank_inputs, top_n=rerank_limit)
    except Exception:
        LOGGER.warning(
            "Retrieval rerank provider failed; falling back to RRF order.",
            extra={
                "query": query,
                "rerank_provider": settings.rerank_provider,
                "rerank_model": settings.rerank_model,
                "candidate_count": len(rerank_inputs),
            },
            exc_info=True,
        )
        for group in rerank_groups[:rerank_limit]:
            for match in group.matches:
                match.rerank_applied = False
                match.rerank_rank = None
                match.rerank_score = None
                match.rerank_fallback_reason = "provider_error"
        return matches

    rerank_score_by_group_id = {item.candidate_id: item for item in rerank_scores}
    top_groups = rerank_groups[:rerank_limit]
    for group in top_groups:
        score = rerank_score_by_group_id.get(group.candidate_id)
        for match in group.matches:
            if score is None:
                match.rerank_applied = False
                match.rerank_score = None
                match.rerank_rank = None
                match.rerank_fallback_reason = "missing_score"
                continue
            match.rerank_applied = True
            match.rerank_score = score.score
            match.rerank_fallback_reason = None

    reranked_top_groups = sorted(
        top_groups,
        key=lambda item: (
            0 if any(match.rerank_applied for match in item.matches) else 1,
            -(
                max(match.rerank_score for match in item.matches if match.rerank_score is not None)
                if any(match.rerank_score is not None for match in item.matches)
                else float("-inf")
            ),
            item.order,
        ),
    )
    for index, group in enumerate(reranked_top_groups, start=1):
        for match in group.matches:
            if match.rerank_applied:
                match.rerank_rank = index

    ordered_matches: list[RankedChunkMatch] = []
    for group in reranked_top_groups + rerank_groups[rerank_limit:]:
        ordered_matches.extend(group.matches)
    return ordered_matches


def _group_matches_for_parent_rerank(*, matches: list[RankedChunkMatch]) -> list[_RerankParentGroup]:
    """依 parent 邊界將 child candidates 聚合為 rerank 群組。

    參數：
    - `matches`：已完成 RRF 的 child-level 候選。

    回傳：
    - `list[_RerankParentGroup]`：供 parent-level rerank 使用的群組列表。
    """

    grouped_matches: OrderedDict[tuple[str, str, ChunkStructureKind], list[RankedChunkMatch]] = OrderedDict()
    for match in matches:
        group_parent_id = match.chunk.parent_chunk_id or match.chunk.id
        group_key = (str(match.chunk.document_id), str(group_parent_id), match.chunk.structure_kind)
        grouped_matches.setdefault(group_key, []).append(match)

    rerank_groups: list[_RerankParentGroup] = []
    for order, records in enumerate(grouped_matches.values()):
        sorted_records = sorted(
            records,
            key=lambda item: (
                item.chunk.child_index if item.chunk.child_index is not None else -1,
                item.chunk.position,
                item.chunk.id,
            ),
        )
        heading = next((match.chunk.heading for match in sorted_records if match.chunk.heading), None)
        content = merge_chunk_contents(
            structure_kind=sorted_records[0].chunk.structure_kind,
            contents=[match.chunk.content for match in sorted_records],
        )
        rerank_groups.append(
            _RerankParentGroup(
                candidate_id=_build_parent_rerank_candidate_id(matches=sorted_records),
                heading=heading,
                content=content,
                matches=sorted_records,
                order=order,
            )
        )
    return rerank_groups


def _build_parent_rerank_candidate_id(*, matches: list[RankedChunkMatch]) -> str:
    """建立 parent-level rerank 群組識別碼。

    參數：
    - `matches`：屬於同一 parent 群組的 child 候選。

    回傳：
    - `str`：穩定且可映射回 child 候選群組的識別碼。
    """

    first_match = matches[0]
    parent_or_chunk_id = first_match.chunk.parent_chunk_id or first_match.chunk.id
    return (
        f"{first_match.chunk.document_id}:"
        f"{parent_or_chunk_id}:"
        f"{first_match.chunk.structure_kind.value}"
    )


def _build_retrieval_candidate(match: RankedChunkMatch) -> RetrievalCandidate:
    """將中間結構轉為對外使用的 retrieval candidate。"""

    return RetrievalCandidate(
        document_id=str(match.chunk.document_id),
        chunk_id=str(match.chunk.id),
        parent_chunk_id=str(match.chunk.parent_chunk_id) if match.chunk.parent_chunk_id is not None else None,
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
        rerank_fallback_reason=match.rerank_fallback_reason,
    )


def _resolve_candidate_source(match: RankedChunkMatch) -> str:
    """根據 rank 來源決定 candidate source 欄位。"""

    if match.vector_rank is not None and match.fts_rank is not None:
        return "hybrid"
    if match.vector_rank is not None:
        return "vector"
    return "fts"
