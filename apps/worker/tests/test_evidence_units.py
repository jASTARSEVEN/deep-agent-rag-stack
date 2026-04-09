"""Evidence units 的 path quality、fallback 與 clustering 測試。"""

from __future__ import annotations

from types import SimpleNamespace

from worker.core.settings import WorkerSettings
from worker.db import EvidenceBuildStrategy, EvidencePathQualityReason
from worker.evidence_units import (
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


def test_generate_evidence_units_auto_falls_back_to_deterministic(monkeypatch) -> None:
    """`auto` 模式在 LLM 失敗時應回退 deterministic。"""

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

    def fail_llm_provider(*, settings: WorkerSettings, strategy: EvidenceBuildStrategy):
        """讓 LLM provider 明確失敗，逼出 deterministic fallback。"""

        from worker.evidence_units import DeterministicEvidenceUnitProvider

        if strategy == EvidenceBuildStrategy.llm:
            raise ValueError("llm unavailable")
        return DeterministicEvidenceUnitProvider()

    monkeypatch.setattr("worker.evidence_units.build_evidence_unit_provider", fail_llm_provider)

    result = generate_evidence_units_for_document(
        settings=settings,
        file_name="results.md",
        parent_chunks=[parent],
        child_chunks=[child],
    )

    assert result.effective_strategy == EvidenceBuildStrategy.deterministic
    assert result.fallback_reason is not None
    assert result.drafts
