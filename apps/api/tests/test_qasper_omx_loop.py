"""受控 OMX QASPER loop 判定邏輯測試。"""

from __future__ import annotations

from app.core.settings import AppSettings
from app.scripts.run_qasper_omx_loop import (
    HYPOTHESIS_ASSEMBLER,
    HYPOTHESIS_EVIDENCE_SYNOPSIS,
    HYPOTHESIS_QUERY_FOCUS,
    QASPER_BENCHMARK_WEIGHT,
    SELF_BENCHMARK_WEIGHT,
    build_deterministic_gate_result,
    build_effect_check,
    build_effect_opt,
    build_guard,
    build_implement_result,
    build_rollback_strategy,
)


def _report(*, assembled_recall: float, assembled_ndcg: float, assembled_mrr: float, rerank_recall: float | None = None) -> dict:
    """建立最小 run report payload。

    參數：
    - `assembled_recall`：assembled recall。
    - `assembled_ndcg`：assembled nDCG。
    - `assembled_mrr`：assembled MRR。
    - `rerank_recall`：rerank recall；若未指定則沿用 assembled recall。

    回傳：
    - `dict`：可供 loop helper 使用的最小 report payload。
    """

    rerank_recall_value = assembled_recall if rerank_recall is None else rerank_recall
    return {
        "run": {"id": "run-id", "evaluation_profile": "production_like_v1"},
        "summary_metrics": {
            "assembled": {
                "recall_at_k": assembled_recall,
                "nDCG_at_k": assembled_ndcg,
                "mrr_at_k": assembled_mrr,
                "precision_at_k": 0.1,
                "document_coverage_at_k": 1.0,
            },
            "rerank": {
                "recall_at_k": rerank_recall_value,
                "nDCG_at_k": assembled_ndcg,
                "mrr_at_k": assembled_mrr,
                "precision_at_k": 0.1,
                "document_coverage_at_k": 1.0,
            },
        },
    }


def _compare(*, recall_delta: float, ndcg_delta: float, mrr_delta: float, precision_delta: float = 0.0, doc_delta: float = 0.0) -> dict:
    """建立最小 compare payload。

    參數：
    - `recall_delta`：Recall delta。
    - `ndcg_delta`：nDCG delta。
    - `mrr_delta`：MRR delta。
    - `precision_delta`：Precision delta。
    - `doc_delta`：Doc coverage delta。

    回傳：
    - `dict`：可供 implement 判定使用的 compare payload。
    """

    return {
        "summary_metric_deltas": {
            "assembled": {
                "Recall@k": {"delta": recall_delta},
                "nDCG@k": {"delta": ndcg_delta},
                "MRR@k": {"delta": mrr_delta},
                "Precision@k": {"delta": precision_delta},
                "Doc Coverage@k": {"delta": doc_delta},
            }
        }
    }


def test_effect_check_selects_assembler_lane_when_recall_below_target() -> None:
    """weighted Recall 未達標時應直接選擇 assembler lane。"""

    artifact = build_effect_check(
        baseline_qasper=_report(assembled_recall=0.56, assembled_ndcg=0.45, assembled_mrr=0.41),
        baseline_self=_report(assembled_recall=0.86, assembled_ndcg=0.81, assembled_mrr=0.79),
        target_recall=0.8,
        baseline_profile="production_like_v1",
    )

    assert artifact["main_hypothesis"] == HYPOTHESIS_ASSEMBLER
    assert artifact["candidate_profiles"] == ["generic_guarded_assembler_v1", "generic_guarded_assembler_v2"]
    assert artifact["baseline_metrics"]["weighted"]["weights"] == {
        "self": SELF_BENCHMARK_WEIGHT,
        "qasper": QASPER_BENCHMARK_WEIGHT,
    }


def test_effect_check_stops_when_weighted_recall_reaches_target() -> None:
    """若 weighted baseline Recall 已達標，應不進入 iteration。"""

    artifact = build_effect_check(
        baseline_qasper=_report(assembled_recall=0.70, assembled_ndcg=0.45, assembled_mrr=0.41),
        baseline_self=_report(assembled_recall=0.90, assembled_ndcg=0.81, assembled_mrr=0.79),
        target_recall=0.8,
        baseline_profile="production_like_v1",
    )

    assert artifact["main_hypothesis"] == "no_iteration_needed"
    assert artifact["candidate_profiles"] == []


def test_rollback_strategy_switches_from_assembler_to_evidence_synopsis_lane() -> None:
    """assembler lane rollback 後，應先切到 evidence-synopsis lane。"""

    rethink = build_rollback_strategy(
        effect_check={
            "main_hypothesis": HYPOTHESIS_ASSEMBLER,
            "baseline_profile": "production_like_v1",
            "baseline_metrics": {},
            "target_recall": 0.8,
        },
        attempted_profiles=["generic_guarded_assembler_v1"],
    )

    assert rethink is not None
    assert rethink["main_hypothesis"] == HYPOTHESIS_EVIDENCE_SYNOPSIS
    assert rethink["candidate_profiles"] == [
        "generic_guarded_evidence_synopsis_v1",
        "generic_guarded_evidence_synopsis_v2",
        "generic_guarded_evidence_synopsis_v3",
    ]


def test_rollback_strategy_switches_from_evidence_synopsis_to_query_focus_lane() -> None:
    """evidence-synopsis lane rollback 後，應切到 query-focus lane。"""

    rethink = build_rollback_strategy(
        effect_check={
            "main_hypothesis": HYPOTHESIS_EVIDENCE_SYNOPSIS,
            "baseline_profile": "production_like_v1",
            "baseline_metrics": {},
            "target_recall": 0.8,
        },
        attempted_profiles=["generic_guarded_evidence_synopsis_v1"],
    )

    assert rethink is not None
    assert rethink["main_hypothesis"] == HYPOTHESIS_QUERY_FOCUS
    assert rethink["candidate_profiles"] == ["generic_guarded_query_focus_v1"]


def test_rollback_strategy_stops_after_query_focus_lane() -> None:
    """query-focus lane rollback 後，若無後續 lane 應停止。"""

    rethink = build_rollback_strategy(
        effect_check={
            "main_hypothesis": HYPOTHESIS_QUERY_FOCUS,
            "baseline_profile": "production_like_v1",
            "baseline_metrics": {},
            "target_recall": 0.8,
        },
        attempted_profiles=["generic_guarded_query_focus_v1"],
    )

    assert rethink is None


def test_guard_agent_accepts_active_profile_gated_proposal() -> None:
    """guard-agent 應放行目前保留的受控 profile。"""

    settings = AppSettings()
    effect_check = build_effect_check(
        baseline_qasper=_report(assembled_recall=0.56, assembled_ndcg=0.45, assembled_mrr=0.41),
        baseline_self=_report(assembled_recall=0.86, assembled_ndcg=0.81, assembled_mrr=0.79),
        target_recall=0.8,
        baseline_profile="production_like_v1",
    )
    effect_opt = build_effect_opt(
        iteration_index=1,
        main_hypothesis=effect_check["main_hypothesis"],
        profile_name="generic_guarded_assembler_v1",
        settings=settings,
    )
    advice = {
        "guardrails": [
            "所有 guarded knobs 必須維持在 <= 100。",
            "不得修改 production defaults。",
        ]
    }

    guard = build_guard(effect_check=effect_check, effect_opt=effect_opt, advice=advice)

    assert guard["decision"] == "go"
    assert guard["approved"] is True


def test_guard_agent_allows_assembler_profile_with_large_char_budget() -> None:
    """assembler lane 的 char budget 不應被 count-style <=100 guard 錯誤擋下。"""

    settings = AppSettings()
    effect_opt = build_effect_opt(
        iteration_index=1,
        main_hypothesis=HYPOTHESIS_ASSEMBLER,
        profile_name="generic_guarded_assembler_v1",
        settings=settings,
    )
    advice = {"guardrails": ["所有 guarded knobs 必須維持在 <= 100。"]}

    guard = build_guard(
        effect_check={
            "candidate_profiles": ["generic_guarded_assembler_v1", "generic_guarded_assembler_v2"],
        },
        effect_opt=effect_opt,
        advice=advice,
    )

    assert guard["decision"] == "go"
    assert guard["approved"] is True


def test_guard_agent_blocks_non_generic_retrieval_variants_to_prevent_domain_overfit() -> None:
    """若 candidate profile 想引入非 generic retrieval variant，guard-agent 應直接擋下。"""

    advice = {
        "guardrails": [
            "所有 guarded knobs 必須維持在 <= 100。",
            "不得修改 production defaults。",
            "benchmark 策略不得引入非 generic-first 的 retrieval variants。",
        ]
    }

    guard = build_guard(
        effect_check={
            "candidate_profiles": ["generic_guarded_query_focus_v1"],
        },
        effect_opt={
            "profile_name": "generic_guarded_query_focus_v1",
            "profile_overrides": {
                "retrieval_query_focus_variant": "domain_locked_v1",
                "retrieval_evidence_synopsis_variant": "generic_v1",
            },
        },
        advice=advice,
    )

    assert guard["decision"] == "stop"
    assert guard["approved"] is False
    assert guard["domain_overfit_violations"]
    assert "anti-domain-overfit" in guard["reason"]


def test_deterministic_gate_blocks_live_rerank_until_recall_exceeds_target() -> None:
    """weighted deterministic gate 未達標時，不應直接進 live rerank。"""

    gate = build_deterministic_gate_result(
        iteration_index=1,
        profile_name="generic_guarded_assembler_v1",
        gate_profile_name="generic_guarded_assembler_v1_gate",
        gate_qasper_report=_report(assembled_recall=0.74, assembled_ndcg=0.47, assembled_mrr=0.43),
        gate_self_report=_report(assembled_recall=0.80, assembled_ndcg=0.78, assembled_mrr=0.75),
        target_recall=0.8,
        has_next_iteration=True,
    )

    assert gate["decision"] == "continue"
    assert "跳過 live rerank" in gate["reason"]


def test_deterministic_gate_passes_before_live_rerank_when_recall_exceeds_target() -> None:
    """weighted deterministic gate 達標後才允許進 live rerank。"""

    gate = build_deterministic_gate_result(
        iteration_index=1,
        profile_name="generic_guarded_evidence_synopsis_v2",
        gate_profile_name="generic_guarded_evidence_synopsis_v2_gate",
        gate_qasper_report=_report(assembled_recall=0.82, assembled_ndcg=0.50, assembled_mrr=0.46),
        gate_self_report=_report(assembled_recall=0.90, assembled_ndcg=0.80, assembled_mrr=0.78),
        target_recall=0.8,
        has_next_iteration=True,
    )

    assert gate["decision"] == "pass"
    assert "可進入 live rerank" in gate["reason"]
    assert gate["gate_metrics"]["weighted"]["weights"] == {
        "self": SELF_BENCHMARK_WEIGHT,
        "qasper": QASPER_BENCHMARK_WEIGHT,
    }


def test_implement_result_continues_when_weighted_metrics_improve_but_recall_still_below_target() -> None:
    """若 weighted guardrails 通過但 weighted Recall 仍未達標，應進入下一輪。"""

    result = build_implement_result(
        iteration_index=1,
        profile_name="generic_guarded_evidence_synopsis_v1",
        candidate_qasper=_report(assembled_recall=0.74, assembled_ndcg=0.47, assembled_mrr=0.43),
        candidate_self=_report(assembled_recall=0.79, assembled_ndcg=0.82, assembled_mrr=0.80),
        qasper_compare=_compare(recall_delta=0.18, ndcg_delta=0.02, mrr_delta=0.02),
        self_compare=_compare(recall_delta=0.01, ndcg_delta=0.01, mrr_delta=0.01),
        target_recall=0.8,
        has_next_iteration=True,
    )

    assert result["decision"] == "continue"
    assert result["guardrails_passed"]["weighted"] is True
    assert result["delta_summary"]["weighted"]["Recall@k"] > 0


def test_implement_result_rolls_back_when_weighted_objective_regresses() -> None:
    """若 weighted objective 退化，必須 rollback。"""

    result = build_implement_result(
        iteration_index=1,
        profile_name="generic_guarded_evidence_synopsis_v1",
        candidate_qasper=_report(assembled_recall=0.60, assembled_ndcg=0.44, assembled_mrr=0.40),
        candidate_self=_report(assembled_recall=0.80, assembled_ndcg=0.77, assembled_mrr=0.74),
        qasper_compare=_compare(recall_delta=-0.02, ndcg_delta=-0.01, mrr_delta=-0.01),
        self_compare=_compare(recall_delta=-0.02, ndcg_delta=-0.02, mrr_delta=0.0),
        target_recall=0.8,
        has_next_iteration=True,
    )

    assert result["decision"] == "rollback"
    assert result["guardrails_passed"]["weighted"] is False
    assert "weighted benchmark guardrails" in result["reason"]


def test_implement_result_stops_when_weighted_target_recall_is_reached() -> None:
    """weighted Recall 達標後應停止後續迭代。"""

    result = build_implement_result(
        iteration_index=2,
        profile_name="generic_guarded_evidence_synopsis_v2",
        candidate_qasper=_report(assembled_recall=0.75, assembled_ndcg=0.48, assembled_mrr=0.44),
        candidate_self=_report(assembled_recall=0.85, assembled_ndcg=0.81, assembled_mrr=0.79),
        qasper_compare=_compare(recall_delta=0.26, ndcg_delta=0.03, mrr_delta=0.03),
        self_compare=_compare(recall_delta=0.02, ndcg_delta=0.01, mrr_delta=0.01),
        target_recall=0.8,
        has_next_iteration=False,
    )

    assert result["decision"] == "stop"
    assert result["reason"] == "weighted assembled Recall 已達標，停止後續迭代。"
