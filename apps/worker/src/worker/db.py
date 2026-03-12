"""Worker 使用的資料庫 engine、session 與最小 ORM model。"""

from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from enum import Enum
from uuid import uuid4

from sqlalchemy import DateTime, Enum as SqlEnum, ForeignKey, String, Text, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from worker.core.settings import WorkerSettings


# 主鍵統一使用 UUID 字串，與 API schema 保持一致。
UUID_LENGTH = 36


def utc_now() -> datetime:
    """回傳 UTC aware 的目前時間。

    參數：
    - 無

    回傳：
    - `datetime`：目前 UTC aware 時間。
    """

    return datetime.now(UTC)


def generate_uuid() -> str:
    """產生新的 UUID 字串。

    參數：
    - 無

    回傳：
    - `str`：新的 UUID 字串。
    """

    return str(uuid4())


class Base(DeclarativeBase):
    """Worker 使用的 ORM declarative base。"""


class DocumentStatus(str, Enum):
    """文件處理狀態。"""

    uploaded = "uploaded"
    processing = "processing"
    ready = "ready"
    failed = "failed"


class IngestJobStatus(str, Enum):
    """背景 ingest job 狀態。"""

    queued = "queued"
    processing = "processing"
    succeeded = "succeeded"
    failed = "failed"


class Document(Base):
    """Worker 更新文件狀態時使用的最小 documents model。"""

    __tablename__ = "documents"

    # 文件唯一識別碼。
    id: Mapped[str] = mapped_column(String(UUID_LENGTH), primary_key=True, default=generate_uuid)
    # 文件所屬 area。
    area_id: Mapped[str] = mapped_column(String(UUID_LENGTH), nullable=False)
    # 使用者上傳時的原始檔名。
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # 上傳時記錄的 MIME 類型。
    content_type: Mapped[str] = mapped_column(String(255), nullable=False)
    # 原始檔大小，單位為 bytes。
    file_size: Mapped[int] = mapped_column(nullable=False)
    # 原始檔在物件儲存中的鍵值。
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    # 文件目前處理狀態。
    status: Mapped[DocumentStatus] = mapped_column(SqlEnum(DocumentStatus, native_enum=False), nullable=False)
    # 文件建立時間。
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    # 文件最後更新時間。
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)


class IngestJob(Base):
    """Worker 更新 ingest 狀態時使用的最小 ingest_jobs model。"""

    __tablename__ = "ingest_jobs"

    # 背景 job 唯一識別碼。
    id: Mapped[str] = mapped_column(String(UUID_LENGTH), primary_key=True, default=generate_uuid)
    # 此 job 對應的文件識別碼。
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    # job 目前狀態。
    status: Mapped[IngestJobStatus] = mapped_column(SqlEnum(IngestJobStatus, native_enum=False), nullable=False)
    # job 失敗時的可讀錯誤訊息。
    error_message: Mapped[str | None] = mapped_column(Text(), nullable=True)
    # job 建立時間。
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    # job 最後更新時間。
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)


def create_database_engine(settings: WorkerSettings) -> Engine:
    """建立 worker 使用的資料庫 engine。

    參數：
    - `settings`：包含資料庫連線 URL 的 worker 設定。

    回傳：
    - `Engine`：供 worker task 使用的 SQLAlchemy engine。
    """

    connect_args: dict[str, object] = {}
    if settings.database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    return create_engine(settings.database_url, future=True, connect_args=connect_args)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """建立 worker 使用的 session factory。

    參數：
    - `engine`：已初始化完成的 SQLAlchemy engine。

    回傳：
    - `sessionmaker[Session]`：供 worker task 建立 session 的 factory。
    """

    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, class_=Session)


@contextmanager
def session_scope(session_factory: sessionmaker[Session]) -> Generator[Session, None, None]:
    """提供 worker task 使用的 session scope。

    參數：
    - `session_factory`：用來建立 worker 資料庫 session 的 factory。

    回傳：
    - `Generator[Session, None, None]`：以 context manager 形式提供的資料庫 session。
    """

    session = session_factory()
    try:
        yield session
    finally:
        session.close()
