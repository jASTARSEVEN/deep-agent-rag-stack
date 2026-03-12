"""文件 ingest 任務與狀態轉換。"""

from worker.celery_app import celery_app
from worker.core.settings import get_settings
from worker.db import (
    Document,
    DocumentStatus,
    IngestJob,
    IngestJobStatus,
    create_database_engine,
    create_session_factory,
    session_scope,
)
from worker.parsers import parse_document
from worker.storage import StorageError, build_object_storage_reader


@celery_app.task(name="worker.tasks.ingest.process_document_ingest")
def process_document_ingest(job_id: str) -> str:
    """處理單一 ingest job，並更新 document/job 狀態。

    參數：
    - `job_id`：要處理的 ingest job 識別碼。

    回傳：
    - `str`：本次 task 執行結果代碼，例如 `succeeded`、`failed`、`job-skipped`。
    """

    settings = get_settings()
    session_factory = create_session_factory(create_database_engine(settings))
    storage = build_object_storage_reader(settings)

    with session_scope(session_factory) as session:
        job = session.get(IngestJob, job_id)
        if job is None:
            return "job-missing"
        if job.status != IngestJobStatus.queued:
            return "job-skipped"

        document = session.get(Document, job.document_id)
        if document is None:
            job.status = IngestJobStatus.failed
            job.error_message = "找不到對應的 document。"
            session.commit()
            return "document-missing"
        if document.status != DocumentStatus.uploaded:
            return "document-skipped"

        job.status = IngestJobStatus.processing
        document.status = DocumentStatus.processing
        session.commit()

        try:
            payload = storage.get_object(object_key=document.storage_key)
            parse_document(file_name=document.file_name, payload=payload)
        except (StorageError, ValueError, UnicodeDecodeError) as exc:
            job.status = IngestJobStatus.failed
            job.error_message = str(exc)
            document.status = DocumentStatus.failed
            session.commit()
            return "failed"

        job.status = IngestJobStatus.succeeded
        job.error_message = None
        document.status = DocumentStatus.ready
        session.commit()
        return "succeeded"
