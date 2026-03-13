"""Documents 與 ingest jobs API schema。"""

from datetime import datetime

from pydantic import BaseModel

from app.db.models import DocumentStatus, IngestJobStatus


class ChunkSummary(BaseModel):
    """文件或 ingest job 的 chunk 摘要資訊。"""

    # chunk 總數。
    total_chunks: int
    # parent chunk 數量。
    parent_chunks: int
    # child chunk 數量。
    child_chunks: int
    # 最近一次成功完成 indexing 的時間。
    last_indexed_at: datetime | None


class DocumentSummary(BaseModel):
    """文件摘要資料。"""

    # 文件唯一識別碼。
    id: str
    # 文件所屬 Knowledge Area 識別碼。
    area_id: str
    # 使用者上傳時的原始檔名。
    file_name: str
    # 上傳時記錄的 MIME 類型。
    content_type: str
    # 原始檔案大小，單位為 bytes。
    file_size: int
    # 文件目前處理狀態。
    status: DocumentStatus
    # 文件 chunking 結果摘要。
    chunk_summary: ChunkSummary
    # 文件建立時間。
    created_at: datetime
    # 文件最後更新時間。
    updated_at: datetime


class IngestJobSummary(BaseModel):
    """背景 ingest job 摘要資料。"""

    # 背景 job 唯一識別碼。
    id: str
    # 此 job 對應的文件識別碼。
    document_id: str
    # job 目前狀態。
    status: IngestJobStatus
    # job 目前執行階段。
    stage: str
    # 本次 job 產生或觀測到的 chunk 摘要。
    chunk_summary: ChunkSummary
    # job 失敗時記錄的可讀錯誤訊息。
    error_message: str | None
    # job 建立時間。
    created_at: datetime
    # job 最後更新時間。
    updated_at: datetime


class DocumentListResponse(BaseModel):
    """指定 area 的文件清單。"""

    # 目前使用者在指定 area 可見的文件列表。
    items: list[DocumentSummary]


class UploadDocumentResponse(BaseModel):
    """文件上傳成功後回傳的 document 與 job。"""

    # 剛建立的文件摘要。
    document: DocumentSummary
    # 與本次上傳對應的 ingest job 摘要。
    job: IngestJobSummary


class ReindexDocumentResponse(BaseModel):
    """文件重建索引後回傳的 document 與 job。"""

    # 重新派送後的文件摘要。
    document: DocumentSummary
    # 新建立的 ingest job 摘要。
    job: IngestJobSummary
