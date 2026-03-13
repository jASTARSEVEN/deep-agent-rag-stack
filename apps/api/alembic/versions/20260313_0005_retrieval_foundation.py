"""加入 retrieval foundation 所需的 vector、FTS 與 pg_jieba schema。"""

from alembic import op
import sqlalchemy as sa


# Alembic revision 唯一識別碼。
revision = "20260313_0005"

# 本次 migration 的前一版。
down_revision = "20260313_0004"

# Alembic branch labels 預留欄位。
branch_labels = None

# Alembic dependency 預留欄位。
depends_on = None


def _get_column_names(table_name: str) -> set[str]:
    """讀取指定資料表目前欄位名稱集合。

    參數：
    - `table_name`：要檢查的資料表名稱。

    回傳：
    - `set[str]`：資料表目前存在的欄位名稱集合。
    """

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    """加入 retrieval foundation 所需 schema。"""

    bind = op.get_bind()
    dialect_name = bind.dialect.name
    chunk_columns = _get_column_names("document_chunks")

    if dialect_name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
        op.execute("CREATE EXTENSION IF NOT EXISTS pg_jieba")
        op.execute(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_ts_config
                    WHERE cfgname = 'deep_agent_jieba'
                ) THEN
                    CREATE TEXT SEARCH CONFIGURATION deep_agent_jieba (COPY = jiebacfg);
                END IF;
            END
            $$;
            """
        )
        if "embedding" not in chunk_columns:
            op.execute("ALTER TABLE document_chunks ADD COLUMN embedding vector(1536)")
        if "fts_document" not in chunk_columns:
            op.execute("ALTER TABLE document_chunks ADD COLUMN fts_document tsvector")
        op.execute(
            """
            CREATE INDEX IF NOT EXISTS ix_document_chunks_embedding_ivfflat
            ON document_chunks
            USING ivfflat (embedding vector_cosine_ops)
            WHERE embedding IS NOT NULL;
            """
        )
        op.execute(
            """
            CREATE INDEX IF NOT EXISTS ix_document_chunks_fts_document_gin
            ON document_chunks
            USING gin (fts_document)
            WHERE fts_document IS NOT NULL;
            """
        )
        return

    if "embedding" not in chunk_columns:
        op.add_column("document_chunks", sa.Column("embedding", sa.JSON(), nullable=True))
    if "fts_document" not in chunk_columns:
        op.add_column("document_chunks", sa.Column("fts_document", sa.Text(), nullable=True))
    op.create_index("ix_document_chunks_embedding_ivfflat", "document_chunks", ["embedding"], unique=False)
    op.create_index("ix_document_chunks_fts_document_gin", "document_chunks", ["fts_document"], unique=False)


def downgrade() -> None:
    """回滾 retrieval foundation schema。"""

    bind = op.get_bind()
    dialect_name = bind.dialect.name
    chunk_columns = _get_column_names("document_chunks")

    if dialect_name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding_ivfflat")
        op.execute("DROP INDEX IF EXISTS ix_document_chunks_fts_document_gin")
        if "embedding" in chunk_columns:
            op.execute("ALTER TABLE document_chunks DROP COLUMN embedding")
        if "fts_document" in chunk_columns:
            op.execute("ALTER TABLE document_chunks DROP COLUMN fts_document")
        op.execute("DROP TEXT SEARCH CONFIGURATION IF EXISTS deep_agent_jieba")
        return

    op.drop_index("ix_document_chunks_embedding_ivfflat", table_name="document_chunks")
    op.drop_index("ix_document_chunks_fts_document_gin", table_name="document_chunks")
    if "embedding" in chunk_columns:
        op.drop_column("document_chunks", "embedding")
    if "fts_document" in chunk_columns:
        op.drop_column("document_chunks", "fts_document")
