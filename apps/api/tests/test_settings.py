"""API 設定物件測試。"""

from app.core.settings import AppSettings


def test_app_settings_uses_defaults_for_empty_string_env_values() -> None:
    """空字串環境變數應回退為 API 設定預設值。"""

    settings = AppSettings(
        MINIO_SECURE="",
        MAX_UPLOAD_SIZE_BYTES="",
        INGEST_INLINE_MODE="",
        CHUNK_MIN_PARENT_SECTION_LENGTH="",
        CHUNK_TARGET_CHILD_SIZE="",
        CHUNK_CHILD_OVERLAP="",
        CHUNK_CONTENT_PREVIEW_LENGTH="",
        CHUNK_TXT_PARENT_GROUP_SIZE="",
    )

    assert settings.minio_secure is False
    assert settings.max_upload_size_bytes == 5 * 1024 * 1024
    assert settings.ingest_inline_mode is False
    assert settings.chunk_min_parent_section_length == 300
    assert settings.chunk_target_child_size == 800
    assert settings.chunk_child_overlap == 120
    assert settings.chunk_content_preview_length == 120
    assert settings.chunk_txt_parent_group_size == 4
