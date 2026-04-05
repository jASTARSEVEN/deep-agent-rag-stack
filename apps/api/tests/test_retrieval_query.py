"""query focus planner 與 query tokenization 測試。"""

from __future__ import annotations

from app.core.settings import AppSettings
from app.services.retrieval_query import (
    QUERY_FOCUS_VARIANT_GENERIC_FIELD_V1,
    build_query_focus_plan,
    build_query_focus_plan_from_settings,
    extract_query_tokens,
)


def test_query_focus_plan_detects_deadline_query_in_traditional_chinese() -> None:
    """繁中期限題應命中 date_or_deadline intent。"""

    plan = build_query_focus_plan(
        query="文件申請期限是多久內？",
        enabled=True,
        variant=QUERY_FOCUS_VARIANT_GENERIC_FIELD_V1,
        confidence_threshold=0.7,
    )

    assert plan.applied is True
    assert plan.language == "zh-TW"
    assert plan.intents == ("date_or_deadline",)
    assert plan.slots["target_field"] == "日期或期限"
    assert "期限" in plan.focus_query
    assert "Need:" in plan.rerank_query
    assert plan.variant == QUERY_FOCUS_VARIANT_GENERIC_FIELD_V1
    assert plan.rule_family == "generic"


def test_query_focus_plan_detects_eligibility_query_in_traditional_chinese() -> None:
    """繁中資格題應命中 eligibility_or_actor intent。"""

    plan = build_query_focus_plan(
        query="研究助理的申請資格有哪些？",
        enabled=True,
        variant=QUERY_FOCUS_VARIANT_GENERIC_FIELD_V1,
        confidence_threshold=0.7,
    )

    assert plan.applied is True
    assert plan.intents == ("eligibility_or_actor", "enumeration_or_inventory")
    assert plan.slots["subject"] == "研究助理"
    assert plan.slots["target_field"] == "資格或責任對象 / 項目清單或列舉內容"
    assert "資格" in plan.focus_query
    assert "適用對象" in plan.focus_query


def test_query_focus_plan_detects_amount_limit_query_in_traditional_chinese() -> None:
    """繁中金額上限題應命中 amount_or_limit intent。"""

    plan = build_query_focus_plan(
        query="這個補助的最高金額是多少？",
        enabled=True,
        variant=QUERY_FOCUS_VARIANT_GENERIC_FIELD_V1,
        confidence_threshold=0.7,
    )

    assert plan.applied is True
    assert plan.intents == ("amount_or_limit", "count_or_size")
    assert plan.slots["subject"] == "這個補助"
    assert "金額或上限" in plan.focus_query
    assert "上限" in plan.focus_query


def test_query_focus_plan_detects_count_size_query_in_english_without_domain_specific_injection() -> None:
    """英文 dataset size 題應命中 count_or_size，且不注入 corpus-specific token。"""

    plan = build_query_focus_plan(
        query="How big is the dataset?",
        enabled=True,
        variant=QUERY_FOCUS_VARIANT_GENERIC_FIELD_V1,
        confidence_threshold=0.7,
    )

    assert plan.applied is True
    assert plan.language == "en"
    assert plan.intents == ("count_or_size",)
    assert plan.slots["subject"] == "dataset"
    assert "count or size" in plan.focus_query
    assert "reviews" not in plan.focus_query
    assert "amazon mechanical turk" not in plan.rerank_query.casefold()


def test_query_focus_plan_detects_comparison_axis_query_in_english() -> None:
    """英文比較題應命中 comparison_axis intent。"""

    plan = build_query_focus_plan(
        query="Which setting performs better, local or hosted?",
        enabled=True,
        variant=QUERY_FOCUS_VARIANT_GENERIC_FIELD_V1,
        confidence_threshold=0.7,
    )

    assert plan.applied is True
    assert plan.intents == ("comparison_axis",)
    assert plan.slots["comparison_target"] == "local / hosted"
    assert "comparison result or axis" in plan.focus_query
    assert "direct comparison evidence" in plan.rerank_query


def test_query_focus_plan_does_not_apply_to_low_confidence_query() -> None:
    """低信心 query 不應套用 query focus。"""

    plan = build_query_focus_plan(
        query="alpha",
        enabled=True,
        variant=QUERY_FOCUS_VARIANT_GENERIC_FIELD_V1,
        confidence_threshold=0.7,
    )

    assert plan.applied is False
    assert plan.intents == ()
    assert plan.focus_query == "alpha"
    assert plan.rerank_query == "alpha"


def test_query_focus_plan_respects_settings_flags() -> None:
    """從 AppSettings 建立 plan 時應尊重 query focus 設定。"""

    settings = AppSettings(
        RETRIEVAL_QUERY_FOCUS_ENABLED=True,
        RETRIEVAL_QUERY_FOCUS_VARIANT=QUERY_FOCUS_VARIANT_GENERIC_FIELD_V1,
        RETRIEVAL_QUERY_FOCUS_CONFIDENCE_THRESHOLD=0.7,
    )

    plan = build_query_focus_plan_from_settings(
        settings=settings,
        query="文件申請期限是多久內？",
    )

    assert plan.applied is True
    assert plan.intents == ("date_or_deadline",)


def test_extract_query_tokens_emits_cjk_bigrams_and_latin_tokens() -> None:
    """query tokenization 應同時支援 CJK bigrams 與英文詞。"""

    tokens = extract_query_tokens(query="身分限制 single-domain")

    assert "身分限制" in tokens
    assert "身分" in tokens
    assert "限制" in tokens
    assert "single-domain" in tokens
