"""文件表格感知 parent-child chunk tree 建立邏輯。"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import count
import re

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.services.parsers import ParsedDocument


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
    # 整張表格可原封保留的最大字元數。
    table_preserve_max_chars: int
    # 超大表格分段時每個 child 最多資料列數。
    table_max_rows_per_child: int


@dataclass(slots=True)
class SectionDraft:
    """尚未展開 child chunks 前的 parent section 草稿。"""

    # parent section 順序。
    section_index: int
    # 內容結構型別。
    structure_kind: str
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
    # chunk 內容結構型別。
    structure_kind: str
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


def build_chunk_tree(*, parsed_document: ParsedDocument, config: ChunkingConfig) -> ChunkingResult:
    """將 ParsedDocument 切成 parent-child chunk tree。

    參數：
    - `parsed_document`：parser 回傳的結構化文件內容。
    - `config`：chunking 參數設定。

    回傳：
    - `ChunkingResult`：包含 parent 與 child chunk 草稿的結果。
    """

    if not parsed_document.normalized_text.strip():
        raise ValueError("文件內容不可為空白。")

    sections = _build_sections(parsed_document=parsed_document, config=config)
    if not sections:
        raise ValueError("無法從文件內容建立有效 chunks。")

    parent_chunks: list[ChunkDraft] = []
    child_chunks: list[ChunkDraft] = []
    position_counter = count()

    for section in sections:
        parent_chunks.append(
            ChunkDraft(
                chunk_type="parent",
                structure_kind=section.structure_kind,
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


def _build_sections(*, parsed_document: ParsedDocument, config: ChunkingConfig) -> list[SectionDraft]:
    """將 ParsedDocument 轉為 parent section 草稿。

    參數：
    - `parsed_document`：parser 回傳的結構化文件內容。
    - `config`：chunking 參數設定。

    回傳：
    - `list[SectionDraft]`：正規化後的 parent sections。
    """

    if parsed_document.source_format == "txt":
        return _build_text_sections(text=parsed_document.normalized_text, config=config)

    sections = [
        SectionDraft(
            section_index=index,
            structure_kind=block.block_kind,
            heading=block.heading,
            content=block.content,
            start_offset=block.start_offset,
            end_offset=block.end_offset,
        )
        for index, block in enumerate(parsed_document.blocks)
        if block.content.strip()
    ]
    return _normalize_sections(sections, config=config)


def _build_text_sections(text: str, *, config: ChunkingConfig) -> list[SectionDraft]:
    """依 TXT 段落群組建立 parent sections。

    參數：
    - `text`：normalize 後的純文字內容。
    - `config`：chunking 參數設定。

    回傳：
    - `list[SectionDraft]`：依段落群組切好的 parent section 草稿。
    """

    paragraphs = [paragraph.strip() for paragraph in re.split(r"\n\s*\n", text) if paragraph.strip()]
    if not paragraphs:
        return []

    grouped_sections: list[SectionDraft] = []
    for index in range(0, len(paragraphs), config.txt_parent_group_size):
        content = "\n\n".join(paragraphs[index : index + config.txt_parent_group_size]).strip()
        grouped_sections.append(
            SectionDraft(
                section_index=len(grouped_sections),
                structure_kind="text",
                heading=None,
                content=content,
                start_offset=0,
                end_offset=0,
            )
        )
    return _normalize_sections(grouped_sections, config=config)


def _normalize_sections(sections: list[SectionDraft], *, config: ChunkingConfig) -> list[SectionDraft]:
    """合併過短文字 parent sections，並重算 section index 與 offsets。

    參數：
    - `sections`：初步切好的 parent section 草稿。
    - `config`：chunking 參數設定。

    回傳：
    - `list[SectionDraft]`：合併短 section 後的正規化結果。
    """

    if not sections:
        return []

    merged_sections: list[SectionDraft] = []
    index = 0
    while index < len(sections):
        current = sections[index]
        index += 1

        if current.structure_kind == "table":
            merged_sections.append(current)
            continue

        while (
            current.structure_kind == "text"
            and len(current.content) < config.min_parent_section_length
            and index < len(sections)
            and sections[index].structure_kind == "text"
        ):
            current = _merge_sections(current, sections[index])
            index += 1

        if (
            current.structure_kind == "text"
            and len(current.content) < config.min_parent_section_length
            and merged_sections
            and merged_sections[-1].structure_kind == "text"
        ):
            previous = merged_sections.pop()
            current = _merge_sections(previous, current)

        merged_sections.append(current)

    normalized_sections: list[SectionDraft] = []
    cursor = 0
    for section_index, section in enumerate(merged_sections):
        start_offset = cursor
        end_offset = start_offset + len(section.content)
        normalized_sections.append(
            SectionDraft(
                section_index=section_index,
                structure_kind=section.structure_kind,
                heading=section.heading,
                content=section.content,
                start_offset=start_offset,
                end_offset=end_offset,
            )
        )
        cursor = end_offset + 2
    return normalized_sections


def _merge_sections(left_section: SectionDraft, right_section: SectionDraft) -> SectionDraft:
    """合併兩個相鄰文字 parent section 草稿。

    參數：
    - `left_section`：前段 section。
    - `right_section`：後段 section。

    回傳：
    - `SectionDraft`：尚未重新計算 index 與 offset 的合併結果。
    """

    return SectionDraft(
        section_index=0,
        structure_kind="text",
        heading=_merge_headings(left_section.heading, right_section.heading),
        content=f"{left_section.content}\n\n{right_section.content}",
        start_offset=0,
        end_offset=0,
    )


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
    - `config`：chunking 參數設定。

    回傳：
    - `list[ChunkDraft]`：此 section 下的 child chunk 草稿。
    """

    if section.structure_kind == "table":
        return _build_table_child_chunks(section=section, position_counter=position_counter, config=config)
    return _build_text_child_chunks(section=section, position_counter=position_counter, config=config)


def _build_text_child_chunks(
    *,
    section: SectionDraft,
    position_counter: count[int],
    config: ChunkingConfig,
) -> list[ChunkDraft]:
    """將文字 parent section 切成 child chunks。

    參數：
    - `section`：待切分的文字 parent section。
    - `position_counter`：整份文件的全域 position 計數器。
    - `config`：chunking 參數設定。

    回傳：
    - `list[ChunkDraft]`：文字 child chunk 草稿。
    """

    children: list[ChunkDraft] = []
    child_index = 0
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.target_child_chunk_size,
        chunk_overlap=config.child_chunk_overlap,
        add_start_index=True,
        strip_whitespace=False,
    )

    for relative_start, chunk_content in _split_text_content(section.content, splitter=splitter):
        normalized_start = section.start_offset + relative_start
        normalized_end = normalized_start + len(chunk_content)
        children.append(
            ChunkDraft(
                chunk_type="child",
                structure_kind="text",
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


def _split_text_content(content: str, *, splitter: RecursiveCharacterTextSplitter) -> list[tuple[int, str]]:
    """將文字內容切成帶相對 offset 的 child 內容。

    參數：
    - `content`：文字 parent 內容。
    - `splitter`：LangChain splitter 實例。

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
        normalized_end = len(raw_content) - trailing_trim
        if normalized_end <= leading_trim:
            continue
        chunk_content = raw_content[leading_trim:normalized_end]
        if not chunk_content.strip():
            continue
        children.append((start_index + leading_trim, chunk_content))
    return children


def _build_table_child_chunks(
    *,
    section: SectionDraft,
    position_counter: count[int],
    config: ChunkingConfig,
) -> list[ChunkDraft]:
    """將表格 parent section 切成 table-aware child chunks。

    參數：
    - `section`：待切分的表格 parent section。
    - `position_counter`：整份文件的全域 position 計數器。
    - `config`：chunking 參數設定。

    回傳：
    - `list[ChunkDraft]`：表格 child chunk 草稿。
    """

    if len(section.content) <= config.table_preserve_max_chars:
        return [
            ChunkDraft(
                chunk_type="child",
                structure_kind="table",
                position=next(position_counter),
                section_index=section.section_index,
                child_index=0,
                heading=section.heading,
                content=section.content,
                content_preview=_build_content_preview(section.content, config=config),
                char_count=len(section.content),
                start_offset=section.start_offset,
                end_offset=section.end_offset,
            )
        ]

    table_parts = _parse_markdown_table_content(section.content)
    if not table_parts.data_rows:
        return [
            ChunkDraft(
                chunk_type="child",
                structure_kind="table",
                position=next(position_counter),
                section_index=section.section_index,
                child_index=0,
                heading=section.heading,
                content=section.content,
                content_preview=_build_content_preview(section.content, config=config),
                char_count=len(section.content),
                start_offset=section.start_offset,
                end_offset=section.end_offset,
            )
        ]

    children: list[ChunkDraft] = []
    for child_index, row_group in enumerate(
        _group_table_rows(data_rows=table_parts.data_rows, max_rows_per_child=config.table_max_rows_per_child)
    ):
        row_start = row_group[0].start_offset
        row_end = row_group[-1].end_offset
        child_content = "\n".join(
            [table_parts.header_row, table_parts.delimiter_row, *(row.content for row in row_group)]
        ).strip()
        children.append(
            ChunkDraft(
                chunk_type="child",
                structure_kind="table",
                position=next(position_counter),
                section_index=section.section_index,
                child_index=child_index,
                heading=section.heading,
                content=child_content,
                content_preview=_build_content_preview(child_content, config=config),
                char_count=len(child_content),
                start_offset=section.start_offset + row_start,
                end_offset=section.start_offset + row_end,
            )
        )
    return children


@dataclass(slots=True)
class _TableRow:
    """表格資料列與其在 parent content 中的 offset。"""

    # 資料列文字內容。
    content: str
    # 資料列相對於表格內容的起始 offset。
    start_offset: int
    # 資料列相對於表格內容的結束 offset。
    end_offset: int


@dataclass(slots=True)
class _ParsedTableContent:
    """表格內容拆解結果。"""

    # 表頭列文字。
    header_row: str
    # delimiter 列文字。
    delimiter_row: str
    # 資料列清單。
    data_rows: list[_TableRow]


def _parse_markdown_table_content(content: str) -> _ParsedTableContent:
    """將 Markdown table 文本拆成 header、delimiter 與資料列。

    參數：
    - `content`：Markdown table 文字。

    回傳：
    - `_ParsedTableContent`：拆解後的表格內容。
    """

    lines = content.splitlines()
    if len(lines) < 2:
        return _ParsedTableContent(header_row=content, delimiter_row="| --- |", data_rows=[])

    line_offsets = _compute_line_offsets(content)
    data_rows = [
        _TableRow(
            content=line,
            start_offset=line_offsets[index],
            end_offset=line_offsets[index] + len(line),
        )
        for index, line in enumerate(lines[2:], start=2)
        if line.strip()
    ]
    return _ParsedTableContent(header_row=lines[0], delimiter_row=lines[1], data_rows=data_rows)


def _compute_line_offsets(content: str) -> list[int]:
    """計算每一行在原始字串中的相對起始 offset。

    參數：
    - `content`：原始字串。

    回傳：
    - `list[int]`：每一行的起始 offset。
    """

    offsets: list[int] = []
    cursor = 0
    for line in content.splitlines():
        offsets.append(cursor)
        cursor += len(line) + 1
    return offsets


def _group_table_rows(*, data_rows: list[_TableRow], max_rows_per_child: int) -> list[list[_TableRow]]:
    """將表格資料列依固定列數分組。

    參數：
    - `data_rows`：表格資料列。
    - `max_rows_per_child`：每個 child 最多資料列數。

    回傳：
    - `list[list[_TableRow]]`：分組後的資料列。
    """

    if not data_rows:
        return []
    return [data_rows[index : index + max_rows_per_child] for index in range(0, len(data_rows), max_rows_per_child)]


def _build_content_preview(content: str, *, config: ChunkingConfig) -> str:
    """建立固定長度的 chunk 摘要。

    參數：
    - `content`：原始 chunk 內容。
    - `config`：chunking 參數設定。

    回傳：
    - `str`：固定長度、去除多餘空白的摘要字串。
    """

    normalized = " ".join(content.split())
    return normalized[: config.content_preview_length]
