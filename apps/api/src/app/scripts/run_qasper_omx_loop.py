"""執行受控 OMX QASPER 五-agent loop 的 CLI 與 helper。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from app.auth.verifier import CurrentPrincipal
from app.core.settings import AppSettings, get_settings
from app.db.session import create_database_engine, create_session_factory
from app.scripts.compare_benchmark_runs import compare_reports, load_report_from_run_id, read_report_json
from app.services.evaluation_dataset import create_evaluation_run, get_evaluation_run_report
from app.services.evaluation_profiles import (
    HYPOTHESIS_ASSEMBLER,
    HYPOTHESIS_EVIDENCE_SYNOPSIS,
    HYPOTHESIS_QUERY_FOCUS,
    HYPOTHESIS_NONE,
    PRODUCTION_LIKE_V1,
    get_candidate_profiles_for_hypothesis,
    get_evaluation_profile_overrides,
    get_gate_profile_for_profile,
    get_rollback_target_hypothesis,
)
from app.services.retrieval_query import QUERY_FOCUS_VARIANT_GENERIC_FIELD_V1
from app.services.retrieval_text import EVIDENCE_SYNOPSIS_VARIANT_GENERIC_V1

# 內建的 QASPER pilot dataset 識別碼。
DEFAULT_QASPER_DATASET_ID = "db6d581c-2feb-5914-afb8-b4f1fa2092e2"
# 內建的自家 benchmark dataset 識別碼。
DEFAULT_SELF_DATASET_ID = "bb10c343-7d7c-4ae3-b78b-a513759867f2"
# QASPER pilot reference run id。
DEFAULT_QASPER_REFERENCE_RUN_ID = "6f1150df-1343-4905-a417-7334ea87c9d6"
# repo 根目錄；用於推導 reference report 預設路徑。
REPO_ROOT = Path(__file__).resolve().parents[3]
# 自家 benchmark reference report 路徑。
DEFAULT_SELF_REFERENCE_REPORT = REPO_ROOT / "benchmarks" / "tw-insurance-rag-benchmark-v1" / "reference_run_report.json"
# 自家 benchmark 在 weighted strategy 中的權重。
SELF_BENCHMARK_WEIGHT = 0.6
# QASPER benchmark 在 weighted strategy 中的權重。
QASPER_BENCHMARK_WEIGHT = 0.4


def _collect_domain_overfit_violations(*, profile_overrides: dict[str, Any]) -> list[str]:
    """檢查 candidate profile 是否違反 anti-domain-overfit guardrail。

    參數：
    - `profile_overrides`：candidate profile 的設定覆寫。

    回傳：
    - `list[str]`：所有違規原因；若為空代表通過 generic-first 檢查。
    """

    violations: list[str] = []
    evidence_variant = profile_overrides.get("retrieval_evidence_synopsis_variant")
    if isinstance(evidence_variant, str) and evidence_variant != EVIDENCE_SYNOPSIS_VARIANT_GENERIC_V1:
        violations.append(
            "retrieval_evidence_synopsis_variant 必須維持 generic_v1，避免以 benchmark-specific wording 造成 domain overfit。"
        )

    query_focus_variant = profile_overrides.get("retrieval_query_focus_variant")
    if isinstance(query_focus_variant, str) and query_focus_variant != QUERY_FOCUS_VARIANT_GENERIC_FIELD_V1:
        violations.append(
            "retrieval_query_focus_variant 必須維持 generic_field_focus_v1，避免以 domain-specific query rewrite 造成 domain overfit。"
        )
    return violations


def _candidate_profiles_for_hypothesis(*, main_hypothesis: str) -> list[str]:
    """依主假設回傳對應的受控 profile 順序。

    參數：
    - `main_hypothesis`：本輪唯一主假設。

    回傳：
    - `list[str]`：此主假設對應的 candidate profile 順序。
    """

    return get_candidate_profiles_for_hypothesis(main_hypothesis=main_hypothesis)


def _gate_profile_for_profile(*, profile_name: str) -> str:
    """將 live guarded profile 映射為 deterministic gate profile。

    參數：
    - `profile_name`：live guarded profile 名稱。

    回傳：
    - `str`：對應的 deterministic gate profile 名稱。
    """

    return get_gate_profile_for_profile(profile_name=profile_name)


def _assembled_metric(*, report_payload: dict[str, Any], metric_name: str) -> float | None:
    """讀取單一 report 的 assembled metric。

    參數：
    - `report_payload`：run report payload。
    - `metric_name`：assembled schema key，例如 `recall_at_k`。

    回傳：
    - `float | None`：metric 值；若缺少則回傳 `None`。
    """

    value = report_payload.get("summary_metrics", {}).get("assembled", {}).get(metric_name)
    return float(value) if isinstance(value, (int, float)) else None


def _delta(*, compare_payload: dict[str, Any], metric_name: str) -> float | None:
    """讀取 compare payload 中 assembled stage 的單一 delta。

    參數：
    - `compare_payload`：`compare_reports()` 的輸出。
    - `metric_name`：顯示用 metric 名稱，例如 `Recall@k`。

    回傳：
    - `float | None`：對應 delta；若缺少則回傳 `None`。
    """

    value = compare_payload.get("summary_metric_deltas", {}).get("assembled", {}).get(metric_name, {}).get("delta")
    return float(value) if isinstance(value, (int, float)) else None


def _weighted_value(*, qasper_value: float | None, self_value: float | None) -> float:
    """依固定 benchmark 權重計算單一加權數值。

    參數：
    - `qasper_value`：QASPER 指標值；若缺少視為 `0.0`。
    - `self_value`：自家 benchmark 指標值；若缺少視為 `0.0`。

    回傳：
    - `float`：依 `self=0.6`、`qasper=0.4` 計算後的加權值。
    """

    return (SELF_BENCHMARK_WEIGHT * (self_value or 0.0)) + (QASPER_BENCHMARK_WEIGHT * (qasper_value or 0.0))


def _weighted_assembled_metric(
    *,
    qasper_report: dict[str, Any],
    self_report: dict[str, Any],
    metric_name: str,
) -> float:
    """讀取兩個 benchmark 的 assembled metric 並計算加權值。

    參數：
    - `qasper_report`：QASPER run report payload。
    - `self_report`：自家 benchmark run report payload。
    - `metric_name`：assembled schema key，例如 `recall_at_k`。

    回傳：
    - `float`：加權後 assembled metric。
    """

    return _weighted_value(
        qasper_value=_assembled_metric(report_payload=qasper_report, metric_name=metric_name),
        self_value=_assembled_metric(report_payload=self_report, metric_name=metric_name),
    )


def _weighted_metric_delta(
    *,
    qasper_compare: dict[str, Any],
    self_compare: dict[str, Any],
    metric_name: str,
) -> float:
    """讀取兩個 benchmark 的 assembled delta 並計算加權值。

    參數：
    - `qasper_compare`：QASPER compare payload。
    - `self_compare`：自家 benchmark compare payload。
    - `metric_name`：顯示用 metric 名稱，例如 `Recall@k`。

    回傳：
    - `float`：加權後的 delta 值。
    """

    return _weighted_value(
        qasper_value=_delta(compare_payload=qasper_compare, metric_name=metric_name),
        self_value=_delta(compare_payload=self_compare, metric_name=metric_name),
    )


def _json_dumps(payload: dict[str, Any]) -> str:
    """將 payload 序列化為格式化 JSON。

    參數：
    - `payload`：待序列化資料。

    回傳：
    - `str`：格式化 JSON 字串。
    """

    return json.dumps(payload, ensure_ascii=False, indent=2)


def _write_artifact(*, path: Path | None, payload: dict[str, Any]) -> None:
    """將 artifact 寫到指定檔案。

    參數：
    - `path`：輸出檔案路徑；若為 `None` 則略過。
    - `payload`：要寫出的 JSON payload。

    回傳：
    - `None`：直接寫檔。
    """

    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_json_dumps(payload), encoding="utf-8")


def build_effect_check(
    *,
    baseline_qasper: dict[str, Any],
    baseline_self: dict[str, Any],
    target_recall: float,
    baseline_profile: str,
) -> dict[str, Any]:
    """建立 effect-check artifact。

    參數：
    - `baseline_qasper`：QASPER baseline run report。
    - `baseline_self`：自家 benchmark baseline run report。
    - `target_recall`：本輪目標 recall 門檻。
    - `baseline_profile`：baseline 使用的 evaluation profile。

    回傳：
    - `dict[str, Any]`：effect-check artifact。
    """

    weighted_assembled_recall = _weighted_assembled_metric(
        qasper_report=baseline_qasper,
        self_report=baseline_self,
        metric_name="recall_at_k",
    )
    if weighted_assembled_recall >= target_recall:
        main_hypothesis = HYPOTHESIS_NONE
        candidate_profiles: list[str] = []
    else:
        main_hypothesis = HYPOTHESIS_ASSEMBLER
        candidate_profiles = _candidate_profiles_for_hypothesis(main_hypothesis=main_hypothesis)

    return {
        "role": "effect-check",
        "baseline_profile": baseline_profile,
        "baseline_metrics": {
            "qasper": baseline_qasper.get("summary_metrics", {}),
            "self": baseline_self.get("summary_metrics", {}),
            "weighted": {
                "assembled": {
                    "recall_at_k": weighted_assembled_recall,
                    "nDCG_at_k": _weighted_assembled_metric(
                        qasper_report=baseline_qasper,
                        self_report=baseline_self,
                        metric_name="nDCG_at_k",
                    ),
                    "mrr_at_k": _weighted_assembled_metric(
                        qasper_report=baseline_qasper,
                        self_report=baseline_self,
                        metric_name="mrr_at_k",
                    ),
                    "precision_at_k": _weighted_assembled_metric(
                        qasper_report=baseline_qasper,
                        self_report=baseline_self,
                        metric_name="precision_at_k",
                    ),
                    "document_coverage_at_k": _weighted_assembled_metric(
                        qasper_report=baseline_qasper,
                        self_report=baseline_self,
                        metric_name="document_coverage_at_k",
                    ),
                },
                "weights": {
                    "self": SELF_BENCHMARK_WEIGHT,
                    "qasper": QASPER_BENCHMARK_WEIGHT,
                },
            },
        },
        "main_hypothesis": main_hypothesis,
        "candidate_profiles": candidate_profiles,
        "target_recall": target_recall,
    }


def build_rollback_strategy(
    *,
    effect_check: dict[str, Any],
    attempted_profiles: list[str],
) -> dict[str, Any] | None:
    """在 rollback 後推導下一個可嘗試的替代策略。

    參數：
    - `effect_check`：當前 lane 的 effect-check artifact。
    - `attempted_profiles`：目前已嘗試過的 guarded profiles。

    回傳：
    - `dict[str, Any] | None`：若存在可行替代策略，回傳新的 effect-check-like artifact；否則回傳 `None`。
    """

    current_hypothesis = effect_check.get("main_hypothesis")
    if current_hypothesis == HYPOTHESIS_NONE:
        return None

    next_hypothesis = get_rollback_target_hypothesis(main_hypothesis=current_hypothesis)
    if next_hypothesis == HYPOTHESIS_EVIDENCE_SYNOPSIS:
        reason = "assembler lane rollback，改以 evidence-synopsis lane 作為下一輪單一主假設。"
    elif next_hypothesis == HYPOTHESIS_QUERY_FOCUS:
        reason = "evidence-synopsis lane rollback，改以 query-focus lane 作為下一輪單一主假設。"
    elif next_hypothesis is None:
        return None

    remaining_profiles = [
        profile
        for profile in _candidate_profiles_for_hypothesis(main_hypothesis=next_hypothesis)
        if profile not in attempted_profiles
    ]
    if not remaining_profiles:
        return None

    return {
        "role": "effect-check",
        "baseline_profile": effect_check.get("baseline_profile"),
        "baseline_metrics": effect_check.get("baseline_metrics", {}),
        "main_hypothesis": next_hypothesis,
        "candidate_profiles": remaining_profiles,
        "target_recall": effect_check.get("target_recall"),
        "rollback_rethink": True,
        "reason": reason,
    }


def build_effect_opt(
    *,
    iteration_index: int,
    main_hypothesis: str,
    profile_name: str,
    settings: AppSettings,
) -> dict[str, Any]:
    """建立 effect-opt artifact。

    參數：
    - `iteration_index`：目前 iteration 序號。
    - `main_hypothesis`：本輪唯一主假設。
    - `profile_name`：本輪要嘗試的 guarded profile。
    - `settings`：目前 app settings。

    回傳：
    - `dict[str, Any]`：effect-opt artifact。
    """

    return {
        "role": "effect-opt",
        "iteration": iteration_index,
        "main_hypothesis": main_hypothesis,
        "profile_name": profile_name,
        "gate_profile_name": _gate_profile_for_profile(profile_name=profile_name),
        "profile_overrides": get_evaluation_profile_overrides(settings=settings, evaluation_profile=profile_name),
        "expected_improvement": "提升 weighted benchmark objective（self=0.6, qasper=0.4），並維持受控 guardrails。",
        "explicit_non_goals": [
            "不修改 production defaults",
            "不修改 chunking",
            "不修改 query normalization",
            "不修改 rerank structure",
            "不以 benchmark-specific wording 或 query rewrite 換取分數",
            "不修改 benchmark gold spans 或 alignment artifacts",
        ],
    }


def build_advice(*, effect_opt: dict[str, Any]) -> dict[str, Any]:
    """建立 advice-agent artifact。

    參數：
    - `effect_opt`：effect-opt artifact。

    回傳：
    - `dict[str, Any]`：advice-agent artifact。
    """

    return {
        "role": "advice-agent",
        "support_points": [
            "本輪變更維持在 benchmark/profile-gated lane。",
            "會先經過 deterministic gate，再決定是否進入 live rerank。",
            "可由 config snapshot 明確追蹤調整來源。",
        ],
        "risk_points": [
            "若提升主要來自拉高候選數，可能只是以成本換分數。",
            "真實 provider 可能因 429 進入 fail-open fallback。",
            "若 candidate profile 引入 domain-specific wording 或 query rewrite，應直接視為 domain overfit 失敗。",
        ],
        "guardrails": [
            "所有 guarded knobs 必須維持在 <= 100。",
            "不得修改 production defaults。",
            "benchmark 策略不得引入非 generic-first 的 retrieval variants。",
        ],
        "reviewed_profile": effect_opt["profile_name"],
    }


def build_guard(*, effect_check: dict[str, Any], effect_opt: dict[str, Any], advice: dict[str, Any]) -> dict[str, Any]:
    """建立 implement 前的 guard-agent 判定。

    參數：
    - `effect_check`：effect-check artifact。
    - `effect_opt`：effect-opt artifact。
    - `advice`：advice-agent artifact。

    回傳：
    - `dict[str, Any]`：guard-agent 判定結果。
    """

    allowed_profiles = set(effect_check.get("candidate_profiles", []))
    overrides = effect_opt.get("profile_overrides", {})
    bounded_keys = {
        "retrieval_vector_top_k",
        "retrieval_fts_top_k",
        "retrieval_max_candidates",
        "rerank_top_n",
        "assembler_max_contexts",
        "assembler_max_children_per_parent",
    }
    bounded = all(
        key not in bounded_keys or not isinstance(value, int) or value <= 100
        for key, value in overrides.items()
    )
    domain_overfit_violations = _collect_domain_overfit_violations(profile_overrides=overrides)
    generic_first = not domain_overfit_violations
    approved = effect_opt.get("profile_name") in allowed_profiles and bounded and generic_first
    return {
        "role": "guard-agent",
        "decision": "go" if approved else "stop",
        "approved": approved,
        "reason": (
            "候選 profile 位於批准 lane、guarded overrides 未超出上限，且通過 anti-domain-overfit generic-first 檢查。"
            if approved
            else (
                "候選 profile 違反 anti-domain-overfit generic-first guardrail。"
                if not generic_first
                else "候選 profile 不在批准 lane，或 guarded overrides 超出上限。"
            )
        ),
        "allowed_scope": sorted(overrides.keys()),
        "guardrails": advice.get("guardrails", []),
        "domain_overfit_violations": domain_overfit_violations,
    }


def build_deterministic_gate_result(
    *,
    iteration_index: int,
    profile_name: str,
    gate_profile_name: str,
    gate_qasper_report: dict[str, Any],
    gate_self_report: dict[str, Any],
    target_recall: float,
    has_next_iteration: bool,
) -> dict[str, Any]:
    """建立 deterministic gate artifact。

    參數：
    - `iteration_index`：目前 iteration 序號。
    - `profile_name`：原始 live profile 名稱。
    - `gate_profile_name`：deterministic gate profile 名稱。
    - `gate_qasper_report`：QASPER gate run report。
    - `gate_self_report`：自家 benchmark gate run report。
    - `target_recall`：目標 recall 門檻。
    - `has_next_iteration`：後面是否仍有其他 profile/lane 可測。

    回傳：
    - `dict[str, Any]`：gate artifact。
    """

    weighted_gate_recall = _weighted_assembled_metric(
        qasper_report=gate_qasper_report,
        self_report=gate_self_report,
        metric_name="recall_at_k",
    )
    if weighted_gate_recall > target_recall:
        decision = "pass"
        reason = "weighted deterministic gate 已通過，可進入 live rerank。"
    elif has_next_iteration:
        decision = "continue"
        reason = "weighted deterministic gate 未達 Recall 目標，跳過 live rerank，改試下一個 profile。"
    else:
        decision = "rollback"
        reason = "weighted deterministic gate 未達 Recall 目標，且已無同 lane 下一個 profile。"

    return {
        "role": "deterministic-gate",
        "iteration": iteration_index,
        "profile_name": profile_name,
        "gate_profile_name": gate_profile_name,
        "gate_run_id": {
            "qasper": gate_qasper_report.get("run", {}).get("id"),
            "self": gate_self_report.get("run", {}).get("id"),
        },
        "gate_metrics": {
            "qasper": gate_qasper_report.get("summary_metrics", {}),
            "self": gate_self_report.get("summary_metrics", {}),
            "weighted": {
                "assembled": {
                    "recall_at_k": weighted_gate_recall,
                    "nDCG_at_k": _weighted_assembled_metric(
                        qasper_report=gate_qasper_report,
                        self_report=gate_self_report,
                        metric_name="nDCG_at_k",
                    ),
                    "mrr_at_k": _weighted_assembled_metric(
                        qasper_report=gate_qasper_report,
                        self_report=gate_self_report,
                        metric_name="mrr_at_k",
                    ),
                    "precision_at_k": _weighted_assembled_metric(
                        qasper_report=gate_qasper_report,
                        self_report=gate_self_report,
                        metric_name="precision_at_k",
                    ),
                    "document_coverage_at_k": _weighted_assembled_metric(
                        qasper_report=gate_qasper_report,
                        self_report=gate_self_report,
                        metric_name="document_coverage_at_k",
                    ),
                },
                "weights": {
                    "self": SELF_BENCHMARK_WEIGHT,
                    "qasper": QASPER_BENCHMARK_WEIGHT,
                },
            },
        },
        "decision": decision,
        "reason": reason,
        "target_recall": target_recall,
        "gate_recall_at_k": weighted_gate_recall,
    }


def build_implement_result(
    *,
    iteration_index: int,
    profile_name: str,
    candidate_qasper: dict[str, Any],
    candidate_self: dict[str, Any],
    qasper_compare: dict[str, Any],
    self_compare: dict[str, Any],
    target_recall: float,
    has_next_iteration: bool,
) -> dict[str, Any]:
    """建立 implement-agent artifact 與 post-run 判定。

    參數：
    - `iteration_index`：目前 iteration 序號。
    - `profile_name`：本輪候選 profile 名稱。
    - `candidate_qasper`：QASPER candidate run report。
    - `candidate_self`：自家 benchmark candidate run report。
    - `qasper_compare`：QASPER compare payload。
    - `self_compare`：自家 benchmark compare payload。
    - `target_recall`：目標 recall 門檻。
    - `has_next_iteration`：是否仍有下一輪可用 profile。

    回傳：
    - `dict[str, Any]`：implement-agent artifact。
    """

    qasper_guardrails_passed = all(
        (_delta(compare_payload=qasper_compare, metric_name=metric_name) is None or _delta(compare_payload=qasper_compare, metric_name=metric_name) >= 0)
        for metric_name in ("Recall@k", "nDCG@k", "MRR@k", "Precision@k", "Doc Coverage@k")
    )
    self_guardrails_passed = all(
        (_delta(compare_payload=self_compare, metric_name=metric_name) is None or _delta(compare_payload=self_compare, metric_name=metric_name) >= 0)
        for metric_name in ("Recall@k", "nDCG@k", "MRR@k", "Precision@k", "Doc Coverage@k")
    )
    weighted_delta_summary = {
        "Recall@k": _weighted_metric_delta(qasper_compare=qasper_compare, self_compare=self_compare, metric_name="Recall@k"),
        "nDCG@k": _weighted_metric_delta(qasper_compare=qasper_compare, self_compare=self_compare, metric_name="nDCG@k"),
        "MRR@k": _weighted_metric_delta(qasper_compare=qasper_compare, self_compare=self_compare, metric_name="MRR@k"),
        "Precision@k": _weighted_metric_delta(qasper_compare=qasper_compare, self_compare=self_compare, metric_name="Precision@k"),
        "Doc Coverage@k": _weighted_metric_delta(qasper_compare=qasper_compare, self_compare=self_compare, metric_name="Doc Coverage@k"),
    }
    weighted_guardrails_passed = (
        weighted_delta_summary["Recall@k"] > 0
        and weighted_delta_summary["nDCG@k"] >= 0
        and weighted_delta_summary["MRR@k"] >= 0
        and weighted_delta_summary["Precision@k"] >= 0
        and weighted_delta_summary["Doc Coverage@k"] >= 0
    )

    candidate_weighted_recall = _weighted_assembled_metric(
        qasper_report=candidate_qasper,
        self_report=candidate_self,
        metric_name="recall_at_k",
    )
    if not weighted_guardrails_passed:
        decision = "rollback"
        reason = "weighted benchmark guardrails 未通過，必須 rollback。"
    elif candidate_weighted_recall >= target_recall:
        decision = "stop"
        reason = "weighted assembled Recall 已達標，停止後續迭代。"
    elif has_next_iteration:
        decision = "continue"
        reason = "weighted assembled Recall 尚未達標，但 guardrails 通過，進入下一輪。"
    else:
        decision = "stop"
        reason = "已用盡受控 profile ladder，停止後續迭代。"

    return {
        "role": "implement-agent",
        "iteration": iteration_index,
        "profile_name": profile_name,
        "candidate_run_ids": {
            "qasper": candidate_qasper.get("run", {}).get("id"),
            "self": candidate_self.get("run", {}).get("id"),
        },
        "candidate_metrics": {
            "qasper": candidate_qasper.get("summary_metrics", {}),
            "self": candidate_self.get("summary_metrics", {}),
        },
        "delta_summary": {
            "qasper": qasper_compare,
            "self": self_compare,
            "weighted": weighted_delta_summary,
        },
        "guardrails_passed": {
            "qasper": qasper_guardrails_passed,
            "self": self_guardrails_passed,
            "weighted": weighted_guardrails_passed,
        },
        "decision": decision,
        "reason": reason,
    }


def build_parser() -> argparse.ArgumentParser:
    """建立 CLI argument parser。

    參數：
    - 無。

    回傳：
    - `argparse.ArgumentParser`：QASPER OMX loop CLI parser。
    """

    parser = argparse.ArgumentParser(description="執行受控 OMX QASPER 五-agent loop。")
    parser.add_argument("--qasper-dataset-id", default=DEFAULT_QASPER_DATASET_ID)
    parser.add_argument("--self-dataset-id", default=DEFAULT_SELF_DATASET_ID)
    parser.add_argument("--qasper-reference-run-id", default=DEFAULT_QASPER_REFERENCE_RUN_ID)
    parser.add_argument("--self-reference-report", default=str(DEFAULT_SELF_REFERENCE_REPORT))
    parser.add_argument("--qasper-actor-sub", default="cli-evaluator")
    parser.add_argument("--self-actor-sub", default="cli-evaluator")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--target-recall", type=float, default=0.8)
    parser.add_argument("--output-dir", default=None)
    return parser


def main() -> None:
    """CLI 主入口。

    參數：
    - 無。

    回傳：
    - `None`：直接輸出 loop summary JSON。
    """

    parser = build_parser()
    args = parser.parse_args()
    settings = get_settings()
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    qasper_reference_report = load_report_from_run_id(run_id=args.qasper_reference_run_id, actor_sub=args.qasper_actor_sub)
    self_reference_report = read_report_json(Path(args.self_reference_report).resolve())
    output_dir = Path(args.output_dir).resolve() if args.output_dir else None

    effect_check = build_effect_check(
        baseline_qasper=qasper_reference_report,
        baseline_self=self_reference_report,
        target_recall=args.target_recall,
        baseline_profile=PRODUCTION_LIKE_V1,
    )
    _write_artifact(path=output_dir / "effect-check.json" if output_dir else None, payload=effect_check)

    iterations: list[dict[str, Any]] = []
    attempted_profiles: list[str] = []
    pending_effect_checks: list[dict[str, Any]] = [effect_check]
    iteration_index = 0

    while pending_effect_checks:
        active_effect_check = pending_effect_checks.pop(0)
        profiles = [
            profile
            for profile in active_effect_check.get("candidate_profiles", [])
            if profile not in attempted_profiles
        ]
        if not profiles:
            continue

        for profile_name in profiles:
            iteration_index += 1
            attempted_profiles.append(profile_name)
            index = iteration_index
            effect_opt = build_effect_opt(
                iteration_index=index,
                main_hypothesis=active_effect_check["main_hypothesis"],
                profile_name=profile_name,
                settings=settings,
            )
            advice = build_advice(effect_opt=effect_opt)
            guard = build_guard(effect_check=active_effect_check, effect_opt=effect_opt, advice=advice)
            iteration_dir = output_dir / f"iteration-{index:02d}" if output_dir else None
            _write_artifact(path=iteration_dir / "effect-opt.json" if iteration_dir else None, payload=effect_opt)
            _write_artifact(path=iteration_dir / "advice-agent.json" if iteration_dir else None, payload=advice)
            _write_artifact(path=iteration_dir / "guard-agent.json" if iteration_dir else None, payload=guard)
            if not guard["approved"]:
                iterations.append(
                    {
                        "iteration": index,
                        "effect_check": active_effect_check,
                        "effect_opt": effect_opt,
                        "advice": advice,
                        "guard": guard,
                    }
                )
                break

            with session_factory() as session:
                qasper_principal = CurrentPrincipal(sub=args.qasper_actor_sub, groups=())
                self_principal = CurrentPrincipal(sub=args.self_actor_sub, groups=())
                gate_qasper_run = create_evaluation_run(
                    session=session,
                    principal=qasper_principal,
                    settings=settings,
                    dataset_id=args.qasper_dataset_id,
                    top_k=args.top_k,
                    evaluation_profile=effect_opt["gate_profile_name"],
                )
                gate_self_run = create_evaluation_run(
                    session=session,
                    principal=self_principal,
                    settings=settings,
                    dataset_id=args.self_dataset_id,
                    top_k=args.top_k,
                    evaluation_profile=effect_opt["gate_profile_name"],
                )
                gate_qasper_report = get_evaluation_run_report(
                    session=session,
                    principal=qasper_principal,
                    run_id=str(gate_qasper_run.run.id),
                ).model_dump(mode="json")
                gate_self_report = get_evaluation_run_report(
                    session=session,
                    principal=self_principal,
                    run_id=str(gate_self_run.run.id),
                ).model_dump(mode="json")

            gate_result = build_deterministic_gate_result(
                iteration_index=index,
                profile_name=profile_name,
                gate_profile_name=effect_opt["gate_profile_name"],
                gate_qasper_report=gate_qasper_report,
                gate_self_report=gate_self_report,
                target_recall=args.target_recall,
                has_next_iteration=(profile_name != profiles[-1]) or bool(pending_effect_checks),
            )
            _write_artifact(path=iteration_dir / "deterministic-gate.json" if iteration_dir else None, payload=gate_result)

            if gate_result["decision"] != "pass":
                rethink_strategy = None
                if gate_result["decision"] == "rollback":
                    rethink_strategy = build_rollback_strategy(
                        effect_check=active_effect_check,
                        attempted_profiles=attempted_profiles,
                    )
                    if rethink_strategy is not None:
                        pending_effect_checks.append(rethink_strategy)
                        _write_artifact(
                            path=iteration_dir / "rollback-rethink.json" if iteration_dir else None,
                            payload=rethink_strategy,
                        )
                iterations.append(
                    {
                        "iteration": index,
                        "effect_check": active_effect_check,
                        "effect_opt": effect_opt,
                        "advice": advice,
                        "guard": guard,
                        "deterministic_gate": gate_result,
                        "implement": None,
                        "rollback_rethink": rethink_strategy,
                    }
                )
                if gate_result["decision"] == "continue":
                    continue
                if gate_result["decision"] == "rollback" and rethink_strategy is not None:
                    break
                if gate_result["decision"] != "pass":
                    pending_effect_checks = []
                    break

            with session_factory() as session:
                qasper_principal = CurrentPrincipal(sub=args.qasper_actor_sub, groups=())
                self_principal = CurrentPrincipal(sub=args.self_actor_sub, groups=())
                qasper_run = create_evaluation_run(
                    session=session,
                    principal=qasper_principal,
                    settings=settings,
                    dataset_id=args.qasper_dataset_id,
                    top_k=args.top_k,
                    evaluation_profile=profile_name,
                )
                self_run = create_evaluation_run(
                    session=session,
                    principal=self_principal,
                    settings=settings,
                    dataset_id=args.self_dataset_id,
                    top_k=args.top_k,
                    evaluation_profile=profile_name,
                )
                qasper_report = get_evaluation_run_report(
                    session=session,
                    principal=qasper_principal,
                    run_id=str(qasper_run.run.id),
                ).model_dump(mode="json")
                self_report = get_evaluation_run_report(
                    session=session,
                    principal=self_principal,
                    run_id=str(self_run.run.id),
                ).model_dump(mode="json")

            implement = build_implement_result(
                iteration_index=index,
                profile_name=profile_name,
                candidate_qasper=qasper_report,
                candidate_self=self_report,
                qasper_compare=compare_reports(reference_report=qasper_reference_report, candidate_report=qasper_report),
                self_compare=compare_reports(reference_report=self_reference_report, candidate_report=self_report),
                target_recall=args.target_recall,
                has_next_iteration=(profile_name != profiles[-1]) or bool(pending_effect_checks),
            )
            rethink_strategy = None
            if implement["decision"] == "rollback":
                rethink_strategy = build_rollback_strategy(
                    effect_check=active_effect_check,
                    attempted_profiles=attempted_profiles,
                )
                if rethink_strategy is not None:
                    pending_effect_checks.append(rethink_strategy)
                    _write_artifact(
                        path=iteration_dir / "rollback-rethink.json" if iteration_dir else None,
                        payload=rethink_strategy,
                    )
            _write_artifact(path=iteration_dir / "implement-agent.json" if iteration_dir else None, payload=implement)
            iterations.append(
                {
                    "iteration": index,
                    "effect_check": active_effect_check,
                    "effect_opt": effect_opt,
                    "advice": advice,
                    "guard": guard,
                    "deterministic_gate": gate_result,
                    "implement": implement,
                    "rollback_rethink": rethink_strategy,
                }
            )
            if implement["decision"] == "continue":
                continue
            if implement["decision"] == "rollback" and rethink_strategy is not None:
                break
            if implement["decision"] != "continue":
                pending_effect_checks = []
                break

    last_iteration = iterations[-1] if iterations else {}
    last_implement = last_iteration.get("implement") if isinstance(last_iteration, dict) else None
    last_gate = last_iteration.get("deterministic_gate") if isinstance(last_iteration, dict) else None
    final_decision = "stop"
    final_reason = "未執行 iteration。"
    if last_implement is not None:
        final_decision = last_implement.get("decision", "stop")
        final_reason = last_implement.get("reason", final_reason)
    elif last_gate is not None:
        final_decision = last_gate.get("decision", "stop")
        final_reason = last_gate.get("reason", final_reason)

    final_summary = {
        "role_sequence": ["effect-check", "effect-opt", "advice-agent", "guard-agent", "implement-agent"],
        "main_hypothesis": effect_check["main_hypothesis"],
        "candidate_profiles": effect_check["candidate_profiles"],
        "benchmark_weights": {
            "self": SELF_BENCHMARK_WEIGHT,
            "qasper": QASPER_BENCHMARK_WEIGHT,
        },
        "final_decision": final_decision,
        "final_reason": final_reason,
        "iterations": iterations,
    }
    _write_artifact(path=output_dir / "final-summary.json" if output_dir else None, payload=final_summary)
    print(_json_dumps({"effect_check": effect_check, "iterations": iterations, "final_summary": final_summary}))


if __name__ == "__main__":
    main()
