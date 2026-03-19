"""retrieval 與 assembler 共用的文字組裝 helper。"""

from __future__ import annotations

from app.db.models import ChunkStructureKind


def merge_chunk_contents(*, structure_kind: ChunkStructureKind, contents: list[str]) -> str:
    """依 chunk 結構型別合併多筆 child content。

    參數：
    - `structure_kind`：chunk 內容結構型別。
    - `contents`：同一 parent 下、已依既定順序排列的 child content。

    回傳：
    - `str`：合併後的文字；table 只保留一次表頭。
    """

    normalized_contents = [content.strip() for content in contents if content and content.strip()]
    if not normalized_contents:
        return ""
    if structure_kind == ChunkStructureKind.table:
        return _merge_table_contents(contents=normalized_contents)
    return "\n\n".join(normalized_contents).strip()


def build_rerank_document_text(*, heading: str | None, content: str, max_chars: int) -> str:
    """建立送進 rerank provider 的文件文字。

    參數：
    - `heading`：此文件片段的標題；允許為空值。
    - `content`：已組裝完成的正文內容。
    - `max_chars`：允許送入 rerank 的最大字元數。

    回傳：
    - `str`：帶有 `Header:` / `Content:` 前綴且受成本 guardrail 限制的文字。
    """

    normalized_heading = (heading or "").strip()
    normalized_content = content.strip()
    structured_text = f"Header: {normalized_heading}\nContent:\n{normalized_content}".strip()
    if len(structured_text) <= max_chars:
        return structured_text
    return structured_text[:max_chars]


def _merge_table_contents(*, contents: list[str]) -> str:
    """將多個 table row-group child 合併為單一 table 文字。

    參數：
    - `contents`：同一 parent 下、已依 child 順序排列的 table child content。

    回傳：
    - `str`：只保留一次表頭的 Markdown table。
    """

    merged_lines: list[str] = []
    for index, content in enumerate(contents):
        lines = [line.rstrip() for line in content.splitlines() if line.strip()]
        if not lines:
            continue
        if index == 0 or len(lines) < 3:
            merged_lines.extend(lines)
            continue
        merged_lines.extend(lines[2:])
    return "\n".join(merged_lines).strip()
