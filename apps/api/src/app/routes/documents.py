"""Documents 上傳、列表與詳情路由。"""

from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_principal
from app.auth.verifier import CurrentPrincipal
from app.core.settings import AppSettings, get_app_settings
from app.db.session import get_database_session
from app.schemas.documents import DocumentListResponse, DocumentSummary, UploadDocumentResponse
from app.services.documents import create_document_upload, get_document_detail, list_area_documents
from app.services.storage import ObjectStorage, build_object_storage
from app.services.tasks import get_celery_client


# Documents 相關最小授權路由集合。
router = APIRouter(tags=["documents"])


def get_object_storage(settings: AppSettings = Depends(get_app_settings)) -> ObjectStorage:
    """建立目前 request 使用的 object storage。

    參數：
    - `settings`：目前應用程式的儲存相關設定。

    回傳：
    - `ObjectStorage`：符合目前執行模式的物件儲存實作。
    """

    return build_object_storage(settings=settings)


@router.post(
    "/areas/{area_id}/documents",
    response_model=UploadDocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_document_route(
    area_id: str,
    file: UploadFile = File(...),
    principal: CurrentPrincipal = Depends(get_current_principal),
    settings: AppSettings = Depends(get_app_settings),
    storage: ObjectStorage = Depends(get_object_storage),
    celery_client=Depends(get_celery_client),
    session: Session = Depends(get_database_session),
) -> UploadDocumentResponse:
    """上傳單一文件並建立 ingest job。

    參數：
    - `area_id`：文件所屬 area 識別碼。
    - `file`：上傳的單一檔案。
    - `principal`：目前已驗證使用者。
    - `settings`：目前應用程式設定。
    - `storage`：原始檔物件儲存介面。
    - `celery_client`：用來派送 ingest task 的 Celery client。
    - `session`：目前 request 的資料庫 session。

    回傳：
    - `UploadDocumentResponse`：剛建立的 document 與 ingest job 摘要。
    """

    document, job = create_document_upload(
        session=session,
        principal=principal,
        settings=settings,
        storage=storage,
        celery_client=celery_client,
        area_id=area_id,
        upload=file,
    )
    return UploadDocumentResponse(document=document, job=job)


@router.get("/areas/{area_id}/documents", response_model=DocumentListResponse)
def list_documents_route(
    area_id: str,
    principal: CurrentPrincipal = Depends(get_current_principal),
    session: Session = Depends(get_database_session),
) -> DocumentListResponse:
    """列出指定 area 內文件。

    參數：
    - `area_id`：要查詢的 area 識別碼。
    - `principal`：目前已驗證使用者。
    - `session`：目前 request 的資料庫 session。

    回傳：
    - `DocumentListResponse`：指定 area 的文件清單。
    """

    return DocumentListResponse(items=list_area_documents(session=session, principal=principal, area_id=area_id))


@router.get("/documents/{document_id}", response_model=DocumentSummary)
def read_document_route(
    document_id: str,
    principal: CurrentPrincipal = Depends(get_current_principal),
    session: Session = Depends(get_database_session),
) -> DocumentSummary:
    """讀取單一文件詳情。

    參數：
    - `document_id`：要查詢的文件識別碼。
    - `principal`：目前已驗證使用者。
    - `session`：目前 request 的資料庫 session。

    回傳：
    - `DocumentSummary`：指定文件的摘要資料。
    """

    return get_document_detail(session=session, principal=principal, document_id=document_id)
