"""Worker 使用的資料庫 engine、session 與 chunking 流程 ORM model。"""

from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from enum import Enum
from uuid import uuid4

from sqlalchemy import DateTime, Enum as SqlEnum, ForeignKey, Integer, String, Text, UniqueConstraint, create_engine
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


class ChunkType(str, Enum):
    """文件 chunk 結構型別。"""

    parent = "parent"
    child = "child"


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
    # 最近一次成功完成 chunking 的時間。
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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
    # job 目前執行階段。
    stage: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    # job 失敗時的可讀錯誤訊息。
    error_message: Mapped[str | None] = mapped_column(Text(), nullable=True)
    # 本次 job 產生的 parent chunk 數量。
    parent_chunk_count: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    # 本次 job 產生的 child chunk 數量。
    child_chunk_count: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    # job 建立時間。
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    # job 最後更新時間。
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)


class DocumentChunk(Base):
    """Worker 寫入的文件 parent-child chunk tree。"""

    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "position", name="uq_document_chunks_document_position"),
        UniqueConstraint("document_id", "section_index", "child_index", name="uq_document_chunks_document_section_child"),
    )

    # chunk 唯一識別碼。
    id: Mapped[str] = mapped_column(String(UUID_LENGTH), primary_key=True, default=generate_uuid)
    # chunk 所屬文件。
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    # child chunk 對應的 parent chunk；parent 為空值。
    parent_chunk_id: Mapped[str | None] = mapped_column(
        ForeignKey("document_chunks.id", ondelete="CASCADE"),
        nullable=True,
    )
    # chunk 型別。
    chunk_type: Mapped[ChunkType] = mapped_column(SqlEnum(ChunkType, native_enum=False), nullable=False)
    # chunk 在整份文件中的穩定排序。
    position: Mapped[int] = mapped_column(Integer(), nullable=False)
    # parent section 順序。
    section_index: Mapped[int] = mapped_column(Integer(), nullable=False)
    # parent 下 child 順序；parent 本身為空值。
    child_index: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    # markdown section 標題；TXT 或無標題時為空值。
    heading: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # chunk 原始內容。
    content: Mapped[str] = mapped_column(Text(), nullable=False)
    # 供 observability 使用的內容摘要。
    content_preview: Mapped[str] = mapped_column(String(255), nullable=False)
    # chunk 內容長度。
    char_count: Mapped[int] = mapped_column(Integer(), nullable=False)
    # normalize 後文字座標起點。
    start_offset: Mapped[int] = mapped_column(Integer(), nullable=False)
    # normalize 後文字座標終點。
    end_offset: Mapped[int] = mapped_column(Integer(), nullable=False)
    # chunk 建立時間。
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    # chunk 最後更新時間。
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
