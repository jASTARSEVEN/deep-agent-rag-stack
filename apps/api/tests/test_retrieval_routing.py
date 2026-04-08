"""Query-aware retrieval routing 測試。"""

from uuid import uuid4

from app.auth.verifier import CurrentPrincipal
from app.core.settings import AppSettings
from app.db.models import Area, AreaUserRole, Document, DocumentStatus, EvaluationQueryType, Role
from app.services.retrieval_routing import build_query_routing_decision, classify_query_type


def _uuid() -> str:
    """建立測試用 UUID 字串。"""

    return str(uuid4())


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
    assert decision.summary_strategy == "multi_document_theme"
    assert decision.selected_profile == "document_summary_multi_document_diversified_v1"
    assert decision.effective_settings.retrieval_query_focus_enabled is True
    assert decision.resolved_settings["query_focus_enabled"] is True


def test_build_query_routing_decision_uses_section_focused_for_single_document_section_query(db_session) -> None:
    """單文件摘要且帶 section cue 時應選 `section_focused`。"""

    area = Area(id=_uuid(), name="Routing Area")
    document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="employee-handbook.md",
        content_type="text/markdown",
        file_size=10,
        storage_key="routing/employee-handbook.md",
        status=DocumentStatus.ready,
    )
    db_session.add_all([area, AreaUserRole(area_id=area.id, user_sub="user-reader", role=Role.reader), document])
    db_session.commit()

    decision = build_query_routing_decision(
        settings=AppSettings(),
        query="請摘要 employee handbook 關於 leave policy 的章節",
        session=db_session,
        principal=CurrentPrincipal(sub="user-reader", groups=()),
        area_id=area.id,
    )

    assert decision.summary_scope == "single_document"
    assert decision.summary_strategy == "section_focused"
    assert decision.summary_strategy_source == "section_focus_rule"


def test_build_query_routing_decision_uses_document_overview_for_single_document_summary(db_session) -> None:
    """單文件摘要且未命中 section cue 時應選 `document_overview`。"""

    area = Area(id=_uuid(), name="Routing Overview Area")
    document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="benefits-policy.md",
        content_type="text/markdown",
        file_size=10,
        storage_key="routing/benefits-policy.md",
        status=DocumentStatus.ready,
    )
    db_session.add_all([area, AreaUserRole(area_id=area.id, user_sub="user-reader", role=Role.reader), document])
    db_session.commit()

    decision = build_query_routing_decision(
        settings=AppSettings(),
        query="請摘要 benefits policy",
        session=db_session,
        principal=CurrentPrincipal(sub="user-reader", groups=()),
        area_id=area.id,
    )

    assert decision.summary_scope == "single_document"
    assert decision.summary_strategy == "document_overview"
    assert decision.summary_strategy_source == "single_document_default"
