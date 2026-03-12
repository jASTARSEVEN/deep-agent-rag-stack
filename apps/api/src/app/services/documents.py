"""Documents 與 ingest jobs service。"""

from pathlib import PurePosixPath
from uuid import uuid4

from celery import Celery
from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.verifier import CurrentPrincipal
from app.core.settings import AppSettings
from app.db.models import Document, DocumentStatus, IngestJob, IngestJobStatus, Role
from app.schemas.documents import DocumentSummary, IngestJobSummary
from app.services.access import require_area_access, require_minimum_area_role
from app.services.ingest import process_ingest_job_inline
from app.services.storage import ObjectStorage
from app.services.tasks import dispatch_document_ingest


# Phase 3 MVP 真正支援解析的副檔名。
SUPPORTED_TEXT_EXTENSIONS = {".txt", ".md"}

# 產品範圍內但本 phase 尚未真正處理的副檔名。
RECOGNIZED_EXTENSIONS = {".txt", ".md", ".pdf", ".docx", ".pptx", ".html"}

# 若瀏覽器沒有帶 content type，退回使用的 MIME 類型。
DEFAULT_TEXT_CONTENT_TYPE = "text/plain"


def create_document_upload(
    session: Session,
    principal: CurrentPrincipal,
    settings: AppSettings,
    storage: ObjectStorage,
    celery_client: Celery,
    *,
    area_id: str,
    upload: UploadFile,
) -> tuple[DocumentSummary, IngestJobSummary]:
    """驗證、寫入儲存、建立 document/job，並派送 ingest。

    參數：
    - `session`：用來建立文件與 job 的資料庫 session。
    - `principal`：目前已驗證使用者。
    - `settings`：應用程式設定，包含 upload 與 ingest 模式。
    - `storage`：原始檔物件儲存介面。
    - `celery_client`：用來派送 ingest task 的 Celery client。
    - `area_id`：文件所屬 area 識別碼。
    - `upload`：上傳的單一檔案。

    回傳：
    - `tuple[DocumentSummary, IngestJobSummary]`：剛建立的文件與 ingest job 摘要。
    """

    require_minimum_area_role(session=session, principal=principal, area_id=area_id, minimum_role=Role.maintainer)

    file_name, content_type, payload = _read_validated_upload(settings=settings, upload=upload)
    document_id = str(uuid4())
    storage_key = str(PurePosixPath(area_id) / document_id / file_name)
    storage.put_object(object_key=storage_key, payload=payload, content_type=content_type)

    document = Document(
        id=document_id,
        area_id=area_id,
        file_name=file_name,
        content_type=content_type,
        file_size=len(payload),
        storage_key=storage_key,
        status=DocumentStatus.uploaded,
    )
    job = IngestJob(document_id=document.id, status=IngestJobStatus.queued)
    session.add_all([document, job])
    session.commit()
    session.refresh(document)
    session.refresh(job)
    if settings.ingest_inline_mode:
        process_ingest_job_inline(session=session, storage=storage, job_id=job.id)
        session.refresh(document)
        session.refresh(job)
    else:
        dispatch_document_ingest(celery_client=celery_client, job_id=job.id)
    return build_document_summary(document), build_ingest_job_summary(job)


def list_area_documents(session: Session, principal: CurrentPrincipal, *, area_id: str) -> list[DocumentSummary]:
    """列出指定 area 內文件。

    參數：
    - `session`：用來查詢文件的資料庫 session。
    - `principal`：目前已驗證使用者。
    - `area_id`：要查詢的 area 識別碼。

    回傳：
    - `list[DocumentSummary]`：指定 area 內可見的文件清單。
    """

    require_area_access(session=session, principal=principal, area_id=area_id)
    documents = session.scalars(
        select(Document).where(Document.area_id == area_id).order_by(Document.created_at.desc())
    ).all()
    return [build_document_summary(item) for item in documents]


def get_document_detail(session: Session, principal: CurrentPrincipal, *, document_id: str) -> DocumentSummary:
    """取得單一文件詳情。

    參數：
    - `session`：用來查詢文件的資料庫 session。
    - `principal`：目前已驗證使用者。
    - `document_id`：要查詢的文件識別碼。

    回傳：
    - `DocumentSummary`：指定文件的摘要資料。
    """

    document = session.get(Document, document_id)
    if document is None:
        raise _build_document_not_found_error()
    try:
        require_area_access(session=session, principal=principal, area_id=document.area_id)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_404_NOT_FOUND:
            raise _build_document_not_found_error() from exc
        raise
    return build_document_summary(document)


def get_ingest_job_detail(session: Session, principal: CurrentPrincipal, *, job_id: str) -> IngestJobSummary:
    """取得單一 ingest job 詳情。

    參數：
    - `session`：用來查詢 ingest job 的資料庫 session。
    - `principal`：目前已驗證使用者。
    - `job_id`：要查詢的 ingest job 識別碼。

    回傳：
    - `IngestJobSummary`：指定 ingest job 的摘要資料。
    """

    job = session.get(IngestJob, job_id)
    if job is None:
        raise _build_job_not_found_error()
    document = session.get(Document, job.document_id)
    if document is None:
        raise _build_job_not_found_error()
    try:
        require_area_access(session=session, principal=principal, area_id=document.area_id)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_404_NOT_FOUND:
            raise _build_job_not_found_error() from exc
        raise
    return build_ingest_job_summary(job)


def build_document_summary(document: Document) -> DocumentSummary:
    """將 document model 轉成 API schema。

    參數：
    - `document`：ORM document model。

    回傳：
    - `DocumentSummary`：可供 API 回傳的文件摘要資料。
    """

    return DocumentSummary(
        id=document.id,
        area_id=document.area_id,
        file_name=document.file_name,
        content_type=document.content_type,
        file_size=document.file_size,
        status=document.status,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


def build_ingest_job_summary(job: IngestJob) -> IngestJobSummary:
    """將 ingest job model 轉成 API schema。

    參數：
    - `job`：ORM ingest job model。

    回傳：
    - `IngestJobSummary`：可供 API 回傳的 ingest job 摘要資料。
    """

    return IngestJobSummary(
        id=job.id,
        document_id=job.document_id,
        status=job.status,
        error_message=job.error_message,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


def _read_validated_upload(settings: AppSettings, upload: UploadFile) -> tuple[str, str, bytes]:
    """驗證上傳檔案並回傳標準化資訊。

    參數：
    - `settings`：包含上傳大小限制等設定的應用程式設定。
    - `upload`：待驗證的上傳檔案。

    回傳：
    - `tuple[str, str, bytes]`：標準化後的檔名、content type 與原始位元組內容。
    """

    file_name = (upload.filename or "").strip()
    if not file_name:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="檔名不可為空。")

    extension = _extract_extension(file_name)
    if extension not in RECOGNIZED_EXTENSIONS:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="目前不支援此檔案類型。")

    payload = upload.file.read()
    if not payload:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="上傳檔案不可為空。")
    if len(payload) > settings.max_upload_size_bytes:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="檔案超過上傳大小限制。")

    content_type = (upload.content_type or DEFAULT_TEXT_CONTENT_TYPE).strip() or DEFAULT_TEXT_CONTENT_TYPE
    return file_name, content_type, payload


def _extract_extension(file_name: str) -> str:
    """取得標準化副檔名。

    參數：
    - `file_name`：待解析副檔名的檔名。

    回傳：
    - `str`：標準化副檔名；若無法識別則回傳空字串。
    """

    lower_name = file_name.lower()
    for extension in sorted(RECOGNIZED_EXTENSIONS, key=len, reverse=True):
        if lower_name.endswith(extension):
            return extension
    return ""


def _build_document_not_found_error() -> HTTPException:
    """建立文件不存在或未授權時共用的 404。

    參數：
    - 無

    回傳：
    - `HTTPException`：用來隱藏文件存在性的 404 例外。
    """

    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到指定的 document。")


def _build_job_not_found_error() -> HTTPException:
    """建立 ingest job 不存在或未授權時共用的 404。

    參數：
    - 無

    回傳：
    - `HTTPException`：用來隱藏 ingest job 存在性的 404 例外。
    """

    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到指定的 ingest job。")
