"""Evidence recall merge 與 trace 的測試。"""

from uuid import uuid4

import pytest

from app.auth.verifier import CurrentPrincipal
from app.db.models import (
    Area,
    AreaUserRole,
    ChunkStructureKind,
    ChunkType,
    Document,
    DocumentChunk,
    DocumentChunkEvidenceUnit,
    DocumentChunkEvidenceUnitChildSource,
    DocumentStatus,
    EvidenceBuildStrategy,
    EvidenceClusterStrategy,
    EvidencePathQualityReason,
    EvidenceType,
    Role,
)
from app.services.retrieval import (
    EVIDENCE_CHILD_BOOST_CAP,
    EVIDENCE_LOW_PATH_QUALITY_CAP_MULTIPLIER,
    _merge_evidence_recall,
    retrieve_area_candidates,
)


def _uuid() -> str:
    """建立測試用 UUID 字串。

    參數：
    - 無。

    回傳：
    - `str`：新的 UUID 字串。
    """

    return str(uuid4())


def _add_evidence_document(
    *,
    db_session,
    app_settings,
    area: Area,
    file_name: str,
    evidence_count: int,
    evidence_position_offset: int,
    path_quality_score: float,
) -> DocumentChunk:
    """建立帶多個 evidence units 的測試文件。

    參數：
    - `db_session`：目前測試資料庫 session。
    - `app_settings`：測試用 API 設定。
    - `area`：文件所屬 area。
    - `file_name`：測試文件名稱。
    - `evidence_count`：要建立的 evidence unit 數量。
    - `evidence_position_offset`：evidence unit position 起始偏移。
    - `path_quality_score`：所有 evidence units 使用的 path quality 分數。

    回傳：
    - `DocumentChunk`：建立好的 child chunk。
    """

    document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name=file_name,
        content_type="text/markdown",
        file_size=100,
        storage_key=f"area/{file_name}",
        display_text=f"{file_name} boost phrase",
        normalized_text=f"{file_name} boost phrase",
        status=DocumentStatus.ready,
    )
    parent = DocumentChunk(
        id=_uuid(),
        document_id=document.id,
        parent_chunk_id=None,
        chunk_type=ChunkType.parent,
        structure_kind=ChunkStructureKind.text,
        position=evidence_position_offset,
        section_index=0,
        child_index=None,
        heading="Results",
        content=f"{file_name} boost phrase",
        content_preview=f"{file_name} boost phrase",
        char_count=32,
        start_offset=0,
        end_offset=32,
    )
    child = DocumentChunk(
        id=_uuid(),
        document_id=document.id,
        parent_chunk_id=parent.id,
        chunk_type=ChunkType.child,
        structure_kind=ChunkStructureKind.text,
        position=evidence_position_offset + 1,
        section_index=0,
        child_index=0,
        heading="Results",
        content=f"{file_name} boost phrase",
        content_preview=f"{file_name} boost phrase",
        char_count=32,
        start_offset=0,
        end_offset=32,
        embedding=[0.1] * app_settings.embedding_dimensions,
    )
    db_session.add_all([document, parent, child])
    for index in range(evidence_count):
        evidence_unit = DocumentChunkEvidenceUnit(
            id=_uuid(),
            document_id=document.id,
            primary_parent_chunk_id=parent.id,
            evidence_type=EvidenceType.claim,
            evidence_text=f"boost phrase {index}",
            evidence_embedding=[0.1] * app_settings.embedding_dimensions,
            build_strategy=EvidenceBuildStrategy.deterministic,
            position=evidence_position_offset + index,
            confidence=0.8,
            path_quality_score=path_quality_score,
            path_quality_reason=(
                EvidencePathQualityReason.missing_path
                if path_quality_score < 0.3
                else EvidencePathQualityReason.ok
            ),
            cluster_strategy=EvidenceClusterStrategy.single_parent,
            heading_path="Results" if path_quality_score >= 0.3 else None,
            section_path_text="Results" if path_quality_score >= 0.3 else None,
        )
        db_session.add_all(
            [
                evidence_unit,
                DocumentChunkEvidenceUnitChildSource(
                    evidence_unit_id=evidence_unit.id,
                    child_chunk_id=child.id,
                    position=0,
                ),
            ]
        )
    return child


def test_merge_evidence_recall_can_add_child_candidate_from_evidence(db_session, app_settings) -> None:
    """evidence recall 應可在 child recall 之外額外帶入映射 child。"""

    area = Area(id=_uuid(), name="Evidence Merge")
    document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="evidence.md",
        content_type="text/markdown",
        file_size=100,
        storage_key="area/evidence.md",
        display_text="alpha internal term",
        normalized_text="alpha internal term",
        status=DocumentStatus.ready,
    )
    parent = DocumentChunk(
        id=_uuid(),
        document_id=document.id,
        parent_chunk_id=None,
        chunk_type=ChunkType.parent,
        structure_kind=ChunkStructureKind.text,
        position=0,
        section_index=0,
        child_index=None,
        heading="Results",
        content="alpha internal term",
        content_preview="alpha internal term",
        char_count=19,
        start_offset=0,
        end_offset=19,
    )
    child = DocumentChunk(
        id=_uuid(),
        document_id=document.id,
        parent_chunk_id=parent.id,
        chunk_type=ChunkType.child,
        structure_kind=ChunkStructureKind.text,
        position=1,
        section_index=0,
        child_index=0,
        heading="Results",
        content="alpha internal term",
        content_preview="alpha internal term",
        char_count=19,
        start_offset=0,
        end_offset=19,
        embedding=[0.1] * app_settings.embedding_dimensions,
    )
    evidence_unit = DocumentChunkEvidenceUnit(
        id=_uuid(),
        document_id=document.id,
        primary_parent_chunk_id=parent.id,
        evidence_type=EvidenceType.claim,
        evidence_text="friendly business phrase",
        evidence_embedding=[0.1] * app_settings.embedding_dimensions,
        build_strategy=EvidenceBuildStrategy.deterministic,
        position=0,
        confidence=0.8,
        path_quality_score=0.2,
        path_quality_reason=EvidencePathQualityReason.missing_path,
        cluster_strategy=EvidenceClusterStrategy.adjacency_fallback,
        heading_path=None,
        section_path_text=None,
    )
    child_source = DocumentChunkEvidenceUnitChildSource(
        evidence_unit_id=evidence_unit.id,
        child_chunk_id=child.id,
        position=0,
    )
    db_session.add_all(
        [
            area,
            AreaUserRole(area_id=area.id, user_sub="user-reader", role=Role.reader),
            document,
            parent,
            child,
            evidence_unit,
            child_source,
        ]
    )
    db_session.commit()

    merged = _merge_evidence_recall(
        session=db_session,
        settings=app_settings.model_copy(update={"retrieval_evidence_units_enabled": True}),
        area_id=area.id,
        query="friendly business phrase",
        matches=[],
        allowed_document_ids=None,
    )

    assert merged.hits
    assert merged.matches
    assert merged.matches[0].chunk.id == child.id
    assert merged.matches[0].evidence_unit_id == evidence_unit.id
    assert merged.matches[0].evidence_rrf_score > 0
    assert merged.matches[0].evidence_rrf_score <= (
        EVIDENCE_CHILD_BOOST_CAP * EVIDENCE_LOW_PATH_QUALITY_CAP_MULTIPLIER
    )


def test_retrieve_area_candidates_emits_evidence_trace_when_enabled(db_session, app_settings) -> None:
    """evidence lane 啟用時 retrieval trace 應帶出 evidence hits。"""

    area = Area(id=_uuid(), name="Evidence Trace")
    document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="evidence-trace.md",
        content_type="text/markdown",
        file_size=100,
        storage_key="area/evidence-trace.md",
        display_text="alpha internal term",
        normalized_text="alpha internal term",
        status=DocumentStatus.ready,
    )
    parent = DocumentChunk(
        id=_uuid(),
        document_id=document.id,
        parent_chunk_id=None,
        chunk_type=ChunkType.parent,
        structure_kind=ChunkStructureKind.text,
        position=0,
        section_index=0,
        child_index=None,
        heading="Results",
        content="alpha internal term",
        content_preview="alpha internal term",
        char_count=19,
        start_offset=0,
        end_offset=19,
    )
    child = DocumentChunk(
        id=_uuid(),
        document_id=document.id,
        parent_chunk_id=parent.id,
        chunk_type=ChunkType.child,
        structure_kind=ChunkStructureKind.text,
        position=1,
        section_index=0,
        child_index=0,
        heading="Results",
        content="alpha internal term",
        content_preview="alpha internal term",
        char_count=19,
        start_offset=0,
        end_offset=19,
        embedding=[0.1] * app_settings.embedding_dimensions,
    )
    evidence_unit = DocumentChunkEvidenceUnit(
        id=_uuid(),
        document_id=document.id,
        primary_parent_chunk_id=parent.id,
        evidence_type=EvidenceType.claim,
        evidence_text="friendly business phrase",
        evidence_embedding=[0.1] * app_settings.embedding_dimensions,
        build_strategy=EvidenceBuildStrategy.deterministic,
        position=0,
        confidence=0.8,
        path_quality_score=0.2,
        path_quality_reason=EvidencePathQualityReason.missing_path,
        cluster_strategy=EvidenceClusterStrategy.adjacency_fallback,
        heading_path=None,
        section_path_text=None,
    )
    child_source = DocumentChunkEvidenceUnitChildSource(
        evidence_unit_id=evidence_unit.id,
        child_chunk_id=child.id,
        position=0,
    )
    db_session.add_all(
        [
            area,
            AreaUserRole(area_id=area.id, user_sub="user-reader", role=Role.reader),
            document,
            parent,
            child,
            evidence_unit,
            child_source,
        ]
    )
    db_session.commit()

    result = retrieve_area_candidates(
        session=db_session,
        principal=CurrentPrincipal(sub="user-reader", groups=("/group/reader",)),
        settings=app_settings.model_copy(update={"retrieval_evidence_units_enabled": True}),
        area_id=area.id,
        query="friendly business phrase",
    )

    assert result.trace.evidence_units_enabled is True
    assert result.trace.evidence_recall_hits
    assert child.id in (result.trace.mapped_child_ids or [])


def test_merge_evidence_recall_caps_repeated_hits_for_same_child(db_session, app_settings) -> None:
    """同一 child 被多個 evidence units 命中時，boost 不得超過 cap。

    參數：
    - `db_session`：測試資料庫 session。
    - `app_settings`：測試用 API 設定。

    回傳：
    - `None`：此測試只驗證 capped boost 行為。
    """

    area = Area(id=_uuid(), name="Evidence Cap")
    db_session.add_all(
        [
            area,
            AreaUserRole(area_id=area.id, user_sub="user-reader", role=Role.reader),
        ]
    )
    child = _add_evidence_document(
        db_session=db_session,
        app_settings=app_settings,
        area=area,
        file_name="high-path.md",
        evidence_count=5,
        evidence_position_offset=0,
        path_quality_score=0.9,
    )
    db_session.commit()

    merged = _merge_evidence_recall(
        session=db_session,
        settings=app_settings.model_copy(update={"retrieval_evidence_units_enabled": True}),
        area_id=area.id,
        query="boost phrase",
        matches=[],
        allowed_document_ids=None,
    )

    match = next(item for item in merged.matches if item.chunk.id == child.id)
    assert match.evidence_rrf_score == pytest.approx(EVIDENCE_CHILD_BOOST_CAP)


def test_merge_evidence_recall_uses_lower_cap_for_low_path_quality(db_session, app_settings) -> None:
    """低 path quality 的 child evidence boost cap 應低於一般 path。

    參數：
    - `db_session`：測試資料庫 session。
    - `app_settings`：測試用 API 設定。

    回傳：
    - `None`：此測試只驗證 path quality 對 boost cap 的影響。
    """

    area = Area(id=_uuid(), name="Evidence Path Cap")
    db_session.add_all(
        [
            area,
            AreaUserRole(area_id=area.id, user_sub="user-reader", role=Role.reader),
        ]
    )
    low_path_child = _add_evidence_document(
        db_session=db_session,
        app_settings=app_settings,
        area=area,
        file_name="low-path.md",
        evidence_count=5,
        evidence_position_offset=0,
        path_quality_score=0.2,
    )
    high_path_child = _add_evidence_document(
        db_session=db_session,
        app_settings=app_settings,
        area=area,
        file_name="high-path.md",
        evidence_count=5,
        evidence_position_offset=20,
        path_quality_score=0.9,
    )
    db_session.commit()

    merged = _merge_evidence_recall(
        session=db_session,
        settings=app_settings.model_copy(update={"retrieval_evidence_units_enabled": True}),
        area_id=area.id,
        query="boost phrase",
        matches=[],
        allowed_document_ids=None,
    )

    boost_by_child_id = {match.chunk.id: match.evidence_rrf_score for match in merged.matches}
    low_path_cap = EVIDENCE_CHILD_BOOST_CAP * EVIDENCE_LOW_PATH_QUALITY_CAP_MULTIPLIER
    assert boost_by_child_id[low_path_child.id] == pytest.approx(low_path_cap)
    assert boost_by_child_id[high_path_child.id] == pytest.approx(EVIDENCE_CHILD_BOOST_CAP)
    assert boost_by_child_id[low_path_child.id] < boost_by_child_id[high_path_child.id]
