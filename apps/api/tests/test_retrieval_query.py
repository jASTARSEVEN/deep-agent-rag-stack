"""query focus planner 與 query tokenization 測試。"""

from __future__ import annotations

from app.core.settings import AppSettings
from app.services.retrieval_query import build_query_focus_plan, build_query_focus_plan_from_settings, extract_query_tokens


def test_query_focus_plan_detects_deadline_query_in_traditional_chinese() -> None:
    """繁中申請時間題應命中 deadline intent。"""

    plan = build_query_focus_plan(
        query="保單更約權的申請時間",
        enabled=True,
        variant="query_focus_v1",
        confidence_threshold=0.7,
    )

    assert plan.applied is True
    assert plan.language == "zh-TW"
    assert plan.intents == ("deadline",)
    assert plan.slots["target_field"] == "申請時間"
    assert "申請時間" in plan.focus_query
    assert "Need:" in plan.rerank_query


def test_query_focus_plan_detects_eligibility_query_in_traditional_chinese() -> None:
    """繁中身分限制題應命中 eligibility_identity intent。"""

    plan = build_query_focus_plan(
        query="網路保險申請保單借款的身分限制",
        enabled=True,
        variant="query_focus_v1",
        confidence_threshold=0.7,
    )

    assert plan.applied is True
    assert plan.intents == ("eligibility_identity",)
    assert plan.slots["action"] == "申請"
    assert "身分限制" in plan.focus_query
    assert "保單借款" in plan.focus_query


def test_query_focus_plan_detects_amount_max_query_in_traditional_chinese() -> None:
    """繁中最高投保金額題應命中 amount_max intent。"""

    plan = build_query_focus_plan(
        query="保利美美元利率變動型終身壽險其累計最高投保金額為何?",
        enabled=True,
        variant="query_focus_v1",
        confidence_threshold=0.7,
    )

    assert plan.applied is True
    assert plan.intents == ("amount_max",)
    assert plan.slots["target_field"] == "最高投保金額"
    assert "投保金額" in plan.focus_query


def test_query_focus_plan_detects_age_and_payment_term_query_in_traditional_chinese() -> None:
    """繁中投保年齡與年期題應同時命中 age_range 與 payment_term。"""

    plan = build_query_focus_plan(
        query="新傳承富利利率變動型終身壽險幾歲可以投保？各年期的限制是什麼？",
        enabled=True,
        variant="query_focus_v1",
        confidence_threshold=0.7,
    )

    assert plan.applied is True
    assert plan.intents == ("age_range", "payment_term")
    assert plan.slots["product_name"] == "新傳承富利利率變動型終身壽險"
    assert "投保年齡" in plan.focus_query
    assert "繳費年期" in plan.focus_query


def test_query_focus_plan_detects_total_count_query_in_english() -> None:
    """英文 total count 題應命中 count_total intent。"""

    plan = build_query_focus_plan(
        query="How many reviews in total (both generated and true) do they evaluate on Amazon Mechanical Turk?",
        enabled=True,
        variant="query_focus_v1",
        confidence_threshold=0.7,
    )

    assert plan.applied is True
    assert plan.language == "en"
    assert plan.intents == ("count_total",)
    assert plan.slots["target_field"] == "total count"
    assert "reviews" in plan.focus_query
    assert "exact total count evidence" in plan.rerank_query


def test_query_focus_plan_detects_comparison_axis_query_in_english() -> None:
    """英文比較題應命中 comparison_axis intent。"""

    plan = build_query_focus_plan(
        query="Does this approach perform better in the multi-domain or single-domain setting?",
        enabled=True,
        variant="query_focus_v1",
        confidence_threshold=0.7,
    )

    assert plan.applied is True
    assert plan.intents == ("comparison_axis",)
    assert plan.slots["target_field"] == "comparison result"
    assert "single-domain" in plan.focus_query
    assert "multi-domain" in plan.focus_query


def test_query_focus_plan_does_not_apply_to_low_confidence_query() -> None:
    """低信心 query 不應套用 query focus。"""

    plan = build_query_focus_plan(
        query="alpha",
        enabled=True,
        variant="query_focus_v1",
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
        RETRIEVAL_QUERY_FOCUS_VARIANT="query_focus_v1",
        RETRIEVAL_QUERY_FOCUS_CONFIDENCE_THRESHOLD=0.7,
    )

    plan = build_query_focus_plan_from_settings(
        settings=settings,
        query="保單更約權的申請時間",
    )

    assert plan.applied is True
    assert plan.intents == ("deadline",)


def test_extract_query_tokens_emits_cjk_bigrams_and_latin_tokens() -> None:
    """query tokenization 應同時支援 CJK bigrams 與英文詞。"""

    tokens = extract_query_tokens(query="身分限制 single-domain")

    assert "身分限制" in tokens
    assert "身分" in tokens
    assert "限制" in tokens
    assert "single-domain" in tokens
