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

    id: Mapped[str] = mapped_column(String(UUID_LENGTH), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)


class AreaUserRole(Base):
    """Area 與直接使用者角色映射。"""

    __tablename__ = "area_user_roles"
    __table_args__ = (UniqueConstraint("area_id", "user_sub", name="uq_area_user_roles_area_subject"),)

    id: Mapped[str] = mapped_column(String(UUID_LENGTH), primary_key=True, default=generate_uuid)
    area_id: Mapped[str] = mapped_column(ForeignKey("areas.id", ondelete="CASCADE"), nullable=False)
    user_sub: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[Role] = mapped_column(SqlEnum(Role, native_enum=False), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class AreaGroupRole(Base):
    """Area 與 Keycloak group path 角色映射。"""

    __tablename__ = "area_group_roles"
    __table_args__ = (UniqueConstraint("area_id", "group_path", name="uq_area_group_roles_area_group_path"),)

    id: Mapped[str] = mapped_column(String(UUID_LENGTH), primary_key=True, default=generate_uuid)
    area_id: Mapped[str] = mapped_column(ForeignKey("areas.id", ondelete="CASCADE"), nullable=False)
    group_path: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[Role] = mapped_column(SqlEnum(Role, native_enum=False), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class Document(Base):
    """未來文件上傳與檢索流程使用的最小占位 model。"""

    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(UUID_LENGTH), primary_key=True, default=generate_uuid)
    area_id: Mapped[str] = mapped_column(ForeignKey("areas.id", ondelete="CASCADE"), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[DocumentStatus] = mapped_column(SqlEnum(DocumentStatus, native_enum=False), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)


class IngestJob(Base):
    """未來背景索引流程使用的最小占位 model。"""

    __tablename__ = "ingest_jobs"

    id: Mapped[str] = mapped_column(String(UUID_LENGTH), primary_key=True, default=generate_uuid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[IngestJobStatus] = mapped_column(SqlEnum(IngestJobStatus, native_enum=False), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)
