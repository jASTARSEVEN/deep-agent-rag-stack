"""FastAPI 服務的執行期設定與設定依賴。"""

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from fastapi import Request


# 本機開發命令預設使用的環境變數檔名稱。
ENV_FILE_NAME = ".env"

EMPTY_STRING_ENV_KEYS = {
    "MINIO_SECURE",
    "MAX_UPLOAD_SIZE_BYTES",
    "INGEST_INLINE_MODE",
    "CHUNK_MIN_PARENT_SECTION_LENGTH",
    "CHUNK_TARGET_CHILD_SIZE",
    "CHUNK_CHILD_OVERLAP",
    "CHUNK_CONTENT_PREVIEW_LENGTH",
    "CHUNK_TXT_PARENT_GROUP_SIZE",
}


def _drop_empty_string_env_values(data: Any) -> Any:
    """移除值為空字串的設定輸入，讓欄位回退預設值。

    Args:
        data: Pydantic 在 model 驗證前收到的原始輸入資料。

    Returns:
        若輸入為 dict，會移除指定欄位中的空字串值；否則保留原值。
    """

    if not isinstance(data, dict):
        return data

    normalized_data = dict(data)
    for key in EMPTY_STRING_ENV_KEYS:
        value = normalized_data.get(key)
        if isinstance(value, str) and value.strip() == "":
            normalized_data.pop(key)
    return normalized_data


class AppSettings(BaseSettings):
    """FastAPI 服務的執行期設定。"""

    model_config = SettingsConfigDict(env_file=ENV_FILE_NAME, env_file_encoding="utf-8", extra="ignore")

    service_name: Annotated[str, Field(alias="API_SERVICE_NAME")] = "deep-agent-api"
    version: Annotated[str, Field(alias="API_VERSION")] = "0.1.0"
    host: Annotated[str, Field(alias="API_HOST")] = "0.0.0.0"
    port: Annotated[int, Field(alias="API_PORT")] = 8000
    cors_origins: Annotated[str, Field(alias="API_CORS_ORIGINS")] = "http://localhost:3000,http://localhost:13000"
    database_url: Annotated[str, Field(alias="DATABASE_URL")] = "postgresql://app:app@postgres:5432/deep_agent_rag"
    database_echo: Annotated[bool, Field(alias="DATABASE_ECHO")] = False
    redis_url: Annotated[str, Field(alias="REDIS_URL")] = "redis://redis:6379/0"
    storage_backend: Annotated[str, Field(alias="STORAGE_BACKEND")] = "minio"
    minio_endpoint: Annotated[str, Field(alias="MINIO_ENDPOINT")] = "http://minio:9000"
    minio_access_key: Annotated[str, Field(alias="MINIO_ACCESS_KEY")] = "minio"
    minio_secret_key: Annotated[str, Field(alias="MINIO_SECRET_KEY")] = "minio123"
    minio_secure: Annotated[bool, Field(alias="MINIO_SECURE")] = False
    minio_bucket: Annotated[str, Field(alias="MINIO_BUCKET")] = "documents"
    local_storage_path: Annotated[Path, Field(alias="LOCAL_STORAGE_PATH")] = Path(".local-storage")
    max_upload_size_bytes: Annotated[int, Field(alias="MAX_UPLOAD_SIZE_BYTES")] = 5 * 1024 * 1024
    chunk_min_parent_section_length: Annotated[int, Field(alias="CHUNK_MIN_PARENT_SECTION_LENGTH")] = 300
    chunk_target_child_size: Annotated[int, Field(alias="CHUNK_TARGET_CHILD_SIZE")] = 800
    chunk_child_overlap: Annotated[int, Field(alias="CHUNK_CHILD_OVERLAP")] = 120
    chunk_content_preview_length: Annotated[int, Field(alias="CHUNK_CONTENT_PREVIEW_LENGTH")] = 120
    chunk_txt_parent_group_size: Annotated[int, Field(alias="CHUNK_TXT_PARENT_GROUP_SIZE")] = 4
    celery_broker_url: Annotated[str, Field(alias="CELERY_BROKER_URL")] = "redis://redis:6379/0"
    celery_result_backend: Annotated[str, Field(alias="CELERY_RESULT_BACKEND")] = "redis://redis:6379/1"
    ingest_inline_mode: Annotated[bool, Field(alias="INGEST_INLINE_MODE")] = False
    keycloak_url: Annotated[str, Field(alias="KEYCLOAK_URL")] = "http://keycloak:8080"
    keycloak_issuer: Annotated[str, Field(alias="KEYCLOAK_ISSUER")] = "http://localhost:18080/realms/deep-agent-dev"
    keycloak_jwks_url: Annotated[str, Field(alias="KEYCLOAK_JWKS_URL")] = (
        "http://keycloak:8080/realms/deep-agent-dev/protocol/openid-connect/certs"
    )
    keycloak_groups_claim: Annotated[str, Field(alias="KEYCLOAK_GROUPS_CLAIM")] = "groups"
    auth_test_mode: Annotated[bool, Field(alias="AUTH_TEST_MODE")] = False

    @model_validator(mode="before")
    @classmethod
    def normalize_empty_string_env(cls, data: Any) -> Any:
        """將 compose 注入的空字串欄位移除，避免覆蓋預設值。

        Args:
            data: model 驗證前收到的原始設定輸入。

        Returns:
            已移除空字串設定的輸入資料。
        """

        return _drop_empty_string_env_values(data)


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """回傳快取後的設定物件，確保同一個行程內設定一致。

    參數：
    - 無

    回傳：
    - `AppSettings`：目前行程共用的 API 執行期設定。
    """

    return AppSettings()


def get_app_settings(request: Request) -> AppSettings:
    """從應用程式狀態讀取設定。

    參數：
    - `request`：目前 HTTP request；用來讀取 `app.state.settings`。

    回傳：
    - `AppSettings`：目前 request 所屬應用程式的設定物件。

    前置條件：
    - `app.main.create_app()` 必須已將 `settings` 放入 `app.state`。

    風險：
    - 若繞過此 dependency 直接呼叫 `get_settings()`，測試或多實例情境可能讀到錯誤設定。
    """

    return request.app.state.settings
