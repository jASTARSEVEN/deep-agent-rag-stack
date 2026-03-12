"""授權與資料基礎骨架使用的 ORM models。"""

from datetime import UTC, datetime
from enum import Enum
from uuid import uuid4

from sqlalchemy import DateTime, Enum as SqlEnum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


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
    # 文件目前處理狀態。
    status: Mapped[DocumentStatus] = mapped_column(SqlEnum(DocumentStatus, native_enum=False), nullable=False)
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
    # job 失敗時的可讀錯誤訊息。
    error_message: Mapped[str | None] = mapped_column(Text(), nullable=True)
    # job 建立時間。
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    # job 最後更新時間。
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)
