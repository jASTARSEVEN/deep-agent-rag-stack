"""Retrieval evaluation profile registry 與目前保留的受控 benchmark profile。"""

from __future__ import annotations

from app.core.settings import AppSettings


# 正式 production-like benchmark profile 名稱。
PRODUCTION_LIKE_V1 = "production_like_v1"
# 離線 deterministic regression gate profile 名稱。
DETERMINISTIC_GATE_V1 = "deterministic_gate_v1"
# assembler lane 第一輪 profile 名稱。
QASPER_GUARDED_ASSEMBLER_V1 = "qasper_guarded_assembler_v1"
# assembler lane 第二輪 profile 名稱。
QASPER_GUARDED_ASSEMBLER_V2 = "qasper_guarded_assembler_v2"
# evidence synopsis lane 第一輪 profile 名稱。
QASPER_GUARDED_EVIDENCE_SYNOPSIS_V1 = "qasper_guarded_evidence_synopsis_v1"
# evidence synopsis lane 第二輪 profile 名稱。
QASPER_GUARDED_EVIDENCE_SYNOPSIS_V2 = "qasper_guarded_evidence_synopsis_v2"
# assembler lane 第一輪 deterministic gate profile 名稱。
QASPER_GUARDED_ASSEMBLER_V1_GATE = "qasper_guarded_assembler_v1_gate"
# assembler lane 第二輪 deterministic gate profile 名稱。
QASPER_GUARDED_ASSEMBLER_V2_GATE = "qasper_guarded_assembler_v2_gate"
# evidence synopsis lane 第一輪 deterministic gate profile 名稱。
QASPER_GUARDED_EVIDENCE_SYNOPSIS_V1_GATE = "qasper_guarded_evidence_synopsis_v1_gate"
# evidence synopsis lane 第二輪 deterministic gate profile 名稱。
QASPER_GUARDED_EVIDENCE_SYNOPSIS_V2_GATE = "qasper_guarded_evidence_synopsis_v2_gate"

# guarded profile 的安全上限，避免 benchmark-only 調參失控。
MAX_GUARDED_RECALL_DEPTH = 100

# 所有允許的 evaluation profile 名稱。
SUPPORTED_EVALUATION_PROFILES = (
    PRODUCTION_LIKE_V1,
    DETERMINISTIC_GATE_V1,
    QASPER_GUARDED_ASSEMBLER_V1,
    QASPER_GUARDED_ASSEMBLER_V2,
    QASPER_GUARDED_EVIDENCE_SYNOPSIS_V1,
    QASPER_GUARDED_EVIDENCE_SYNOPSIS_V2,
    QASPER_GUARDED_ASSEMBLER_V1_GATE,
    QASPER_GUARDED_ASSEMBLER_V2_GATE,
    QASPER_GUARDED_EVIDENCE_SYNOPSIS_V1_GATE,
    QASPER_GUARDED_EVIDENCE_SYNOPSIS_V2_GATE,
)

# assembler lane 的固定 profile 順序。
QASPER_GUARDED_ASSEMBLER_SEQUENCE = (
    QASPER_GUARDED_ASSEMBLER_V1,
    QASPER_GUARDED_ASSEMBLER_V2,
)

# evidence synopsis lane 的固定 profile 順序。
QASPER_GUARDED_EVIDENCE_SYNOPSIS_SEQUENCE = (
    QASPER_GUARDED_EVIDENCE_SYNOPSIS_V1,
    QASPER_GUARDED_EVIDENCE_SYNOPSIS_V2,
)


def resolve_evaluation_settings(*, settings: AppSettings, evaluation_profile: str) -> AppSettings:
    """依 evaluation profile 產生本次 run 的固定設定。

    參數：
    - `settings`：目前應用程式設定。
    - `evaluation_profile`：要解析的 evaluation profile 名稱。

    回傳：
    - `AppSettings`：套用 profile 後的有效設定。
    """

    overrides = get_evaluation_profile_overrides(settings=settings, evaluation_profile=evaluation_profile)
    return settings.model_copy(update=overrides) if overrides else settings


def get_evaluation_profile_overrides(*, settings: AppSettings, evaluation_profile: str) -> dict[str, int | str | bool]:
    """回傳指定 profile 相對於原始設定的覆寫欄位。

    前置條件與風險：
    - 此函式僅供 benchmark/profile-gated 路徑使用，不得直接用來改 production defaults。
    - 目前只保留 `assembler` 與 `evidence synopsis` 兩條受控策略 lane。

    參數：
    - `settings`：目前應用程式設定。
    - `evaluation_profile`：要解析的 evaluation profile 名稱。

    回傳：
    - `dict[str, int | str | bool]`：僅包含發生變化的覆寫欄位。
    """

    if evaluation_profile == PRODUCTION_LIKE_V1:
        return {}
    if evaluation_profile == DETERMINISTIC_GATE_V1:
        return {
            "rerank_provider": "deterministic",
            "rerank_top_n": min(settings.rerank_top_n, 4),
            "retrieval_vector_top_k": min(settings.retrieval_vector_top_k, 6),
            "retrieval_fts_top_k": min(settings.retrieval_fts_top_k, 6),
            "retrieval_max_candidates": min(settings.retrieval_max_candidates, 8),
            "assembler_max_contexts": min(settings.assembler_max_contexts, 4),
            "assembler_max_children_per_parent": min(settings.assembler_max_children_per_parent, 2),
        }
    if evaluation_profile == QASPER_GUARDED_ASSEMBLER_V1:
        return {
            "rerank_top_n": min(max(settings.rerank_top_n, 8), MAX_GUARDED_RECALL_DEPTH),
            "assembler_max_contexts": max(settings.assembler_max_contexts, 8),
            "assembler_max_chars_per_context": max(settings.assembler_max_chars_per_context, 3200),
            "assembler_max_children_per_parent": max(settings.assembler_max_children_per_parent, 4),
        }
    if evaluation_profile == QASPER_GUARDED_ASSEMBLER_V2:
        return {
            "rerank_top_n": min(max(settings.rerank_top_n, 10), MAX_GUARDED_RECALL_DEPTH),
            "assembler_max_contexts": max(settings.assembler_max_contexts, 10),
            "assembler_max_chars_per_context": max(settings.assembler_max_chars_per_context, 3600),
            "assembler_max_children_per_parent": max(settings.assembler_max_children_per_parent, 5),
        }
    if evaluation_profile == QASPER_GUARDED_EVIDENCE_SYNOPSIS_V1:
        return {
            "rerank_top_n": min(max(settings.rerank_top_n, 20), MAX_GUARDED_RECALL_DEPTH),
            "retrieval_evidence_synopsis_enabled": True,
            "assembler_max_contexts": max(settings.assembler_max_contexts, 8),
            "assembler_max_chars_per_context": max(settings.assembler_max_chars_per_context, 3200),
            "assembler_max_children_per_parent": max(settings.assembler_max_children_per_parent, 5),
        }
    if evaluation_profile == QASPER_GUARDED_EVIDENCE_SYNOPSIS_V2:
        return {
            "rerank_top_n": min(max(settings.rerank_top_n, 30), MAX_GUARDED_RECALL_DEPTH),
            "retrieval_evidence_synopsis_enabled": True,
            "assembler_max_contexts": max(settings.assembler_max_contexts, 10),
            "assembler_max_chars_per_context": max(settings.assembler_max_chars_per_context, 3600),
            "assembler_max_children_per_parent": max(settings.assembler_max_children_per_parent, 7),
        }
    if evaluation_profile == QASPER_GUARDED_ASSEMBLER_V1_GATE:
        return {
            **get_evaluation_profile_overrides(settings=settings, evaluation_profile=QASPER_GUARDED_ASSEMBLER_V1),
            "rerank_provider": "deterministic",
        }
    if evaluation_profile == QASPER_GUARDED_ASSEMBLER_V2_GATE:
        return {
            **get_evaluation_profile_overrides(settings=settings, evaluation_profile=QASPER_GUARDED_ASSEMBLER_V2),
            "rerank_provider": "deterministic",
        }
    if evaluation_profile == QASPER_GUARDED_EVIDENCE_SYNOPSIS_V1_GATE:
        return {
            **get_evaluation_profile_overrides(settings=settings, evaluation_profile=QASPER_GUARDED_EVIDENCE_SYNOPSIS_V1),
            "rerank_provider": "deterministic",
        }
    if evaluation_profile == QASPER_GUARDED_EVIDENCE_SYNOPSIS_V2_GATE:
        return {
            **get_evaluation_profile_overrides(settings=settings, evaluation_profile=QASPER_GUARDED_EVIDENCE_SYNOPSIS_V2),
            "rerank_provider": "deterministic",
        }
    raise ValueError(f"不支援的 evaluation profile：{evaluation_profile}")
