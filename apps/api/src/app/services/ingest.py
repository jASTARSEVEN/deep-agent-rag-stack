"""API 測試與 E2E 使用的 inline ingest 與 chunking 流程。"""

from datetime import UTC, datetime
import logging

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.settings import AppSettings
from app.services.chunking import ChunkingConfig
from app.db.models import ChunkStructureKind, ChunkType, Document, DocumentChunk, DocumentStatus, IngestJob, IngestJobStatus
from app.services.chunking import ChunkingResult, build_chunk_tree
from app.services.indexing import index_document_chunks
from app.services.parsers import PdfParserConfig, parse_document
from app.services.storage import ObjectStorage, StorageError

logger = logging.getLogger(__name__)

# `document_chunks.heading` 欄位的資料庫最大長度。
MAX_CHUNK_HEADING_LENGTH = 255

# `document_chunks.content_preview` 欄位的資料庫最大長度。
MAX_CHUNK_CONTENT_PREVIEW_LENGTH = 255


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
    pdf_provider = settings.pdf_parser_provider if document.file_name.lower().endswith(".pdf") else None

    try:
        payload = storage.get_object(object_key=document.storage_key)
        job.stage = "parsing"
        session.commit()
        parsed_document = parse_document(
            file_name=document.file_name,
            payload=payload,
            pdf_config=_build_pdf_parser_config(settings),
        )
        document.normalized_text = parsed_document.normalized_text
        job.stage = "chunking"
        session.commit()
        chunking_result = build_chunk_tree(
            parsed_document=parsed_document,
            config=_build_chunking_config(settings),
        )
        _log_chunking_observability(
            document=document,
            job=job,
            parsed_document=parsed_document,
            chunking_result=chunking_result,
            pdf_provider=pdf_provider,
        )
        _replace_document_chunks(session=session, document=document, chunking_result=chunking_result)
        job.stage = "indexing"
        session.commit()
        index_document_chunks(session=session, document=document, settings=settings)
    except (StorageError, ValueError, UnicodeDecodeError) as exc:
        _mark_failed(
            session=session,
            document=document,
            job=job,
            message=_format_failure_message(message=str(exc), pdf_provider=pdf_provider),
        )
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
    document.normalized_text = None
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
            heading=_sanitize_chunk_heading(draft.heading),
            content=draft.content,
            content_preview=_sanitize_content_preview(draft.content_preview),
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
                heading=_sanitize_chunk_heading(draft.heading),
                content=draft.content,
                content_preview=_sanitize_content_preview(draft.content_preview),
                char_count=draft.char_count,
                start_offset=draft.start_offset,
                end_offset=draft.end_offset,
            )
        )

    session.flush()


def _sanitize_chunk_heading(heading: str | None) -> str | None:
    """將 chunk heading 裁切到資料庫欄位可接受的長度。

    參數：
    - `heading`：chunk 草稿上的 heading。

    回傳：
    - `str | None`：可安全寫入資料庫的 heading；若原值為空則回傳空值。
    """

    if heading is None:
        return None
    return heading[:MAX_CHUNK_HEADING_LENGTH]


def _sanitize_content_preview(content_preview: str) -> str:
    """將 chunk 摘要裁切到資料庫欄位可接受的長度。

    參數：
    - `content_preview`：chunk 草稿上的摘要文字。

    回傳：
    - `str`：可安全寫入資料庫的摘要文字。
    """

    return content_preview[:MAX_CHUNK_CONTENT_PREVIEW_LENGTH]


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
    document.normalized_text = None
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


def _log_chunking_observability(
    *,
    document: Document,
    job: IngestJob,
    parsed_document,
    chunking_result: ChunkingResult,
    pdf_provider: str | None,
) -> None:
    """記錄 ingest/chunking 的觀測資訊，方便診斷 PDF 路徑。

    參數：
    - `document`：目前處理中的文件。
    - `job`：目前 ingest job。
    - `parsed_document`：parser 產出的標準化文件。
    - `chunking_result`：chunking 結果。
    - `pdf_provider`：若為 PDF，實際使用的 provider。

    回傳：
    - `None`：此函式只負責輸出 log。
    """

    diagnostics = _collect_chunking_diagnostics(chunking_result=chunking_result)
    logger.info(
        "inline ingest chunking completed file=%s job_id=%s source_format=%s pdf_provider=%s parent_chunks=%s child_chunks=%s text_table_text_clusters=%s mixed_structure_parents=%s",
        document.file_name,
        job.id,
        parsed_document.source_format,
        pdf_provider or "n/a",
        len(chunking_result.parent_chunks),
        len(chunking_result.child_chunks),
        diagnostics["text_table_text_clusters"],
        diagnostics["mixed_structure_parents"],
    )


def _collect_chunking_diagnostics(*, chunking_result: ChunkingResult) -> dict[str, int]:
    """彙整 chunk tree 的最小診斷資訊。

    參數：
    - `chunking_result`：已建立完成的 chunk tree。

    回傳：
    - `dict[str, int]`：供 log 與觀測使用的診斷計數。
    """

    child_kinds_by_section: dict[int, list[str]] = {}
    for child in chunking_result.child_chunks:
        child_kinds_by_section.setdefault(child.section_index, []).append(child.structure_kind)

    mixed_structure_parents = 0
    text_table_text_clusters = 0
    for kinds in child_kinds_by_section.values():
        unique_kinds = set(kinds)
        if len(unique_kinds) > 1:
            mixed_structure_parents += 1
        if kinds == ["text", "table", "text"]:
            text_table_text_clusters += 1

    return {
        "mixed_structure_parents": mixed_structure_parents,
        "text_table_text_clusters": text_table_text_clusters,
    }


def _format_failure_message(*, message: str, pdf_provider: str | None) -> str:
    """在失敗訊息中補上 PDF parser 路徑，方便從 DB 直接診斷。

    參數：
    - `message`：原始可讀失敗訊息。
    - `pdf_provider`：若為 PDF，實際使用的 provider。

    回傳：
    - `str`：補上 provider 前綴後的失敗訊息。
    """

    if not pdf_provider:
        return message
    return f"[pdf_provider={pdf_provider}] {message}"


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


def _build_pdf_parser_config(settings: AppSettings) -> PdfParserConfig:
    """將 API 設定物件映射為 PDF parser 參數。

    參數：
    - `settings`：目前 API 執行期設定。

    回傳：
    - `PdfParserConfig`：供 PDF parser provider 使用的參數物件。
    """

    return PdfParserConfig(
        provider=settings.pdf_parser_provider,
        llamaparse_api_key=settings.llamaparse_api_key,
        llamaparse_do_not_cache=settings.llamaparse_do_not_cache,
        llamaparse_merge_continued_tables=settings.llamaparse_merge_continued_tables,
    )
