"""Worker 設定物件測試。"""

from worker.core.settings import WorkerSettings


def test_worker_settings_uses_defaults_for_empty_string_env_values() -> None:
    """空字串環境變數應回退為 worker 設定預設值。"""

    settings = WorkerSettings(MINIO_SECURE="")

    assert settings.minio_secure is False
