"""Area 範圍內的 internal retrieval service。"""

from __future__ import annotations

import logging
import math
from collections import OrderedDict
from dataclasses import dataclass

from sqlalchemy import Integer, String, bindparam, select, text
from sqlalchemy.dialects.postgresql import ARRAY as PG_ARRAY
from sqlalchemy.orm import Session

from app.auth.verifier import CurrentPrincipal
from app.core.settings import AppSettings
from app.db.models import (
    ChunkStructureKind,
    ChunkType,
    Document,
    DocumentChunk,
    DocumentChunkEvidenceUnit,
    DocumentChunkEvidenceUnitChildSource,
    DocumentStatus,
    EvaluationQueryType,
)
from app.db.sql_types import DEFAULT_EMBEDDING_DIMENSIONS, Vector
from app.services.access import require_area_access
from app.services.embeddings import build_embedding_provider
from app.services.retrieval_query import (
    QueryFocusPlan,
    build_query_focus_plan_from_settings,
    extract_query_tokens,
    get_query_focus_boost_terms,
)
from app.services.retrieval_routing import build_query_routing_decision
from app.services.retrieval_routing import RetrievalStrategy
from app.services.retrieval_selection import apply_scope_aware_selection
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
    evidence_rank: int | None = None
    evidence_rrf_score: float = 0.0
    evidence_unit_id: str | None = None
    evidence_type: str | None = None
    path_quality_score: float | None = None
    cluster_strategy: str | None = None


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
    evidence_rank: int | None = None
    evidence_rrf_score: float = 0.0
    evidence_unit_id: str | None = None
    evidence_type: str | None = None
    path_quality_score: float | None = None
    cluster_strategy: str | None = None


@dataclass(slots=True)
class DocumentRecallTraceEntry:
    """單一 document recall candidate 的 trace metadata。"""

    document_id: str
    file_name: str
    vector_rank: int | None
    fts_rank: int | None
    rrf_rank: int
    rrf_score: float


@dataclass(slots=True)
class DocumentRecallTrace:
    """第一階段 document recall 的 trace metadata。"""

    applied: bool
    strategy: str
    top_k: int
    selected_document_ids: list[str]
    dropped_document_ids: list[str]
    candidates: list[DocumentRecallTraceEntry]


@dataclass(slots=True)
class SectionRecallTraceEntry:
    """單一 section recall candidate 的 trace metadata。"""

    parent_chunk_id: str
    document_id: str
    heading: str | None
    heading_path: str | None
    section_path_text: str | None
    vector_rank: int | None
    fts_rank: int | None
    rrf_rank: int
    rrf_score: float


@dataclass(slots=True)
class SectionRecallTrace:
    """section recall trace metadata。"""

    applied: bool
    strategy: str
    top_k: int
    selected_parent_ids: list[str]
    dropped_parent_ids: list[str]
    candidates: list[SectionRecallTraceEntry]


@dataclass(slots=True)
class RetrievalTrace:
    """單次 retrieval 的 trace metadata。"""

    query: str
    vector_top_k: int
    fts_top_k: int
    max_candidates: int
    rerank_top_n: int
    candidates: list[RetrievalTraceEntry]
    query_type: str = EvaluationQueryType.fact_lookup.value
    query_type_language: str = "en"
    query_type_source: str = "fallback"
    query_type_confidence: float = 0.0
    query_type_matched_rules: list[str] | None = None
    query_type_rule_hits: list[dict[str, object]] | None = None
    query_type_embedding_scores: list[dict[str, object]] | None = None
    query_type_top_label: str | None = None
    query_type_runner_up_label: str | None = None
    query_type_embedding_margin: float = 0.0
    query_type_fallback_used: bool = False
    query_type_fallback_reason: str | None = None
    summary_scope: str | None = None
    summary_strategy: str | None = None
    summary_strategy_source: str = "not_applicable"
    summary_strategy_confidence: float = 0.0
    summary_strategy_rule_hits: list[dict[str, object]] | None = None
    summary_strategy_embedding_scores: list[dict[str, object]] | None = None
    summary_strategy_top_label: str | None = None
    summary_strategy_runner_up_label: str | None = None
    summary_strategy_embedding_margin: float = 0.0
    summary_strategy_fallback_used: bool = False
    summary_strategy_fallback_reason: str | None = None
    resolved_document_ids: list[str] | None = None
    document_mention_source: str = "none"
    document_mention_confidence: float = 0.0
    document_mention_candidates: list[dict[str, object]] | None = None
    selected_profile: str = ""
    profile_settings: dict[str, object] | None = None
    selection_applied: bool = False
    selection_strategy: str = "disabled"
    selected_document_count: int = 0
    selected_parent_count: int = 0
    selected_document_ids: list[str] | None = None
    selected_parent_ids: list[str] | None = None
    dropped_by_diversity: list[dict[str, object]] | None = None
    query_focus_applied: bool = False
    query_focus_language: str = "en"
    query_focus_intents: list[str] | None = None
    query_focus_slots: dict[str, str] | None = None
    query_focus_variant: str = ""
    query_focus_rule_family: str = ""
    evidence_synopsis_variant: str = ""
    evidence_units_enabled: bool = False
    evidence_build_strategy_used: str | None = None
    evidence_recall_hits: list[dict[str, object]] | None = None
    mapped_child_ids: list[str] | None = None
    path_quality_score: float | None = None
    cluster_strategy: str | None = None
    evidence_fallback_reason: str | None = None
    focus_query: str = ""
    rerank_query: str = ""
    fallback_reason: str | None = None


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
    evidence_rank: int | None = None
    evidence_rrf_score: float = 0.0
    evidence_unit_id: str | None = None
    evidence_type: str | None = None
    path_quality_score: float | None = None
    cluster_strategy: str | None = None


@dataclass(slots=True)
class _EvidenceRecallMatch:
    """單一 evidence recall 命中的中間結構。"""

    evidence_unit: DocumentChunkEvidenceUnit
    mapped_child_chunk_ids: tuple[str, ...]
    vector_rank: int | None = None
    fts_rank: int | None = None
    rrf_rank: int | None = None
    rrf_score: float = 0.0


@dataclass(slots=True)
class EvidenceRecallMergeResult:
    """Evidence recall merge 後的結果。"""

    matches: list[RankedChunkMatch]
    hits: list[_EvidenceRecallMatch]
    build_strategy_used: str | None
    mapped_child_ids: list[str]
    fallback_reason: str | None


@dataclass(slots=True)
class _RerankParentGroup:
    """rerank 前依 parent 聚合的候選群組。"""

    candidate_id: str
    heading: str | None
    content: str
    matches: list[RankedChunkMatch]
    order: int


@dataclass(slots=True)
class _DocumentRecallMatch:
    """document-level recall 使用的中間結構。"""

    document: Document
    vector_rank: int | None = None
    fts_rank: int | None = None
    rrf_rank: int | None = None
    rrf_score: float = 0.0


@dataclass(slots=True)
class DocumentRecallResult:
    """第一階段 document recall 的選文件結果。"""

    selected_document_ids: tuple[str, ...]
    trace: DocumentRecallTrace


@dataclass(slots=True)
class _SectionRecallMatch:
    """section-level recall 使用的中間結構。"""

    parent_chunk: DocumentChunk
    vector_rank: int | None = None
    fts_rank: int | None = None
    rrf_rank: int | None = None
    rrf_score: float = 0.0


@dataclass(slots=True)
class SectionRecallResult:
    """section-level recall 結果。"""

    selected_parent_ids: tuple[str, ...]
    trace: SectionRecallTrace


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
        "SELECT * FROM match_chunks(:query_embedding, :query_text, :area_id, :vector_top_k, :fts_top_k, :allowed_document_ids, :allowed_parent_chunk_ids)"
    ).bindparams(
        bindparam("query_embedding", type_=Vector(DEFAULT_EMBEDDING_DIMENSIONS)),
        bindparam("query_text", type_=String()),
        bindparam("area_id", type_=String()),
        bindparam("vector_top_k", type_=Integer()),
        bindparam("fts_top_k", type_=Integer()),
        bindparam("allowed_document_ids", type_=PG_ARRAY(String(36))),
        bindparam("allowed_parent_chunk_ids", type_=PG_ARRAY(String(36))),
    )


def _build_document_recall_statement():
    """建立 PostgreSQL document synopsis recall 的 SQL statement。

    參數：
    - 無

    回傳：
    - `TextClause`：已綁定 vector/text/varchar/int 型別的 SQL statement。
    """

    if Vector is None:  # pragma: no cover - PostgreSQL 正式路徑應固定安裝 pgvector。
        raise RuntimeError("PostgreSQL document recall 路徑需要 `pgvector` SQLAlchemy 型別支援。")

    return text(
        """
        WITH vector_matches AS (
            SELECT
                d.id,
                ROW_NUMBER() OVER (ORDER BY d.synopsis_embedding <=> :query_embedding, d.id) :: INT AS rank
            FROM documents d
            WHERE d.area_id = :area_id
              AND d.status = 'ready'
              AND d.synopsis_embedding IS NOT NULL
            ORDER BY d.synopsis_embedding <=> :query_embedding, d.id
            LIMIT :vector_top_k
        ),
        fts_matches AS (
            SELECT
                d.id,
                ROW_NUMBER() OVER (
                    ORDER BY pgroonga_score(d.tableoid, d.ctid) DESC, d.id
                ) :: INT AS rank,
                pgroonga_score(d.tableoid, d.ctid) :: FLOAT AS score
            FROM documents d
            WHERE d.area_id = :area_id
              AND d.status = 'ready'
              AND d.synopsis_text IS NOT NULL
              AND d.synopsis_text &@~ :query_text
            ORDER BY pgroonga_score(d.tableoid, d.ctid) DESC, d.id
            LIMIT :fts_top_k
        ),
        candidate_ids AS (
            SELECT id FROM vector_matches
            UNION
            SELECT id FROM fts_matches
        )
        SELECT
            d.id,
            d.file_name,
            vm.rank AS vector_rank,
            fm.rank AS fts_rank,
            fm.score AS fts_score
        FROM candidate_ids c
        JOIN documents d ON d.id = c.id
        LEFT JOIN vector_matches vm ON vm.id = d.id
        LEFT JOIN fts_matches fm ON fm.id = d.id
        ORDER BY
            COALESCE(vm.rank, 2147483647),
            COALESCE(fm.rank, 2147483647),
            d.id
        """
    ).bindparams(
        bindparam("query_embedding", type_=Vector(DEFAULT_EMBEDDING_DIMENSIONS)),
        bindparam("query_text", type_=String()),
        bindparam("area_id", type_=String()),
        bindparam("vector_top_k", type_=Integer()),
        bindparam("fts_top_k", type_=Integer()),
    )


def _build_section_recall_statement():
    """建立 PostgreSQL section synopsis recall 的 SQL statement。"""

    if Vector is None:  # pragma: no cover - PostgreSQL 正式路徑應固定安裝 pgvector。
        raise RuntimeError("PostgreSQL section recall 路徑需要 `pgvector` SQLAlchemy 型別支援。")

    return text(
        """
        WITH vector_matches AS (
            SELECT
                dc.id,
                ROW_NUMBER() OVER (ORDER BY dc.section_synopsis_embedding <=> :query_embedding, dc.id) :: INT AS rank
            FROM document_chunks dc
            JOIN documents d ON d.id = dc.document_id
            WHERE d.area_id = :area_id
              AND d.status = 'ready'
              AND dc.chunk_type = 'parent'
              AND dc.section_synopsis_embedding IS NOT NULL
              AND (
                :allowed_document_ids IS NULL
                OR d.id = ANY(:allowed_document_ids)
              )
            ORDER BY dc.section_synopsis_embedding <=> :query_embedding, dc.id
            LIMIT :vector_top_k
        ),
        fts_matches AS (
            SELECT
                dc.id,
                ROW_NUMBER() OVER (
                    ORDER BY pgroonga_score(dc.tableoid, dc.ctid) DESC, dc.id
                ) :: INT AS rank,
                pgroonga_score(dc.tableoid, dc.ctid) :: FLOAT AS score
            FROM document_chunks dc
            JOIN documents d ON d.id = dc.document_id
            WHERE d.area_id = :area_id
              AND d.status = 'ready'
              AND dc.chunk_type = 'parent'
              AND dc.section_synopsis_text IS NOT NULL
              AND dc.section_synopsis_text &@~ :query_text
              AND (
                :allowed_document_ids IS NULL
                OR d.id = ANY(:allowed_document_ids)
              )
            ORDER BY pgroonga_score(dc.tableoid, dc.ctid) DESC, dc.id
            LIMIT :fts_top_k
        ),
        candidate_ids AS (
            SELECT id FROM vector_matches
            UNION
            SELECT id FROM fts_matches
        )
        SELECT
            dc.id,
            dc.document_id,
            dc.heading,
            dc.heading_path,
            dc.section_path_text,
            vm.rank AS vector_rank,
            fm.rank AS fts_rank,
            fm.score AS fts_score
        FROM candidate_ids c
        JOIN document_chunks dc ON dc.id = c.id
        LEFT JOIN vector_matches vm ON vm.id = dc.id
        LEFT JOIN fts_matches fm ON fm.id = dc.id
        ORDER BY
            COALESCE(vm.rank, 2147483647),
            COALESCE(fm.rank, 2147483647),
            dc.id
        """
    ).bindparams(
        bindparam("query_embedding", type_=Vector(DEFAULT_EMBEDDING_DIMENSIONS)),
        bindparam("query_text", type_=String()),
        bindparam("area_id", type_=String()),
        bindparam("vector_top_k", type_=Integer()),
        bindparam("fts_top_k", type_=Integer()),
        bindparam("allowed_document_ids", type_=PG_ARRAY(String(36))),
    )


def _build_evidence_recall_statement():
    """建立 PostgreSQL evidence recall 的 SQL statement。

    參數：
    - 無

    回傳：
    - `TextClause`：已綁定 vector/text/varchar/int 型別的 SQL statement。
    """

    if Vector is None:  # pragma: no cover - PostgreSQL 正式路徑應固定安裝 pgvector。
        raise RuntimeError("PostgreSQL evidence recall 路徑需要 `pgvector` SQLAlchemy 型別支援。")

    return text(
        """
        WITH vector_matches AS (
            SELECT
                eu.id,
                ROW_NUMBER() OVER (ORDER BY eu.evidence_embedding <=> :query_embedding, eu.id) :: INT AS rank
            FROM document_chunk_evidence_units eu
            JOIN documents d ON d.id = eu.document_id
            WHERE d.area_id = :area_id
              AND d.status = 'ready'
              AND eu.evidence_embedding IS NOT NULL
              AND (
                :allowed_document_ids IS NULL
                OR d.id = ANY(:allowed_document_ids)
              )
            ORDER BY eu.evidence_embedding <=> :query_embedding, eu.id
            LIMIT :vector_top_k
        ),
        fts_matches AS (
            SELECT
                eu.id,
                ROW_NUMBER() OVER (
                    ORDER BY pgroonga_score(eu.tableoid, eu.ctid) DESC, eu.id
                ) :: INT AS rank,
                pgroonga_score(eu.tableoid, eu.ctid) :: FLOAT AS score
            FROM document_chunk_evidence_units eu
            JOIN documents d ON d.id = eu.document_id
            WHERE d.area_id = :area_id
              AND d.status = 'ready'
              AND (
                COALESCE(eu.heading_path, '') || ' ' || COALESCE(eu.section_path_text, '') || ' ' || eu.evidence_text
              ) &@~ :query_text
              AND (
                :allowed_document_ids IS NULL
                OR d.id = ANY(:allowed_document_ids)
              )
            ORDER BY pgroonga_score(eu.tableoid, eu.ctid) DESC, eu.id
            LIMIT :fts_top_k
        ),
        candidate_ids AS (
            SELECT id FROM vector_matches
            UNION
            SELECT id FROM fts_matches
        )
        SELECT
            eu.id,
            eu.document_id,
            eu.primary_parent_chunk_id,
            eu.evidence_type,
            eu.path_quality_score,
            eu.cluster_strategy,
            vm.rank AS vector_rank,
            fm.rank AS fts_rank
        FROM candidate_ids c
        JOIN document_chunk_evidence_units eu ON eu.id = c.id
        LEFT JOIN vector_matches vm ON vm.id = eu.id
        LEFT JOIN fts_matches fm ON fm.id = eu.id
        ORDER BY
            COALESCE(vm.rank, 2147483647),
            COALESCE(fm.rank, 2147483647),
            eu.id
        """
    ).bindparams(
        bindparam("query_embedding", type_=Vector(DEFAULT_EMBEDDING_DIMENSIONS)),
        bindparam("query_text", type_=String()),
        bindparam("area_id", type_=String()),
        bindparam("vector_top_k", type_=Integer()),
        bindparam("fts_top_k", type_=Integer()),
        bindparam("allowed_document_ids", type_=PG_ARRAY(String(36))),
    )


def retrieve_area_candidates(
    *,
    session: Session,
    principal: CurrentPrincipal,
    settings: AppSettings,
    area_id: str,
    query: str,
    retrieval_strategy: RetrievalStrategy | str | None = None,
    query_type: EvaluationQueryType | None = None,
) -> RetrievalResult:
    """在指定 area 內取得 hybrid recall、Python RRF 與 rerank candidates。

    參數：
    - `session`：目前資料庫 session。
    - `principal`：目前已驗證使用者。
    - `settings`：API 執行期設定。
    - `area_id`：要檢索的 area 識別碼。
    - `query`：使用者查詢文字。
    - `retrieval_strategy`：若由外部直接指定最終 retrieval strategy，優先信任採用。
    - `query_type`：若已由上層明確指定的 query type；否則由 classifier 自動判定。

    回傳：
    - `RetrievalResult`：已完成 recall、RRF、ranking hook 與 rerank 的候選集合。
    """

    require_area_access(session=session, principal=principal, area_id=area_id)

    routing_decision = build_query_routing_decision(
        settings=settings,
        query=query,
        explicit_retrieval_strategy=retrieval_strategy,
        explicit_query_type=query_type,
        session=session,
        principal=principal,
        area_id=area_id,
    )
    effective_settings = routing_decision.effective_settings
    query_focus_plan = build_query_focus_plan_from_settings(settings=effective_settings, query=query)
    recalled_matches = _recall_ranked_candidates(
        session=session,
        settings=effective_settings,
        area_id=area_id,
        query=query_focus_plan.focus_query if query_focus_plan.applied else query,
        allowed_document_ids=routing_decision.resolved_document_ids or None,
        allowed_parent_ids=None,
    )
    rrf_matches = _apply_python_rrf(matches=recalled_matches, settings=effective_settings)
    evidence_merge_result = _merge_evidence_recall(
        session=session,
        settings=effective_settings,
        area_id=area_id,
        query=query_focus_plan.focus_query if query_focus_plan.applied else query,
        matches=rrf_matches,
        allowed_document_ids=routing_decision.resolved_document_ids or None,
    )
    ranked_matches = _apply_ranking_policy(
        matches=evidence_merge_result.matches,
        query=query,
        settings=effective_settings,
        focus_query=query_focus_plan.focus_query if query_focus_plan.applied else None,
        query_focus_plan=query_focus_plan,
    )
    reranked_matches = _apply_rerank(
        matches=ranked_matches,
        query=query_focus_plan.rerank_query if query_focus_plan.applied else query,
        settings=effective_settings,
    )
    reranked_candidates = [_build_retrieval_candidate(match) for match in reranked_matches]
    selection_result = apply_scope_aware_selection(
        candidates=reranked_candidates,
        selected_profile=routing_decision.selected_profile,
        resolved_document_ids=routing_decision.resolved_document_ids,
        max_contexts=effective_settings.assembler_max_contexts,
    )
    candidates = selection_result.candidates

    return RetrievalResult(
        candidates=candidates,
        trace=RetrievalTrace(
            query=query,
            vector_top_k=effective_settings.retrieval_vector_top_k,
            fts_top_k=effective_settings.retrieval_fts_top_k,
            max_candidates=effective_settings.retrieval_max_candidates,
            rerank_top_n=min(effective_settings.rerank_top_n, len(reranked_matches)),
            query_type=routing_decision.query_type.value,
            query_type_language=routing_decision.language,
            query_type_source=routing_decision.source,
            query_type_confidence=routing_decision.confidence,
            query_type_matched_rules=list(routing_decision.matched_rules),
            query_type_rule_hits=[
                {
                    "label": hit.label,
                    "reason": hit.reason,
                    "confidence": hit.confidence,
                }
                for hit in routing_decision.query_type_rule_hits
            ],
            query_type_embedding_scores=[
                {
                    "label": score.label,
                    "score": score.score,
                }
                for score in routing_decision.query_type_embedding_scores
            ],
            query_type_top_label=routing_decision.query_type_top_label,
            query_type_runner_up_label=routing_decision.query_type_runner_up_label,
            query_type_embedding_margin=routing_decision.query_type_embedding_margin,
            query_type_fallback_used=routing_decision.query_type_fallback_used,
            query_type_fallback_reason=routing_decision.query_type_fallback_reason,
            summary_scope=routing_decision.summary_scope,
            summary_strategy=routing_decision.summary_strategy,
            summary_strategy_source=routing_decision.summary_strategy_source,
            summary_strategy_confidence=routing_decision.summary_strategy_confidence,
            summary_strategy_rule_hits=[
                {
                    "label": hit.label,
                    "reason": hit.reason,
                    "confidence": hit.confidence,
                }
                for hit in routing_decision.summary_strategy_rule_hits
            ],
            summary_strategy_embedding_scores=[
                {
                    "label": score.label,
                    "score": score.score,
                }
                for score in routing_decision.summary_strategy_embedding_scores
            ],
            summary_strategy_top_label=routing_decision.summary_strategy_top_label,
            summary_strategy_runner_up_label=routing_decision.summary_strategy_runner_up_label,
            summary_strategy_embedding_margin=routing_decision.summary_strategy_embedding_margin,
            summary_strategy_fallback_used=routing_decision.summary_strategy_fallback_used,
            summary_strategy_fallback_reason=routing_decision.summary_strategy_fallback_reason,
            resolved_document_ids=list(routing_decision.resolved_document_ids),
            document_mention_source=routing_decision.document_mention_source,
            document_mention_confidence=routing_decision.document_mention_confidence,
            document_mention_candidates=[dict(candidate) for candidate in routing_decision.document_mention_candidates],
            selected_profile=routing_decision.selected_profile,
            profile_settings=routing_decision.resolved_settings,
            selection_applied=selection_result.applied,
            selection_strategy=selection_result.strategy,
            selected_document_count=len(selection_result.selected_document_ids),
            selected_parent_count=len(selection_result.selected_parent_ids),
            selected_document_ids=list(selection_result.selected_document_ids),
            selected_parent_ids=list(selection_result.selected_parent_ids),
            dropped_by_diversity=[
                {
                    "document_id": entry.document_id,
                    "parent_chunk_id": entry.parent_chunk_id,
                    "chunk_id": entry.chunk_id,
                    "drop_reason": entry.drop_reason,
                }
                for entry in selection_result.dropped_by_diversity
            ],
            query_focus_applied=query_focus_plan.applied,
            query_focus_language=query_focus_plan.language,
            query_focus_intents=list(query_focus_plan.intents),
            query_focus_slots=dict(query_focus_plan.slots),
            query_focus_variant=query_focus_plan.variant,
            query_focus_rule_family=query_focus_plan.rule_family,
            evidence_synopsis_variant=effective_settings.retrieval_evidence_synopsis_variant,
            evidence_units_enabled=effective_settings.retrieval_evidence_units_enabled,
            evidence_build_strategy_used=evidence_merge_result.build_strategy_used,
            evidence_recall_hits=[
                {
                    "evidence_unit_id": hit.evidence_unit.id,
                    "document_id": hit.evidence_unit.document_id,
                    "primary_parent_chunk_id": hit.evidence_unit.primary_parent_chunk_id,
                    "evidence_type": hit.evidence_unit.evidence_type.value,
                    "vector_rank": hit.vector_rank,
                    "fts_rank": hit.fts_rank,
                    "rrf_rank": hit.rrf_rank,
                    "rrf_score": hit.rrf_score,
                    "mapped_child_ids": list(hit.mapped_child_chunk_ids),
                    "path_quality_score": hit.evidence_unit.path_quality_score,
                    "cluster_strategy": hit.evidence_unit.cluster_strategy.value,
                }
                for hit in evidence_merge_result.hits
            ],
            mapped_child_ids=evidence_merge_result.mapped_child_ids,
            evidence_fallback_reason=evidence_merge_result.fallback_reason,
            focus_query=query_focus_plan.focus_query,
            rerank_query=query_focus_plan.rerank_query,
            fallback_reason=None,
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
                    evidence_rank=candidate.evidence_rank,
                    evidence_rrf_score=candidate.evidence_rrf_score,
                    evidence_unit_id=candidate.evidence_unit_id,
                    evidence_type=candidate.evidence_type,
                    path_quality_score=candidate.path_quality_score,
                    cluster_strategy=candidate.cluster_strategy,
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
    allowed_document_ids: tuple[str, ...] | None = None,
    allowed_parent_ids: tuple[str, ...] | None = None,
) -> list[RankedChunkMatch]:
    """依資料庫方言取得已套用 area/ready 邊界的 ranked candidates。"""

    dialect_name = session.get_bind().dialect.name
    if dialect_name == "postgresql":
        return _run_postgres_candidate_generation(
            session=session,
            settings=settings,
            area_id=area_id,
            query=query,
            allowed_document_ids=allowed_document_ids,
            allowed_parent_ids=allowed_parent_ids,
        )
    return _run_sqlite_candidate_generation(
        session=session,
        settings=settings,
        area_id=area_id,
        query=query,
        allowed_document_ids=allowed_document_ids,
        allowed_parent_ids=allowed_parent_ids,
    )


def _run_postgres_candidate_generation(
    *,
    session: Session,
    settings: AppSettings,
    area_id: str,
    query: str,
    allowed_document_ids: tuple[str, ...] | None,
    allowed_parent_ids: tuple[str, ...] | None,
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
    query_embedding = provider.embed_query(query)
    rpc_stmt = _build_match_chunks_rpc_statement()
    rows = session.execute(
        rpc_stmt,
        {
            "query_embedding": query_embedding,
            "query_text": query,
            "area_id": area_id,
            "vector_top_k": settings.retrieval_vector_top_k,
            "fts_top_k": settings.retrieval_fts_top_k,
            "allowed_document_ids": list(allowed_document_ids) if allowed_document_ids else None,
            "allowed_parent_chunk_ids": list(allowed_parent_ids) if allowed_parent_ids else None,
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
    allowed_document_ids: tuple[str, ...] | None,
    allowed_parent_ids: tuple[str, ...] | None,
) -> list[RankedChunkMatch]:
    """SQLite 本機測試專用的 candidate generation 路徑。"""

    provider = build_embedding_provider(settings)
    query_embedding = provider.embed_query(query)
    chunks = session.scalars(
        select(DocumentChunk)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(
            Document.area_id == area_id,
            Document.status == DocumentStatus.ready,
            DocumentChunk.chunk_type == ChunkType.child,
            Document.id.in_(allowed_document_ids) if allowed_document_ids else True,
            DocumentChunk.parent_chunk_id.in_(allowed_parent_ids) if allowed_parent_ids else True,
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


def _recall_evidence_units(
    *,
    session: Session,
    settings: AppSettings,
    area_id: str,
    query: str,
    allowed_document_ids: tuple[str, ...] | None,
) -> list[_EvidenceRecallMatch]:
    """對 evidence units 執行 hybrid recall。

    參數：
    - `session`：目前資料庫 session。
    - `settings`：API 執行期設定。
    - `area_id`：目標 area。
    - `query`：本次 recall query。
    - `allowed_document_ids`：可用文件白名單。

    回傳：
    - `list[_EvidenceRecallMatch]`：依 evidence-level RRF 排序後的命中。
    """

    dialect_name = session.get_bind().dialect.name
    if dialect_name == "postgresql":
        matches = _run_postgres_evidence_recall(
            session=session,
            settings=settings,
            area_id=area_id,
            query=query,
            allowed_document_ids=allowed_document_ids,
        )
    else:
        matches = _run_sqlite_evidence_recall(
            session=session,
            settings=settings,
            area_id=area_id,
            query=query,
            allowed_document_ids=allowed_document_ids,
        )

    for match in matches:
        match.rrf_score = _compute_rrf_score(match=match, rrf_k=settings.retrieval_rrf_k)

    merged_matches = sorted(
        matches,
        key=lambda item: (
            -item.rrf_score,
            _best_rank(item),
            item.evidence_unit.position,
            item.evidence_unit.id,
        ),
    )[: settings.retrieval_evidence_units_top_k]
    for index, match in enumerate(merged_matches, start=1):
        match.rrf_rank = index
        match.rrf_score = _compute_rrf_score(match=match, rrf_k=settings.retrieval_rrf_k)
    return merged_matches


def _run_postgres_evidence_recall(
    *,
    session: Session,
    settings: AppSettings,
    area_id: str,
    query: str,
    allowed_document_ids: tuple[str, ...] | None,
) -> list[_EvidenceRecallMatch]:
    """透過 PostgreSQL 執行 evidence units recall。"""

    provider = build_embedding_provider(settings)
    query_embedding = provider.embed_query(query)
    rows = session.execute(
        _build_evidence_recall_statement(),
        {
            "query_embedding": query_embedding,
            "query_text": query,
            "area_id": area_id,
            "vector_top_k": settings.retrieval_evidence_units_top_k,
            "fts_top_k": settings.retrieval_evidence_units_top_k,
            "allowed_document_ids": list(allowed_document_ids) if allowed_document_ids else None,
        },
    ).all()
    mapped_child_ids = _load_evidence_child_sources(session=session, evidence_unit_ids=[str(row.id) for row in rows])

    matches: list[_EvidenceRecallMatch] = []
    for row in rows:
        evidence_unit = session.get(DocumentChunkEvidenceUnit, str(row.id))
        if evidence_unit is None:
            continue
        matches.append(
            _EvidenceRecallMatch(
                evidence_unit=evidence_unit,
                mapped_child_chunk_ids=tuple(
                    mapped_child_ids.get(evidence_unit.id, [])[: settings.retrieval_evidence_units_max_mapped_children]
                ),
                vector_rank=row.vector_rank,
                fts_rank=row.fts_rank,
            )
        )
    return matches


def _run_sqlite_evidence_recall(
    *,
    session: Session,
    settings: AppSettings,
    area_id: str,
    query: str,
    allowed_document_ids: tuple[str, ...] | None,
) -> list[_EvidenceRecallMatch]:
    """SQLite 測試路徑的 evidence recall。"""

    provider = build_embedding_provider(settings)
    query_embedding = provider.embed_query(query)
    evidence_units = session.scalars(
        select(DocumentChunkEvidenceUnit)
        .join(Document, Document.id == DocumentChunkEvidenceUnit.document_id)
        .where(
            Document.area_id == area_id,
            Document.status == DocumentStatus.ready,
            Document.id.in_(allowed_document_ids) if allowed_document_ids else True,
        )
        .order_by(DocumentChunkEvidenceUnit.position.asc(), DocumentChunkEvidenceUnit.id.asc())
    ).all()
    mapped_child_ids = _load_evidence_child_sources(
        session=session,
        evidence_unit_ids=[evidence_unit.id for evidence_unit in evidence_units],
    )
    merged_by_unit_id: dict[str, _EvidenceRecallMatch] = {}

    vector_scored = sorted(
        (
            (_cosine_distance(query_embedding, evidence_unit.evidence_embedding), evidence_unit)
            for evidence_unit in evidence_units
            if evidence_unit.evidence_embedding is not None
        ),
        key=lambda item: (item[0], item[1].position, item[1].id),
    )[: settings.retrieval_evidence_units_top_k]
    for index, (_, evidence_unit) in enumerate(vector_scored, start=1):
        current = merged_by_unit_id.setdefault(
            evidence_unit.id,
            _EvidenceRecallMatch(
                evidence_unit=evidence_unit,
                mapped_child_chunk_ids=tuple(
                    mapped_child_ids.get(evidence_unit.id, [])[: settings.retrieval_evidence_units_max_mapped_children]
                ),
            ),
        )
        current.vector_rank = index

    fts_scored = sorted(
        (
            (
                _sqlite_fts_score(
                    query=query,
                    content=" ".join(
                        filter(
                            None,
                            [
                                evidence_unit.heading_path or "",
                                evidence_unit.section_path_text or "",
                                evidence_unit.evidence_text,
                            ],
                        )
                    ),
                ),
                evidence_unit,
            )
            for evidence_unit in evidence_units
            if evidence_unit.evidence_text
        ),
        key=lambda item: (-item[0], item[1].position, item[1].id),
    )
    for index, (_, evidence_unit) in enumerate((item for item in fts_scored if item[0] > 0), start=1):
        if index > settings.retrieval_evidence_units_top_k:
            break
        current = merged_by_unit_id.setdefault(
            evidence_unit.id,
            _EvidenceRecallMatch(
                evidence_unit=evidence_unit,
                mapped_child_chunk_ids=tuple(
                    mapped_child_ids.get(evidence_unit.id, [])[: settings.retrieval_evidence_units_max_mapped_children]
                ),
            ),
        )
        current.fts_rank = index

    return list(merged_by_unit_id.values())


def _load_evidence_child_sources(*, session: Session, evidence_unit_ids: list[str]) -> dict[str, list[str]]:
    """載入 evidence unit 對應的 child source ids。

    參數：
    - `session`：目前資料庫 session。
    - `evidence_unit_ids`：待查 evidence unit ids。

    回傳：
    - `dict[str, list[str]]`：evidence unit -> child ids 映射。
    """

    if not evidence_unit_ids:
        return {}
    rows = session.execute(
        select(
            DocumentChunkEvidenceUnitChildSource.evidence_unit_id,
            DocumentChunkEvidenceUnitChildSource.child_chunk_id,
        )
        .where(DocumentChunkEvidenceUnitChildSource.evidence_unit_id.in_(evidence_unit_ids))
        .order_by(
            DocumentChunkEvidenceUnitChildSource.evidence_unit_id.asc(),
            DocumentChunkEvidenceUnitChildSource.position.asc(),
        )
    ).all()
    mapped: dict[str, list[str]] = {}
    for evidence_unit_id, child_chunk_id in rows:
        mapped.setdefault(str(evidence_unit_id), []).append(str(child_chunk_id))
    return mapped


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


def _merge_evidence_recall(
    *,
    session: Session,
    settings: AppSettings,
    area_id: str,
    query: str,
    matches: list[RankedChunkMatch],
    allowed_document_ids: tuple[str, ...] | None,
) -> EvidenceRecallMergeResult:
    """將 evidence recall 命中映射回 child candidates 並與既有結果合併。

    參數：
    - `session`：目前資料庫 session。
    - `settings`：API 執行期設定。
    - `area_id`：目標 area。
    - `query`：本次實際 recall query。
    - `matches`：既有 child recall 的 RRF 候選。
    - `allowed_document_ids`：可用文件白名單。

    回傳：
    - `EvidenceRecallMergeResult`：合併後的候選與 evidence trace。
    """

    if not settings.retrieval_evidence_units_enabled:
        return EvidenceRecallMergeResult(
            matches=matches,
            hits=[],
            build_strategy_used=None,
            mapped_child_ids=[],
            fallback_reason=None,
        )

    try:
        evidence_hits = _recall_evidence_units(
            session=session,
            settings=settings,
            area_id=area_id,
            query=query,
            allowed_document_ids=allowed_document_ids,
        )
    except Exception as exc:
        LOGGER.warning("Evidence recall failed; falling back to child-only retrieval.", exc_info=True)
        return EvidenceRecallMergeResult(
            matches=matches,
            hits=[],
            build_strategy_used=None,
            mapped_child_ids=[],
            fallback_reason=f"evidence_recall_error:{exc}",
        )

    if not evidence_hits:
        return EvidenceRecallMergeResult(
            matches=matches,
            hits=[],
            build_strategy_used=None,
            mapped_child_ids=[],
            fallback_reason=None,
        )

    merged_by_chunk_id = {match.chunk.id: match for match in matches}
    mapped_child_ids: list[str] = []
    build_strategy_used = evidence_hits[0].evidence_unit.build_strategy.value
    for evidence_hit in evidence_hits:
        for child_chunk_id in evidence_hit.mapped_child_chunk_ids[: settings.retrieval_evidence_units_max_mapped_children]:
            mapped_child_ids.append(child_chunk_id)
            match = merged_by_chunk_id.get(child_chunk_id)
            if match is None:
                chunk = session.get(DocumentChunk, child_chunk_id)
                if chunk is None:
                    continue
                match = RankedChunkMatch(chunk=chunk)
                merged_by_chunk_id[child_chunk_id] = match
            match.evidence_rank = min(
                (value for value in (match.evidence_rank, evidence_hit.rrf_rank) if value is not None),
                default=evidence_hit.rrf_rank,
            )
            match.evidence_rrf_score += evidence_hit.rrf_score
            match.rrf_score += evidence_hit.rrf_score
            match.evidence_unit_id = evidence_hit.evidence_unit.id
            match.evidence_type = evidence_hit.evidence_unit.evidence_type.value
            match.path_quality_score = evidence_hit.evidence_unit.path_quality_score
            match.cluster_strategy = evidence_hit.evidence_unit.cluster_strategy.value

    merged_matches = sorted(
        merged_by_chunk_id.values(),
        key=lambda item: (
            -item.rrf_score,
            _best_rank(item),
            item.chunk.position,
            item.chunk.id,
        ),
    )[: settings.retrieval_max_candidates]
    for index, match in enumerate(merged_matches, start=1):
        match.rrf_rank = index
    return EvidenceRecallMergeResult(
        matches=merged_matches,
        hits=evidence_hits,
        build_strategy_used=build_strategy_used,
        mapped_child_ids=sorted(set(mapped_child_ids)),
        fallback_reason=None,
    )


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

    available_ranks = [
        rank
        for rank in (
            getattr(match, "vector_rank", None),
            getattr(match, "fts_rank", None),
            getattr(match, "evidence_rank", None),
            getattr(match, "rrf_rank", None),
        )
        if rank is not None
    ]
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


def _resolve_document_recall_result(
    *,
    session: Session,
    settings: AppSettings,
    area_id: str,
    query: str,
    query_type: EvaluationQueryType,
    summary_scope: str | None,
    resolved_document_ids: tuple[str, ...],
) -> DocumentRecallResult:
    """依 query type 與 synopsis recall 決定第二階段允許的文件集合。

    參數：
    - `session`：目前資料庫 session。
    - `settings`：routing 後的有效設定。
    - `area_id`：目標 area。
    - `query`：使用者原始查詢。
    - `query_type`：本次 query type。
    - `summary_scope`：若為摘要問題，表示 single/multi document scope。
    - `resolved_document_ids`：document mention resolver 高信心命中的文件集合。

    回傳：
    - `DocumentRecallResult`：第一階段選文件結果與 trace。
    """

    if query_type == EvaluationQueryType.fact_lookup or not settings.retrieval_document_recall_enabled:
        return DocumentRecallResult(
            selected_document_ids=(),
            trace=DocumentRecallTrace(
                applied=False,
                strategy="disabled",
                top_k=settings.retrieval_document_recall_top_k,
                selected_document_ids=[],
                dropped_document_ids=[],
                candidates=[],
            ),
        )

    if summary_scope == "single_document" and len(resolved_document_ids) == 1:
        return DocumentRecallResult(
            selected_document_ids=resolved_document_ids,
            trace=DocumentRecallTrace(
                applied=True,
                strategy="mention_resolved_single_document_v1",
                top_k=1,
                selected_document_ids=list(resolved_document_ids),
                dropped_document_ids=[],
                candidates=[],
            ),
        )

    recall_matches = _recall_documents_by_synopsis(
        session=session,
        settings=settings,
        area_id=area_id,
        query=query,
    )
    selected_document_ids: list[str] = []
    for document_id in resolved_document_ids:
        if document_id not in selected_document_ids:
            selected_document_ids.append(document_id)
    for match in recall_matches:
        if match.document.id in selected_document_ids:
            continue
        selected_document_ids.append(match.document.id)
        if len(selected_document_ids) >= settings.retrieval_document_recall_top_k:
            break

    selected_document_set = set(selected_document_ids)
    return DocumentRecallResult(
        selected_document_ids=tuple(selected_document_ids),
        trace=DocumentRecallTrace(
            applied=True,
            strategy="synopsis_rrf_v1",
            top_k=settings.retrieval_document_recall_top_k,
            selected_document_ids=selected_document_ids,
            dropped_document_ids=[match.document.id for match in recall_matches if match.document.id not in selected_document_set],
            candidates=[
                DocumentRecallTraceEntry(
                    document_id=match.document.id,
                    file_name=match.document.file_name,
                    vector_rank=match.vector_rank,
                    fts_rank=match.fts_rank,
                    rrf_rank=match.rrf_rank or 0,
                    rrf_score=match.rrf_score,
                )
                for match in recall_matches
            ],
        ),
    )


def _recall_documents_by_synopsis(
    *,
    session: Session,
    settings: AppSettings,
    area_id: str,
    query: str,
) -> list[_DocumentRecallMatch]:
    """以 document synopsis 執行第一階段 document-level recall。

    參數：
    - `session`：目前資料庫 session。
    - `settings`：routing 後的有效設定。
    - `area_id`：目標 area。
    - `query`：使用者原始查詢。

    回傳：
    - `list[_DocumentRecallMatch]`：依 RRF 排序後的文件候選。
    """

    dialect_name = session.get_bind().dialect.name
    if dialect_name == "postgresql":
        matches = _run_postgres_document_recall(
            session=session,
            settings=settings,
            area_id=area_id,
            query=query,
        )
    else:
        matches = _run_sqlite_document_recall(
            session=session,
            settings=settings,
            area_id=area_id,
            query=query,
        )

    for match in matches:
        match.rrf_score = _compute_rrf_score(match=match, rrf_k=settings.retrieval_rrf_k)

    merged_matches = sorted(
        matches,
        key=lambda item: (
            -item.rrf_score,
            _best_rank(item),
            item.document.file_name.casefold(),
            item.document.id,
        ),
    )[: settings.retrieval_document_recall_top_k]
    for index, match in enumerate(merged_matches, start=1):
        match.rrf_rank = index
    return merged_matches


def _run_postgres_document_recall(
    *,
    session: Session,
    settings: AppSettings,
    area_id: str,
    query: str,
) -> list[_DocumentRecallMatch]:
    """透過 PostgreSQL 對 document synopsis 執行 recall。"""

    provider = build_embedding_provider(settings)
    query_embedding = provider.embed_query(query)
    rows = session.execute(
        _build_document_recall_statement(),
        {
            "query_embedding": query_embedding,
            "query_text": query,
            "area_id": area_id,
            "vector_top_k": settings.retrieval_document_recall_top_k,
            "fts_top_k": settings.retrieval_document_recall_top_k,
        },
    ).all()

    matches: list[_DocumentRecallMatch] = []
    for row in rows:
        document = session.get(Document, str(row.id))
        if document is None:
            continue
        matches.append(
            _DocumentRecallMatch(
                document=document,
                vector_rank=row.vector_rank,
                fts_rank=row.fts_rank,
            )
        )
    return matches


def _run_sqlite_document_recall(
    *,
    session: Session,
    settings: AppSettings,
    area_id: str,
    query: str,
) -> list[_DocumentRecallMatch]:
    """SQLite 測試路徑使用的 document synopsis recall。"""

    provider = build_embedding_provider(settings)
    query_embedding = provider.embed_query(query)
    documents = session.scalars(
        select(Document)
        .where(
            Document.area_id == area_id,
            Document.status == DocumentStatus.ready,
        )
        .order_by(Document.file_name.asc())
    ).all()

    merged_by_document_id: dict[str, _DocumentRecallMatch] = {}
    vector_scored = sorted(
        (
            (_cosine_distance(query_embedding, document.synopsis_embedding), document)
            for document in documents
            if document.synopsis_embedding is not None
        ),
        key=lambda item: (item[0], item[1].file_name.casefold(), item[1].id),
    )[: settings.retrieval_document_recall_top_k]
    for index, (_, document) in enumerate(vector_scored, start=1):
        current = merged_by_document_id.setdefault(document.id, _DocumentRecallMatch(document=document))
        current.vector_rank = index

    fts_scored = sorted(
        (
            (_sqlite_fts_score(query=query, content=document.synopsis_text or ""), document)
            for document in documents
            if document.synopsis_text
        ),
        key=lambda item: (-item[0], item[1].file_name.casefold(), item[1].id),
    )
    for index, (_, document) in enumerate((item for item in fts_scored if item[0] > 0), start=1):
        if index > settings.retrieval_document_recall_top_k:
            break
        current = merged_by_document_id.setdefault(document.id, _DocumentRecallMatch(document=document))
        current.fts_rank = index

    return list(merged_by_document_id.values())


def _resolve_section_recall_result(
    *,
    session: Session,
    settings: AppSettings,
    area_id: str,
    query: str,
    query_type: EvaluationQueryType,
    summary_strategy: str | None,
    allowed_document_ids: tuple[str, ...] | None,
) -> SectionRecallResult:
    """依 query type 與 summary strategy 決定第二階段 section 集合。"""

    if query_type == EvaluationQueryType.fact_lookup:
        return SectionRecallResult(
            selected_parent_ids=(),
            trace=SectionRecallTrace(
                applied=False,
                strategy="disabled",
                top_k=0,
                selected_parent_ids=[],
                dropped_parent_ids=[],
                candidates=[],
            ),
        )

    section_top_k = _resolve_section_recall_top_k(
        settings=settings,
        query_type=query_type,
        summary_strategy=summary_strategy,
    )
    recall_matches = _recall_sections_by_synopsis(
        session=session,
        settings=settings,
        area_id=area_id,
        query=query,
        allowed_document_ids=allowed_document_ids,
        top_k=section_top_k,
    )
    selected_parent_ids = [match.parent_chunk.id for match in recall_matches[:section_top_k]]
    selected_parent_set = set(selected_parent_ids)
    return SectionRecallResult(
        selected_parent_ids=tuple(selected_parent_ids),
        trace=SectionRecallTrace(
            applied=bool(selected_parent_ids),
            strategy="section_synopsis_rrf_v1",
            top_k=section_top_k,
            selected_parent_ids=selected_parent_ids,
            dropped_parent_ids=[match.parent_chunk.id for match in recall_matches if match.parent_chunk.id not in selected_parent_set],
            candidates=[
                SectionRecallTraceEntry(
                    parent_chunk_id=match.parent_chunk.id,
                    document_id=match.parent_chunk.document_id,
                    heading=match.parent_chunk.heading,
                    heading_path=match.parent_chunk.heading_path,
                    section_path_text=match.parent_chunk.section_path_text,
                    vector_rank=match.vector_rank,
                    fts_rank=match.fts_rank,
                    rrf_rank=match.rrf_rank or 0,
                    rrf_score=match.rrf_score,
                )
                for match in recall_matches
            ],
        ),
    )


def _resolve_section_recall_top_k(
    *,
    settings: AppSettings,
    query_type: EvaluationQueryType,
    summary_strategy: str | None,
) -> int:
    """依題型與策略決定 section recall top-k。"""

    if query_type == EvaluationQueryType.cross_document_compare:
        return max(settings.assembler_max_contexts * 2, 10)
    if summary_strategy == "section_focused":
        return max(settings.assembler_max_contexts, 6)
    return max(settings.assembler_max_contexts * 2, 8)


def _recall_sections_by_synopsis(
    *,
    session: Session,
    settings: AppSettings,
    area_id: str,
    query: str,
    allowed_document_ids: tuple[str, ...] | None,
    top_k: int,
) -> list[_SectionRecallMatch]:
    """以 section synopsis 執行 parent-level recall。"""

    dialect_name = session.get_bind().dialect.name
    if dialect_name == "postgresql":
        matches = _run_postgres_section_recall(
            session=session,
            settings=settings,
            area_id=area_id,
            query=query,
            allowed_document_ids=allowed_document_ids,
            top_k=top_k,
        )
    else:
        matches = _run_sqlite_section_recall(
            session=session,
            settings=settings,
            area_id=area_id,
            query=query,
            allowed_document_ids=allowed_document_ids,
            top_k=top_k,
        )

    for match in matches:
        match.rrf_score = _compute_rrf_score(match=match, rrf_k=settings.retrieval_rrf_k)

    merged_matches = sorted(
        matches,
        key=lambda item: (
            -item.rrf_score,
            _best_rank(item),
            item.parent_chunk.position,
            item.parent_chunk.id,
        ),
    )[:top_k]
    for index, match in enumerate(merged_matches, start=1):
        match.rrf_rank = index
    return merged_matches


def _run_postgres_section_recall(
    *,
    session: Session,
    settings: AppSettings,
    area_id: str,
    query: str,
    allowed_document_ids: tuple[str, ...] | None,
    top_k: int,
) -> list[_SectionRecallMatch]:
    """透過 PostgreSQL 對 section synopsis 執行 recall。"""

    provider = build_embedding_provider(settings)
    query_embedding = provider.embed_query(query)
    rows = session.execute(
        _build_section_recall_statement(),
        {
            "query_embedding": query_embedding,
            "query_text": query,
            "area_id": area_id,
            "vector_top_k": top_k,
            "fts_top_k": top_k,
            "allowed_document_ids": list(allowed_document_ids) if allowed_document_ids else None,
        },
    ).all()

    matches: list[_SectionRecallMatch] = []
    for row in rows:
        parent_chunk = session.get(DocumentChunk, str(row.id))
        if parent_chunk is None:
            continue
        matches.append(
            _SectionRecallMatch(
                parent_chunk=parent_chunk,
                vector_rank=row.vector_rank,
                fts_rank=row.fts_rank,
            )
        )
    return matches


def _run_sqlite_section_recall(
    *,
    session: Session,
    settings: AppSettings,
    area_id: str,
    query: str,
    allowed_document_ids: tuple[str, ...] | None,
    top_k: int,
) -> list[_SectionRecallMatch]:
    """SQLite 測試路徑使用的 section synopsis recall。"""

    provider = build_embedding_provider(settings)
    query_embedding = provider.embed_query(query)
    parents = session.scalars(
        select(DocumentChunk)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(
            Document.area_id == area_id,
            Document.status == DocumentStatus.ready,
            DocumentChunk.chunk_type == ChunkType.parent,
            Document.id.in_(allowed_document_ids) if allowed_document_ids else True,
        )
        .order_by(DocumentChunk.position.asc())
    ).all()

    merged_by_parent_id: dict[str, _SectionRecallMatch] = {}
    vector_scored = sorted(
        (
            (_cosine_distance(query_embedding, parent.section_synopsis_embedding), parent)
            for parent in parents
            if parent.section_synopsis_embedding is not None
        ),
        key=lambda item: (item[0], item[1].position, item[1].id),
    )[:top_k]
    for index, (_, parent) in enumerate(vector_scored, start=1):
        current = merged_by_parent_id.setdefault(parent.id, _SectionRecallMatch(parent_chunk=parent))
        current.vector_rank = index

    fts_scored = sorted(
        (
            (_sqlite_fts_score(query=query, content=parent.section_synopsis_text or ""), parent)
            for parent in parents
            if parent.section_synopsis_text
        ),
        key=lambda item: (-item[0], item[1].position, item[1].id),
    )
    for index, (_, parent) in enumerate((item for item in fts_scored if item[0] > 0), start=1):
        if index > top_k:
            break
        current = merged_by_parent_id.setdefault(parent.id, _SectionRecallMatch(parent_chunk=parent))
        current.fts_rank = index

    return list(merged_by_parent_id.values())


def _resolve_retrieval_fallback_reason(
    *,
    document_recall_result: DocumentRecallResult,
    section_recall_result: SectionRecallResult,
) -> str | None:
    """依 document/section recall 結果決定是否有摘要層級 fallback。"""

    if document_recall_result.trace.strategy != "disabled" and not document_recall_result.selected_document_ids:
        return "document_recall_empty_fallback_to_child"
    if section_recall_result.trace.strategy != "disabled" and not section_recall_result.selected_parent_ids:
        return "section_recall_empty_fallback_to_document_scope"
    return None


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
        evidence_rank=match.evidence_rank,
        evidence_rrf_score=match.evidence_rrf_score,
        evidence_unit_id=match.evidence_unit_id,
        evidence_type=match.evidence_type,
        path_quality_score=match.path_quality_score,
        cluster_strategy=match.cluster_strategy,
    )


def _resolve_candidate_source(match: RankedChunkMatch) -> str:
    """根據 rank 來源決定 candidate source 欄位。"""

    if match.evidence_rank is not None and (match.vector_rank is not None or match.fts_rank is not None):
        return "hybrid+evidence"
    if match.vector_rank is not None and match.fts_rank is not None:
        return "hybrid"
    if match.evidence_rank is not None:
        return "evidence_hybrid"
    if match.vector_rank is not None:
        return "vector"
    return "fts"
