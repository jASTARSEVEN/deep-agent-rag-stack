"""Evaluation profile 與 benchmark strategy lane registry 測試。"""

from __future__ import annotations

from app.core.settings import AppSettings
from app.services.evaluation_profiles import (
    HYPOTHESIS_ASSEMBLER,
    HYPOTHESIS_EVIDENCE_SYNOPSIS,
    HYPOTHESIS_QUERY_FOCUS,
    QASPER_GUARDED_ASSEMBLER_V1,
    QASPER_GUARDED_ASSEMBLER_V1_GATE,
    QASPER_GUARDED_EVIDENCE_SYNOPSIS_V2,
    QASPER_GUARDED_EVIDENCE_SYNOPSIS_V2_GATE,
    QASPER_GUARDED_EVIDENCE_SYNOPSIS_V3,
    QASPER_GUARDED_EVIDENCE_SYNOPSIS_V3_GATE,
    QASPER_GUARDED_QUERY_FOCUS_BUDGET_6X3000,
    QASPER_GUARDED_QUERY_FOCUS_V1,
    QASPER_GUARDED_QUERY_FOCUS_V1_GATE,
    SUPPORTED_EVALUATION_PROFILES,
    get_candidate_profiles_for_hypothesis,
    get_evaluation_profile_overrides,
    get_gate_profile_for_profile,
    get_rollback_target_hypothesis,
)


def test_profile_registry_exposes_supported_profiles() -> None:
    """支援的 evaluation profiles 應由單一 registry 提供。"""

    assert "production_like_v1" in SUPPORTED_EVALUATION_PROFILES
    assert QASPER_GUARDED_ASSEMBLER_V1 in SUPPORTED_EVALUATION_PROFILES
    assert QASPER_GUARDED_ASSEMBLER_V1_GATE in SUPPORTED_EVALUATION_PROFILES
    assert QASPER_GUARDED_EVIDENCE_SYNOPSIS_V3 in SUPPORTED_EVALUATION_PROFILES
    assert QASPER_GUARDED_EVIDENCE_SYNOPSIS_V3_GATE in SUPPORTED_EVALUATION_PROFILES
    assert QASPER_GUARDED_QUERY_FOCUS_V1 in SUPPORTED_EVALUATION_PROFILES
    assert QASPER_GUARDED_QUERY_FOCUS_V1_GATE in SUPPORTED_EVALUATION_PROFILES
    assert QASPER_GUARDED_QUERY_FOCUS_BUDGET_6X3000 in SUPPORTED_EVALUATION_PROFILES


def test_gate_profile_inherits_live_profile_overrides() -> None:
    """gate profile 應繼承 live profile 並額外改成 deterministic rerank。"""

    settings = AppSettings()

    live_overrides = get_evaluation_profile_overrides(
        settings=settings,
        evaluation_profile=QASPER_GUARDED_EVIDENCE_SYNOPSIS_V2,
    )
    gate_overrides = get_evaluation_profile_overrides(
        settings=settings,
        evaluation_profile=QASPER_GUARDED_EVIDENCE_SYNOPSIS_V2_GATE,
    )

    assert gate_overrides["rerank_provider"] == "deterministic"
    assert gate_overrides["rerank_top_n"] == live_overrides["rerank_top_n"]
    assert gate_overrides["retrieval_evidence_synopsis_enabled"] is True


def test_v3_profile_enables_qasper_v3_variant() -> None:
    """v3 profile 應在維持 v2 knobs 下啟用 qasper_v3 variant。"""

    settings = AppSettings()

    overrides = get_evaluation_profile_overrides(
        settings=settings,
        evaluation_profile=QASPER_GUARDED_EVIDENCE_SYNOPSIS_V3,
    )
    gate_overrides = get_evaluation_profile_overrides(
        settings=settings,
        evaluation_profile=QASPER_GUARDED_EVIDENCE_SYNOPSIS_V3_GATE,
    )

    assert overrides["retrieval_evidence_synopsis_enabled"] is True
    assert overrides["retrieval_evidence_synopsis_variant"] == "qasper_v3"
    assert gate_overrides["retrieval_evidence_synopsis_variant"] == "qasper_v3"
    assert gate_overrides["rerank_provider"] == "deterministic"


def test_query_focus_profile_extends_v3_with_query_focus_knobs() -> None:
    """query focus profile 應在 v3 基礎上開啟 query focus knobs。"""

    settings = AppSettings()

    overrides = get_evaluation_profile_overrides(
        settings=settings,
        evaluation_profile=QASPER_GUARDED_QUERY_FOCUS_V1,
    )
    gate_overrides = get_evaluation_profile_overrides(
        settings=settings,
        evaluation_profile=QASPER_GUARDED_QUERY_FOCUS_V1_GATE,
    )

    assert overrides["retrieval_evidence_synopsis_variant"] == "qasper_v3"
    assert overrides["retrieval_query_focus_enabled"] is True
    assert overrides["retrieval_query_focus_variant"] == "query_focus_v1"
    assert overrides["retrieval_query_focus_confidence_threshold"] == 0.7
    assert overrides["assembler_max_contexts"] == 9
    assert overrides["assembler_max_chars_per_context"] == 3000
    assert gate_overrides["rerank_provider"] == "deterministic"
    assert gate_overrides["retrieval_query_focus_enabled"] is True


def test_strategy_lane_registry_provides_profile_sequence_and_rollback_target() -> None:
    """strategy lane 應由 registry 提供 profile 順序與 rollback 目標。"""

    assert get_candidate_profiles_for_hypothesis(main_hypothesis=HYPOTHESIS_ASSEMBLER) == [
        "qasper_guarded_assembler_v1",
        "qasper_guarded_assembler_v2",
    ]
    assert get_candidate_profiles_for_hypothesis(main_hypothesis=HYPOTHESIS_EVIDENCE_SYNOPSIS) == [
        "qasper_guarded_evidence_synopsis_v1",
        "qasper_guarded_evidence_synopsis_v2",
        "qasper_guarded_evidence_synopsis_v3",
    ]
    assert get_candidate_profiles_for_hypothesis(main_hypothesis=HYPOTHESIS_QUERY_FOCUS) == [
        "qasper_guarded_query_focus_v1",
    ]
    assert get_gate_profile_for_profile(profile_name=QASPER_GUARDED_ASSEMBLER_V1) == QASPER_GUARDED_ASSEMBLER_V1_GATE
    assert get_rollback_target_hypothesis(main_hypothesis=HYPOTHESIS_ASSEMBLER) == HYPOTHESIS_EVIDENCE_SYNOPSIS
    assert get_rollback_target_hypothesis(main_hypothesis=HYPOTHESIS_EVIDENCE_SYNOPSIS) == HYPOTHESIS_QUERY_FOCUS
    assert get_rollback_target_hypothesis(main_hypothesis=HYPOTHESIS_QUERY_FOCUS) is None


def test_query_focus_budget_profiles_only_tighten_assembler_budget() -> None:
    """query focus 成本 profile 應只改 assembler budget，並保留 query focus 主線設定。"""

    settings = AppSettings()
    overrides = get_evaluation_profile_overrides(
        settings=settings,
        evaluation_profile=QASPER_GUARDED_QUERY_FOCUS_BUDGET_6X3000,
    )

    assert overrides["retrieval_query_focus_enabled"] is True
    assert overrides["retrieval_query_focus_variant"] == "query_focus_v1"
    assert overrides["retrieval_evidence_synopsis_variant"] == "qasper_v3"
    assert overrides["assembler_max_contexts"] == 6
    assert overrides["assembler_max_chars_per_context"] == 3000
    assert overrides["assembler_max_children_per_parent"] == settings.assembler_max_children_per_parent
    assert overrides["rerank_top_n"] == settings.rerank_top_n
