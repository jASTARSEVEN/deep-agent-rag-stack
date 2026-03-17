"""建立 Playwright E2E 測試所需的 SQLite schema 與固定 seed data。"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session


# `apps/api/src` 目錄，供 E2E seed 腳本重用既有 model 與 metadata。
API_SRC_DIRECTORY = Path(__file__).resolve().parents[4] / "api" / "src"


def build_engine(database_path: Path):
    """建立 E2E 專用 SQLite engine。

    參數：
    - `database_path`：E2E SQLite 資料庫檔案路徑。

    回傳：
    - 建立完成的 SQLAlchemy engine。
    """

    return create_engine(
        f"sqlite+pysqlite:///{database_path}",
        future=True,
        connect_args={"check_same_thread": False},
    )


def seed_e2e_database(database_path: Path, storage_path: Path) -> None:
    """重建 schema 並寫入 Playwright E2E 固定資料。

    參數：
    - `database_path`：E2E SQLite 資料庫檔案路徑。
    - `storage_path`：E2E 本機物件儲存根目錄。

    回傳：
    - `None`：此函式只負責重建 schema 與寫入 seed data。
    """

    sys.path.insert(0, str(API_SRC_DIRECTORY))

    from app.db.base import Base
    from app.db.models import Area, AreaGroupRole, AreaUserRole, ChunkStructureKind, ChunkType, Document, DocumentChunk, DocumentStatus, Role

    engine = build_engine(database_path)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    with Session(bind=engine) as session:
        session.add_all(
            [
                Area(id="area-admin", name="Admin Control Area", description="供 admin 驗證 access management 使用。"),
                Area(id="area-reader", name="Reader Handbook Area", description="供 reader 驗證唯讀存取使用。"),
                Area(id="area-maintainer", name="Maintainer Docs Area", description="供 maintainer 驗證 detail 顯示使用。"),
            ]
        )
        session.add_all(
            [
                AreaUserRole(area_id="area-admin", user_sub="user-admin", role=Role.admin),
                AreaGroupRole(area_id="area-reader", group_path="/group/reader", role=Role.reader),
                AreaGroupRole(area_id="area-maintainer", group_path="/group/maintainer", role=Role.maintainer),
            ]
        )
        session.add_all(
            [
                Document(
                    id="document-reader-ready",
                    area_id="area-reader",
                    file_name="reader-handbook.md",
                    content_type="text/markdown",
                    file_size=128,
                    storage_key="seed/reader-handbook.md",
                    status=DocumentStatus.ready,
                    indexed_at=datetime(2026, 3, 13, 0, 0, tzinfo=UTC),
                ),
                Document(
                    id="document-maintainer-ready",
                    area_id="area-maintainer",
                    file_name="maintainer-guide.md",
                    content_type="text/markdown",
                    file_size=256,
                    storage_key="seed/maintainer-guide.md",
                    status=DocumentStatus.ready,
                    indexed_at=datetime(2026, 3, 13, 0, 5, tzinfo=UTC),
                ),
            ]
        )
        session.add_all(
            [
                DocumentChunk(
                    id="chunk-reader-parent",
                    document_id="document-reader-ready",
                    parent_chunk_id=None,
                    chunk_type=ChunkType.parent,
                    structure_kind=ChunkStructureKind.text,
                    position=0,
                    section_index=0,
                    child_index=None,
                    heading="Reader Intro",
                    content="Reader intro section",
                    content_preview="Reader intro section",
                    char_count=20,
                    start_offset=0,
                    end_offset=20,
                ),
                DocumentChunk(
                    id="chunk-reader-child",
                    document_id="document-reader-ready",
                    parent_chunk_id="chunk-reader-parent",
                    chunk_type=ChunkType.child,
                    structure_kind=ChunkStructureKind.text,
                    position=1,
                    section_index=0,
                    child_index=0,
                    heading="Reader Intro",
                    content="Reader intro content explains the reader policy and citations behavior.",
                    content_preview="Reader intro content explains the reader policy",
                    char_count=68,
                    start_offset=0,
                    end_offset=68,
                    embedding=[0.2] * 1536,
                ),
                DocumentChunk(
                    id="chunk-maintainer-parent",
                    document_id="document-maintainer-ready",
                    parent_chunk_id=None,
                    chunk_type=ChunkType.parent,
                    structure_kind=ChunkStructureKind.text,
                    position=0,
                    section_index=0,
                    child_index=None,
                    heading="Maintainer Intro",
                    content="Maintainer intro section",
                    content_preview="Maintainer intro section",
                    char_count=24,
                    start_offset=0,
                    end_offset=24,
                ),
                DocumentChunk(
                    id="chunk-maintainer-child",
                    document_id="document-maintainer-ready",
                    parent_chunk_id="chunk-maintainer-parent",
                    chunk_type=ChunkType.child,
                    structure_kind=ChunkStructureKind.text,
                    position=1,
                    section_index=0,
                    child_index=0,
                    heading="Maintainer Intro",
                    content="Maintainer intro content explains upload, reindex, and chat behavior.",
                    content_preview="Maintainer intro content explains upload",
                    char_count=69,
                    start_offset=0,
                    end_offset=69,
                    embedding=[0.21] * 1536,
                ),
            ]
        )
        session.commit()

    (storage_path / "seed").mkdir(parents=True, exist_ok=True)
    (storage_path / "seed" / "reader-handbook.md").write_text("# Reader Intro\nReader intro content\n", encoding="utf-8")
    (storage_path / "seed" / "maintainer-guide.md").write_text(
        "# Maintainer Intro\nMaintainer intro content\n",
        encoding="utf-8",
    )


def main() -> None:
    """解析 CLI 參數並執行 seed。

    參數：
    - 無

    回傳：
    - `None`：此函式以程序副作用方式完成 seed。
    """

    if len(sys.argv) != 3:
        raise SystemExit("用法：python seed_e2e_data.py <sqlite_db_path> <storage_path>")

    database_path = Path(sys.argv[1]).resolve()
    storage_path = Path(sys.argv[2]).resolve()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    storage_path.mkdir(parents=True, exist_ok=True)
    seed_e2e_database(database_path=database_path, storage_path=storage_path)


if __name__ == "__main__":
    main()
