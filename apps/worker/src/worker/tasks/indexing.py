"""Worker 文件 chunk indexing 與 retrieval preparation (Phase 6 PGroonga 版)。"""

from datetime import UTC, datetime

from sqlalchemy import func, select, update

from worker.core.settings import WorkerSettings
from worker.db import ChunkType, Document, DocumentChunk
from worker.embedding_text import build_embedding_input_text
from worker.embeddings import build_embedding_provider
from worker.synopsis import (
    build_document_synopsis_provider,
    build_document_synopsis_source_text,
    detect_synopsis_language,
)


def index_document_chunks(*, session, document: Document, settings: WorkerSettings) -> None:
    """對指定文件的 child chunks 寫入 embedding。
    
    在 Phase 6 中，全文檢索已切換為 PGroonga，它會直接在 `content` 欄位上自動建立索引，
    因此此處不再需要手動寫入 FTS payload。

    參數：
    - `session`：目前資料庫 session。
    - `document`：要建立 retrieval payload 的文件。
    - `settings`：worker 執行期設定。

    回傳：
    - `None`：此函式只負責更新 chunks 的向量資訊。
    """

    child_chunks = session.scalars(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document.id, DocumentChunk.chunk_type == ChunkType.child)
        .order_by(DocumentChunk.position.asc())
    ).all()
    if not child_chunks:
        raise ValueError("文件沒有可供 retrieval 使用的 child chunks。")
    parent_chunks = session.scalars(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document.id, DocumentChunk.chunk_type == ChunkType.parent)
        .order_by(DocumentChunk.position.asc())
    ).all()
    if not parent_chunks:
        raise ValueError("文件沒有可供 document synopsis 使用的 parent chunks。")

    # 執行向量編碼
    provider = build_embedding_provider(settings)
    embeddings = provider.embed_texts(
        [
            build_embedding_input_text(
                heading=chunk.heading,
                content=chunk.content,
            )
            for chunk in child_chunks
        ]
    )
    
    # 更新 embedding 欄位
    for chunk, embedding in zip(child_chunks, embeddings, strict=True):
        chunk.embedding = embedding

    synopsis_source_text = build_document_synopsis_source_text(
        file_name=document.file_name,
        parent_chunks=parent_chunks,
        max_input_chars=settings.document_synopsis_max_input_chars,
    )
    synopsis_provider = build_document_synopsis_provider(settings)
    synopsis_text = synopsis_provider.generate_synopsis(
        file_name=document.file_name,
        source_text=synopsis_source_text,
        output_language=detect_synopsis_language(parent_chunks=parent_chunks, file_name=document.file_name),
        max_output_chars=settings.document_synopsis_max_output_chars,
    )
    document.synopsis_text = synopsis_text
    document.synopsis_embedding = provider.embed_texts([synopsis_text])[0]
    document.synopsis_updated_at = datetime.now(UTC)

    session.flush()
