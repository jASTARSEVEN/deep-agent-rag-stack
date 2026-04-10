"""Evaluation profile 與 benchmark strategy lane registry 測試。"""

from __future__ import annotations

from app.core.settings import AppSettings
from app.services.evaluation_profiles import (
    GENERIC_GUARDED_ASSEMBLER_V1,
    GENERIC_GUARDED_ASSEMBLER_V1_GATE,
    GENERIC_GUARDED_EVIDENCE_SYNOPSIS_V2,
    GENERIC_GUARDED_EVIDENCE_SYNOPSIS_V2_GATE,
    GENERIC_GUARDED_EVIDENCE_SYNOPSIS_V3,
    GENERIC_GUARDED_EVIDENCE_SYNOPSIS_V3_GATE,
    HYPOTHESIS_ASSEMBLER,
    HYPOTHESIS_EVIDENCE_SYNOPSIS,
    SUPPORTED_EVALUATION_PROFILES,
    get_candidate_profiles_for_hypothesis,
    get_evaluation_profile_overrides,
    get_gate_profile_for_profile,
    get_rollback_target_hypothesis,
)


def test_profile_registry_exposes_supported_profiles() -> None:
    """支援的 evaluation profiles 應由單一 registry 提供。"""

    assert "production_like_v1" in SUPPORTED_EVALUATION_PROFILES
    assert GENERIC_GUARDED_ASSEMBLER_V1 in SUPPORTED_EVALUATION_PROFILES
    assert GENERIC_GUARDED_ASSEMBLER_V1_GATE in SUPPORTED_EVALUATION_PROFILES
    assert GENERIC_GUARDED_EVIDENCE_SYNOPSIS_V3 in SUPPORTED_EVALUATION_PROFILES
    assert GENERIC_GUARDED_EVIDENCE_SYNOPSIS_V3_GATE in SUPPORTED_EVALUATION_PROFILES


def test_gate_profile_inherits_live_profile_overrides() -> None:
    """gate profile 應繼承 live profile 並額外改成 deterministic rerank。"""

    settings = AppSettings()

    live_overrides = get_evaluation_profile_overrides(
        settings=settings,
        evaluation_profile=GENERIC_GUARDED_EVIDENCE_SYNOPSIS_V2,
    )
    gate_overrides = get_evaluation_profile_overrides(
        settings=settings,
        evaluation_profile=GENERIC_GUARDED_EVIDENCE_SYNOPSIS_V2_GATE,
    )

    assert gate_overrides["rerank_provider"] == "deterministic"
    assert gate_overrides["rerank_top_n"] == live_overrides["rerank_top_n"]
    assert gate_overrides["retrieval_evidence_synopsis_enabled"] is True


def test_v3_profile_keeps_generic_variant_with_sweet_spot_budget() -> None:
    """v3 profile 應維持 generic variant，並鎖定 sweet-spot assembler budget。"""

    settings = AppSettings()

    overrides = get_evaluation_profile_overrides(
        settings=settings,
        evaluation_profile=GENERIC_GUARDED_EVIDENCE_SYNOPSIS_V3,
    )
    gate_overrides = get_evaluation_profile_overrides(
        settings=settings,
        evaluation_profile=GENERIC_GUARDED_EVIDENCE_SYNOPSIS_V3_GATE,
    )

    assert overrides["retrieval_evidence_synopsis_enabled"] is True
    assert overrides["retrieval_evidence_synopsis_variant"] == "generic_v1"
    assert overrides["assembler_max_contexts"] == 9
    assert overrides["assembler_max_chars_per_context"] == 3000
    assert gate_overrides["retrieval_evidence_synopsis_variant"] == "generic_v1"
    assert gate_overrides["rerank_provider"] == "deterministic"


def test_strategy_lane_registry_provides_profile_sequence_and_rollback_target() -> None:
    """strategy lane 應由 registry 提供 profile 順序與 rollback 目標。"""

    assert get_candidate_profiles_for_hypothesis(main_hypothesis=HYPOTHESIS_ASSEMBLER) == [
        "generic_guarded_assembler_v1",
        "generic_guarded_assembler_v2",
    ]
    assert get_candidate_profiles_for_hypothesis(main_hypothesis=HYPOTHESIS_EVIDENCE_SYNOPSIS) == [
        "generic_guarded_evidence_synopsis_v1",
        "generic_guarded_evidence_synopsis_v2",
        "generic_guarded_evidence_synopsis_v3",
    ]
    assert get_gate_profile_for_profile(profile_name=GENERIC_GUARDED_ASSEMBLER_V1) == GENERIC_GUARDED_ASSEMBLER_V1_GATE
    assert get_rollback_target_hypothesis(main_hypothesis=HYPOTHESIS_ASSEMBLER) == HYPOTHESIS_EVIDENCE_SYNOPSIS
    assert get_rollback_target_hypothesis(main_hypothesis=HYPOTHESIS_EVIDENCE_SYNOPSIS) is None
