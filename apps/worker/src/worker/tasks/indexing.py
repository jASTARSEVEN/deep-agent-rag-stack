"""Worker 文件 chunk indexing 與 retrieval preparation (Phase 6 PGroonga 版)。"""

from sqlalchemy import func, select, update

from worker.core.settings import WorkerSettings
from worker.db import ChunkType, Document, DocumentChunk
from worker.embeddings import build_embedding_provider


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

    # 執行向量編碼
    provider = build_embedding_provider(settings)
    embeddings = provider.embed_texts([chunk.content for chunk in child_chunks])
    
    # 更新 embedding 欄位
    for chunk, embedding in zip(child_chunks, embeddings, strict=True):
        chunk.embedding = embedding

    session.flush()
