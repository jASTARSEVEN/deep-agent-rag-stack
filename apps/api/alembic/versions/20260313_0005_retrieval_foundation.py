"""加入 retrieval foundation 所需的 vector 與 PGroonga schema。"""

from alembic import op
import sqlalchemy as sa


revision = "20260313_0005"
down_revision = "20260313_0004"
branch_labels = None
depends_on = None


def _get_column_names(table_name: str) -> set[str]:
    """讀取指定資料表目前欄位名稱集合。"""

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
        op.execute("CREATE EXTENSION IF NOT EXISTS pgroonga")
        if "embedding" not in chunk_columns:
            op.execute("ALTER TABLE document_chunks ADD COLUMN embedding vector(1536)")
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
            CREATE INDEX IF NOT EXISTS ix_document_chunks_content_pgroonga
            ON document_chunks
            USING pgroonga (content)
            WHERE chunk_type = 'child';
            """
        )
        return

    if "embedding" not in chunk_columns:
        op.add_column("document_chunks", sa.Column("embedding", sa.JSON(), nullable=True))
    op.create_index("ix_document_chunks_embedding_ivfflat", "document_chunks", ["embedding"], unique=False)
    op.create_index("ix_document_chunks_content_idx", "document_chunks", ["content"], unique=False)


def downgrade() -> None:
    """回滾 retrieval foundation schema。"""

    bind = op.get_bind()
    dialect_name = bind.dialect.name
    chunk_columns = _get_column_names("document_chunks")

    if dialect_name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding_ivfflat")
        op.execute("DROP INDEX IF EXISTS ix_document_chunks_content_pgroonga")
        if "embedding" in chunk_columns:
            op.execute("ALTER TABLE document_chunks DROP COLUMN embedding")
        return

    op.drop_index("ix_document_chunks_embedding_ivfflat", table_name="document_chunks")
    op.drop_index("ix_document_chunks_content_idx", table_name="document_chunks")
    if "embedding" in chunk_columns:
        op.drop_column("document_chunks", "embedding")
