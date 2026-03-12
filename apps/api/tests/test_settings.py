"""API 設定物件測試。"""

from app.core.settings import AppSettings


def test_app_settings_uses_defaults_for_empty_string_env_values() -> None:
    """空字串環境變數應回退為 API 設定預設值。"""

    settings = AppSettings(
        MINIO_SECURE="",
        MAX_UPLOAD_SIZE_BYTES="",
        INGEST_INLINE_MODE="",
    )

    assert settings.minio_secure is False
    assert settings.max_upload_size_bytes == 5 * 1024 * 1024
    assert settings.ingest_inline_mode is False
