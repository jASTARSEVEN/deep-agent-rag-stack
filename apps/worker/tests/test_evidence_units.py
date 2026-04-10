"""Evidence units 的 path quality、fallback 與 clustering 測試。"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from worker.core.settings import WorkerSettings
from worker.db import EvidenceBuildStrategy, EvidencePathQualityReason, EvidenceType
from worker.evidence_units import (
    EvidenceUnitDraft,
    build_evidence_clusters,
    generate_evidence_units_for_document,
    score_path_quality,
)


def _build_parent(
    *,
    chunk_id: str,
    position: int,
    heading: str,
    heading_path: str | None,
    section_path_text: str | None,
    content: str,
    structure_kind: str = "text",
) -> SimpleNamespace:
    """建立 evidence unit 測試使用的 parent chunk 替身。

    參數：
    - `chunk_id`：chunk 識別碼。
    - `position`：chunk 穩定排序位置。
    - `heading`：顯示 heading。
    - `heading_path`：heading path。
    - `section_path_text`：section path text。
    - `content`：chunk 內容。
    - `structure_kind`：chunk 結構型別。

    回傳：
    - `SimpleNamespace`：具備 evidence clustering 所需欄位的替身。
    """

    return SimpleNamespace(
        id=chunk_id,
        position=position,
        heading=heading,
        heading_path=heading_path,
        section_path_text=section_path_text,
        content=content,
        structure_kind=SimpleNamespace(value=structure_kind),
    )


def _build_child(
    *,
    chunk_id: str,
    parent_chunk_id: str,
    position: int,
    heading: str,
    content: str,
) -> SimpleNamespace:
    """建立 evidence unit 測試使用的 child chunk 替身。

    參數：
    - `chunk_id`：chunk 識別碼。
    - `parent_chunk_id`：所屬 parent chunk 識別碼。
    - `position`：chunk 穩定排序位置。
    - `heading`：顯示 heading。
    - `content`：chunk 內容。

    回傳：
    - `SimpleNamespace`：具備 evidence clustering 所需欄位的替身。
    """

    return SimpleNamespace(
        id=chunk_id,
        parent_chunk_id=parent_chunk_id,
        position=position,
        heading=heading,
        content=content,
    )


def test_score_path_quality_treats_mu_lu_as_toc_noise() -> None:
    """命中 `目錄` 的 path 應直接視為 TOC-like noise。"""

    parent = _build_parent(
        chunk_id="parent-1",
        position=0,
        heading="目錄",
        heading_path="目錄",
        section_path_text="目錄",
        content="目錄 ........ 1",
    )

    result = score_path_quality(parent_chunk=parent, next_parent=None)

    assert result.is_toc_like_noise is True
    assert result.reason == EvidencePathQualityReason.toc_noise
    assert result.score < 0.1


def test_build_evidence_clusters_uses_adjacency_fallback_when_path_is_missing() -> None:
    """path 缺失時應退回 adjacency/content clustering，而不是放棄 evidence。"""

    parent_one = _build_parent(
        chunk_id="parent-1",
        position=0,
        heading="(missing)",
        heading_path=None,
        section_path_text=None,
        content="Alpha metric reaches 92 percent in baseline.",
    )
    parent_two = _build_parent(
        chunk_id="parent-2",
        position=1,
        heading="(missing)",
        heading_path=None,
        section_path_text=None,
        content="The same alpha metric remains stable after reindex.",
    )
    child_one = _build_child(
        chunk_id="child-1",
        parent_chunk_id="parent-1",
        position=2,
        heading="(missing)",
        content="Alpha metric reaches 92 percent in baseline.",
    )
    child_two = _build_child(
        chunk_id="child-2",
        parent_chunk_id="parent-2",
        position=3,
        heading="(missing)",
        content="The same alpha metric remains stable after reindex.",
    )

    clusters = build_evidence_clusters(
        parent_chunks=[parent_one, parent_two],
        child_chunks=[child_one, child_two],
    )

    assert len(clusters) == 1
    assert clusters[0].cluster_strategy.value in {
        "adjacency_fallback",
        "content_similarity_fallback",
    }
    assert clusters[0].path_quality_score < 0.4


def test_generate_evidence_units_auto_retries_llm_then_succeeds(monkeypatch) -> None:
    """`auto` 模式在 LLM 暫時失敗時應重試，而不是回退 deterministic。"""

    settings = WorkerSettings(
        _env_file=None,
        EVIDENCE_UNITS_ENABLED=True,
        EVIDENCE_UNITS_BUILD_STRATEGY="auto",
        OPENAI_API_KEY="test-key",
    )
    parent = _build_parent(
        chunk_id="parent-1",
        position=0,
        heading="Results",
        heading_path="Results",
        section_path_text="Results",
        content="Accuracy reaches 91.3 percent after the new policy.",
    )
    child = _build_child(
        chunk_id="child-1",
        parent_chunk_id="parent-1",
        position=1,
        heading="Results",
        content="Accuracy reaches 91.3 percent after the new policy.",
    )
    sleep_calls: list[int] = []
    attempts = 0

    class FlakyLlmProvider:
        """測試用的 LLM provider，前兩次失敗後成功。"""

        def generate_units(self, **kwargs):
            """依測試計數回傳 LLM evidence 或丟出暫時性錯誤。

            參數：
            - `kwargs`：provider contract 傳入的 cluster 與其他呼叫參數。

            回傳：
            - `list[EvidenceUnitDraft]`：成功時回傳單一 LLM evidence 草稿。
            """

            nonlocal attempts
            attempts += 1
            cluster = kwargs["cluster"]
            if attempts <= 2:
                raise ValueError("temporary llm json error")
            return [
                EvidenceUnitDraft(
                    evidence_type=EvidenceType.metric,
                    evidence_text="Accuracy reaches 91.3 percent after the new policy.",
                    build_strategy=EvidenceBuildStrategy.llm,
                    confidence=0.8,
                    cluster_strategy=cluster.cluster_strategy,
                    path_quality_score=cluster.path_quality_score,
                    path_quality_reason=cluster.path_quality_reason,
                    heading_path=cluster.heading_path,
                    section_path_text=cluster.section_path_text,
                    parent_chunk_ids=tuple(str(parent_chunk.id) for parent_chunk in cluster.parent_chunks),
                    child_chunk_ids=tuple(str(child_chunk.id) for child_chunk in cluster.child_chunks),
                )
            ]

    def build_flaky_llm_provider(*, settings: WorkerSettings, strategy: EvidenceBuildStrategy):
        """只允許建立 LLM provider，避免測試誤走 deterministic。

        參數：
        - `settings`：worker 測試設定。
        - `strategy`：測試中要求建立的 evidence strategy。

        回傳：
        - `FlakyLlmProvider`：測試用的暫時性失敗 provider。
        """

        del settings
        assert strategy == EvidenceBuildStrategy.llm
        return FlakyLlmProvider()

    monkeypatch.setattr("worker.evidence_units.build_evidence_unit_provider", build_flaky_llm_provider)
    monkeypatch.setattr("worker.evidence_units.time.sleep", lambda seconds: sleep_calls.append(seconds))

    result = generate_evidence_units_for_document(
        settings=settings,
        file_name="results.md",
        parent_chunks=[parent],
        child_chunks=[child],
    )

    assert result.effective_strategy == EvidenceBuildStrategy.llm
    assert result.fallback_reason is None
    assert [draft.build_strategy for draft in result.drafts] == [EvidenceBuildStrategy.llm]
    assert attempts == 3
    assert sleep_calls == [1, 4]


def test_generate_evidence_units_auto_fails_after_llm_retry_exhausted(monkeypatch) -> None:
    """`auto` 模式重試耗盡後應失敗，不得把 deterministic 當成功結果。"""

    settings = WorkerSettings(
        _env_file=None,
        EVIDENCE_UNITS_ENABLED=True,
        EVIDENCE_UNITS_BUILD_STRATEGY="auto",
        OPENAI_API_KEY="test-key",
    )
    parent = _build_parent(
        chunk_id="parent-1",
        position=0,
        heading="Results",
        heading_path="Results",
        section_path_text="Results",
        content="Accuracy reaches 91.3 percent after the new policy.",
    )
    child = _build_child(
        chunk_id="child-1",
        parent_chunk_id="parent-1",
        position=1,
        heading="Results",
        content="Accuracy reaches 91.3 percent after the new policy.",
    )
    sleep_calls: list[int] = []

    def fail_llm_provider(*, settings: WorkerSettings, strategy: EvidenceBuildStrategy):
        """讓 LLM provider 明確失敗，驗證不會回退 deterministic。

        參數：
        - `settings`：worker 測試設定。
        - `strategy`：測試中要求建立的 evidence strategy。

        回傳：
        - 不回傳；此 helper 永遠丟出例外。
        """

        del settings
        assert strategy == EvidenceBuildStrategy.llm
        raise ValueError("temporary llm json error")

    monkeypatch.setattr("worker.evidence_units.build_evidence_unit_provider", fail_llm_provider)
    monkeypatch.setattr("worker.evidence_units.time.sleep", lambda seconds: sleep_calls.append(seconds))

    with pytest.raises(ValueError, match="已重試 10 次"):
        generate_evidence_units_for_document(
            settings=settings,
            file_name="results.md",
            parent_chunks=[parent],
            child_chunks=[child],
        )

    assert sleep_calls == [failure_count**2 for failure_count in range(1, 11)]


def test_generate_evidence_units_deterministic_skips_source_metadata_lines() -> None:
    """deterministic 模式不應把 cluster 控制欄位當作 evidence 內容。"""

    settings = WorkerSettings(
        _env_file=None,
        EVIDENCE_UNITS_ENABLED=True,
        EVIDENCE_UNITS_BUILD_STRATEGY="deterministic",
    )
    parent = _build_parent(
        chunk_id="parent-1",
        position=0,
        heading="Results",
        heading_path="Results",
        section_path_text="Results",
        content="Accuracy reaches 91.3 percent after the new policy.",
    )
    child = _build_child(
        chunk_id="child-1",
        parent_chunk_id="parent-1",
        position=1,
        heading="Results",
        content="Accuracy reaches 91.3 percent after the new policy.",
    )

    result = generate_evidence_units_for_document(
        settings=settings,
        file_name="results.md",
        parent_chunks=[parent],
        child_chunks=[child],
    )

    assert result.effective_strategy == EvidenceBuildStrategy.deterministic
    assert result.drafts
    assert all(
        not draft.evidence_text.startswith(("Heading Path:", "Section Path:", "Cluster Strategy:", "Path Quality:"))
        for draft in result.drafts
    )
