"""API inline ingest 使用的 chunk indexing 與 retrieval preparation。"""

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.settings import AppSettings
from app.db.models import ChunkType, Document, DocumentChunk
from app.services.embeddings import build_embedding_provider


def index_document_chunks(*, session: Session, document: Document, settings: AppSettings) -> None:
    """對指定文件的 child chunks 寫入 embedding 與 FTS payload。

    參數：
    - `session`：目前資料庫 session。
    - `document`：要建立 retrieval payload 的文件。
    - `settings`：API 執行期設定。

    回傳：
    - `None`：此函式只負責更新 chunks。
    """

    child_chunks = session.scalars(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document.id, DocumentChunk.chunk_type == ChunkType.child)
        .order_by(DocumentChunk.position.asc())
    ).all()
    if not child_chunks:
        raise ValueError("文件沒有可供 retrieval 使用的 child chunks。")

    provider = build_embedding_provider(settings)
    embeddings = provider.embed_texts([chunk.content for chunk in child_chunks])
    for chunk, embedding in zip(child_chunks, embeddings, strict=True):
        chunk.embedding = embedding

    session.flush()
    _write_fts_payload(session=session, document=document, settings=settings, child_chunks=child_chunks)
    session.flush()


def _write_fts_payload(
    *,
    session: Session,
    document: Document,
    settings: AppSettings,
    child_chunks: list[DocumentChunk],
) -> None:
    """依資料庫方言寫入 chunk 的 FTS payload。

    參數：
    - `session`：目前資料庫 session。
    - `document`：要更新的文件。
    - `settings`：API 執行期設定。
    - `child_chunks`：已查出的 child chunk 清單。

    回傳：
    - `None`：此函式只負責更新 FTS 欄位。
    """

    dialect_name = session.get_bind().dialect.name
    if dialect_name == "postgresql":
        session.execute(
            update(DocumentChunk)
            .where(DocumentChunk.document_id == document.id, DocumentChunk.chunk_type == ChunkType.child)
            .values(fts_document=func.to_tsvector(settings.text_search_config, DocumentChunk.content))
        )
        return

    for chunk in child_chunks:
        chunk.fts_document = chunk.content
