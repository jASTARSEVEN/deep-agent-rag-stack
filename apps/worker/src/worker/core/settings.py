"""Celery 骨架 worker 使用的設定物件。"""

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# 本機開發命令預設使用的環境變數檔名稱。
ENV_FILE_NAME = ".env"


EMPTY_STRING_ENV_KEYS = {
    "MINIO_SECURE",
    "CELERY_WORKER_POOL",
    "CELERY_WORKER_CONCURRENCY",
    "CELERY_WORKER_PREFETCH_MULTIPLIER",
    "CELERY_WORKER_MAX_TASKS_PER_CHILD",
    "CHUNK_MIN_PARENT_SECTION_LENGTH",
    "CHUNK_TARGET_CHILD_SIZE",
    "CHUNK_CHILD_OVERLAP",
    "CHUNK_CONTENT_PREVIEW_LENGTH",
    "CHUNK_TXT_PARENT_GROUP_SIZE",
    "CHUNK_TABLE_PRESERVE_MAX_CHARS",
    "CHUNK_TABLE_MAX_ROWS_PER_CHILD",
    "EMBEDDING_DIMENSIONS",
    "MARKER_FORCE_OCR",
    "MARKER_STRIP_EXISTING_OCR",
    "MARKER_USE_LLM",
    "MARKER_LLM_SERVICE",
    "MARKER_OPENAI_API_KEY",
    "MARKER_OPENAI_MODEL",
    "MARKER_OPENAI_BASE_URL",
    "MARKER_DISABLE_IMAGE_EXTRACTION",
    "LLAMAPARSE_DO_NOT_CACHE",
    "LLAMAPARSE_MERGE_CONTINUED_TABLES",
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


class WorkerSettings(BaseSettings):
    """Celery 骨架 worker 的執行期設定。"""

    model_config = SettingsConfigDict(env_file=ENV_FILE_NAME, env_file_encoding="utf-8", extra="ignore")

    service_name: Annotated[str, Field(alias="WORKER_SERVICE_NAME")] = "deep-agent-worker"
    database_url: Annotated[str, Field(alias="DATABASE_URL")] = "postgresql://app:app@postgres:5432/deep_agent_rag"
    broker_url: Annotated[str, Field(alias="CELERY_BROKER_URL")] = "redis://redis:6379/0"
    result_backend: Annotated[str, Field(alias="CELERY_RESULT_BACKEND")] = "redis://redis:6379/1"
    worker_pool: Annotated[str, Field(alias="CELERY_WORKER_POOL")] = "solo"
    worker_concurrency: Annotated[int, Field(alias="CELERY_WORKER_CONCURRENCY")] = 1
    worker_prefetch_multiplier: Annotated[int, Field(alias="CELERY_WORKER_PREFETCH_MULTIPLIER")] = 1
    worker_max_tasks_per_child: Annotated[int, Field(alias="CELERY_WORKER_MAX_TASKS_PER_CHILD")] = 1
    storage_backend: Annotated[str, Field(alias="STORAGE_BACKEND")] = "minio"
    minio_endpoint: Annotated[str, Field(alias="MINIO_ENDPOINT")] = "http://minio:9000"
    minio_access_key: Annotated[str, Field(alias="MINIO_ACCESS_KEY")] = "minio"
    minio_secret_key: Annotated[str, Field(alias="MINIO_SECRET_KEY")] = "minio123"
    minio_secure: Annotated[bool, Field(alias="MINIO_SECURE")] = False
    minio_bucket: Annotated[str, Field(alias="MINIO_BUCKET")] = "documents"
    local_storage_path: Annotated[Path, Field(alias="LOCAL_STORAGE_PATH")] = Path(".local-storage")
    chunk_min_parent_section_length: Annotated[int, Field(alias="CHUNK_MIN_PARENT_SECTION_LENGTH")] = 300
    chunk_target_child_size: Annotated[int, Field(alias="CHUNK_TARGET_CHILD_SIZE")] = 800
    chunk_child_overlap: Annotated[int, Field(alias="CHUNK_CHILD_OVERLAP")] = 120
    chunk_content_preview_length: Annotated[int, Field(alias="CHUNK_CONTENT_PREVIEW_LENGTH")] = 120
    chunk_txt_parent_group_size: Annotated[int, Field(alias="CHUNK_TXT_PARENT_GROUP_SIZE")] = 4
    chunk_table_preserve_max_chars: Annotated[int, Field(alias="CHUNK_TABLE_PRESERVE_MAX_CHARS")] = 4000
    chunk_table_max_rows_per_child: Annotated[int, Field(alias="CHUNK_TABLE_MAX_ROWS_PER_CHILD")] = 20
    pdf_parser_provider: Annotated[str, Field(alias="PDF_PARSER_PROVIDER")] = "marker"
    marker_model_cache_dir: Annotated[Path, Field(alias="MARKER_MODEL_CACHE_DIR")] = Path(".marker-cache/models")
    marker_force_ocr: Annotated[bool, Field(alias="MARKER_FORCE_OCR")] = False
    marker_strip_existing_ocr: Annotated[bool, Field(alias="MARKER_STRIP_EXISTING_OCR")] = False
    marker_use_llm: Annotated[bool, Field(alias="MARKER_USE_LLM")] = False
    marker_llm_service: Annotated[str, Field(alias="MARKER_LLM_SERVICE")] = "marker.services.openai.OpenAIService"
    marker_openai_api_key: Annotated[str | None, Field(alias="MARKER_OPENAI_API_KEY")] = None
    marker_openai_model: Annotated[str, Field(alias="MARKER_OPENAI_MODEL")] = "gpt-4.1-mini"
    marker_openai_base_url: Annotated[str | None, Field(alias="MARKER_OPENAI_BASE_URL")] = None
    marker_disable_image_extraction: Annotated[bool, Field(alias="MARKER_DISABLE_IMAGE_EXTRACTION")] = True
    llamaparse_api_key: Annotated[str | None, Field(alias="LLAMAPARSE_API_KEY")] = None
    llamaparse_do_not_cache: Annotated[bool, Field(alias="LLAMAPARSE_DO_NOT_CACHE")] = True
    llamaparse_merge_continued_tables: Annotated[bool, Field(alias="LLAMAPARSE_MERGE_CONTINUED_TABLES")] = False
    embedding_provider: Annotated[str, Field(alias="EMBEDDING_PROVIDER")] = "openai"
    embedding_model: Annotated[str, Field(alias="EMBEDDING_MODEL")] = "text-embedding-3-small"
    embedding_dimensions: Annotated[int, Field(alias="EMBEDDING_DIMENSIONS")] = 1536
    openai_api_key: Annotated[str | None, Field(alias="OPENAI_API_KEY")] = None

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
def get_settings() -> WorkerSettings:
    """回傳快取後的設定物件，確保同一個行程內設定一致。

    參數：
    - 無

    回傳：
    - `WorkerSettings`：目前行程共用的 worker 執行期設定。
    """

    return WorkerSettings()
