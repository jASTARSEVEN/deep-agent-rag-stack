"""API ORM 使用的 PostgreSQL/SQLite 相容 SQL 型別。"""

from sqlalchemy import JSON, Text
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.sql.type_api import TypeEngine


# 初版 retrieval schema 固定使用的 embedding 維度。
DEFAULT_EMBEDDING_DIMENSIONS = 1536


try:
    from pgvector.sqlalchemy import Vector
except ImportError:  # pragma: no cover - 測試或未安裝依賴時退回 SQLite 相容型別。
    Vector = None


def build_embedding_type() -> TypeEngine:
    """建立 document chunk embedding 欄位型別。

    參數：
    - 無

    回傳：
    - `TypeEngine`：PostgreSQL 使用 pgvector；SQLite 測試退回 JSON。
    """

    if Vector is None:
        return JSON()
    return Vector(DEFAULT_EMBEDDING_DIMENSIONS).with_variant(JSON(), "sqlite")


def build_fts_document_type() -> TypeEngine:
    """建立 document chunk FTS payload 欄位型別。

    參數：
    - 無

    回傳：
    - `TypeEngine`：PostgreSQL 使用 `tsvector`；SQLite 測試退回文字欄位。
    """

    return TSVECTOR().with_variant(Text(), "sqlite")
