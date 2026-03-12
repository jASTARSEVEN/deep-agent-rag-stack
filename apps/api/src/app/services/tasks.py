"""API 端 Celery dispatch 與測試 inline ingest 輔助。"""

from celery import Celery
from fastapi import Request

from app.core.settings import AppSettings


# Documents ingest task 的固定名稱。
INGEST_DOCUMENT_TASK_NAME = "worker.tasks.ingest.process_document_ingest"

# API 與 worker 共用的 Celery queue 名稱。
DEFAULT_TASK_QUEUE_NAME = "default"


def build_celery_client(settings: AppSettings) -> Celery:
    """建立 API 用 Celery client。

    參數：
    - `settings`：包含 Celery broker 與 result backend 設定的應用程式設定。

    回傳：
    - `Celery`：供 API 派送背景任務使用的 Celery client。
    """

    client = Celery(
        f"{settings.service_name}-producer",
        broker=settings.celery_broker_url,
        backend=settings.celery_result_backend,
    )
    client.conf.update(task_default_queue=DEFAULT_TASK_QUEUE_NAME)
    return client


def get_celery_client(request: Request) -> Celery:
    """從應用程式狀態讀取 Celery client。

    參數：
    - `request`：目前 HTTP request；用來讀取 `app.state.celery_client`。

    回傳：
    - `Celery`：目前應用程式使用的 Celery client。
    """

    return request.app.state.celery_client


def dispatch_document_ingest(celery_client: Celery, *, job_id: str) -> None:
    """派送文件 ingest task。

    參數：
    - `celery_client`：用來送出背景任務的 Celery client。
    - `job_id`：要處理的 ingest job 識別碼。

    回傳：
    - `None`：此函式只負責送出任務，不回傳業務資料。
    """

    celery_client.send_task(
        INGEST_DOCUMENT_TASK_NAME,
        kwargs={"job_id": job_id},
        queue=DEFAULT_TASK_QUEUE_NAME,
    )
