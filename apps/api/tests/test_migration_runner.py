"""Supabase bootstrap migration runner 測試。"""

from app.db.migration_runner import (
    ALEMBIC_HEAD_REVISION,
    SUPABASE_BOOTSTRAP_REVISION,
    determine_supabase_bootstrap_revision,
)


def test_determine_supabase_bootstrap_revision_returns_bootstrap_revision_without_display_text() -> None:
    """Supabase bootstrap schema 若尚未建立 `display_text`，應對應到 `20260319_0008`。

    Args:
        無。

    Returns:
        None: 驗證版號判斷結果。
    """

    revision = determine_supabase_bootstrap_revision(
        table_names={
            "areas",
            "area_user_roles",
            "area_group_roles",
            "documents",
            "ingest_jobs",
            "document_chunks",
        },
        document_columns={
            "content_type",
            "file_size",
            "indexed_at",
            "normalized_text",
        },
        ingest_job_columns={"stage", "parent_chunk_count", "child_chunk_count"},
        has_match_chunks_function=True,
    )

    assert revision == SUPABASE_BOOTSTRAP_REVISION


def test_determine_supabase_bootstrap_revision_returns_head_when_display_text_exists() -> None:
    """Supabase bootstrap schema 若已含 `display_text`，應直接對應目前 head。

    Args:
        無。

    Returns:
        None: 驗證版號判斷結果。
    """

    revision = determine_supabase_bootstrap_revision(
        table_names={
            "areas",
            "area_user_roles",
            "area_group_roles",
            "documents",
            "ingest_jobs",
            "document_chunks",
        },
        document_columns={
            "content_type",
            "display_text",
            "file_size",
            "indexed_at",
            "normalized_text",
        },
        ingest_job_columns={"stage", "parent_chunk_count", "child_chunk_count"},
        has_match_chunks_function=True,
    )

    assert revision == ALEMBIC_HEAD_REVISION


def test_determine_supabase_bootstrap_revision_rejects_partial_schema() -> None:
    """缺少 Supabase bootstrap 關鍵訊號時，不應自動 stamp 任何 revision。

    Args:
        無。

    Returns:
        None: 驗證未知狀態會回傳 `None`。
    """

    revision = determine_supabase_bootstrap_revision(
        table_names={"areas", "documents", "ingest_jobs"},
        document_columns={"content_type", "file_size", "normalized_text"},
        ingest_job_columns={"stage", "parent_chunk_count", "child_chunk_count"},
        has_match_chunks_function=False,
    )

    assert revision is None
