"""Celery 骨架 worker 使用的設定物件。"""

from functools import lru_cache
from typing import Annotated

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# 本機開發命令預設使用的環境變數檔名稱。
ENV_FILE_NAME = ".env"


class WorkerSettings(BaseSettings):
    """Celery 骨架 worker 的執行期設定。"""

    model_config = SettingsConfigDict(env_file=ENV_FILE_NAME, env_file_encoding="utf-8", extra="ignore")

    service_name: Annotated[str, Field(alias="WORKER_SERVICE_NAME")] = "deep-agent-worker"
    broker_url: Annotated[str, Field(alias="CELERY_BROKER_URL")] = "redis://redis:6379/0"
    result_backend: Annotated[str, Field(alias="CELERY_RESULT_BACKEND")] = "redis://redis:6379/1"


@lru_cache(maxsize=1)
def get_settings() -> WorkerSettings:
    """回傳快取後的設定物件，確保同一個行程內設定一致。"""

    return WorkerSettings()
