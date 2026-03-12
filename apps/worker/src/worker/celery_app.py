"""Worker 骨架的 Celery 應用程式進入點。"""

from celery import Celery

from worker.core.settings import get_settings


def create_celery_app() -> Celery:
    """建立並設定 Celery 應用程式實例。

    參數：
    - 無

    回傳：
    - `Celery`：已完成基本 queue 與 serializer 設定的 Celery 應用程式。
    """

    settings = get_settings()
    application = Celery(
        settings.service_name,
        broker=settings.broker_url,
        backend=settings.result_backend,
    )
    application.conf.update(
        task_default_queue="default",
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
    )
    application.autodiscover_tasks(["worker.tasks"])
    return application


celery_app = create_celery_app()
