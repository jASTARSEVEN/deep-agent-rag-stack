"""資料庫 engine 與 session dependency。"""

from collections.abc import Generator

from fastapi import Request
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.settings import AppSettings


def create_database_engine(settings: AppSettings) -> Engine:
    """建立資料庫 engine。

    前置條件：
    - `settings.database_url` 必須指向可連線的資料庫。

    風險：
    - SQLite 僅供測試；正式授權與 SQL gate 行為仍以 PostgreSQL 為目標環境。
    """

    connect_args: dict[str, object] = {}
    if settings.database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    return create_engine(settings.database_url, echo=settings.database_echo, future=True, connect_args=connect_args)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """建立供 request-scoped session 使用的 factory。"""

    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, class_=Session)


def get_database_session(request: Request) -> Generator[Session, None, None]:
    """提供 request-scoped SQLAlchemy session。

    前置條件：
    - `app.state.session_factory` 必須在 app 啟動時初始化。

    風險：
    - 若 route 繞過此 dependency 自行管理 session，可能破壞授權查詢的一致性。
    """

    session_factory: sessionmaker[Session] = request.app.state.session_factory
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
