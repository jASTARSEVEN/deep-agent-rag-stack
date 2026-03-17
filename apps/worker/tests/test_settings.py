"""Worker 設定物件測試。"""

from worker.core.settings import WorkerSettings


def test_worker_settings_uses_defaults_for_empty_string_env_values() -> None:
    """空字串環境變數應回退為 worker 設定預設值。"""

    settings = WorkerSettings(
        MINIO_SECURE="",
        CHUNK_MIN_PARENT_SECTION_LENGTH="",
        CHUNK_TARGET_CHILD_SIZE="",
        CHUNK_CHILD_OVERLAP="",
        CHUNK_CONTENT_PREVIEW_LENGTH="",
        CHUNK_TXT_PARENT_GROUP_SIZE="",
        CHUNK_TABLE_PRESERVE_MAX_CHARS="",
        CHUNK_TABLE_MAX_ROWS_PER_CHILD="",
        LLAMAPARSE_DO_NOT_CACHE="",
        LLAMAPARSE_MERGE_CONTINUED_TABLES="",
    )

    assert settings.minio_secure is False
    assert settings.chunk_min_parent_section_length == 300
    assert settings.chunk_target_child_size == 800
    assert settings.chunk_child_overlap == 120
    assert settings.chunk_content_preview_length == 120
    assert settings.chunk_txt_parent_group_size == 4
    assert settings.chunk_table_preserve_max_chars == 4000
    assert settings.chunk_table_max_rows_per_child == 20
    assert settings.pdf_parser_provider == "local"
    assert settings.llamaparse_do_not_cache is True
    assert settings.llamaparse_merge_continued_tables is False
