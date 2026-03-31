"""Chat answer、citation 與 trace 的資料契約。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from app.db.models import ChunkStructureKind


class ChatCitationRegion(BaseModel):
    """單一 citation 的 PDF locator。"""

    # 所屬頁碼。
    page_number: int
    # 同一 citation/chunk 內的區域順序。
    region_order: int
    # 左邊界座標。
    bbox_left: float
    # 下邊界座標。
    bbox_bottom: float
    # 右邊界座標。
    bbox_right: float
    # 上邊界座標。
    bbox_top: float


class ChatDisplayCitation(BaseModel):
    """前端顯示用的單一 citation chip。"""

    # 引用對應的 context 順序。
    context_index: int
    # 提供給回答與 UI 共用的穩定引用標籤。
    context_label: str
    # 引用所屬文件識別碼。
    document_id: str
    # 引用所屬文件名稱。
    document_name: str
    # 引用所屬段落標題。
    heading: str | None
    # 引用涵蓋的起始頁碼。
    page_start: int | None = None
    # 引用涵蓋的結束頁碼。
    page_end: int | None = None


class ChatAnswerBlock(BaseModel):
    """回答中的單一可顯示文字區塊。"""

    # 區塊純文字內容。
    text: str
    # 此區塊引用的 context 順序列表。
    citation_context_indices: list[int]
    # 提供 UI 句尾 chips 使用的 citation 清單。
    display_citations: list[ChatDisplayCitation]


class ChatCitation(BaseModel):
    """單一 assembled-context reference。"""

    # context 在回傳列表中的順序。
    context_index: int
    # 提供給回答與 UI 共用的穩定引用標籤。
    context_label: str
    # context 所屬文件識別碼。
    document_id: str
    # context 所屬文件名稱。
    document_name: str
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
    # context 涵蓋的起始頁碼。
    page_start: int | None = None
    # context 涵蓋的結束頁碼。
    page_end: int | None = None
    # context 關聯的 PDF locator。
    regions: list[ChatCitationRegion] = []


class ChatTrace(BaseModel):
    """整合 retrieval、assembler 與 agent 的 trace。"""

    # retrieval trace metadata。
    retrieval: dict[str, Any]
    # assembler trace metadata。
    assembler: dict[str, Any]
    # answer layer trace metadata。
    agent: dict[str, Any]


class ChatMessageArtifact(BaseModel):
    """持久化於 LangGraph thread state 的 assistant turn UI artifact。"""

    # assistant turn 在 thread 內的順序。
    assistant_turn_index: int
    # 乾淨回答文字。
    answer: str
    # 解析後的回答區塊。
    answer_blocks: list[ChatAnswerBlock]
    # 對應此 turn 的 assembled-context references。
    citations: list[ChatCitation]
    # 此回合是否使用知識庫內容。
    used_knowledge_base: bool
