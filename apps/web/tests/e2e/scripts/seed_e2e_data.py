"""建立 Playwright E2E 測試所需的 SQLite schema 與固定 seed data。"""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session


# `apps/api/src` 目錄，供 E2E seed 腳本重用既有 model 與 metadata。
API_SRC_DIRECTORY = Path(__file__).resolve().parents[4] / "api" / "src"


def build_engine(database_path: Path):
    """建立 E2E 專用 SQLite engine。"""

    return create_engine(
        f"sqlite+pysqlite:///{database_path}",
        future=True,
        connect_args={"check_same_thread": False},
    )


def seed_e2e_database(database_path: Path) -> None:
    """重建 schema 並寫入 Playwright E2E 固定資料。"""

    sys.path.insert(0, str(API_SRC_DIRECTORY))

    from app.db.base import Base
    from app.db.models import Area, AreaGroupRole, AreaUserRole, Role

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
        session.commit()


def main() -> None:
    """解析 CLI 參數並執行 seed。"""

    if len(sys.argv) != 2:
        raise SystemExit("用法：python seed_e2e_data.py <sqlite_db_path>")

    database_path = Path(sys.argv[1]).resolve()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    seed_e2e_database(database_path=database_path)


if __name__ == "__main__":
    main()
