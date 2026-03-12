"""Worker ingest task 測試。"""

from pathlib import Path

from worker.core.settings import WorkerSettings
from worker.db import (
    Base,
    Document,
    DocumentStatus,
    IngestJob,
    IngestJobStatus,
    create_database_engine,
    create_session_factory,
)
from worker.tasks.ingest import process_document_ingest


def build_settings(tmp_path: Path) -> WorkerSettings:
    """建立 worker 測試用設定。

    參數：
    - `tmp_path`：pytest 提供的暫存目錄。

    回傳：
    - `WorkerSettings`：供 worker 測試使用的設定物件。
    """

    return WorkerSettings(
        WORKER_SERVICE_NAME="deep-agent-worker-test",
        DATABASE_URL=f"sqlite+pysqlite:///{tmp_path / 'worker.sqlite'}",
        CELERY_BROKER_URL="redis://redis:6379/0",
        CELERY_RESULT_BACKEND="redis://redis:6379/1",
        STORAGE_BACKEND="filesystem",
        LOCAL_STORAGE_PATH=tmp_path / "storage",
        MINIO_ENDPOINT="http://minio:9000",
        MINIO_ACCESS_KEY="minio",
        MINIO_SECRET_KEY="minio123",
        MINIO_BUCKET="documents",
    )


def seed_job(session_factory, *, file_name: str, payload: bytes, status=DocumentStatus.uploaded, job_status=IngestJobStatus.queued):
    """建立測試用 document/job 與對應原始檔。

    參數：
    - `session_factory`：用來建立測試資料庫 session 的 factory。
    - `file_name`：測試文件檔名。
    - `payload`：測試文件原始內容。
    - `status`：文件初始狀態。
    - `job_status`：ingest job 初始狀態。

    回傳：
    - 包含 `Document` 與 `IngestJob` 的 tuple。
    """

    with session_factory() as session:
        document = Document(
            id="document-1",
            area_id="area-1",
            file_name=file_name,
            content_type="text/markdown",
            file_size=len(payload),
            storage_key="area-1/document-1/" + file_name,
            status=status,
        )
        job = IngestJob(id="job-1", document_id=document.id, status=job_status)
        session.add_all([document, job])
        session.commit()
        return document, job


def test_process_document_ingest_updates_ready(monkeypatch, tmp_path: Path) -> None:
    """支援的 md 文件應推進到 ready/succeeded。"""

    settings = build_settings(tmp_path)
    monkeypatch.setattr("worker.tasks.ingest.get_settings", lambda: settings)
    engine = create_database_engine(settings)
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    document, job = seed_job(session_factory, file_name="notes.md", payload=b"# Title\ncontent")
    storage_path = Path(settings.local_storage_path) / document.storage_key
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    storage_path.write_bytes(b"# Title\ncontent")

    result = process_document_ingest(job.id)

    with session_factory() as session:
        refreshed_document = session.get(Document, document.id)
        refreshed_job = session.get(IngestJob, job.id)
        assert result == "succeeded"
        assert refreshed_document is not None
        assert refreshed_document.status == DocumentStatus.ready
        assert refreshed_job is not None
        assert refreshed_job.status == IngestJobStatus.succeeded


def test_process_document_ingest_marks_failed_for_unsupported_type(monkeypatch, tmp_path: Path) -> None:
    """未支援副檔名應轉為 failed。"""

    settings = build_settings(tmp_path)
    monkeypatch.setattr("worker.tasks.ingest.get_settings", lambda: settings)
    engine = create_database_engine(settings)
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    document, job = seed_job(session_factory, file_name="deck.pdf", payload=b"%PDF-1.4")
    storage_path = Path(settings.local_storage_path) / document.storage_key
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    storage_path.write_bytes(b"%PDF-1.4")

    result = process_document_ingest(job.id)

    with session_factory() as session:
        refreshed_document = session.get(Document, document.id)
        refreshed_job = session.get(IngestJob, job.id)
        assert result == "failed"
        assert refreshed_document is not None
        assert refreshed_document.status == DocumentStatus.failed
        assert refreshed_job is not None
        assert refreshed_job.status == IngestJobStatus.failed
        assert refreshed_job.error_message == "目前尚未支援此檔案類型的解析。"


def test_process_document_ingest_skips_non_queued_job(monkeypatch, tmp_path: Path) -> None:
    """非 queued 的 job 不應重複處理。"""

    settings = build_settings(tmp_path)
    monkeypatch.setattr("worker.tasks.ingest.get_settings", lambda: settings)
    engine = create_database_engine(settings)
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    document, job = seed_job(
        session_factory,
        file_name="notes.md",
        payload=b"# Title\ncontent",
        job_status=IngestJobStatus.processing,
    )

    result = process_document_ingest(job.id)

    with session_factory() as session:
        refreshed_document = session.get(Document, document.id)
        refreshed_job = session.get(IngestJob, job.id)
        assert result == "job-skipped"
        assert refreshed_document is not None
        assert refreshed_document.status == DocumentStatus.uploaded
        assert refreshed_job is not None
        assert refreshed_job.status == IngestJobStatus.processing
