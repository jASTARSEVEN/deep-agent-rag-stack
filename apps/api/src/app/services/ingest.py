"""API 測試與 E2E 使用的 inline ingest 與 chunking 流程。"""

from datetime import UTC, datetime

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.settings import AppSettings
from app.services.chunking import ChunkingConfig
from app.db.models import ChunkStructureKind, ChunkType, Document, DocumentChunk, DocumentStatus, IngestJob, IngestJobStatus
from app.services.chunking import ChunkingResult, build_chunk_tree
from app.services.parsers import parse_document
from app.services.storage import ObjectStorage, StorageError


def process_ingest_job_inline(
    session: Session,
    storage: ObjectStorage,
    *,
    job_id: str,
    settings: AppSettings,
) -> None:
    """在同一行程內執行 ingest 與 chunking，供測試與 E2E 使用。

    參數：
    - `session`：用來讀寫 documents、ingest_jobs 與 document_chunks 的資料庫 session。
    - `storage`：用來讀取原始檔內容的物件儲存介面。
    - `job_id`：要處理的 ingest job 識別碼。

    回傳：
    - `None`：此函式只負責推進狀態，不回傳業務資料。
    """

    job = session.get(IngestJob, job_id)
    if job is None or job.status != IngestJobStatus.queued:
        return

    document = session.get(Document, job.document_id)
    if document is None or document.status != DocumentStatus.uploaded:
        return

    _mark_processing(session=session, document=document, job=job)

    try:
        payload = storage.get_object(object_key=document.storage_key)
        job.stage = "parsing"
        session.commit()
        parsed_document = parse_document(file_name=document.file_name, payload=payload)
        job.stage = "chunking"
        session.commit()
        chunking_result = build_chunk_tree(
            parsed_document=parsed_document,
            config=_build_chunking_config(settings),
        )
        _replace_document_chunks(session=session, document=document, chunking_result=chunking_result)
    except (StorageError, ValueError, UnicodeDecodeError) as exc:
        _mark_failed(session=session, document=document, job=job, message=str(exc))
        return

    _mark_succeeded(session=session, document=document, job=job, chunking_result=chunking_result)
def _mark_processing(*, session: Session, document: Document, job: IngestJob) -> None:
    """將 document 與 job 標記為 processing。

    參數：
    - `session`：目前資料庫 session。
    - `document`：要更新狀態的文件。
    - `job`：要更新狀態的 ingest job。

    回傳：
    - `None`：此函式只負責更新狀態。
    """

    job.status = IngestJobStatus.processing
    job.stage = "processing"
    job.error_message = None
    job.parent_chunk_count = 0
    job.child_chunk_count = 0
    document.status = DocumentStatus.processing
    session.commit()


def _replace_document_chunks(*, session: Session, document: Document, chunking_result: ChunkingResult) -> None:
    """以 replace-all 方式重建文件 chunks。

    參數：
    - `session`：目前資料庫 session。
    - `document`：本次要重建 chunks 的文件。
    - `chunking_result`：已建立完成的 chunk tree 草稿。

    回傳：
    - `None`：此函式只負責刪除舊 chunks 並寫入新 chunks。
    """

    parent_id_by_section: dict[int, str] = {}
    session.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))

    for draft in chunking_result.parent_chunks:
        chunk = DocumentChunk(
            document_id=document.id,
            parent_chunk_id=None,
            chunk_type=ChunkType.parent,
            structure_kind=ChunkStructureKind(draft.structure_kind),
            position=draft.position,
            section_index=draft.section_index,
            child_index=None,
            heading=draft.heading,
            content=draft.content,
            content_preview=draft.content_preview,
            char_count=draft.char_count,
            start_offset=draft.start_offset,
            end_offset=draft.end_offset,
        )
        session.add(chunk)
        session.flush()
        parent_id_by_section[draft.section_index] = chunk.id

    for draft in chunking_result.child_chunks:
        session.add(
            DocumentChunk(
                document_id=document.id,
                parent_chunk_id=parent_id_by_section[draft.section_index],
                chunk_type=ChunkType.child,
                structure_kind=ChunkStructureKind(draft.structure_kind),
                position=draft.position,
                section_index=draft.section_index,
                child_index=draft.child_index,
                heading=draft.heading,
                content=draft.content,
                content_preview=draft.content_preview,
                char_count=draft.char_count,
                start_offset=draft.start_offset,
                end_offset=draft.end_offset,
            )
        )

    session.flush()


def _mark_failed(*, session: Session, document: Document, job: IngestJob, message: str) -> None:
    """將 document 與 job 標為 failed，並清掉殘留 chunks。

    參數：
    - `session`：目前資料庫 session。
    - `document`：要標記失敗的文件。
    - `job`：要標記失敗的 ingest job。
    - `message`：可讀失敗原因。

    回傳：
    - `None`：此函式只負責更新失敗狀態。
    """

    session.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))
    job.status = IngestJobStatus.failed
    job.stage = "failed"
    job.error_message = message
    job.parent_chunk_count = 0
    job.child_chunk_count = 0
    document.status = DocumentStatus.failed
    document.indexed_at = None
    session.commit()


def _mark_succeeded(*, session: Session, document: Document, job: IngestJob, chunking_result: ChunkingResult) -> None:
    """將 document 與 job 標為成功完成 chunking。

    參數：
    - `session`：目前資料庫 session。
    - `document`：要標記完成的文件。
    - `job`：要標記完成的 ingest job。
    - `chunking_result`：本次產生的 chunk tree 草稿。

    回傳：
    - `None`：此函式只負責更新成功狀態。
    """

    indexed_at = datetime.now(UTC)
    job.stage = "finalizing"
    job.parent_chunk_count = len(chunking_result.parent_chunks)
    job.child_chunk_count = len(chunking_result.child_chunks)
    session.flush()
    job.status = IngestJobStatus.succeeded
    job.stage = "succeeded"
    job.error_message = None
    document.status = DocumentStatus.ready
    document.indexed_at = indexed_at
    session.commit()


def _build_chunking_config(settings: AppSettings) -> ChunkingConfig:
    """將 API 設定物件映射為 chunking 參數。

    參數：
    - `settings`：目前 API 執行期設定。

    回傳：
    - `ChunkingConfig`：供 chunking 流程使用的參數物件。
    """

    return ChunkingConfig(
        min_parent_section_length=settings.chunk_min_parent_section_length,
        target_child_chunk_size=settings.chunk_target_child_size,
        child_chunk_overlap=settings.chunk_child_overlap,
        content_preview_length=settings.chunk_content_preview_length,
        txt_parent_group_size=settings.chunk_txt_parent_group_size,
        table_preserve_max_chars=settings.chunk_table_preserve_max_chars,
        table_max_rows_per_child=settings.chunk_table_max_rows_per_child,
    )
