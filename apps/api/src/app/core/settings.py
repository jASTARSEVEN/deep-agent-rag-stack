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
    "CHUNK_MIN_PARENT_SECTION_LENGTH",
    "CHUNK_TARGET_CHILD_SIZE",
    "CHUNK_CHILD_OVERLAP",
    "CHUNK_CONTENT_PREVIEW_LENGTH",
    "CHUNK_TXT_PARENT_GROUP_SIZE",
    "CHUNK_TABLE_PRESERVE_MAX_CHARS",
    "CHUNK_TABLE_MAX_ROWS_PER_CHILD",
    "EMBEDDING_DIMENSIONS",
    "RETRIEVAL_VECTOR_TOP_K",
    "RETRIEVAL_FTS_TOP_K",
    "RETRIEVAL_MAX_CANDIDATES",
    "RETRIEVAL_RRF_K",
    "RETRIEVAL_HNSW_EF_SEARCH",
    "RERANK_TOP_N",
    "RERANK_MAX_CHARS_PER_DOC",
    "ASSEMBLER_MAX_CONTEXTS",
    "ASSEMBLER_MAX_CHARS_PER_CONTEXT",
    "ASSEMBLER_MAX_CHILDREN_PER_PARENT",
    "CHAT_PROVIDER",
    "CHAT_MODEL",
    "CHAT_MAX_OUTPUT_TOKENS",
    "CHAT_TIMEOUT_SECONDS",
    "CHAT_STREAM_CHUNK_SIZE",
    "CHAT_STREAM_DEBUG",
    "LANGGRAPH_SERVICE_PORT",
    "LANGSMITH_API_KEY",
    "LANGSMITH_ENDPOINT",
    "LANGSMITH_WORKSPACE_ID",
    "LANGSMITH_TRACING",
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
    chunk_table_preserve_max_chars: Annotated[int, Field(alias="CHUNK_TABLE_PRESERVE_MAX_CHARS")] = 4000
    chunk_table_max_rows_per_child: Annotated[int, Field(alias="CHUNK_TABLE_MAX_ROWS_PER_CHILD")] = 20
    celery_broker_url: Annotated[str, Field(alias="CELERY_BROKER_URL")] = "redis://redis:6379/0"
    celery_result_backend: Annotated[str, Field(alias="CELERY_RESULT_BACKEND")] = "redis://redis:6379/1"
    celery_broker_path: Annotated[Path, Field(alias="CELERY_BROKER_PATH")] = Path(".celery-broker")
    keycloak_url: Annotated[str, Field(alias="KEYCLOAK_URL")] = "http://keycloak:8080"
    keycloak_issuer: Annotated[str, Field(alias="KEYCLOAK_ISSUER")] = "http://localhost:18080/realms/deep-agent-dev"
    keycloak_jwks_url: Annotated[str, Field(alias="KEYCLOAK_JWKS_URL")] = (
        "http://keycloak:8080/realms/deep-agent-dev/protocol/openid-connect/certs"
    )
    keycloak_groups_claim: Annotated[str, Field(alias="KEYCLOAK_GROUPS_CLAIM")] = "groups"
    keycloak_admin_user: Annotated[str, Field(alias="KEYCLOAK_ADMIN")] = "admin"
    keycloak_admin_password: Annotated[str, Field(alias="KEYCLOAK_ADMIN_PASSWORD")] = "admin"
    keycloak_realm: Annotated[str, Field(alias="KEYCLOAK_REALM")] = "deep-agent-dev"
    auth_test_mode: Annotated[bool, Field(alias="AUTH_TEST_MODE")] = False
    embedding_provider: Annotated[str, Field(alias="EMBEDDING_PROVIDER")] = "openai"
    embedding_model: Annotated[str, Field(alias="EMBEDDING_MODEL")] = "text-embedding-3-small"
    embedding_dimensions: Annotated[int, Field(alias="EMBEDDING_DIMENSIONS")] = 1536
    openai_api_key: Annotated[str | None, Field(alias="OPENAI_API_KEY")] = None
    retrieval_vector_top_k: Annotated[int, Field(alias="RETRIEVAL_VECTOR_TOP_K")] = 8
    retrieval_fts_top_k: Annotated[int, Field(alias="RETRIEVAL_FTS_TOP_K")] = 8
    retrieval_max_candidates: Annotated[int, Field(alias="RETRIEVAL_MAX_CANDIDATES")] = 12
    retrieval_rrf_k: Annotated[int, Field(alias="RETRIEVAL_RRF_K")] = 60
    retrieval_hnsw_ef_search: Annotated[int, Field(alias="RETRIEVAL_HNSW_EF_SEARCH")] = 100
    rerank_provider: Annotated[str, Field(alias="RERANK_PROVIDER")] = "deterministic"
    rerank_model: Annotated[str, Field(alias="RERANK_MODEL")] = "rerank-v3.5"
    cohere_api_key: Annotated[str | None, Field(alias="COHERE_API_KEY")] = None
    rerank_top_n: Annotated[int, Field(alias="RERANK_TOP_N")] = 6
    rerank_max_chars_per_doc: Annotated[int, Field(alias="RERANK_MAX_CHARS_PER_DOC")] = 2000
    assembler_max_contexts: Annotated[int, Field(alias="ASSEMBLER_MAX_CONTEXTS")] = 6
    assembler_max_chars_per_context: Annotated[int, Field(alias="ASSEMBLER_MAX_CHARS_PER_CONTEXT")] = 2500
    assembler_max_children_per_parent: Annotated[int, Field(alias="ASSEMBLER_MAX_CHILDREN_PER_PARENT")] = 3
    chat_provider: Annotated[str, Field(alias="CHAT_PROVIDER")] = "deterministic"
    chat_model: Annotated[str, Field(alias="CHAT_MODEL")] = "gpt-4.1-mini"
    chat_max_output_tokens: Annotated[int, Field(alias="CHAT_MAX_OUTPUT_TOKENS")] = 700
    chat_timeout_seconds: Annotated[int, Field(alias="CHAT_TIMEOUT_SECONDS")] = 30
    chat_include_trace: Annotated[bool, Field(alias="CHAT_INCLUDE_TRACE")] = False
    chat_stream_chunk_size: Annotated[int, Field(alias="CHAT_STREAM_CHUNK_SIZE")] = 64
    chat_stream_debug: Annotated[bool, Field(alias="CHAT_STREAM_DEBUG")] = False
    langgraph_service_port: Annotated[int, Field(alias="LANGGRAPH_SERVICE_PORT")] = 8000
    langsmith_tracing: Annotated[bool, Field(alias="LANGSMITH_TRACING")] = False
    langsmith_api_key: Annotated[str | None, Field(alias="LANGSMITH_API_KEY")] = None
    langsmith_project: Annotated[str, Field(alias="LANGSMITH_PROJECT")] = "deep-agent-rag-stack"
    langsmith_endpoint: Annotated[str | None, Field(alias="LANGSMITH_ENDPOINT")] = None
    langsmith_workspace_id: Annotated[str | None, Field(alias="LANGSMITH_WORKSPACE_ID")] = None

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
