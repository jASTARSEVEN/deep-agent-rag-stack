"""Worker 設定物件測試。"""

from worker.core.settings import WorkerSettings


def test_worker_settings_uses_defaults_for_empty_string_env_values() -> None:
    """空字串環境變數應回退為 worker 設定預設值。"""

    settings = WorkerSettings(
        MINIO_SECURE="",
        CELERY_WORKER_POOL="",
        CELERY_WORKER_CONCURRENCY="",
        CELERY_WORKER_PREFETCH_MULTIPLIER="",
        CELERY_WORKER_MAX_TASKS_PER_CHILD="",
        CHUNK_MIN_PARENT_SECTION_LENGTH="",
        CHUNK_TARGET_CHILD_SIZE="",
        CHUNK_CHILD_OVERLAP="",
        CHUNK_CONTENT_PREVIEW_LENGTH="",
        CHUNK_TXT_PARENT_GROUP_SIZE="",
        CHUNK_TABLE_PRESERVE_MAX_CHARS="",
        CHUNK_TABLE_MAX_ROWS_PER_CHILD="",
        MARKER_FORCE_OCR="",
        MARKER_STRIP_EXISTING_OCR="",
        MARKER_USE_LLM="",
        MARKER_LLM_SERVICE="",
        MARKER_OPENAI_API_KEY="",
        MARKER_OPENAI_MODEL="",
        MARKER_OPENAI_BASE_URL="",
        MARKER_DISABLE_IMAGE_EXTRACTION="",
        LLAMAPARSE_DO_NOT_CACHE="",
        LLAMAPARSE_MERGE_CONTINUED_TABLES="",
    )

    assert settings.minio_secure is False
    assert settings.worker_pool == "solo"
    assert settings.worker_concurrency == 1
    assert settings.worker_prefetch_multiplier == 1
    assert settings.worker_max_tasks_per_child == 1
    assert settings.chunk_min_parent_section_length == 300
    assert settings.chunk_target_child_size == 800
    assert settings.chunk_child_overlap == 120
    assert settings.chunk_content_preview_length == 120
    assert settings.chunk_txt_parent_group_size == 4
    assert settings.chunk_table_preserve_max_chars == 4000
    assert settings.chunk_table_max_rows_per_child == 20
    assert settings.marker_force_ocr is False
    assert settings.marker_strip_existing_ocr is False
    assert settings.marker_use_llm is False
    assert settings.marker_llm_service == "marker.services.openai.OpenAIService"
    assert settings.marker_openai_api_key is None
    assert settings.marker_openai_model == "gpt-4.1-mini"
    assert settings.marker_openai_base_url is None
    assert settings.marker_disable_image_extraction is True
    assert settings.llamaparse_do_not_cache is True
    assert settings.llamaparse_merge_continued_tables is False
