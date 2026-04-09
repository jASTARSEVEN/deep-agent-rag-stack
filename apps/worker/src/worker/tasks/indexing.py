"""Worker 文件 chunk indexing 與 retrieval preparation (Phase 6 PGroonga 版)。"""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from itertools import repeat

from sqlalchemy import delete, func, select, update

from worker.core.settings import WorkerSettings
from worker.db import (
    ChunkType,
    Document,
    DocumentChunk,
    DocumentChunkEvidenceUnit,
    DocumentChunkEvidenceUnitChildSource,
    DocumentChunkEvidenceUnitParentSource,
    EvidenceEnrichmentStatus,
)
from worker.embedding_text import build_embedding_input_text
from worker.embeddings import build_embedding_provider
from worker.evidence_units import generate_evidence_units_for_document
from worker.synopsis import (
    build_document_synopsis_provider,
    build_document_synopsis_source_text,
    build_section_synopsis_source_text,
    detect_synopsis_language,
    detect_section_synopsis_language,
)


def index_document_chunks(*, session, document: Document, settings: WorkerSettings) -> None:
    """對指定文件的 child chunks 寫入 embedding。
    
    在 Phase 6 中，全文檢索已切換為 PGroonga，它會直接在 `content` 欄位上自動建立索引，
    因此此處不再需要手動寫入 FTS payload。

    參數：
    - `session`：目前資料庫 session。
    - `document`：要建立 retrieval payload 的文件。
    - `settings`：worker 執行期設定。

    回傳：
    - `None`：此函式只負責更新 chunks 的向量資訊。
    """

    child_chunks = session.scalars(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document.id, DocumentChunk.chunk_type == ChunkType.child)
        .order_by(DocumentChunk.position.asc())
    ).all()
    if not child_chunks:
        raise ValueError("文件沒有可供 retrieval 使用的 child chunks。")
    parent_chunks = session.scalars(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document.id, DocumentChunk.chunk_type == ChunkType.parent)
        .order_by(DocumentChunk.position.asc())
    ).all()
    if not parent_chunks:
        raise ValueError("文件沒有可供 document synopsis 使用的 parent chunks。")

    # 執行向量編碼
    provider = build_embedding_provider(settings)
    embeddings = provider.embed_texts(
        [
            build_embedding_input_text(
                heading=chunk.heading,
                content=chunk.content,
            )
            for chunk in child_chunks
        ]
    )
    
    # 更新 embedding 欄位
    for chunk, embedding in zip(child_chunks, embeddings, strict=True):
        chunk.embedding = embedding

    if settings.document_section_synopsis_enabled:
        section_synopsis_texts = _generate_section_synopsis_texts(
            settings=settings,
            file_name=document.file_name,
            parent_chunks=parent_chunks,
        )
        section_synopsis_embeddings = provider.embed_texts(section_synopsis_texts)
        section_synopsis_updated_at = datetime.now(UTC)
        for parent_chunk, synopsis_text, synopsis_embedding in zip(
            parent_chunks,
            section_synopsis_texts,
            section_synopsis_embeddings,
            strict=True,
        ):
            parent_chunk.section_synopsis_text = synopsis_text
            parent_chunk.section_synopsis_embedding = synopsis_embedding
            parent_chunk.section_synopsis_updated_at = section_synopsis_updated_at
    else:
        for parent_chunk in parent_chunks:
            parent_chunk.section_synopsis_text = None
            parent_chunk.section_synopsis_embedding = None
            parent_chunk.section_synopsis_updated_at = None

    synopsis_provider = build_document_synopsis_provider(settings)
    synopsis_source_text = build_document_synopsis_source_text(
        file_name=document.file_name,
        parent_chunks=parent_chunks,
        max_input_chars=settings.document_synopsis_max_input_chars,
    )
    synopsis_text = synopsis_provider.generate_synopsis(
        file_name=document.file_name,
        source_text=synopsis_source_text,
        output_language=detect_synopsis_language(parent_chunks=parent_chunks, file_name=document.file_name),
        max_output_chars=settings.document_synopsis_max_output_chars,
    )
    document.synopsis_text = synopsis_text
    document.synopsis_embedding = provider.embed_texts([synopsis_text])[0]
    document.synopsis_updated_at = datetime.now(UTC)
    _replace_document_evidence_units(
        session=session,
        document=document,
        parent_chunks=parent_chunks,
        child_chunks=child_chunks,
        settings=settings,
        embedding_provider=provider,
    )

    session.flush()


def _replace_document_evidence_units(
    *,
    session,
    document: Document,
    parent_chunks: list[DocumentChunk],
    child_chunks: list[DocumentChunk],
    settings: WorkerSettings,
    embedding_provider,
) -> None:
    """以 replace-all 方式重建單一文件的 evidence units。

    參數：
    - `session`：目前資料庫 session。
    - `document`：目前處理中的文件。
    - `parent_chunks`：依文件順序排列的 parent chunks。
    - `child_chunks`：依文件順序排列的 child chunks。
    - `settings`：worker 執行期設定。
    - `embedding_provider`：目前 indexing 共用的 embedding provider。

    回傳：
    - `None`：此函式只負責更新 evidence units 與 observability 欄位。
    """

    session.execute(
        delete(DocumentChunkEvidenceUnitChildSource).where(
            DocumentChunkEvidenceUnitChildSource.evidence_unit_id.in_(
                select(DocumentChunkEvidenceUnit.id).where(DocumentChunkEvidenceUnit.document_id == document.id)
            )
        )
    )
    session.execute(
        delete(DocumentChunkEvidenceUnitParentSource).where(
            DocumentChunkEvidenceUnitParentSource.evidence_unit_id.in_(
                select(DocumentChunkEvidenceUnit.id).where(DocumentChunkEvidenceUnit.document_id == document.id)
            )
        )
    )
    session.execute(delete(DocumentChunkEvidenceUnit).where(DocumentChunkEvidenceUnit.document_id == document.id))

    if not settings.evidence_units_enabled:
        document.evidence_enrichment_status = EvidenceEnrichmentStatus.skipped
        document.evidence_enrichment_strategy = None
        document.evidence_enrichment_error = None
        document.evidence_enrichment_updated_at = datetime.now(UTC)
        return

    document.evidence_enrichment_status = EvidenceEnrichmentStatus.processing
    generation_result = generate_evidence_units_for_document(
        settings=settings,
        file_name=document.file_name,
        parent_chunks=parent_chunks,
        child_chunks=child_chunks,
    )

    if not generation_result.drafts:
        document.evidence_enrichment_status = EvidenceEnrichmentStatus.failed
        document.evidence_enrichment_strategy = generation_result.effective_strategy
        document.evidence_enrichment_error = generation_result.fallback_reason or "no_evidence_generated"
        document.evidence_enrichment_updated_at = datetime.now(UTC)
        return

    texts = [draft.evidence_text for draft in generation_result.drafts]
    embeddings = embedding_provider.embed_texts(texts)
    now = datetime.now(UTC)
    for position, (draft, embedding) in enumerate(zip(generation_result.drafts, embeddings, strict=True)):
        evidence_unit = DocumentChunkEvidenceUnit(
            document_id=document.id,
            primary_parent_chunk_id=draft.parent_chunk_ids[0],
            evidence_type=draft.evidence_type,
            evidence_text=draft.evidence_text,
            evidence_embedding=embedding,
            build_strategy=draft.build_strategy,
            position=position,
            confidence=draft.confidence,
            path_quality_score=draft.path_quality_score,
            path_quality_reason=draft.path_quality_reason,
            cluster_strategy=draft.cluster_strategy,
            heading_path=draft.heading_path,
            section_path_text=draft.section_path_text,
            created_at=now,
            updated_at=now,
        )
        session.add(evidence_unit)
        session.flush()
        session.add_all(
            [
                DocumentChunkEvidenceUnitChildSource(
                    evidence_unit_id=evidence_unit.id,
                    child_chunk_id=child_chunk_id,
                    position=child_position,
                    created_at=now,
                )
                for child_position, child_chunk_id in enumerate(draft.child_chunk_ids)
            ]
        )
        session.add_all(
            [
                DocumentChunkEvidenceUnitParentSource(
                    evidence_unit_id=evidence_unit.id,
                    parent_chunk_id=parent_chunk_id,
                    position=parent_position,
                    created_at=now,
                )
                for parent_position, parent_chunk_id in enumerate(draft.parent_chunk_ids)
            ]
        )

    document.evidence_enrichment_status = EvidenceEnrichmentStatus.ready
    document.evidence_enrichment_strategy = generation_result.effective_strategy
    document.evidence_enrichment_error = generation_result.fallback_reason
    document.evidence_enrichment_updated_at = now


def _generate_section_synopsis_texts(
    *,
    settings: WorkerSettings,
    file_name: str,
    parent_chunks: list[DocumentChunk],
) -> list[str]:
    """以受控並發方式生成 parent-level section synopsis。

    參數：
    - `settings`：worker 執行期設定。
    - `file_name`：目前文件檔名。
    - `parent_chunks`：依文件順序排列的 parent chunks。

    回傳：
    - `list[str]`：與 `parent_chunks` 順序一致的 section synopsis 文字。
    """

    heading_paths = [parent_chunk.heading_path for parent_chunk in parent_chunks]
    source_texts = [
        build_section_synopsis_source_text(
            file_name=file_name,
            heading_path=parent_chunk.heading_path,
            section_path_text=parent_chunk.section_path_text,
            content=parent_chunk.content,
            structure_kind=str(parent_chunk.structure_kind.value),
            max_input_chars=settings.document_synopsis_max_input_chars,
        )
        for parent_chunk in parent_chunks
    ]
    output_languages = [
        detect_section_synopsis_language(
            file_name=file_name,
            heading_path=parent_chunk.heading_path,
            content=parent_chunk.content,
        )
        for parent_chunk in parent_chunks
    ]
    max_workers = max(1, min(settings.document_synopsis_parallelism, len(parent_chunks)))
    if max_workers == 1:
        return [
            _generate_single_section_synopsis(
                settings,
                file_name,
                heading_path,
                source_text,
                output_language,
                settings.document_synopsis_max_output_chars,
            )
            for heading_path, source_text, output_language in zip(
                heading_paths,
                source_texts,
                output_languages,
                strict=True,
            )
        ]

    with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="section-synopsis") as executor:
        return list(
            executor.map(
                _generate_single_section_synopsis,
                repeat(settings),
                repeat(file_name),
                heading_paths,
                source_texts,
                output_languages,
                repeat(settings.document_synopsis_max_output_chars),
            )
        )


def _generate_single_section_synopsis(
    settings: WorkerSettings,
    file_name: str,
    heading_path: str | None,
    source_text: str,
    output_language: str,
    max_output_chars: int,
) -> str:
    """生成單一 section synopsis，供受控並發路徑重複呼叫。

    參數：
    - `settings`：worker 執行期設定。
    - `file_name`：目前文件檔名。
    - `heading_path`：目前 section 的階層路徑。
    - `source_text`：已做 path-aware 壓縮的輸入文字。
    - `output_language`：期望輸出語言。
    - `max_output_chars`：允許的 synopsis 最大字元數。

    回傳：
    - `str`：單一 parent chunk 的 section synopsis。
    """

    synopsis_provider = build_document_synopsis_provider(settings)
    return synopsis_provider.generate_section_synopsis(
        file_name=file_name,
        heading_path=heading_path,
        source_text=source_text,
        output_language=output_language,
        max_output_chars=max_output_chars,
    )
