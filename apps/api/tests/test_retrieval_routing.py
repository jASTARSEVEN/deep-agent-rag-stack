"""Query-aware retrieval routing 測試。"""

from app.core.settings import AppSettings
from app.db.models import EvaluationQueryType
from app.services.retrieval_routing import build_query_routing_decision, classify_query_type


def test_classifier_detects_document_summary_in_traditional_chinese() -> None:
    """中文摘要 cue 應被分類為 document summary。

    參數：
    - 無。

    回傳：
    - `None`：以斷言驗證分類結果。
    """

    result = classify_query_type(query="請幫我摘要這份政策的重點")

    assert result.query_type == EvaluationQueryType.document_summary
    assert result.language == "zh-TW"
    assert result.source == "classified"
    assert "摘要" in result.matched_rules


def test_classifier_detects_cross_document_compare_in_english() -> None:
    """英文 compare cue 應被分類為 cross-document compare。

    參數：
    - 無。

    回傳：
    - `None`：以斷言驗證分類結果。
    """

    result = classify_query_type(query="Compare the onboarding policy versus the security policy")

    assert result.query_type == EvaluationQueryType.cross_document_compare
    assert result.language == "en"
    assert result.source == "classified"
    assert any(rule in result.matched_rules for rule in ("Compare", "compare", "versus"))


def test_classifier_falls_back_to_fact_lookup_for_ambiguous_query() -> None:
    """未命中摘要/比較 cues 時應回退到 fact lookup。

    參數：
    - 無。

    回傳：
    - `None`：以斷言驗證 fallback 行為。
    """

    result = classify_query_type(query="保單申請資格是什麼")

    assert result.query_type == EvaluationQueryType.fact_lookup
    assert result.source == "fallback"
    assert result.confidence == 0.0
    assert result.matched_rules == ()


def test_build_query_routing_decision_respects_explicit_query_type() -> None:
    """明示題型時應直接採用該題型，且 query focus 維持停用。

    參數：
    - 無。

    回傳：
    - `None`：以斷言驗證 routing 決策與有效設定。
    """

    settings = AppSettings()

    decision = build_query_routing_decision(
        settings=settings,
        query="請整理這份文件",
        explicit_query_type=EvaluationQueryType.cross_document_compare,
    )

    assert decision.query_type == EvaluationQueryType.cross_document_compare
    assert decision.source == "explicit"
    assert decision.selected_profile == "cross_document_compare_diversified_v1"
    assert decision.summary_scope is None
    assert decision.effective_settings.retrieval_query_focus_enabled is False
    assert decision.resolved_settings["query_focus_enabled"] is False


def test_build_query_routing_decision_keeps_query_focus_env_toggle() -> None:
    """routing/profile 應保留由 env settings 控制的 query focus 開關。"""

    settings = AppSettings(RETRIEVAL_QUERY_FOCUS_ENABLED=True)

    decision = build_query_routing_decision(
        settings=settings,
        query="summary this document",
    )

    assert decision.query_type == EvaluationQueryType.document_summary
    assert decision.summary_scope == "multi_document"
    assert decision.selected_profile == "document_summary_multi_document_diversified_v1"
    assert decision.effective_settings.retrieval_query_focus_enabled is True
    assert decision.resolved_settings["query_focus_enabled"] is True
