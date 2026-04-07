"""Query-aware retrieval 的 query type classifier 與 profile resolver。"""

from __future__ import annotations

from dataclasses import dataclass
import re

from app.core.settings import AppSettings
from app.db.models import EvaluationQueryType
from app.services.retrieval_query import detect_query_language, normalize_query_text


# `classified` 表示 query type 由 classifier 規則命中。
QUERY_ROUTING_SOURCE_CLASSIFIED = "classified"
# `fallback` 表示 classifier 未命中任何規則，回退到 `fact_lookup`。
QUERY_ROUTING_SOURCE_FALLBACK = "fallback"
# `explicit` 表示 query type 由外部 contract 直接指定。
QUERY_ROUTING_SOURCE_EXPLICIT = "explicit"

# `fact_lookup_precision_v1` 表示事實查詢的 precision-first runtime profile。
RETRIEVAL_PROFILE_FACT_LOOKUP_PRECISION_V1 = "fact_lookup_precision_v1"
# `document_summary_skeleton_v1` 表示摘要問題的 skeleton runtime profile。
RETRIEVAL_PROFILE_DOCUMENT_SUMMARY_SKELETON_V1 = "document_summary_skeleton_v1"
# `cross_document_compare_skeleton_v1` 表示比較問題的 skeleton runtime profile。
RETRIEVAL_PROFILE_CROSS_DOCUMENT_COMPARE_SKELETON_V1 = "cross_document_compare_skeleton_v1"

# `zh-TW` 摘要型 query 關鍵詞。
SUMMARY_TRIGGER_PHRASES_ZH_TW = ("摘要", "總結", "整理", "概述", "重點")
# `en` 摘要型 query 關鍵詞。
SUMMARY_TRIGGER_PHRASES_EN = ("summary", "summarize", "overview", "key points")
# `zh-TW` 比較型 query 關鍵詞。
COMPARE_TRIGGER_PHRASES_ZH_TW = ("比較", "差異", "相比", "不同", "優缺點")
# `en` 比較型 query 關鍵詞。
COMPARE_TRIGGER_PHRASES_EN = ("compare", "comparison", "difference", "vs", "versus")


@dataclass(frozen=True, slots=True)
class QueryTypeClassification:
    """單次 query type classifier 的輸出。"""

    query_type: EvaluationQueryType
    language: str
    confidence: float
    source: str
    matched_rules: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class QueryRoutingDecision:
    """單次 query-aware retrieval routing 的決策結果。"""

    query_type: EvaluationQueryType
    language: str
    confidence: float
    source: str
    matched_rules: tuple[str, ...]
    selected_profile: str
    resolved_settings: dict[str, int | bool]
    effective_settings: AppSettings


def classify_query_type(*, query: str) -> QueryTypeClassification:
    """以規則式雙語 classifier 判定 query type。

    參數：
    - `query`：原始使用者問題。

    回傳：
    - `QueryTypeClassification`：分類結果、信心與命中規則。
    """

    normalized_query = normalize_query_text(query=query)
    language = detect_query_language(query=normalized_query)
    lowered_query = normalized_query.casefold()

    compare_matches = _match_trigger_phrases(
        lowered_query=lowered_query,
        language=language,
        zh_tw_phrases=COMPARE_TRIGGER_PHRASES_ZH_TW,
        en_phrases=COMPARE_TRIGGER_PHRASES_EN,
    )
    if compare_matches:
        return QueryTypeClassification(
            query_type=EvaluationQueryType.cross_document_compare,
            language=language,
            confidence=_score_rule_confidence(match_count=len(compare_matches)),
            source=QUERY_ROUTING_SOURCE_CLASSIFIED,
            matched_rules=compare_matches,
        )

    summary_matches = _match_trigger_phrases(
        lowered_query=lowered_query,
        language=language,
        zh_tw_phrases=SUMMARY_TRIGGER_PHRASES_ZH_TW,
        en_phrases=SUMMARY_TRIGGER_PHRASES_EN,
    )
    if summary_matches:
        return QueryTypeClassification(
            query_type=EvaluationQueryType.document_summary,
            language=language,
            confidence=_score_rule_confidence(match_count=len(summary_matches)),
            source=QUERY_ROUTING_SOURCE_CLASSIFIED,
            matched_rules=summary_matches,
        )

    return QueryTypeClassification(
        query_type=EvaluationQueryType.fact_lookup,
        language=language,
        confidence=0.0,
        source=QUERY_ROUTING_SOURCE_FALLBACK,
        matched_rules=(),
    )


def build_query_routing_decision(
    *,
    settings: AppSettings,
    query: str,
    explicit_query_type: EvaluationQueryType | None = None,
) -> QueryRoutingDecision:
    """建立單次 query-aware retrieval routing 決策。

    參數：
    - `settings`：目前應用程式設定。
    - `query`：原始使用者問題。
    - `explicit_query_type`：若由外部 contract 指定 query type，優先使用。

    回傳：
    - `QueryRoutingDecision`：最終 query type、profile 與有效設定。
    """

    normalized_query = normalize_query_text(query=query)
    language = detect_query_language(query=normalized_query)
    if explicit_query_type is not None:
        classification = QueryTypeClassification(
            query_type=explicit_query_type,
            language=language,
            confidence=1.0,
            source=QUERY_ROUTING_SOURCE_EXPLICIT,
            matched_rules=(),
        )
    else:
        classification = classify_query_type(query=normalized_query)

    profile_name, overrides = _resolve_runtime_profile_overrides(
        settings=settings,
        query_type=classification.query_type,
    )
    effective_settings = settings.model_copy(update=overrides)
    return QueryRoutingDecision(
        query_type=classification.query_type,
        language=classification.language,
        confidence=classification.confidence,
        source=classification.source,
        matched_rules=classification.matched_rules,
        selected_profile=profile_name,
        resolved_settings=build_resolved_settings_trace(settings=effective_settings),
        effective_settings=effective_settings,
    )


def _resolve_runtime_profile_overrides(
    *,
    settings: AppSettings,
    query_type: EvaluationQueryType,
) -> tuple[str, dict[str, int | str | bool]]:
    """依 query type 解析 runtime profile 名稱與設定覆寫。

    參數：
    - `settings`：目前應用程式設定。
    - `query_type`：本次 query type。

    回傳：
    - `tuple[str, dict[str, int | str | bool]]`：profile 名稱與設定覆寫。
    """

    if query_type == EvaluationQueryType.document_summary:
        return (
            RETRIEVAL_PROFILE_DOCUMENT_SUMMARY_SKELETON_V1,
            {
                "retrieval_vector_top_k": max(settings.retrieval_vector_top_k, 45),
                "retrieval_fts_top_k": max(settings.retrieval_fts_top_k, 45),
                "retrieval_max_candidates": max(settings.retrieval_max_candidates, 45),
                "rerank_top_n": max(settings.rerank_top_n, 36),
                "assembler_max_contexts": max(settings.assembler_max_contexts, 12),
                "assembler_max_chars_per_context": max(settings.assembler_max_chars_per_context, 3600),
                "assembler_max_children_per_parent": max(settings.assembler_max_children_per_parent, 7),
            },
        )
    if query_type == EvaluationQueryType.cross_document_compare:
        return (
            RETRIEVAL_PROFILE_CROSS_DOCUMENT_COMPARE_SKELETON_V1,
            {
                "retrieval_vector_top_k": max(settings.retrieval_vector_top_k, 45),
                "retrieval_fts_top_k": max(settings.retrieval_fts_top_k, 45),
                "retrieval_max_candidates": max(settings.retrieval_max_candidates, 45),
                "rerank_top_n": max(settings.rerank_top_n, 36),
                "assembler_max_contexts": max(settings.assembler_max_contexts, 12),
                "assembler_max_chars_per_context": max(settings.assembler_max_chars_per_context, 3200),
                "assembler_max_children_per_parent": max(settings.assembler_max_children_per_parent, 5),
            },
        )
    return (
        RETRIEVAL_PROFILE_FACT_LOOKUP_PRECISION_V1,
        {
            "retrieval_vector_top_k": settings.retrieval_vector_top_k,
            "retrieval_fts_top_k": settings.retrieval_fts_top_k,
            "retrieval_max_candidates": settings.retrieval_max_candidates,
            "rerank_top_n": settings.rerank_top_n,
            "assembler_max_contexts": settings.assembler_max_contexts,
            "assembler_max_chars_per_context": settings.assembler_max_chars_per_context,
            "assembler_max_children_per_parent": settings.assembler_max_children_per_parent,
        },
    )


def build_resolved_settings_trace(*, settings: AppSettings) -> dict[str, int | bool]:
    """建立 query routing 可觀測的有效設定摘要。

    參數：
    - `settings`：routing 後的有效設定。

    回傳：
    - `dict[str, int | bool]`：debug-safe 的扁平化設定摘要。
    """

    return {
        "vector_top_k": settings.retrieval_vector_top_k,
        "fts_top_k": settings.retrieval_fts_top_k,
        "max_candidates": settings.retrieval_max_candidates,
        "rerank_top_n": settings.rerank_top_n,
        "assembler_max_contexts": settings.assembler_max_contexts,
        "assembler_max_chars_per_context": settings.assembler_max_chars_per_context,
        "assembler_max_children_per_parent": settings.assembler_max_children_per_parent,
        "query_focus_enabled": settings.retrieval_query_focus_enabled,
    }


def _match_trigger_phrases(
    *,
    lowered_query: str,
    language: str,
    zh_tw_phrases: tuple[str, ...],
    en_phrases: tuple[str, ...],
) -> tuple[str, ...]:
    """依 query language 回傳命中的 trigger phrases。

    參數：
    - `lowered_query`：已 casefold 的 query。
    - `language`：query 語言。
    - `zh_tw_phrases`：中文 trigger phrases。
    - `en_phrases`：英文 trigger phrases。

    回傳：
    - `tuple[str, ...]`：依命中順序去重後的 trigger phrases。
    """

    candidates: list[str] = []
    if language in {"zh-TW", "mixed"}:
        candidates.extend(zh_tw_phrases)
    if language in {"en", "mixed"}:
        candidates.extend(en_phrases)

    matches: list[str] = []
    seen: set[str] = set()
    for phrase in candidates:
        if phrase in seen:
            continue
        if _query_contains_phrase(lowered_query=lowered_query, phrase=phrase):
            seen.add(phrase)
            matches.append(phrase)
    return tuple(matches)


def _query_contains_phrase(*, lowered_query: str, phrase: str) -> bool:
    """判斷 query 是否包含指定 trigger phrase。

    參數：
    - `lowered_query`：已 casefold 的 query。
    - `phrase`：待檢查的 phrase。

    回傳：
    - `bool`：若 query 含有該 phrase 則回傳真值。
    """

    if re.search(r"[A-Za-z]", phrase):
        pattern = re.compile(rf"(?<![A-Za-z0-9]){re.escape(phrase.casefold())}(?![A-Za-z0-9])")
        return bool(pattern.search(lowered_query))
    return phrase.casefold() in lowered_query


def _score_rule_confidence(*, match_count: int) -> float:
    """依命中規則數量估計簡單 confidence。

    參數：
    - `match_count`：命中的規則數量。

    回傳：
    - `float`：簡單估計的 confidence。
    """

    if match_count >= 2:
        return 0.9
    if match_count == 1:
        return 0.75
    return 0.0
