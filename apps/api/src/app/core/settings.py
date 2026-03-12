"""FastAPI 服務的執行期設定與設定依賴。"""

from functools import lru_cache
from typing import Annotated

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from fastapi import Request


# 本機開發命令預設使用的環境變數檔名稱。
ENV_FILE_NAME = ".env"


class AppSettings(BaseSettings):
    """FastAPI 服務的執行期設定。"""

    model_config = SettingsConfigDict(env_file=ENV_FILE_NAME, env_file_encoding="utf-8", extra="ignore")

    service_name: Annotated[str, Field(alias="API_SERVICE_NAME")] = "deep-agent-api"
    version: Annotated[str, Field(alias="API_VERSION")] = "0.1.0"
    host: Annotated[str, Field(alias="API_HOST")] = "0.0.0.0"
    port: Annotated[int, Field(alias="API_PORT")] = 8000
    cors_origins: Annotated[str, Field(alias="API_CORS_ORIGINS")] = "http://localhost:13000"
    database_url: Annotated[str, Field(alias="DATABASE_URL")] = "postgresql://app:app@postgres:5432/deep_agent_rag"
    database_echo: Annotated[bool, Field(alias="DATABASE_ECHO")] = False
    redis_url: Annotated[str, Field(alias="REDIS_URL")] = "redis://redis:6379/0"
    minio_endpoint: Annotated[str, Field(alias="MINIO_ENDPOINT")] = "http://minio:9000"
    minio_bucket: Annotated[str, Field(alias="MINIO_BUCKET")] = "documents"
    keycloak_url: Annotated[str, Field(alias="KEYCLOAK_URL")] = "http://keycloak:8080"
    keycloak_issuer: Annotated[str, Field(alias="KEYCLOAK_ISSUER")] = "http://localhost:18080/realms/deep-agent-dev"
    keycloak_jwks_url: Annotated[str, Field(alias="KEYCLOAK_JWKS_URL")] = (
        "http://keycloak:8080/realms/deep-agent-dev/protocol/openid-connect/certs"
    )
    keycloak_groups_claim: Annotated[str, Field(alias="KEYCLOAK_GROUPS_CLAIM")] = "groups"
    auth_test_mode: Annotated[bool, Field(alias="AUTH_TEST_MODE")] = False


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """回傳快取後的設定物件，確保同一個行程內設定一致。"""

    return AppSettings()


def get_app_settings(request: Request) -> AppSettings:
    """從應用程式狀態讀取設定。

    前置條件：
    - `app.main.create_app()` 必須已將 `settings` 放入 `app.state`。

    風險：
    - 若繞過此 dependency 直接呼叫 `get_settings()`，測試或多實例情境可能讀到錯誤設定。
    """

    return request.app.state.settings
