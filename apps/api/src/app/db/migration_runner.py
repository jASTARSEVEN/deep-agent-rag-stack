"""Alembic migration runner，負責處理 Supabase bootstrap schema 與版號同步。"""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Connection

from app.core.settings import get_settings


# Alembic `20260320_0009` 為目前 API schema head 版號。
ALEMBIC_HEAD_REVISION = "20260320_0009"

# Supabase SQL bootstrap schema 對應到 Alembic `normalized_text` 已存在、`display_text` 尚未建立的版號。
SUPABASE_BOOTSTRAP_REVISION = "20260319_0008"

# Supabase bootstrap schema 必須先存在的核心資料表集合。
SUPABASE_BOOTSTRAP_TABLES = frozenset(
    {
        "areas",
        "area_user_roles",
        "area_group_roles",
        "documents",
        "ingest_jobs",
        "document_chunks",
    }
)

# Supabase bootstrap schema 的 `documents` 關鍵欄位集合。
SUPABASE_BOOTSTRAP_DOCUMENT_COLUMNS = frozenset(
    {
        "content_type",
        "file_size",
        "indexed_at",
        "normalized_text",
    }
)

# Supabase bootstrap schema 的 `ingest_jobs` 關鍵欄位集合。
SUPABASE_BOOTSTRAP_INGEST_JOB_COLUMNS = frozenset(
    {
        "stage",
        "parent_chunk_count",
        "child_chunk_count",
    }
)


def build_alembic_config() -> Config:
    """建立 Alembic 設定物件。

    Args:
        無。

    Returns:
        Config: 指向專案 `alembic.ini` 的設定物件。
    """

    project_root = Path(__file__).resolve().parents[3]
    return Config(str(project_root / "alembic.ini"))


def has_recorded_alembic_revision(connection: Connection) -> bool:
    """確認資料庫是否已經有 Alembic 版號紀錄。

    Args:
        connection: 目前用來檢查資料庫狀態的 SQLAlchemy 連線。

    Returns:
        bool: 若 `alembic_version` 已存在且含有版號資料則回傳 `True`，否則回傳 `False`。
    """

    inspector = inspect(connection)
    if "alembic_version" not in set(inspector.get_table_names()):
        return False

    version = connection.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).scalar_one_or_none()
    return version is not None


def determine_supabase_bootstrap_revision(
    *,
    table_names: set[str],
    document_columns: set[str],
    ingest_job_columns: set[str],
    has_match_chunks_function: bool,
) -> str | None:
    """判斷既有 schema 是否可安全視為 Supabase bootstrap 基線。

    Args:
        table_names: 目前資料庫已存在的資料表名稱集合。
        document_columns: `documents` 資料表欄位名稱集合。
        ingest_job_columns: `ingest_jobs` 資料表欄位名稱集合。
        has_match_chunks_function: 是否已存在 `match_chunks` RPC。

    Returns:
        str | None: 若可判定為 Supabase bootstrap schema，回傳對應 Alembic revision；否則回傳 `None`。
    """

    if not SUPABASE_BOOTSTRAP_TABLES.issubset(table_names):
        return None
    if not SUPABASE_BOOTSTRAP_DOCUMENT_COLUMNS.issubset(document_columns):
        return None
    if not SUPABASE_BOOTSTRAP_INGEST_JOB_COLUMNS.issubset(ingest_job_columns):
        return None
    if not has_match_chunks_function:
        return None
    if "display_text" in document_columns:
        return ALEMBIC_HEAD_REVISION
    return SUPABASE_BOOTSTRAP_REVISION


def detect_supabase_bootstrap_revision(connection: Connection) -> str | None:
    """從既有資料庫 schema 偵測可套用的 Supabase bootstrap 對應版號。

    Args:
        connection: 目前用來檢查資料庫狀態的 SQLAlchemy 連線。

    Returns:
        str | None: 若可安全辨識為 Supabase bootstrap schema，回傳對應 Alembic revision；否則回傳 `None`。
    """

    inspector = inspect(connection)
    table_names = set(inspector.get_table_names())
    document_columns = {column["name"] for column in inspector.get_columns("documents")} if "documents" in table_names else set()
    ingest_job_columns = {column["name"] for column in inspector.get_columns("ingest_jobs")} if "ingest_jobs" in table_names else set()
    has_match_chunks_function = (
        connection.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM pg_proc
                    WHERE proname = 'match_chunks'
                )
                """
            )
        ).scalar_one()
        is True
    )

    return determine_supabase_bootstrap_revision(
        table_names=table_names,
        document_columns=document_columns,
        ingest_job_columns=ingest_job_columns,
        has_match_chunks_function=has_match_chunks_function,
    )


def run_migrations() -> None:
    """執行 migration，並在可辨識的 Supabase bootstrap schema 上先補 Alembic stamp。

    Args:
        無。

    Returns:
        None: 函式完成後會讓資料庫升級到 Alembic head。
    """

    settings = get_settings()
    alembic_config = build_alembic_config()
    engine = create_engine(settings.database_url, future=True)

    try:
        with engine.connect() as connection:
            if not has_recorded_alembic_revision(connection):
                bootstrap_revision = detect_supabase_bootstrap_revision(connection)
                if bootstrap_revision is not None:
                    print(
                        "Detected Supabase bootstrap schema without alembic_version; "
                        f"stamping revision {bootstrap_revision} before upgrade."
                    )
                    command.stamp(alembic_config, bootstrap_revision)

        command.upgrade(alembic_config, "head")
    finally:
        engine.dispose()


def main() -> None:
    """提供 `python -m app.db.migration_runner` 的 CLI 入口。

    Args:
        無。

    Returns:
        None: 直接呼叫 migration 執行流程。
    """

    run_migrations()


if __name__ == "__main__":
    main()
