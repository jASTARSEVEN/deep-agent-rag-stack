"""Worker 使用的文件 parent-child chunk tree 建立邏輯。"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import count
import re

from langchain_text_splitters import RecursiveCharacterTextSplitter

_HEADING_PATTERN = re.compile(r"^(#{1,3})\s+(?P<heading>.+?)\s*$")


@dataclass(slots=True)
class ChunkingConfig:
    """chunking 策略使用的參數。"""

    # parent section 最小長度；不足時優先與後續 section 合併。
    min_parent_section_length: int
    # child chunk 目標大小，單位為字元。
    target_child_chunk_size: int
    # child chunk overlap 大小，單位為字元。
    child_chunk_overlap: int
    # UI 與 observability 使用的內容摘要長度。
    content_preview_length: int
    # TXT 每個 parent section 預設合併的段落數。
    txt_parent_group_size: int


@dataclass(slots=True)
class SectionDraft:
    """尚未展開 child chunks 前的 parent section 草稿。"""

    # parent section 順序。
    section_index: int
    # markdown heading；若無則為空值。
    heading: str | None
    # parent section 文字內容。
    content: str
    # section 在 normalize 後文字中的起始 offset。
    start_offset: int
    # section 在 normalize 後文字中的結束 offset。
    end_offset: int


@dataclass(slots=True)
class ChunkDraft:
    """待寫入資料庫的 chunk 草稿。"""

    # chunk 型別。
    chunk_type: str
    # chunk 在整份文件中的穩定排序。
    position: int
    # parent section 順序。
    section_index: int
    # parent 下 child 順序；parent 本身為空值。
    child_index: int | None
    # markdown heading；若無則為空值。
    heading: str | None
    # chunk 內容。
    content: str
    # UI 與 observability 使用的摘要。
    content_preview: str
    # chunk 內容長度。
    char_count: int
    # chunk 起始 offset。
    start_offset: int
    # chunk 結束 offset。
    end_offset: int


@dataclass(slots=True)
class ChunkingResult:
    """完整 chunking 結果。"""

    # parent chunks 草稿。
    parent_chunks: list[ChunkDraft]
    # child chunks 草稿。
    child_chunks: list[ChunkDraft]


def build_chunk_tree(*, file_name: str, text: str, config: ChunkingConfig) -> ChunkingResult:
    """依檔案型別將文字切成 parent-child chunk tree。

    參數：
    - `file_name`：原始檔名，用來選擇 markdown 或 txt 策略。
    - `text`：parser 回傳的 normalize 後文字內容。

    回傳：
    - `ChunkingResult`：包含 parent 與 child chunk 草稿的結果。
    """

    normalized_text = text.strip()
    if not normalized_text:
        raise ValueError("文件內容不可為空白。")

    if file_name.lower().endswith(".md"):
        sections = _build_markdown_sections(normalized_text, config=config)
    else:
        sections = _build_text_sections(normalized_text, config=config)

    if not sections:
        raise ValueError("無法從文件內容建立有效 chunks。")

    parent_chunks: list[ChunkDraft] = []
    child_chunks: list[ChunkDraft] = []
    position_counter = count()

    for section in sections:
        parent_chunks.append(
            ChunkDraft(
                chunk_type="parent",
                position=next(position_counter),
                section_index=section.section_index,
                child_index=None,
                heading=section.heading,
                content=section.content,
                content_preview=_build_content_preview(section.content, config=config),
                char_count=len(section.content),
                start_offset=section.start_offset,
                end_offset=section.end_offset,
            )
        )
        child_chunks.extend(_build_child_chunks(section=section, position_counter=position_counter, config=config))

    if not child_chunks:
        raise ValueError("無法從文件內容建立有效 chunks。")

    return ChunkingResult(parent_chunks=parent_chunks, child_chunks=child_chunks)


def _build_markdown_sections(text: str, *, config: ChunkingConfig) -> list[SectionDraft]:
    """依 markdown heading 邊界建立 parent sections。

    參數：
    - `text`：normalize 後的 markdown 文字。

    回傳：
    - `list[SectionDraft]`：依 heading 切好的 parent section 草稿。
    """

    sections: list[tuple[str | None, list[str]]] = []
    current_heading: str | None = None
    current_lines: list[str] = []

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        match = _HEADING_PATTERN.match(line)
        if match:
            _append_section_if_not_empty(sections=sections, heading=current_heading, lines=current_lines)
            current_heading = match.group("heading").strip()
            current_lines = []
            continue
        current_lines.append(line)

    _append_section_if_not_empty(sections=sections, heading=current_heading, lines=current_lines)

    if not sections:
        sections = [(None, [text])]

    return _normalize_sections(_materialize_sections(sections), config=config)


def _build_text_sections(text: str, *, config: ChunkingConfig) -> list[SectionDraft]:
    """依 TXT 段落群組建立 parent sections。

    參數：
    - `text`：normalize 後的純文字內容。

    回傳：
    - `list[SectionDraft]`：依段落群組切好的 parent section 草稿。
    """

    paragraphs = [paragraph.strip() for paragraph in re.split(r"\n\s*\n", text) if paragraph.strip()]
    if not paragraphs:
        return []

    grouped_sections: list[tuple[str | None, list[str]]] = []
    for index in range(0, len(paragraphs), config.txt_parent_group_size):
        grouped_sections.append((None, paragraphs[index : index + config.txt_parent_group_size]))
    return _normalize_sections(_materialize_sections(grouped_sections), config=config)


def _append_section_if_not_empty(*, sections: list[tuple[str | None, list[str]]], heading: str | None, lines: list[str]) -> None:
    """若 section 內容非空白則加入待 materialize 清單。

    參數：
    - `sections`：目前累積中的 section 容器。
    - `heading`：當前 section heading。
    - `lines`：當前 section 的行列表。

    回傳：
    - `None`：此函式只在有有效內容時附加 section。
    """

    content = "\n".join(lines).strip()
    if content:
        sections.append((heading, [content]))


def _materialize_sections(section_inputs: list[tuple[str | None, list[str]]]) -> list[SectionDraft]:
    """將 section 輸入轉成包含 offset 的 parent section 草稿。

    參數：
    - `section_inputs`：待 materialize 的 heading 與內容段落清單。

    回傳：
    - `list[SectionDraft]`：帶有 offset 的 section 草稿。
    """

    materialized: list[SectionDraft] = []
    cursor = 0
    for section_index, (heading, parts) in enumerate(section_inputs):
        content = "\n\n".join(part.strip() for part in parts if part.strip()).strip()
        if not content:
            continue
        start_offset = cursor
        end_offset = start_offset + len(content)
        materialized.append(
            SectionDraft(
                section_index=section_index,
                heading=heading,
                content=content,
                start_offset=start_offset,
                end_offset=end_offset,
            )
        )
        cursor = end_offset + 2
    return materialized


def _normalize_sections(sections: list[SectionDraft], *, config: ChunkingConfig) -> list[SectionDraft]:
    """合併過短 parent sections，並重算 section index 與 offsets。

    參數：
    - `sections`：初步切好的 parent section 草稿。

    回傳：
    - `list[SectionDraft]`：合併短 section 後的正規化結果。
    """

    if not sections:
        return []

    merged_sections: list[SectionDraft] = []
    index = 0
    while index < len(sections):
        current = sections[index]
        if len(current.content) < config.min_parent_section_length and index + 1 < len(sections):
            next_section = sections[index + 1]
            merged_sections.append(
                SectionDraft(
                    section_index=0,
                    heading=_merge_headings(current.heading, next_section.heading),
                    content=f"{current.content}\n\n{next_section.content}",
                    start_offset=0,
                    end_offset=0,
                )
            )
            index += 2
            continue
        if len(current.content) < config.min_parent_section_length and merged_sections:
            previous = merged_sections.pop()
            merged_sections.append(
                SectionDraft(
                    section_index=0,
                    heading=_merge_headings(previous.heading, current.heading),
                    content=f"{previous.content}\n\n{current.content}",
                    start_offset=0,
                    end_offset=0,
                )
            )
            index += 1
            continue
        merged_sections.append(current)
        index += 1

    normalized_sections: list[SectionDraft] = []
    cursor = 0
    for section_index, section in enumerate(merged_sections):
        start_offset = cursor
        end_offset = start_offset + len(section.content)
        normalized_sections.append(
            SectionDraft(
                section_index=section_index,
                heading=section.heading,
                content=section.content,
                start_offset=start_offset,
                end_offset=end_offset,
            )
        )
        cursor = end_offset + 2
    return normalized_sections


def _merge_headings(left_heading: str | None, right_heading: str | None) -> str | None:
    """合併兩個 parent section 的 heading。

    參數：
    - `left_heading`：前段 heading。
    - `right_heading`：後段 heading。

    回傳：
    - `str | None`：合併後的 heading；若兩側都沒有則回傳空值。
    """

    if left_heading and right_heading and left_heading != right_heading:
        return f"{left_heading} / {right_heading}"
    return left_heading or right_heading


def _build_child_chunks(
    *,
    section: SectionDraft,
    position_counter: count[int],
    config: ChunkingConfig,
) -> list[ChunkDraft]:
    """將 parent section 切成 child chunks。

    參數：
    - `section`：待切分的 parent section。
    - `position_counter`：整份文件的全域 position 計數器。

    回傳：
    - `list[ChunkDraft]`：此 section 下的 child chunk 草稿。
    """

    children: list[ChunkDraft] = []
    child_index = 0
    splitter = _build_child_splitter(config=config)

    for relative_start, chunk_content in _split_section_content(section.content, splitter=splitter):
        normalized_start = section.start_offset + relative_start
        normalized_end = normalized_start + len(chunk_content)
        children.append(
            ChunkDraft(
                chunk_type="child",
                position=next(position_counter),
                section_index=section.section_index,
                child_index=child_index,
                heading=section.heading,
                content=chunk_content,
                content_preview=_build_content_preview(chunk_content, config=config),
                char_count=len(chunk_content),
                start_offset=normalized_start,
                end_offset=normalized_end,
            )
        )
        child_index += 1

    return children


def _build_child_splitter(*, config: ChunkingConfig) -> RecursiveCharacterTextSplitter:
    """建立 child chunk 使用的 LangChain splitter。

    參數：
    - `config`：目前 chunking 策略設定。

    回傳：
    - `RecursiveCharacterTextSplitter`：保留 start index 的 splitter 實例。
    """

    return RecursiveCharacterTextSplitter(
        chunk_size=config.target_child_chunk_size,
        chunk_overlap=config.child_chunk_overlap,
        add_start_index=True,
        strip_whitespace=False,
    )


def _split_section_content(
    content: str,
    *,
    splitter: RecursiveCharacterTextSplitter,
) -> list[tuple[int, str]]:
    """將 parent content 切分為帶相對 offset 的 child 內容。

    參數：
    - `content`：單一 parent section 的文字內容。
    - `splitter`：LangChain RecursiveCharacterTextSplitter 實例。

    回傳：
    - `list[tuple[int, str]]`：每個 child 的相對起始 offset 與內容。
    """

    split_documents = splitter.create_documents([content])
    children: list[tuple[int, str]] = []

    for document in split_documents:
        raw_content = document.page_content
        start_index = int(document.metadata.get("start_index", 0))
        leading_trim = len(raw_content) - len(raw_content.lstrip())
        trailing_trim = len(raw_content) - len(raw_content.rstrip())
        normalized_content = raw_content.strip()
        if not normalized_content:
            continue

        normalized_start = start_index + leading_trim
        normalized_end = len(raw_content) - trailing_trim
        if normalized_end <= leading_trim:
            continue

        children.append((normalized_start, raw_content[leading_trim:normalized_end]))

    return children


def _build_content_preview(content: str, *, config: ChunkingConfig) -> str:
    """建立固定長度的 chunk 摘要。

    參數：
    - `content`：原始 chunk 內容。

    回傳：
    - `str`：固定長度、去除多餘空白的摘要字串。
    """

    normalized = " ".join(content.split())
    return normalized[: config.content_preview_length]
