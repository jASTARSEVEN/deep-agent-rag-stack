"""API 測試與 E2E 使用的 inline ingest 流程。"""

from sqlalchemy.orm import Session

from app.db.models import Document, DocumentStatus, IngestJob, IngestJobStatus
from app.services.storage import ObjectStorage, StorageError


# Phase 3 MVP 真正支援的副檔名。
SUPPORTED_INLINE_EXTENSIONS = {".txt", ".md"}


def process_ingest_job_inline(session: Session, storage: ObjectStorage, *, job_id: str) -> None:
    """在同一行程內執行 ingest，供測試與 E2E 使用。

    參數：
    - `session`：用來讀寫 documents 與 ingest_jobs 的資料庫 session。
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

    job.status = IngestJobStatus.processing
    document.status = DocumentStatus.processing
    session.commit()

    try:
        payload = storage.get_object(object_key=document.storage_key)
        _parse_document(file_name=document.file_name, payload=payload)
    except (StorageError, ValueError, UnicodeDecodeError) as exc:
        job.status = IngestJobStatus.failed
        job.error_message = str(exc)
        document.status = DocumentStatus.failed
        session.commit()
        return

    job.status = IngestJobStatus.succeeded
    job.error_message = None
    document.status = DocumentStatus.ready
    session.commit()


def _parse_document(*, file_name: str, payload: bytes) -> str:
    """執行最小 parser routing。

    參數：
    - `file_name`：使用者上傳時的原始檔名。
    - `payload`：從物件儲存讀出的原始檔內容。

    回傳：
    - `str`：解析後的最小文字內容。
    """

    lower_name = file_name.lower()
    if any(lower_name.endswith(extension) for extension in SUPPORTED_INLINE_EXTENSIONS):
        text = payload.decode("utf-8")
        if not text.strip():
            raise ValueError("文件內容不可為空白。")
        return text
    raise ValueError("目前尚未支援此檔案類型的解析。")
