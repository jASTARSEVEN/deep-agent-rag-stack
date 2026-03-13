"""API inline ingest 使用的 block-aware parser。"""

from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
import re


# 本 phase 真正支援解析的副檔名。
SUPPORTED_TEXT_EXTENSIONS = {".txt", ".md", ".html"}

# Markdown heading 判定規則。
MARKDOWN_HEADING_PATTERN = re.compile(r"^(#{1,3})\s+(?P<heading>.+?)\s*$")

# Markdown table delimiter 判定規則。
MARKDOWN_TABLE_DELIMITER_PATTERN = re.compile(r"^\s*\|?(?:\s*:?-{3,}:?\s*\|)+\s*:?-{3,}:?\s*\|?\s*$")


@dataclass(slots=True)
class ParsedBlock:
    """Parser 輸出的結構化內容區塊。"""

    # block 內容型別。
    block_kind: str
    # 區塊所屬 heading。
    heading: str | None
    # 區塊文字內容。
    content: str
    # 區塊在 normalized text 的起始 offset。
    start_offset: int
    # 區塊在 normalized text 的結束 offset。
    end_offset: int


@dataclass(slots=True)
class ParsedDocument:
    """Parser 輸出的標準化文件內容。"""

    # normalize 後的整份文字內容。
    normalized_text: str
    # 原始來源格式。
    source_format: str
    # parser 辨識出的結構化 blocks。
    blocks: list[ParsedBlock]


def parse_document(*, file_name: str, payload: bytes) -> ParsedDocument:
    """依副檔名選擇 parser，並回傳 block-aware 結果。

    參數：
    - `file_name`：使用者上傳時的原始檔名。
    - `payload`：從物件儲存讀出的原始位元組內容。

    回傳：
    - `ParsedDocument`：解析後的標準化文件內容。
    """

    lower_name = file_name.lower()
    if lower_name.endswith(".txt"):
        return _parse_txt_document(payload=payload)
    if lower_name.endswith(".md"):
        return _parse_markdown_document(payload=payload)
    if lower_name.endswith(".html"):
        return _parse_html_document(payload=payload)
    raise ValueError("目前尚未支援此檔案類型的解析。")


def _decode_payload(*, payload: bytes) -> str:
    """將檔案位元組解碼為 UTF-8 文字。

    參數：
    - `payload`：原始位元組內容。

    回傳：
    - `str`：解碼後文字。
    """

    text = payload.decode("utf-8")
    if not text.strip():
        raise ValueError("文件內容不可為空白。")
    return text


def _parse_txt_document(*, payload: bytes) -> ParsedDocument:
    """解析 TXT 文件。

    參數：
    - `payload`：原始位元組內容。

    回傳：
    - `ParsedDocument`：包含單一 text block 的結果。
    """

    normalized_text = _decode_payload(payload=payload).strip()
    return _materialize_blocks(source_format="txt", block_inputs=[("text", None, normalized_text)])


def _parse_markdown_document(*, payload: bytes) -> ParsedDocument:
    """解析 Markdown 文件，辨識 heading、文字與表格 blocks。

    參數：
    - `payload`：原始位元組內容。

    回傳：
    - `ParsedDocument`：Markdown block-aware 結果。
    """

    text = _decode_payload(payload=payload).strip()
    lines = text.splitlines()
    block_inputs: list[tuple[str, str | None, str]] = []
    current_heading: str | None = None
    current_text_lines: list[str] = []
    index = 0

    while index < len(lines):
        line = lines[index].rstrip()
        heading_match = MARKDOWN_HEADING_PATTERN.match(line)
        if heading_match:
            _append_markdown_text_block(block_inputs=block_inputs, heading=current_heading, lines=current_text_lines)
            current_heading = heading_match.group("heading").strip()
            current_text_lines = []
            index += 1
            continue

        if _is_markdown_table_start(lines=lines, start_index=index):
            _append_markdown_text_block(block_inputs=block_inputs, heading=current_heading, lines=current_text_lines)
            current_text_lines = []
            table_lines, next_index = _consume_markdown_table(lines=lines, start_index=index)
            block_inputs.append(("table", current_heading, "\n".join(table_lines).strip()))
            index = next_index
            continue

        current_text_lines.append(line)
        index += 1

    _append_markdown_text_block(block_inputs=block_inputs, heading=current_heading, lines=current_text_lines)
    if not block_inputs:
        block_inputs.append(("text", None, text))
    return _materialize_blocks(source_format="markdown", block_inputs=block_inputs)


def _append_markdown_text_block(
    *,
    block_inputs: list[tuple[str, str | None, str]],
    heading: str | None,
    lines: list[str],
) -> None:
    """將 Markdown 累積中的文字內容附加為 text block。

    參數：
    - `block_inputs`：目前累積的 block 輸入。
    - `heading`：當前 heading。
    - `lines`：當前文字行列表。

    回傳：
    - `None`：此函式只在有有效內容時附加 block。
    """

    content = "\n".join(lines).strip()
    if content:
        block_inputs.append(("text", heading, content))


def _is_markdown_table_start(*, lines: list[str], start_index: int) -> bool:
    """判定指定位置是否為 Markdown table 起點。

    參數：
    - `lines`：整份 Markdown 行列表。
    - `start_index`：欲檢查的起始行位置。

    回傳：
    - `bool`：若為 GFM table 起點則回傳真。
    """

    if start_index + 1 >= len(lines):
        return False
    header_line = lines[start_index].rstrip()
    delimiter_line = lines[start_index + 1].rstrip()
    return "|" in header_line and bool(MARKDOWN_TABLE_DELIMITER_PATTERN.match(delimiter_line))


def _consume_markdown_table(*, lines: list[str], start_index: int) -> tuple[list[str], int]:
    """讀取從指定位置開始的整張 Markdown table。

    參數：
    - `lines`：整份 Markdown 行列表。
    - `start_index`：table 起始行位置。

    回傳：
    - `tuple[list[str], int]`：table 行列表與下一個尚未消耗的行索引。
    """

    table_lines = [lines[start_index].rstrip(), lines[start_index + 1].rstrip()]
    index = start_index + 2
    while index < len(lines):
        candidate = lines[index].rstrip()
        if not candidate.strip() or "|" not in candidate:
            break
        table_lines.append(candidate)
        index += 1
    return table_lines, index


def _parse_html_document(*, payload: bytes) -> ParsedDocument:
    """解析 HTML 文件，抽出文字與表格 blocks。

    參數：
    - `payload`：原始位元組內容。

    回傳：
    - `ParsedDocument`：HTML block-aware 結果。
    """

    text = _decode_payload(payload=payload)
    parser = _HTMLBlockParser()
    parser.feed(text)
    parser.close()
    if not parser.block_inputs:
        raise ValueError("無法從文件內容建立有效 chunks。")
    return _materialize_blocks(source_format="html", block_inputs=parser.block_inputs)


def _materialize_blocks(*, source_format: str, block_inputs: list[tuple[str, str | None, str]]) -> ParsedDocument:
    """將 block 輸入轉為帶 offset 的 ParsedDocument。

    參數：
    - `source_format`：來源格式。
    - `block_inputs`：block 型別、heading 與內容清單。

    回傳：
    - `ParsedDocument`：帶有 normalized text 與 blocks 的結果。
    """

    blocks: list[ParsedBlock] = []
    normalized_parts: list[str] = []
    cursor = 0

    for block_kind, heading, raw_content in block_inputs:
        content = raw_content.strip()
        if not content:
            continue
        start_offset = cursor
        end_offset = start_offset + len(content)
        blocks.append(
            ParsedBlock(
                block_kind=block_kind,
                heading=heading,
                content=content,
                start_offset=start_offset,
                end_offset=end_offset,
            )
        )
        normalized_parts.append(content)
        cursor = end_offset + 2

    if not blocks:
        raise ValueError("無法從文件內容建立有效 chunks。")

    return ParsedDocument(normalized_text="\n\n".join(normalized_parts), source_format=source_format, blocks=blocks)


class _HTMLBlockParser(HTMLParser):
    """最小 HTML parser，抽出 headings、文字 block 與表格 block。"""

    def __init__(self) -> None:
        """建立 HTML block parser。

        參數：
        - 無

        回傳：
        - `None`：初始化內部狀態。
        """

        super().__init__(convert_charrefs=True)
        self.block_inputs: list[tuple[str, str | None, str]] = []
        self.current_heading: str | None = None
        self._heading_tag: str | None = None
        self._heading_parts: list[str] = []
        self._text_tag_stack: list[str] = []
        self._text_parts: list[str] = []
        self._in_table = False
        self._table_rows: list[list[str]] = []
        self._table_row: list[str] = []
        self._cell_parts: list[str] = []
        self._in_cell = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """處理 HTML 開始標籤。

        參數：
        - `tag`：標籤名稱。
        - `attrs`：標籤屬性列表。

        回傳：
        - `None`：只更新 parser 狀態。
        """

        del attrs
        if tag in {"h1", "h2", "h3"}:
            self._flush_text_block()
            self._heading_tag = tag
            self._heading_parts = []
            return
        if tag in {"p", "li"}:
            self._flush_text_block()
            self._text_tag_stack.append(tag)
            self._text_parts = []
            return
        if tag == "table":
            self._flush_text_block()
            self._in_table = True
            self._table_rows = []
            return
        if not self._in_table:
            return
        if tag == "tr":
            self._table_row = []
            return
        if tag in {"th", "td"}:
            self._in_cell = True
            self._cell_parts = []

    def handle_endtag(self, tag: str) -> None:
        """處理 HTML 結束標籤。

        參數：
        - `tag`：標籤名稱。

        回傳：
        - `None`：只更新 parser 狀態。
        """

        if tag in {"h1", "h2", "h3"} and self._heading_tag == tag:
            heading = _normalize_whitespace(" ".join(self._heading_parts))
            self.current_heading = heading or self.current_heading
            self._heading_tag = None
            self._heading_parts = []
            return
        if tag in {"p", "li"} and self._text_tag_stack:
            self._flush_text_block()
            self._text_tag_stack.pop()
            return
        if not self._in_table:
            return
        if tag in {"th", "td"} and self._in_cell:
            cell_text = _normalize_whitespace(" ".join(self._cell_parts))
            self._table_row.append(cell_text)
            self._cell_parts = []
            self._in_cell = False
            return
        if tag == "tr" and self._table_row:
            self._table_rows.append(self._table_row)
            self._table_row = []
            return
        if tag == "table":
            self._flush_table_block()
            self._in_table = False

    def handle_data(self, data: str) -> None:
        """處理 HTML 純文字內容。

        參數：
        - `data`：當前文字內容。

        回傳：
        - `None`：只更新 parser 狀態。
        """

        if self._heading_tag is not None:
            self._heading_parts.append(data)
            return
        if self._in_table and self._in_cell:
            self._cell_parts.append(data)
            return
        if self._text_tag_stack:
            self._text_parts.append(data)

    def close(self) -> None:
        """結束 parser 並 flush 殘留 block。

        參數：
        - 無

        回傳：
        - `None`：完成 parser 收尾。
        """

        super().close()
        self._flush_text_block()
        if self._in_table:
            self._flush_table_block()
            self._in_table = False

    def _flush_text_block(self) -> None:
        """將目前文字內容輸出為 text block。

        參數：
        - 無

        回傳：
        - `None`：若無內容則不輸出 block。
        """

        content = _normalize_whitespace(" ".join(self._text_parts))
        if content:
            self.block_inputs.append(("text", self.current_heading, content))
        self._text_parts = []

    def _flush_table_block(self) -> None:
        """將目前表格內容輸出為 table block。

        參數：
        - 無

        回傳：
        - `None`：若無有效列則不輸出 block。
        """

        if not self._table_rows:
            return
        table_content = _render_table_rows_as_markdown(self._table_rows)
        if table_content:
            self.block_inputs.append(("table", self.current_heading, table_content))
        self._table_rows = []
        self._table_row = []
        self._cell_parts = []
        self._in_cell = False


def _render_table_rows_as_markdown(rows: list[list[str]]) -> str:
    """將表格列渲染為穩定的 Markdown table 文字。

    參數：
    - `rows`：表格列資料。

    回傳：
    - `str`：Markdown table 文字內容。
    """

    normalized_rows = [[cell.strip() for cell in row] for row in rows if any(cell.strip() for cell in row)]
    if not normalized_rows:
        return ""
    column_count = max(len(row) for row in normalized_rows)
    padded_rows = [row + [""] * (column_count - len(row)) for row in normalized_rows]
    header = padded_rows[0]
    delimiter = ["---"] * column_count
    body = padded_rows[1:]
    lines = [_render_markdown_row(header), _render_markdown_row(delimiter)]
    lines.extend(_render_markdown_row(row) for row in body)
    return "\n".join(lines).strip()


def _render_markdown_row(cells: list[str]) -> str:
    """將單列表格資料轉為 Markdown row。

    參數：
    - `cells`：單列 cell 內容。

    回傳：
    - `str`：Markdown table row。
    """

    return "| " + " | ".join(cell.replace("\n", " ").strip() for cell in cells) + " |"


def _normalize_whitespace(value: str) -> str:
    """將多餘空白壓平成單一空白。

    參數：
    - `value`：原始字串。

    回傳：
    - `str`：正規化後字串。
    """

    return " ".join(value.split()).strip()
