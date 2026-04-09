"""Evidence recall merge 與 trace 的測試。"""

from uuid import uuid4

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
from app.services.retrieval import _merge_evidence_recall, retrieve_area_candidates
from app.auth.verifier import CurrentPrincipal


def _uuid() -> str:
    """建立測試用 UUID 字串。

    參數：
    - 無。

    回傳：
    - `str`：新的 UUID 字串。
    """

    return str(uuid4())


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
