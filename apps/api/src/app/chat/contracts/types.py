"""Chat answer、citation 與 trace 的資料契約。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from app.db.models import ChunkStructureKind


class ChatCitation(BaseModel):
    """單一 assembled-context reference。"""

    # context 在回傳列表中的順序。
    context_index: int
    # context 所屬文件識別碼。
    document_id: str
    # context 所屬 parent chunk 識別碼。
    parent_chunk_id: str | None
    # 合併進此 context 的 child chunk 識別碼。
    child_chunk_ids: list[str]
    # context 所屬段落標題。
    heading: str | None
    # context 內容結構型別。
    structure_kind: ChunkStructureKind
    # context 在 normalized text 的起始 offset。
    start_offset: int
    # context 在 normalized text 的結束 offset。
    end_offset: int
    # context 組裝後可直接送入 LLM 的文字。
    excerpt: str
    # context 來源，可能為 vector、fts 或 hybrid。
    source: str
    # 此 context 是否發生文字裁切。
    truncated: bool


class ChatTrace(BaseModel):
    """整合 retrieval、assembler 與 agent 的 trace。"""

    # retrieval trace metadata。
    retrieval: dict[str, Any]
    # assembler trace metadata。
    assembler: dict[str, Any]
    # answer layer trace metadata。
    agent: dict[str, Any]
