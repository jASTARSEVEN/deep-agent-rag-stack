"""Worker ingest 流程使用的 block-aware parser。"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
from html.parser import HTMLParser
from pathlib import Path
import re
import tempfile


# 本 phase 真正支援解析的副檔名。
SUPPORTED_TEXT_EXTENSIONS = {".txt", ".md", ".html", ".pdf", ".xlsx", ".docx", ".pptx"}

# 支援的 PDF parser provider 名稱。
SUPPORTED_PDF_PARSER_PROVIDERS = {"local", "llamaparse"}

# Markdown heading 判定規則。
MARKDOWN_HEADING_PATTERN = re.compile(r"^(#{1,3})\s+(?P<heading>.+?)\s*$")

# Markdown table delimiter 判定規則。
MARKDOWN_TABLE_DELIMITER_PATTERN = re.compile(r"^\s*\|?(?:\s*:?-{3,}:?\s*\|)+\s*:?-{3,}:?\s*\|?\s*$")

# Markdown table cell 分隔規則；忽略 escaped pipe。
MARKDOWN_TABLE_CELL_SPLIT_PATTERN = re.compile(r"(?<!\\)\|")

# PDF Markdown 常見頁碼噪音。
PDF_PAGE_LABEL_PATTERN = re.compile(r"^\s*(?:page|p\.)\s+\d+(?:\s*(?:/|of)\s*\d+)?\s*$", re.IGNORECASE)

# PDF Markdown 常見頁面分隔符噪音。
PDF_PAGE_SEPARATOR_PATTERN = re.compile(r"^\s*(?:-{3,}|\*{3,}|_{3,})\s*$")

# local PDF parser 使用的 Unstructured strategy。
LOCAL_PDF_UNSTRUCTURED_STRATEGY = "fast"


@dataclass(slots=True)
class PdfParserConfig:
    """PDF parser provider 使用的設定。"""

    # 要使用的 PDF parser provider 名稱。
    provider: str = "local"
    # LlamaParse API 金鑰。
    llamaparse_api_key: str | None = None
    # 是否要求 LlamaParse 不快取文件內容。
    llamaparse_do_not_cache: bool = True
    # 是否啟用跨頁延續表格合併。
    llamaparse_merge_continued_tables: bool = False


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


def parse_document(
    *,
    file_name: str,
    payload: bytes,
    pdf_config: PdfParserConfig | None = None,
) -> ParsedDocument:
    """依副檔名選擇 parser，並回傳 block-aware 結果。

    參數：
    - `file_name`：使用者上傳時的原始檔名。
    - `payload`：從物件儲存讀出的原始位元組內容。
    - `pdf_config`：PDF parser provider 設定；非 PDF 檔案時可省略。

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
    if lower_name.endswith(".pdf"):
        return _parse_pdf_document(payload=payload, pdf_config=pdf_config or PdfParserConfig())
    if lower_name.endswith(".xlsx"):
        return _parse_xlsx_document(payload=payload)
    if lower_name.endswith(".docx"):
        return _parse_docx_document(payload=payload)
    if lower_name.endswith(".pptx"):
        return _parse_pptx_document(payload=payload)
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
    return _parse_markdown_text(text=text, source_format="markdown")


def _parse_markdown_text(*, text: str, source_format: str) -> ParsedDocument:
    """解析 Markdown 字串，辨識 heading、文字與表格 blocks。

    參數：
    - `text`：已解碼的 Markdown 文字。
    - `source_format`：來源格式名稱。

    回傳：
    - `ParsedDocument`：Markdown block-aware 結果。
    """

    if not text.strip():
        raise ValueError("文件內容不可為空白。")

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
    return _materialize_blocks(source_format=source_format, block_inputs=block_inputs)


def _parse_pdf_document(*, payload: bytes, pdf_config: PdfParserConfig) -> ParsedDocument:
    """依 provider 解析 PDF，再交由現有 Markdown parser 處理。

    參數：
    - `payload`：PDF 原始位元組內容。
    - `pdf_config`：PDF parser provider 設定。

    回傳：
    - `ParsedDocument`：解析後的標準化文件內容。
    """

    provider = pdf_config.provider.strip().lower()
    if provider not in SUPPORTED_PDF_PARSER_PROVIDERS:
        raise ValueError(f"不支援的 PDF parser provider：{pdf_config.provider}")

    if provider == "local":
        elements = _extract_pdf_elements_with_unstructured(payload=payload)
        return _materialize_blocks(
            source_format="pdf",
            block_inputs=_build_pdf_block_inputs_from_unstructured_elements(elements=elements),
        )

    markdown = _extract_pdf_markdown_with_llamaparse(payload=payload, pdf_config=pdf_config)
    return _parse_markdown_text(text=_clean_llamaparse_markdown(markdown), source_format="pdf")


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
    return _normalize_markdown_table_lines(table_lines), index


def _normalize_markdown_table_lines(lines: list[str]) -> list[str]:
    """將 Markdown table 正規化為穩定且精簡的 canonical 文字。

    參數：
    - `lines`：原始 Markdown table 行列表，至少包含 header 與 delimiter。

    回傳：
    - `list[str]`：移除 padding 空白並壓縮 delimiter 的 table 行列表。
    """

    if len(lines) < 2:
        return [line.rstrip() for line in lines]

    header_cells = _split_markdown_table_row(lines[0])
    delimiter_cells = _split_markdown_table_row(lines[1])
    data_rows = [_split_markdown_table_row(line) for line in lines[2:]]
    column_count = max(
        len(header_cells),
        len(delimiter_cells),
        *(len(row) for row in data_rows),
    )
    padded_header = _pad_markdown_table_row(header_cells, column_count=column_count)
    padded_data_rows = [_pad_markdown_table_row(row, column_count=column_count) for row in data_rows]
    normalized_delimiter = _normalize_markdown_table_delimiter(
        cells=delimiter_cells,
        column_count=column_count,
    )
    return [
        _render_markdown_row(padded_header),
        _render_markdown_delimiter_row(normalized_delimiter),
        *(_render_markdown_row(row) for row in padded_data_rows),
    ]


def _split_markdown_table_row(line: str) -> list[str]:
    """將 Markdown table row 拆為 cell 清單。

    參數：
    - `line`：單行 Markdown table 文字。

    回傳：
    - `list[str]`：去除欄位 padding 後的 cell 內容。
    """

    normalized_line = line.strip()
    if normalized_line.startswith("|"):
        normalized_line = normalized_line[1:]
    if normalized_line.endswith("|"):
        normalized_line = normalized_line[:-1]
    if not normalized_line:
        return []
    return [cell.strip() for cell in MARKDOWN_TABLE_CELL_SPLIT_PATTERN.split(normalized_line)]


def _pad_markdown_table_row(cells: list[str], *, column_count: int) -> list[str]:
    """補齊 Markdown row 的欄位數，維持穩定欄數。

    參數：
    - `cells`：原始 cell 清單。
    - `column_count`：目標欄位數。

    回傳：
    - `list[str]`：補齊空字串後的 cell 清單。
    """

    return cells + [""] * max(column_count - len(cells), 0)


def _normalize_markdown_table_delimiter(*, cells: list[str], column_count: int) -> list[str]:
    """將 delimiter row 壓成最短合法格式並保留對齊資訊。

    參數：
    - `cells`：原始 delimiter cell 清單。
    - `column_count`：目標欄位數。

    回傳：
    - `list[str]`：最小化後的 delimiter cell 清單。
    """

    normalized_cells: list[str] = []
    padded_cells = _pad_markdown_table_row(cells, column_count=column_count)
    for cell in padded_cells:
        compact = cell.replace(" ", "")
        align_left = compact.startswith(":")
        align_right = compact.endswith(":")
        core = "---"
        if align_left:
            core = ":" + core
        if align_right:
            core = core + ":"
        normalized_cells.append(core)
    return normalized_cells


def _parse_html_document(*, payload: bytes) -> ParsedDocument:
    """解析 HTML 文件，抽出文字與表格 blocks。

    參數：
    - `payload`：原始位元組內容。

    回傳：
    - `ParsedDocument`：HTML block-aware 結果。
    """

    text = _decode_payload(payload=payload)
    return _materialize_blocks(source_format="html", block_inputs=_extract_html_block_inputs(text=text))


def _parse_xlsx_document(*, payload: bytes) -> ParsedDocument:
    """使用 Unstructured 解析 XLSX，並將 worksheet 轉為 table-aware blocks。

    參數：
    - `payload`：XLSX 原始位元組內容。

    回傳：
    - `ParsedDocument`：包含各 worksheet table blocks 的結果。
    """

    elements = _extract_xlsx_elements_with_unstructured(payload=payload)
    block_inputs: list[tuple[str, str | None, str]] = []

    for element in elements:
        metadata = getattr(element, "metadata", None)
        heading = _normalize_worksheet_heading(metadata=metadata)
        text_as_html = (getattr(metadata, "text_as_html", None) or "").strip() if metadata is not None else ""
        if text_as_html:
            block_inputs.extend(
                _extract_html_block_inputs(text=f"<h1>{escape(heading)}</h1>\n{text_as_html}" if heading else text_as_html)
            )
            continue

        fallback_text = (getattr(element, "text", "") or "").strip()
        if fallback_text:
            block_inputs.append(("table", heading, fallback_text))

    if not block_inputs:
        raise ValueError("Unstructured XLSX parser 未回傳可用的 worksheet 內容。")

    return _materialize_blocks(source_format="xlsx", block_inputs=block_inputs)


def _parse_docx_document(*, payload: bytes) -> ParsedDocument:
    """使用 Unstructured 解析 DOCX，並映射為 block-aware 結果。

    參數：
    - `payload`：DOCX 原始位元組內容。

    回傳：
    - `ParsedDocument`：DOCX block-aware 結果。
    """

    elements = _extract_docx_elements_with_unstructured(payload=payload)
    return _materialize_blocks(
        source_format="docx",
        block_inputs=_build_office_block_inputs_from_unstructured_elements(elements=elements),
    )


def _parse_pptx_document(*, payload: bytes) -> ParsedDocument:
    """使用 Unstructured 解析 PPTX，並映射為 block-aware 結果。

    參數：
    - `payload`：PPTX 原始位元組內容。

    回傳：
    - `ParsedDocument`：PPTX block-aware 結果。
    """

    elements = _extract_pptx_elements_with_unstructured(payload=payload)
    return _materialize_blocks(
        source_format="pptx",
        block_inputs=_build_office_block_inputs_from_unstructured_elements(elements=elements),
    )


def _extract_html_block_inputs(*, text: str) -> list[tuple[str, str | None, str]]:
    """將 HTML 字串轉為 block 輸入清單。

    參數：
    - `text`：HTML 原始文字。

    回傳：
    - `list[tuple[str, str | None, str]]`：可供 materialize 的 block 輸入。
    """

    parser = _HTMLBlockParser()
    parser.feed(text)
    parser.close()
    if not parser.block_inputs:
        raise ValueError("無法從文件內容建立有效 chunks。")
    return parser.block_inputs


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


def _build_pdf_block_inputs_from_unstructured_elements(*, elements: list[object]) -> list[tuple[str, str | None, str]]:
    """將 Unstructured PDF elements 映射為 block-aware parser 輸入。

    參數：
    - `elements`：Unstructured PDF partition 回傳的 element 清單。

    回傳：
    - `list[tuple[str, str | None, str]]`：可供 materialize 的 block 輸入。
    """

    block_inputs: list[tuple[str, str | None, str]] = []
    current_heading: str | None = None

    for element in elements:
        metadata = getattr(element, "metadata", None)
        category = str(getattr(element, "category", "") or element.__class__.__name__).strip().lower()
        text_as_html = (getattr(metadata, "text_as_html", None) or "").strip() if metadata is not None else ""
        raw_text = (getattr(element, "text", "") or "").strip()

        if category == "title" and raw_text:
            current_heading = raw_text
            block_inputs.append(("text", None, raw_text))
            continue

        if category == "table":
            if text_as_html:
                block_inputs.extend(
                    _extract_html_block_inputs(
                        text=f"<h1>{escape(current_heading)}</h1>\n{text_as_html}" if current_heading else text_as_html
                    )
                )
                continue
            if raw_text:
                block_inputs.append(("table", current_heading, raw_text))
            continue

        if raw_text:
            block_inputs.append(("text", current_heading, raw_text))

    if not block_inputs:
        raise ValueError("local PDF parser 無法從文件中擷取文字內容。")
    return block_inputs


def _build_office_block_inputs_from_unstructured_elements(
    *,
    elements: list[object],
) -> list[tuple[str, str | None, str]]:
    """將 Unstructured DOCX/PPTX elements 映射為 block-aware parser 輸入。

    參數：
    - `elements`：Unstructured office partition 回傳的 element 清單。

    回傳：
    - `list[tuple[str, str | None, str]]`：可供 materialize 的 block 輸入。
    """

    block_inputs: list[tuple[str, str | None, str]] = []
    current_heading: str | None = None

    for element in elements:
        metadata = getattr(element, "metadata", None)
        category = str(getattr(element, "category", "") or element.__class__.__name__).strip().lower()
        text_as_html = (getattr(metadata, "text_as_html", None) or "").strip() if metadata is not None else ""
        raw_text = (getattr(element, "text", "") or "").strip()

        if category == "title" and raw_text:
            current_heading = raw_text
            block_inputs.append(("text", None, raw_text))
            continue

        if category == "table":
            if text_as_html:
                block_inputs.extend(
                    _extract_html_block_inputs(
                        text=f"<h1>{escape(current_heading)}</h1>\n{text_as_html}" if current_heading else text_as_html
                    )
                )
                continue
            if raw_text:
                block_inputs.append(("table", current_heading, raw_text))
            continue

        if raw_text:
            block_inputs.append(("text", current_heading, raw_text))

    if not block_inputs:
        raise ValueError("Unstructured office parser 未回傳可用內容。")
    return block_inputs


def _extract_pdf_elements_with_unstructured(*, payload: bytes) -> list[object]:
    """使用 Unstructured partition_pdf 萃取 PDF elements。

    參數：
    - `payload`：PDF 原始位元組內容。

    回傳：
    - `list[object]`：Unstructured 回傳的 element 清單。
    """

    try:
        from unstructured.partition.pdf import partition_pdf
    except ImportError as exc:
        raise ValueError("local PDF parser 需要安裝 unstructured[pdf] 與相關系統依賴。") from exc

    temp_path = _write_temporary_pdf(payload=payload)
    try:
        elements = partition_pdf(filename=str(temp_path), strategy=LOCAL_PDF_UNSTRUCTURED_STRATEGY)
    except Exception as exc:  # noqa: BLE001 - 對第三方 parser 失敗統一包成受控錯誤。
        raise ValueError(f"Unstructured PDF 解析失敗：{exc}") from exc
    finally:
        temp_path.unlink(missing_ok=True)

    if not elements:
        raise ValueError("local PDF parser 無法從文件中擷取文字內容。")
    return list(elements)


def _extract_pdf_markdown_with_llamaparse(*, payload: bytes, pdf_config: PdfParserConfig) -> str:
    """使用 LlamaParse 將 PDF 轉為 Markdown。

    參數：
    - `payload`：PDF 原始位元組內容。
    - `pdf_config`：LlamaParse 設定。

    回傳：
    - `str`：LlamaParse 回傳的 Markdown 內容。
    """

    if not pdf_config.llamaparse_api_key:
        raise ValueError("PDF_PARSER_PROVIDER=llamaparse 需要設定 LLAMAPARSE_API_KEY。")

    try:
        from llama_parse import LlamaParse
    except ImportError as exc:
        raise ValueError("llamaparse provider 需要安裝 llama-parse。") from exc

    temp_path = _write_temporary_pdf(payload=payload)
    try:
        parser = LlamaParse(
            api_key=pdf_config.llamaparse_api_key,
            result_type="markdown",
            do_not_cache=pdf_config.llamaparse_do_not_cache,
            merge_tables_across_pages_in_markdown=pdf_config.llamaparse_merge_continued_tables,
        )
        documents = parser.load_data(str(temp_path))
    except Exception as exc:  # noqa: BLE001 - 對外部 SaaS 失敗統一包成受控錯誤。
        raise ValueError(f"LlamaParse PDF 解析失敗：{exc}") from exc
    finally:
        temp_path.unlink(missing_ok=True)

    markdown = "\n\n".join(
        document.text.strip()
        for document in documents
        if getattr(document, "text", "").strip()
    ).strip()
    if not markdown:
        raise ValueError("LlamaParse 未回傳可用的 Markdown 內容。")
    return markdown


def _extract_xlsx_elements_with_unstructured(*, payload: bytes) -> list[object]:
    """使用 Unstructured partition_xlsx 擷取 worksheet elements。

    參數：
    - `payload`：XLSX 原始位元組內容。

    回傳：
    - `list[object]`：Unstructured 回傳的 worksheet elements。
    """

    try:
        from unstructured.partition.xlsx import partition_xlsx
    except ImportError as exc:
        raise ValueError("XLSX parser 需要安裝 unstructured[all-docs] 或至少可用的 xlsx 相依套件。") from exc

    temp_path = _write_temporary_file(payload=payload, suffix=".xlsx")
    try:
        elements = partition_xlsx(filename=str(temp_path))
    except Exception as exc:  # noqa: BLE001 - 對第三方 parser 失敗統一包成受控錯誤。
        raise ValueError(f"Unstructured XLSX 解析失敗：{exc}") from exc
    finally:
        temp_path.unlink(missing_ok=True)

    if not elements:
        raise ValueError("Unstructured XLSX parser 未回傳任何 worksheet。")
    return list(elements)


def _extract_docx_elements_with_unstructured(*, payload: bytes) -> list[object]:
    """使用 Unstructured partition_docx 擷取 DOCX elements。

    參數：
    - `payload`：DOCX 原始位元組內容。

    回傳：
    - `list[object]`：Unstructured 回傳的 element 清單。
    """

    try:
        from unstructured.partition.docx import partition_docx
    except ImportError as exc:
        raise ValueError("DOCX parser 需要安裝 unstructured[docx] 與相關相依套件。") from exc

    temp_path = _write_temporary_file(payload=payload, suffix=".docx")
    try:
        elements = partition_docx(filename=str(temp_path))
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Unstructured DOCX 解析失敗：{exc}") from exc
    finally:
        temp_path.unlink(missing_ok=True)

    if not elements:
        raise ValueError("Unstructured DOCX parser 未回傳任何內容。")
    return list(elements)


def _extract_pptx_elements_with_unstructured(*, payload: bytes) -> list[object]:
    """使用 Unstructured partition_pptx 擷取 PPTX elements。

    參數：
    - `payload`：PPTX 原始位元組內容。

    回傳：
    - `list[object]`：Unstructured 回傳的 element 清單。
    """

    try:
        from unstructured.partition.pptx import partition_pptx
    except ImportError as exc:
        raise ValueError("PPTX parser 需要安裝 unstructured[pptx] 與相關相依套件。") from exc

    temp_path = _write_temporary_file(payload=payload, suffix=".pptx")
    try:
        elements = partition_pptx(filename=str(temp_path))
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Unstructured PPTX 解析失敗：{exc}") from exc
    finally:
        temp_path.unlink(missing_ok=True)

    if not elements:
        raise ValueError("Unstructured PPTX parser 未回傳任何內容。")
    return list(elements)


def _write_temporary_pdf(*, payload: bytes) -> Path:
    """將 PDF bytes 寫入暫存檔，供 PDF loader 使用。

    參數：
    - `payload`：PDF 原始位元組內容。

    回傳：
    - `Path`：暫存 PDF 檔案路徑。
    """

    return _write_temporary_file(payload=payload, suffix=".pdf")


def _write_temporary_file(*, payload: bytes, suffix: str) -> Path:
    """將二進位內容寫入指定副檔名的暫存檔。

    參數：
    - `payload`：原始位元組內容。
    - `suffix`：暫存檔副檔名。

    回傳：
    - `Path`：暫存檔案路徑。
    """

    with tempfile.NamedTemporaryFile("wb", suffix=suffix, delete=False) as temporary_file:
        temporary_file.write(payload)
        return Path(temporary_file.name)


def _normalize_worksheet_heading(*, metadata: object | None) -> str | None:
    """從 Unstructured metadata 擷取 worksheet 名稱。

    參數：
    - `metadata`：Unstructured element metadata。

    回傳：
    - `str | None`：標準化後的 worksheet 名稱。
    """

    if metadata is None:
        return None

    for attribute_name in ("page_name", "sheet_name", "text_as_html"):
        if attribute_name == "text_as_html":
            continue
        value = getattr(metadata, attribute_name, None)
        if isinstance(value, str):
            normalized_value = value.strip()
            if normalized_value:
                return normalized_value
    return None


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


def _render_markdown_delimiter_row(cells: list[str]) -> str:
    """將 delimiter cells 渲染為穩定的 Markdown delimiter row。

    參數：
    - `cells`：delimiter cell 清單。

    回傳：
    - `str`：Markdown delimiter row。
    """

    return "| " + " | ".join(cell.strip() or "---" for cell in cells) + " |"


def _normalize_whitespace(value: str) -> str:
    """將多餘空白壓平成單一空白。

    參數：
    - `value`：原始字串。

    回傳：
    - `str`：正規化後字串。
    """

    return " ".join(value.split()).strip()


def _clean_llamaparse_markdown(markdown: str) -> str:
    """清理 LlamaParse Markdown 中常見的頁碼與分隔噪音。

    參數：
    - `markdown`：LlamaParse 回傳的 Markdown 文字。

    回傳：
    - `str`：移除常見頁面噪音後的 Markdown。
    """

    cleaned_lines: list[str] = []
    previous_was_blank = True

    for line in markdown.splitlines():
        stripped = line.strip()
        if PDF_PAGE_LABEL_PATTERN.match(stripped) or PDF_PAGE_SEPARATOR_PATTERN.match(stripped):
            continue
        if not stripped:
            if previous_was_blank:
                continue
            cleaned_lines.append("")
            previous_was_blank = True
            continue

        cleaned_lines.append(line.rstrip())
        previous_was_blank = False

    cleaned_markdown = "\n".join(cleaned_lines).strip()
    if not cleaned_markdown:
        raise ValueError("LlamaParse Markdown 清理後沒有剩餘內容。")
    return cleaned_markdown
