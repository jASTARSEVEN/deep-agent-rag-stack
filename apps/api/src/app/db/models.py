"""授權、文件、chunking 與 retrieval foundation 使用的 ORM models。"""

from datetime import UTC, datetime
from enum import Enum
from uuid import uuid4

from sqlalchemy import DateTime, Enum as SqlEnum, Float, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.sql_types import build_embedding_type


# 所有主鍵預設使用 UUID 字串，避免在 SQLite 測試與 PostgreSQL 間切換時額外處理型別差異。
UUID_LENGTH = 36


def utc_now() -> datetime:
    """提供 UTC aware 的目前時間。"""

    return datetime.now(UTC)


def generate_uuid() -> str:
    """產生新的 UUID 字串主鍵。"""

    return str(uuid4())


class Role(str, Enum):
    """Knowledge Area 權限角色。"""

    reader = "reader"
    maintainer = "maintainer"
    admin = "admin"


class DocumentStatus(str, Enum):
    """文件處理狀態。"""

    uploaded = "uploaded"
    processing = "processing"
    ready = "ready"
    failed = "failed"


class IngestJobStatus(str, Enum):
    """背景索引工作的最小狀態。"""

    queued = "queued"
    processing = "processing"
    succeeded = "succeeded"
    failed = "failed"


class ChunkType(str, Enum):
    """文件 chunk 結構型別。"""

    parent = "parent"
    child = "child"


class ChunkStructureKind(str, Enum):
    """文件 chunk 的內容結構型別。"""

    text = "text"
    table = "table"


class Area(Base):
    """Knowledge Area 基本資料。"""

    __tablename__ = "areas"

    # Area 唯一識別碼。
    id: Mapped[str] = mapped_column(String(UUID_LENGTH), primary_key=True, default=generate_uuid)
    # Area 顯示名稱。
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Area 補充說明。
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    # Area 建立時間。
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    # Area 最後更新時間。
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)


class AreaUserRole(Base):
    """Area 與直接使用者角色映射。"""

    __tablename__ = "area_user_roles"
    __table_args__ = (UniqueConstraint("area_id", "user_sub", name="uq_area_user_roles_area_subject"),)

    # 角色映射唯一識別碼。
    id: Mapped[str] = mapped_column(String(UUID_LENGTH), primary_key=True, default=generate_uuid)
    # 角色映射所屬 area。
    area_id: Mapped[str] = mapped_column(ForeignKey("areas.id", ondelete="CASCADE"), nullable=False)
    # 被授權使用者的 `sub`。
    user_sub: Mapped[str] = mapped_column(String(255), nullable=False)
    # 直接指派給使用者的角色。
    role: Mapped[Role] = mapped_column(SqlEnum(Role, native_enum=False), nullable=False)
    # 角色映射建立時間。
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class AreaGroupRole(Base):
    """Area 與 Keycloak group path 角色映射。"""

    __tablename__ = "area_group_roles"
    __table_args__ = (UniqueConstraint("area_id", "group_path", name="uq_area_group_roles_area_group_path"),)

    # 群組角色映射唯一識別碼。
    id: Mapped[str] = mapped_column(String(UUID_LENGTH), primary_key=True, default=generate_uuid)
    # 角色映射所屬 area。
    area_id: Mapped[str] = mapped_column(ForeignKey("areas.id", ondelete="CASCADE"), nullable=False)
    # 被授權 Keycloak group path。
    group_path: Mapped[str] = mapped_column(String(255), nullable=False)
    # 指派給群組的角色。
    role: Mapped[Role] = mapped_column(SqlEnum(Role, native_enum=False), nullable=False)
    # 角色映射建立時間。
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class Document(Base):
    """文件上傳與 ingest 流程使用的文件資料。"""

    __tablename__ = "documents"

    # 文件唯一識別碼。
    id: Mapped[str] = mapped_column(String(UUID_LENGTH), primary_key=True, default=generate_uuid)
    # 文件所屬 area。
    area_id: Mapped[str] = mapped_column(ForeignKey("areas.id", ondelete="CASCADE"), nullable=False)
    # 使用者上傳時的原始檔名。
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # 上傳時記錄的 MIME 類型。
    content_type: Mapped[str] = mapped_column(String(255), nullable=False)
    # 原始檔大小，單位為 bytes。
    file_size: Mapped[int] = mapped_column(nullable=False)
    # 原始檔在物件儲存中的鍵值。
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    # 供全文 preview 與 offset 基準使用的完整顯示文字內容。
    display_text: Mapped[str | None] = mapped_column(Text(), nullable=True)
    # parser 正規化後、供內部解析與 chunking 使用的完整文字內容。
    normalized_text: Mapped[str | None] = mapped_column(Text(), nullable=True)
    # 文件目前處理狀態。
    status: Mapped[DocumentStatus] = mapped_column(SqlEnum(DocumentStatus, native_enum=False), nullable=False)
    # 最近一次成功完成 chunking 的時間。
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # 文件建立時間。
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    # 文件最後更新時間。
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)


class IngestJob(Base):
    """背景 ingest 工作狀態資料。"""

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
    """文件 parent-child chunk tree 的持久化資料。"""

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
    # chunk 內容結構型別。
    structure_kind: Mapped[ChunkStructureKind] = mapped_column(
        SqlEnum(ChunkStructureKind, native_enum=False),
        nullable=False,
        default=ChunkStructureKind.text,
    )
    # chunk 在整份文件中的穩定排序位置。
    position: Mapped[int] = mapped_column(Integer(), nullable=False)
    # parent section 順序。
    section_index: Mapped[int] = mapped_column(Integer(), nullable=False)
    # parent 下的 child 順序；parent 本身為空值。
    child_index: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    # markdown section 標題；TXT 或無標題時為空值。
    heading: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # chunk 原始內容。
    content: Mapped[str] = mapped_column(Text(), nullable=False)
    # 供 UI 與 observability 使用的內容摘要。
    content_preview: Mapped[str] = mapped_column(String(255), nullable=False)
    # chunk 內容長度，單位為字元數。
    char_count: Mapped[int] = mapped_column(Integer(), nullable=False)
    # chunk 在 display_text 內容中的起始 offset。
    start_offset: Mapped[int] = mapped_column(Integer(), nullable=False)
    # chunk 在 display_text 內容中的結束 offset。
    end_offset: Mapped[int] = mapped_column(Integer(), nullable=False)
    # 僅 child chunk 使用的 embedding 向量；parent 固定為空值。
    embedding: Mapped[list[float] | None] = mapped_column(build_embedding_type(), nullable=True)
    # chunk 建立時間。
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    # chunk 最後更新時間。
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)


class DocumentChunkRegion(Base):
    """PDF chunk 的 SQL-first 頁碼與 bounding box locator。"""

    __tablename__ = "document_chunk_regions"
    __table_args__ = (
        UniqueConstraint("chunk_id", "region_order", name="uq_document_chunk_regions_chunk_order"),
    )

    # region 唯一識別碼。
    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=generate_uuid)
    # 所屬 child chunk。
    chunk_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("document_chunks.id", ondelete="CASCADE"), nullable=False)
    # 所屬頁碼，從 1 開始。
    page_number: Mapped[int] = mapped_column(Integer(), nullable=False)
    # 在同一 chunk 內的穩定順序。
    region_order: Mapped[int] = mapped_column(Integer(), nullable=False)
    # 左邊界座標。
    bbox_left: Mapped[float] = mapped_column(Float(), nullable=False)
    # 下邊界座標。
    bbox_bottom: Mapped[float] = mapped_column(Float(), nullable=False)
    # 右邊界座標。
    bbox_right: Mapped[float] = mapped_column(Float(), nullable=False)
    # 上邊界座標。
    bbox_top: Mapped[float] = mapped_column(Float(), nullable=False)
    # 建立時間。
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
