"""將外部 benchmark 資料集轉成現有 retrieval benchmark snapshot 的 CLI。"""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select

from app.core.settings import get_settings
from app.db.models import Document, DocumentStatus
from app.db.session import create_database_engine, create_session_factory


# workspace 內統一使用的中間檔名。
PREPARED_DOCUMENTS_FILE = "prepared_documents.jsonl"
PREPARED_ITEMS_FILE = "prepared_items.jsonl"
FILTERED_ITEMS_FILE = "filtered_items.jsonl"
FILTER_REPORT_FILE = "filter_report.json"
ALIGNMENT_CANDIDATES_FILE = "alignment_candidates.jsonl"
ALIGNMENT_REVIEW_QUEUE_FILE = "alignment_review_queue.jsonl"
ALIGNMENT_REPORT_FILE = "alignment_report.json"
REVIEW_OVERRIDES_FILE = "review_overrides.jsonl"
SOURCE_DOCUMENTS_DIRNAME = "source_documents"

# snapshot 內固定輸出的檔名。
SNAPSHOT_REQUIRED_FILES = (
    "manifest.json",
    "documents.jsonl",
    "questions.jsonl",
    "gold_spans.jsonl",
)

# curated v1 允許的最大短答案長度，避免把摘要型答案誤收進 fact lookup。
MAX_SHORT_ANSWER_CHARS = 240

# evidence 太長通常代表需要跨段 synthesis，第一版直接排除。
MAX_EVIDENCE_CHARS = 800

# fuzzy 對齊最低接受分數。
FUZZY_ACCEPT_SCORE = 0.92

# fuzzy 第一名與第二名至少要拉開的分數差距。
FUZZY_ACCEPT_MARGIN = 0.05


@dataclass(slots=True)
class NormalizedText:
    """保存正規化文字與回推原始 offset 的索引。"""

    normalized_text: str
    normalized_to_original: list[int]


def build_parser() -> argparse.ArgumentParser:
    """建立 CLI parser。

    參數：
    - 無。

    回傳：
    - `argparse.ArgumentParser`：可解析外部 benchmark curation 指令的 parser。
    """

    parser = argparse.ArgumentParser(description="將 QASPER / UDA 類外部資料集轉成現有 retrieval benchmark snapshot。")
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare_parser = subparsers.add_parser("prepare-source")
    prepare_parser.add_argument("--dataset", choices=["qasper", "uda"], required=True)
    prepare_parser.add_argument("--input-path", required=True, help="外部資料集檔案或目錄。")
    prepare_parser.add_argument("--workspace-dir", required=True, help="中間產物輸出目錄。")
    prepare_parser.add_argument("--limit-documents", type=int, default=None)
    prepare_parser.add_argument("--limit-items", type=int, default=None)

    filter_parser = subparsers.add_parser("filter-items")
    filter_parser.add_argument("--workspace-dir", required=True)

    align_parser = subparsers.add_parser("align-spans")
    align_parser.add_argument("--workspace-dir", required=True)
    align_parser.add_argument("--area-id", required=True)

    build_parser_cmd = subparsers.add_parser("build-snapshot")
    build_parser_cmd.add_argument("--workspace-dir", required=True)
    build_parser_cmd.add_argument("--output-dir", required=True)
    build_parser_cmd.add_argument("--benchmark-name", required=True)
    build_parser_cmd.add_argument("--include-review-items", action="store_true")

    report_parser = subparsers.add_parser("report")
    report_parser.add_argument("--workspace-dir", required=True)
    return parser


def ensure_workspace_dir(workspace_dir: Path) -> None:
    """建立 benchmark curation workspace。

    參數：
    - `workspace_dir`：工作目錄。

    回傳：
    - `None`：若目錄不存在則建立。
    """

    workspace_dir.mkdir(parents=True, exist_ok=True)
    (workspace_dir / SOURCE_DOCUMENTS_DIRNAME).mkdir(parents=True, exist_ok=True)


def read_json(path: Path) -> Any:
    """讀取 JSON 檔案。

    參數：
    - `path`：JSON 路徑。

    回傳：
    - `Any`：解析後的 JSON payload。
    """

    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """讀取 JSONL 檔案。

    參數：
    - `path`：JSONL 路徑。

    回傳：
    - `list[dict[str, Any]]`：逐行 JSON 物件。
    """

    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: dict[str, Any]) -> None:
    """將 JSON payload 寫入檔案。

    參數：
    - `path`：目標檔案。
    - `payload`：可序列化物件。

    回傳：
    - `None`：寫入完成。
    """

    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    """將 JSONL rows 寫入檔案。

    參數：
    - `path`：目標檔案。
    - `rows`：逐行物件。

    回傳：
    - `None`：寫入完成。
    """

    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")


def slugify_filename(value: str, *, suffix: str) -> str:
    """將字串轉成安全檔名。

    參數：
    - `value`：原始名稱。
    - `suffix`：檔名副檔名。

    回傳：
    - `str`：安全檔名。
    """

    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-") or "document"
    return f"{stem}{suffix}"


def now_iso() -> str:
    """回傳目前 UTC ISO 時間字串。

    參數：
    - 無。

    回傳：
    - `str`：ISO 8601 時間字串。
    """

    return datetime.now(UTC).isoformat()


def stable_uuid(value: str) -> str:
    """依固定字串產生穩定 UUID。

    參數：
    - `value`：穩定輸入字串。

    回傳：
    - `str`：UUID5 字串。
    """

    return str(uuid5(NAMESPACE_URL, value))


def flatten_text(value: Any) -> str:
    """將巢狀文字 payload 攤平成單一字串。

    參數：
    - `value`：可能為字串、list、dict 的資料。

    回傳：
    - `str`：展平成單一字串後的內容。
    """

    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        parts = [flatten_text(item) for item in value]
        return "\n".join(part for part in parts if part)
    if isinstance(value, dict):
        for candidate_key in ("text", "paragraph", "content", "value", "sentence"):
            if candidate_key in value:
                return flatten_text(value[candidate_key])
        return ""
    return str(value).strip()


def normalize_newlines(text: str) -> str:
    """統一換行並清掉多餘空白。

    參數：
    - `text`：原始字串。

    回傳：
    - `str`：清理後文字。
    """

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = re.sub(r"[ \t]+\n", "\n", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def build_qasper_markdown(record: dict[str, Any]) -> str:
    """將 QASPER paper record 轉成 Markdown 文件。

    參數：
    - `record`：單篇 paper 原始資料。

    回傳：
    - `str`：可寫入 repo 的 Markdown 內容。
    """

    title = flatten_text(record.get("title")) or flatten_text(record.get("paper_title")) or "Untitled Paper"
    abstract = flatten_text(record.get("abstract"))
    sections = record.get("full_text") or record.get("sections") or []

    blocks = [f"# {title}"]
    if abstract:
        blocks.extend(["", "## Abstract", "", abstract])

    for section in sections:
        heading = flatten_text(section.get("section_name") or section.get("heading") or section.get("title")) or "Section"
        paragraphs = section.get("paragraphs") or section.get("text") or section.get("contents") or []
        paragraph_text = flatten_text(paragraphs)
        if not paragraph_text:
            continue
        blocks.extend(["", f"## {heading}", "", paragraph_text])
    return normalize_newlines("\n".join(blocks)) + "\n"


def extract_qasper_answer_bundle(raw_answers: list[dict[str, Any]]) -> dict[str, Any] | None:
    """從多個 annotator answer 中挑出最適合 benchmark 的一筆。

    參數：
    - `raw_answers`：QASPER answers 陣列。

    回傳：
    - `dict[str, Any] | None`：整理後的 answer bundle；若無可用答案則回傳空值。
    """

    for raw_answer in raw_answers:
        answer_payload = raw_answer.get("answer") if isinstance(raw_answer, dict) else None
        if not isinstance(answer_payload, dict):
            continue
        if answer_payload.get("unanswerable"):
            continue
        yes_no = answer_payload.get("yes_no") or answer_payload.get("yes_no_answer")
        if isinstance(yes_no, bool):
            continue
        if isinstance(yes_no, str) and yes_no.lower() in {"yes", "no"}:
            continue

        extractive_spans = [span.strip() for span in answer_payload.get("extractive_spans", []) if isinstance(span, str) and span.strip()]
        evidence_nodes = answer_payload.get("evidence") or raw_answer.get("evidence") or []
        evidence_texts = [flatten_text(node) for node in evidence_nodes]
        evidence_texts = [text for text in evidence_texts if text]
        answer_text = flatten_text(
            answer_payload.get("free_form_answer")
            or answer_payload.get("extractive_answer")
            or raw_answer.get("free_form_answer")
        )
        if not extractive_spans and not evidence_texts:
            continue
        if answer_text and len(answer_text) > MAX_SHORT_ANSWER_CHARS:
            continue
        return {
            "answer_text": answer_text,
            "evidence_texts": extractive_spans or evidence_texts,
            "answer_type": "extractive" if extractive_spans else "evidence_only",
            "raw_answer": raw_answer,
        }
    return None


def prepare_qasper_source(*, input_path: Path, workspace_dir: Path, limit_documents: int | None, limit_items: int | None) -> dict[str, Any]:
    """將 QASPER 原始資料轉成中間格式與 source documents。

    參數：
    - `input_path`：QASPER JSON 檔。
    - `workspace_dir`：benchmark 工作目錄。
    - `limit_documents`：最多處理幾份文件。
    - `limit_items`：最多輸出幾題。

    回傳：
    - `dict[str, Any]`：prepare 摘要。
    """

    raw_payload = read_json(input_path)
    if isinstance(raw_payload, dict):
        raw_records = list(raw_payload.values())
    elif isinstance(raw_payload, list):
        raw_records = raw_payload
    else:
        raise ValueError("QASPER input 必須是 JSON object 或 JSON array。")

    documents: list[dict[str, Any]] = []
    items: list[dict[str, Any]] = []
    source_dir = workspace_dir / SOURCE_DOCUMENTS_DIRNAME

    for record_index, record in enumerate(raw_records):
        if limit_documents is not None and len(documents) >= limit_documents:
            break
        paper_id = str(record.get("paper_id") or record.get("id") or record.get("title") or f"qasper-paper-{record_index}")
        file_name = slugify_filename(paper_id, suffix=".md")
        markdown = build_qasper_markdown(record)
        output_path = source_dir / file_name
        output_path.write_text(markdown, encoding="utf-8")

        document_row = {
            "dataset": "qasper",
            "source_document_id": paper_id,
            "file_name": file_name,
            "title": flatten_text(record.get("title") or record.get("paper_title")) or paper_id,
            "source_path": str(output_path.resolve()),
            "content_type": "text/markdown",
            "created_at": now_iso(),
        }
        documents.append(document_row)

        question_groups = record.get("qas") or record.get("questions") or []
        for question_index, question_entry in enumerate(question_groups):
            if limit_items is not None and len(items) >= limit_items:
                break
            question_text = flatten_text(question_entry.get("question") or question_entry.get("query"))
            raw_answers = question_entry.get("answers") or question_entry.get("answer") or []
            if isinstance(raw_answers, dict):
                raw_answers = [raw_answers]
            answer_bundle = extract_qasper_answer_bundle(raw_answers)
            item_id = stable_uuid(f"qasper::{paper_id}::{question_index}::{question_text}")
            items.append(
                {
                    "item_id": item_id,
                    "dataset": "qasper",
                    "source_document_id": paper_id,
                    "file_name": file_name,
                    "query_text": question_text,
                    "language": "en",
                    "query_type": "fact_lookup",
                    "answer_text": answer_bundle["answer_text"] if answer_bundle else "",
                    "evidence_texts": answer_bundle["evidence_texts"] if answer_bundle else [],
                    "answer_type": answer_bundle["answer_type"] if answer_bundle else "missing",
                    "source_question_index": question_index,
                    "source_metadata": {
                        "question_id": question_entry.get("question_id"),
                        "paper_id": paper_id,
                    },
                    "created_at": now_iso(),
                }
            )
        if limit_items is not None and len(items) >= limit_items:
            break

    write_jsonl(workspace_dir / PREPARED_DOCUMENTS_FILE, documents)
    write_jsonl(workspace_dir / PREPARED_ITEMS_FILE, items)
    return {
        "dataset": "qasper",
        "document_count": len(documents),
        "item_count": len(items),
        "workspace_dir": str(workspace_dir),
    }


def read_table_like_rows(input_path: Path) -> list[dict[str, Any]]:
    """讀取 CSV / JSON / JSONL 的列資料。

    參數：
    - `input_path`：輸入檔案。

    回傳：
    - `list[dict[str, Any]]`：列資料。
    """

    if input_path.is_dir():
        raise ValueError("UDA input 目前需提供單一檔案。")
    suffix = input_path.suffix.lower()
    if suffix == ".jsonl":
        return read_jsonl(input_path)
    if suffix == ".json":
        payload = read_json(input_path)
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            rows = payload.get("data") or payload.get("rows")
            if isinstance(rows, list):
                return rows
        raise ValueError("UDA JSON input 必須是 rows list。")
    if suffix in {".csv", ".tsv"}:
        delimiter = "\t" if suffix == ".tsv" else ","
        with input_path.open("r", encoding="utf-8") as file:
            return list(csv.DictReader(file, delimiter=delimiter))
    raise ValueError("UDA input 只支援 .json / .jsonl / .csv / .tsv。")


def first_present(row: dict[str, Any], keys: tuple[str, ...]) -> str:
    """依序取出第一個存在且非空的欄位。

    參數：
    - `row`：列資料。
    - `keys`：候選欄位名。

    回傳：
    - `str`：找到的值；若全部不存在則為空字串。
    """

    for key in keys:
        value = flatten_text(row.get(key))
        if value:
            return value
    return ""


def build_uda_document_content(row: dict[str, Any]) -> str:
    """從 UDA row 中取出可線性化的文件內容。

    參數：
    - `row`：原始列資料。

    回傳：
    - `str`：文件文字內容。
    """

    return first_present(
        row,
        (
            "document_text",
            "doc_text",
            "context",
            "content",
            "passage",
            "source_text",
            "document_content",
        ),
    )


def prepare_uda_source(*, input_path: Path, workspace_dir: Path, limit_documents: int | None, limit_items: int | None) -> dict[str, Any]:
    """將 UDA 類表格資料轉成中間格式與 source documents。

    參數：
    - `input_path`：UDA JSON/JSONL/CSV 檔。
    - `workspace_dir`：benchmark 工作目錄。
    - `limit_documents`：最多處理幾份文件。
    - `limit_items`：最多輸出幾題。

    回傳：
    - `dict[str, Any]`：prepare 摘要。
    """

    rows = read_table_like_rows(input_path)
    source_dir = workspace_dir / SOURCE_DOCUMENTS_DIRNAME
    documents_by_id: dict[str, dict[str, Any]] = {}
    items: list[dict[str, Any]] = []

    for row_index, row in enumerate(rows):
        document_key = first_present(row, ("document_id", "doc_id", "doc_name", "file_name", "source_file"))
        if not document_key:
            document_key = f"uda-document-{row_index}"
        if limit_documents is not None and document_key not in documents_by_id and len(documents_by_id) >= limit_documents:
            continue

        file_name = slugify_filename(document_key, suffix=".md")
        source_document_path = source_dir / file_name
        document_text = build_uda_document_content(row)
        source_file = first_present(row, ("source_file", "file_path", "source_path"))
        if source_file and Path(source_file).exists():
            suffix = Path(source_file).suffix or ".bin"
            file_name = slugify_filename(document_key, suffix=suffix)
            source_document_path = source_dir / file_name
            if not source_document_path.exists():
                shutil.copy2(Path(source_file), source_document_path)
            content_type = "application/octet-stream"
        else:
            if not document_text:
                document_text = first_present(row, ("answer_context",))
            source_document_path.write_text(normalize_newlines(document_text) + "\n", encoding="utf-8")
            content_type = "text/markdown"

        if document_key not in documents_by_id:
            documents_by_id[document_key] = {
                "dataset": "uda",
                "source_document_id": document_key,
                "file_name": file_name,
                "title": first_present(row, ("title", "doc_title", "document_title")) or document_key,
                "source_path": str(source_document_path.resolve()),
                "content_type": content_type,
                "created_at": now_iso(),
            }

        if limit_items is not None and len(items) >= limit_items:
            continue
        question_text = first_present(row, ("question", "query", "prompt"))
        answer_text = first_present(row, ("answer", "gold_answer", "short_answer", "response"))
        evidence_candidates = [
            first_present(row, ("evidence", "gold_evidence", "supporting_text", "supporting_context", "answer_span")),
        ]
        evidence_candidates = [candidate for candidate in evidence_candidates if candidate]
        if not evidence_candidates and answer_text:
            evidence_candidates = [answer_text]
        item_id = stable_uuid(f"uda::{document_key}::{question_text}::{row_index}")
        items.append(
            {
                "item_id": item_id,
                "dataset": "uda",
                "source_document_id": document_key,
                "file_name": file_name,
                "query_text": question_text,
                "language": first_present(row, ("language",)) or "en",
                "query_type": "fact_lookup",
                "answer_text": answer_text,
                "evidence_texts": evidence_candidates,
                "answer_type": "short_answer" if answer_text else "missing",
                "source_question_index": row_index,
                "source_metadata": {
                    "row_index": row_index,
                },
                "created_at": now_iso(),
            }
        )

    documents = list(documents_by_id.values())
    write_jsonl(workspace_dir / PREPARED_DOCUMENTS_FILE, documents)
    write_jsonl(workspace_dir / PREPARED_ITEMS_FILE, items)
    return {
        "dataset": "uda",
        "document_count": len(documents),
        "item_count": len(items),
        "workspace_dir": str(workspace_dir),
    }


def prepare_source(*, dataset: str, input_path: Path, workspace_dir: Path, limit_documents: int | None, limit_items: int | None) -> dict[str, Any]:
    """依資料集型別執行 source preparation。

    參數：
    - `dataset`：資料集型別。
    - `input_path`：原始輸入路徑。
    - `workspace_dir`：工作目錄。
    - `limit_documents`：最多文件數。
    - `limit_items`：最多題數。

    回傳：
    - `dict[str, Any]`：prepare 摘要。
    """

    ensure_workspace_dir(workspace_dir)
    if dataset == "qasper":
        return prepare_qasper_source(
            input_path=input_path,
            workspace_dir=workspace_dir,
            limit_documents=limit_documents,
            limit_items=limit_items,
        )
    if dataset == "uda":
        return prepare_uda_source(
            input_path=input_path,
            workspace_dir=workspace_dir,
            limit_documents=limit_documents,
            limit_items=limit_items,
        )
    raise ValueError(f"不支援的 dataset：{dataset}")


def contains_layout_dependent_keyword(text: str) -> bool:
    """判斷文字是否高度依賴圖像或版面。

    參數：
    - `text`：待檢查文字。

    回傳：
    - `bool`：若疑似依賴圖像/版面則回傳真值。
    """

    lowered = text.lower()
    return any(keyword in lowered for keyword in ("figure", "image", "diagram", "bbox", "coordinate", "left side", "right side"))


def filter_item(item: dict[str, Any]) -> tuple[bool, str]:
    """套用 curated v1 篩題規則。

    參數：
    - `item`：單題中間格式。

    回傳：
    - `tuple[bool, str]`：是否保留與原因。
    """

    query_text = item.get("query_text", "").strip()
    answer_text = item.get("answer_text", "").strip()
    evidence_texts = [text.strip() for text in item.get("evidence_texts", []) if isinstance(text, str) and text.strip()]
    dataset = item.get("dataset")

    if not query_text:
        return False, "missing_query"
    if item.get("query_type") != "fact_lookup":
        return False, "unsupported_query_type"
    if not evidence_texts and not answer_text:
        return False, "missing_evidence"
    if answer_text and len(answer_text) > MAX_SHORT_ANSWER_CHARS:
        return False, "answer_too_long"
    if any(len(text) > MAX_EVIDENCE_CHARS for text in evidence_texts):
        return False, "evidence_too_long"
    if contains_layout_dependent_keyword(query_text) or any(contains_layout_dependent_keyword(text) for text in evidence_texts):
        return False, "layout_dependent"
    if re.search(r"\b(yes|no)\b", answer_text.lower()) and len(answer_text) <= 3:
        return False, "yes_no_answer"
    if dataset == "qasper" and not evidence_texts:
        return False, "qasper_requires_evidence"
    if dataset == "uda" and not evidence_texts and not answer_text:
        return False, "uda_requires_short_answer"
    return True, "kept"


def filter_items(*, workspace_dir: Path) -> dict[str, Any]:
    """執行 curated v1 篩題並輸出報表。

    參數：
    - `workspace_dir`：工作目錄。

    回傳：
    - `dict[str, Any]`：篩題摘要。
    """

    prepared_items = read_jsonl(workspace_dir / PREPARED_ITEMS_FILE)
    kept_items: list[dict[str, Any]] = []
    reason_counter: Counter[str] = Counter()

    for item in prepared_items:
        keep, reason = filter_item(item)
        item["filter_reason"] = reason
        reason_counter[reason] += 1
        if keep:
            kept_items.append(item)

    write_jsonl(workspace_dir / FILTERED_ITEMS_FILE, kept_items)
    report = {
        "prepared_item_count": len(prepared_items),
        "kept_item_count": len(kept_items),
        "drop_item_count": len(prepared_items) - len(kept_items),
        "reason_counts": dict(sorted(reason_counter.items())),
        "generated_at": now_iso(),
    }
    write_json(workspace_dir / FILTER_REPORT_FILE, report)
    return report


def normalize_with_mapping(text: str) -> NormalizedText:
    """將文字正規化並保留 normalized index 到原始 offset 的映射。

    參數：
    - `text`：原始全文或 evidence。

    回傳：
    - `NormalizedText`：正規化後資料。
    """

    normalized_chars: list[str] = []
    mapping: list[int] = []
    previous_was_space = True
    index = 0
    while index < len(text):
        char = text[index]
        if char == "\u00ad":
            index += 1
            continue
        if char == "-" and index + 1 < len(text) and text[index + 1] in {"\n", "\r"}:
            index += 1
            while index < len(text) and text[index] in {"\n", "\r", " "}:
                index += 1
            previous_was_space = False
            continue
        expanded = unicodedata.normalize("NFKC", char)
        for normalized_char in expanded:
            if normalized_char.isspace():
                if not previous_was_space and normalized_chars:
                    normalized_chars.append(" ")
                    mapping.append(index)
                previous_was_space = True
                continue
            normalized_chars.append(normalized_char.lower())
            mapping.append(index)
            previous_was_space = False
        index += 1
    return NormalizedText(normalized_text="".join(normalized_chars).strip(), normalized_to_original=mapping)


def find_all_exact_matches(document: NormalizedText, evidence: NormalizedText) -> list[tuple[int, int]]:
    """在正規化後全文中尋找 evidence 的所有精確命中。

    參數：
    - `document`：文件全文。
    - `evidence`：待對齊 evidence。

    回傳：
    - `list[tuple[int, int]]`：原始 offset 範圍列表。
    """

    if not evidence.normalized_text:
        return []
    hits: list[tuple[int, int]] = []
    start_at = 0
    while True:
        found_index = document.normalized_text.find(evidence.normalized_text, start_at)
        if found_index < 0:
            break
        end_index = found_index + len(evidence.normalized_text) - 1
        if end_index >= len(document.normalized_to_original):
            break
        original_start = document.normalized_to_original[found_index]
        original_end = document.normalized_to_original[end_index] + 1
        hits.append((original_start, original_end))
        start_at = found_index + 1
    deduped: list[tuple[int, int]] = []
    for hit in hits:
        if hit not in deduped:
            deduped.append(hit)
    return deduped


def tokenize(text: str) -> set[str]:
    """將文字切成粗粒度 token 集合。

    參數：
    - `text`：輸入文字。

    回傳：
    - `set[str]`：token 集合。
    """

    return {token for token in re.findall(r"[A-Za-z0-9\u4e00-\u9fff]+", text.lower()) if token}


def overlap_score(query_signal: str, candidate_text: str) -> float:
    """計算 query/answer 與候選片段的 token overlap。

    參數：
    - `query_signal`：問題與答案組成的訊號。
    - `candidate_text`：候選片段。

    回傳：
    - `float`：0 到 1 的 overlap 分數。
    """

    left = tokenize(query_signal)
    right = tokenize(candidate_text)
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def disambiguate_exact_matches(*, display_text: str, matches: list[tuple[int, int]], query_signal: str) -> tuple[tuple[int, int] | None, list[dict[str, Any]]]:
    """對多重 exact matches 做 context disambiguation。

    參數：
    - `display_text`：原始全文。
    - `matches`：所有 exact match 範圍。
    - `query_signal`：問題與答案訊號。

    回傳：
    - `tuple[tuple[int, int] | None, list[dict[str, Any]]]`：最佳命中與評分細節。
    """

    scored: list[dict[str, Any]] = []
    for start_offset, end_offset in matches:
        context_start = max(0, start_offset - 120)
        context_end = min(len(display_text), end_offset + 120)
        context_text = display_text[context_start:context_end]
        score = overlap_score(query_signal, context_text)
        scored.append(
            {
                "start_offset": start_offset,
                "end_offset": end_offset,
                "score": round(score, 6),
                "excerpt": display_text[start_offset:end_offset],
            }
        )
    scored.sort(key=lambda row: (-row["score"], row["start_offset"]))
    if len(scored) == 1:
        return (scored[0]["start_offset"], scored[0]["end_offset"]), scored
    if scored and len(scored) > 1 and scored[0]["score"] > scored[1]["score"]:
        return (scored[0]["start_offset"], scored[0]["end_offset"]), scored
    return None, scored


def iter_candidate_segments(display_text: str, *, window_size: int) -> list[tuple[int, int, str]]:
    """依段落與句子切出 fuzzy 對齊候選片段。

    參數：
    - `display_text`：全文。
    - `window_size`：預估 evidence 長度。

    回傳：
    - `list[tuple[int, int, str]]`：原始 offset 與候選文字。
    """

    segments: list[tuple[int, int, str]] = []
    for match in re.finditer(r"[^\n]+", display_text):
        segment = match.group(0).strip()
        if not segment:
            continue
        start_offset, end_offset = match.start(), match.end()
        segments.append((start_offset, end_offset, segment))
    if segments:
        return segments
    if display_text:
        return [(0, min(len(display_text), window_size), display_text[:window_size])]
    return []


def fuzzy_match_evidence(*, display_text: str, evidence_text: str, query_signal: str) -> dict[str, Any] | None:
    """用句段級 fuzzy 規則搜尋 evidence。

    參數：
    - `display_text`：文件全文。
    - `evidence_text`：待對齊 evidence。
    - `query_signal`：問題與答案訊號。

    回傳：
    - `dict[str, Any] | None`：最佳候選；若信心不足則回傳空值。
    """

    evidence_normalized = normalize_with_mapping(evidence_text).normalized_text
    if not evidence_normalized:
        return None
    candidates: list[dict[str, Any]] = []
    for start_offset, end_offset, segment in iter_candidate_segments(display_text, window_size=max(len(evidence_text) * 2, 80)):
        normalized_segment = normalize_with_mapping(segment).normalized_text
        if not normalized_segment:
            continue
        ratio = SequenceMatcher(None, evidence_normalized, normalized_segment).ratio()
        score = (0.7 * ratio) + (0.3 * overlap_score(query_signal, segment))
        candidates.append(
            {
                "start_offset": start_offset,
                "end_offset": end_offset,
                "score": round(score, 6),
                "excerpt": segment,
            }
        )
    candidates.sort(key=lambda row: (-row["score"], row["start_offset"]))
    if not candidates:
        return None
    top = candidates[0]
    second_score = candidates[1]["score"] if len(candidates) > 1 else 0.0
    if top["score"] >= FUZZY_ACCEPT_SCORE and (top["score"] - second_score) >= FUZZY_ACCEPT_MARGIN:
        return top
    return None


def load_ready_documents_for_area(*, area_id: str) -> dict[str, Document]:
    """載入指定 area 內所有 ready 文件。

    參數：
    - `area_id`：area id。

    回傳：
    - `dict[str, Document]`：以 file_name 為 key 的 ready 文件。
    """

    settings = get_settings()
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        documents = session.scalars(
            select(Document).where(
                Document.area_id == area_id,
                Document.status == DocumentStatus.ready,
            )
        ).all()
    return {document.file_name: document for document in documents}


def align_single_item(*, item: dict[str, Any], display_text: str) -> dict[str, Any]:
    """將單題 evidence 對齊到 display_text offsets。

    參數：
    - `item`：篩題後單題資料。
    - `display_text`：系統正式全文。

    回傳：
    - `dict[str, Any]`：對齊結果。
    """

    document_normalized = normalize_with_mapping(display_text)
    query_signal = " ".join(part for part in (item.get("query_text", ""), item.get("answer_text", "")) if part).strip()
    accepted_spans: list[dict[str, Any]] = []
    review_candidates: list[dict[str, Any]] = []
    rejected_evidences: list[dict[str, Any]] = []

    evidence_texts = [text for text in item.get("evidence_texts", []) if isinstance(text, str) and text.strip()]
    for evidence_text in evidence_texts:
        evidence_normalized = normalize_with_mapping(evidence_text)
        exact_matches = find_all_exact_matches(document_normalized, evidence_normalized)
        if len(exact_matches) == 1:
            accepted_spans.append(
                {
                    "start_offset": exact_matches[0][0],
                    "end_offset": exact_matches[0][1],
                    "match_type": "exact_unique",
                    "evidence_text": evidence_text,
                }
            )
            continue
        if len(exact_matches) > 1:
            chosen, scored_matches = disambiguate_exact_matches(
                display_text=display_text,
                matches=exact_matches,
                query_signal=query_signal,
            )
            if chosen is not None:
                accepted_spans.append(
                    {
                        "start_offset": chosen[0],
                        "end_offset": chosen[1],
                        "match_type": "exact_disambiguated",
                        "evidence_text": evidence_text,
                    }
                )
            else:
                review_candidates.append(
                    {
                        "evidence_text": evidence_text,
                        "reason": "multiple_exact_matches",
                        "candidates": scored_matches,
                    }
                )
            continue
        fuzzy_candidate = fuzzy_match_evidence(
            display_text=display_text,
            evidence_text=evidence_text,
            query_signal=query_signal,
        )
        if fuzzy_candidate is not None:
            accepted_spans.append(
                {
                    "start_offset": fuzzy_candidate["start_offset"],
                    "end_offset": fuzzy_candidate["end_offset"],
                    "match_type": "fuzzy",
                    "score": fuzzy_candidate["score"],
                    "evidence_text": evidence_text,
                }
            )
        else:
            rejected_evidences.append(
                {
                    "evidence_text": evidence_text,
                    "reason": "no_confident_match",
                }
            )

    deduped_spans: list[dict[str, Any]] = []
    seen_offsets: set[tuple[int, int]] = set()
    for span in accepted_spans:
        span_key = (span["start_offset"], span["end_offset"])
        if span_key in seen_offsets:
            continue
        seen_offsets.add(span_key)
        deduped_spans.append(span)

    status = "auto_matched"
    if not deduped_spans and review_candidates:
        status = "needs_review"
    elif not deduped_spans and rejected_evidences:
        status = "rejected"
    elif deduped_spans and review_candidates:
        status = "auto_matched"

    return {
        "item_id": item["item_id"],
        "dataset": item["dataset"],
        "file_name": item["file_name"],
        "query_text": item["query_text"],
        "answer_text": item.get("answer_text"),
        "language": item["language"],
        "query_type": item["query_type"],
        "status": status,
        "accepted_spans": deduped_spans,
        "review_candidates": review_candidates,
        "rejected_evidences": rejected_evidences,
        "source_metadata": item.get("source_metadata", {}),
        "generated_at": now_iso(),
    }


def align_spans(*, workspace_dir: Path, area_id: str) -> dict[str, Any]:
    """對齊所有篩題後 evidence 到指定 area 的 ready 文件。

    參數：
    - `workspace_dir`：工作目錄。
    - `area_id`：目標 area id。

    回傳：
    - `dict[str, Any]`：對齊摘要。
    """

    filtered_items = read_jsonl(workspace_dir / FILTERED_ITEMS_FILE)
    ready_documents = load_ready_documents_for_area(area_id=area_id)
    results: list[dict[str, Any]] = []
    review_queue: list[dict[str, Any]] = []
    status_counter: Counter[str] = Counter()

    for item in filtered_items:
        document = ready_documents.get(item["file_name"])
        if document is None:
            result = {
                "item_id": item["item_id"],
                "dataset": item["dataset"],
                "file_name": item["file_name"],
                "query_text": item["query_text"],
                "answer_text": item.get("answer_text"),
                "language": item["language"],
                "query_type": item["query_type"],
                "status": "rejected",
                "accepted_spans": [],
                "review_candidates": [],
                "rejected_evidences": [{"reason": "missing_ready_document", "evidence_text": ""}],
                "source_metadata": item.get("source_metadata", {}),
                "generated_at": now_iso(),
            }
        else:
            result = align_single_item(item=item, display_text=document.display_text or "")
        results.append(result)
        status_counter[result["status"]] += 1
        if result["status"] in {"needs_review", "rejected"}:
            review_queue.append(result)

    write_jsonl(workspace_dir / ALIGNMENT_CANDIDATES_FILE, results)
    write_jsonl(workspace_dir / ALIGNMENT_REVIEW_QUEUE_FILE, review_queue)
    report = {
        "area_id": area_id,
        "item_count": len(filtered_items),
        "status_counts": dict(sorted(status_counter.items())),
        "auto_matched_ratio": round(status_counter.get("auto_matched", 0) / len(filtered_items), 6) if filtered_items else 0.0,
        "generated_at": now_iso(),
    }
    write_json(workspace_dir / ALIGNMENT_REPORT_FILE, report)
    return report


def read_review_overrides(workspace_dir: Path) -> dict[str, dict[str, Any]]:
    """讀取 reviewer 手動覆核結果。

    參數：
    - `workspace_dir`：工作目錄。

    回傳：
    - `dict[str, dict[str, Any]]`：以 item id 為 key 的 override 映射。
    """

    path = workspace_dir / REVIEW_OVERRIDES_FILE
    if not path.exists():
        return {}
    rows = read_jsonl(path)
    return {row["item_id"]: row for row in rows if row.get("item_id")}


def build_snapshot(*, workspace_dir: Path, output_dir: Path, benchmark_name: str, include_review_items: bool) -> dict[str, Any]:
    """以 auto-matched 與 reviewed-approved 題目建立 snapshot。

    參數：
    - `workspace_dir`：工作目錄。
    - `output_dir`：snapshot 輸出目錄。
    - `benchmark_name`：snapshot 名稱。
    - `include_review_items`：是否保留尚未有 spans 的 review queue 題目。

    回傳：
    - `dict[str, Any]`：snapshot 摘要。
    """

    output_dir.mkdir(parents=True, exist_ok=True)
    prepared_documents = read_jsonl(workspace_dir / PREPARED_DOCUMENTS_FILE)
    filtered_items = {row["item_id"]: row for row in read_jsonl(workspace_dir / FILTERED_ITEMS_FILE)}
    alignment_rows = read_jsonl(workspace_dir / ALIGNMENT_CANDIDATES_FILE)
    overrides = read_review_overrides(workspace_dir)

    questions: list[dict[str, Any]] = []
    spans: list[dict[str, Any]] = []
    included_document_names: set[str] = set()
    accepted_item_count = 0
    dataset_counter: Counter[str] = Counter()

    for alignment_row in alignment_rows:
        item = filtered_items[alignment_row["item_id"]]
        accepted_spans = list(alignment_row.get("accepted_spans", []))
        override = overrides.get(item["item_id"])
        if override:
            decision = override.get("decision")
            if decision == "approved":
                accepted_spans = override.get("spans", [])
            elif decision == "rejected":
                accepted_spans = []

        include_item = bool(accepted_spans)
        if not include_item and include_review_items and alignment_row["status"] == "needs_review":
            include_item = True
        if not include_item:
            continue

        questions.append(
            {
                "question_id": item["item_id"],
                "dataset_id": stable_uuid(f"benchmark::{benchmark_name}"),
                "query_type": "fact_lookup",
                "language": item["language"],
                "question": item["query_text"],
                "notes": json.dumps(
                    {
                        "dataset": item["dataset"],
                        "source_document_id": item["source_document_id"],
                        "answer_text": item.get("answer_text"),
                    },
                    ensure_ascii=False,
                ),
                "created_at": now_iso(),
                "updated_at": now_iso(),
            }
        )
        dataset_counter[item["dataset"]] += 1
        for span_index, span in enumerate(accepted_spans):
            spans.append(
                {
                    "span_id": stable_uuid(f"span::{item['item_id']}::{span['start_offset']}::{span['end_offset']}::{span_index}"),
                    "question_id": item["item_id"],
                    "file_name": item["file_name"],
                    "start_offset": int(span["start_offset"]),
                    "end_offset": int(span["end_offset"]),
                    "relevance_grade": 3,
                    "is_retrieval_miss": False,
                }
            )
            included_document_names.add(item["file_name"])
        if accepted_spans:
            accepted_item_count += 1

    documents = [
        {
            "document_id": stable_uuid(f"document::{row['file_name']}"),
            "file_name": row["file_name"],
            "content_type": row.get("content_type", "application/octet-stream"),
            "file_size": Path(row["source_path"]).stat().st_size if Path(row["source_path"]).exists() else 0,
            "status": "ready",
            "created_at": row.get("created_at", now_iso()),
            "area_id": None,
        }
        for row in prepared_documents
        if row["file_name"] in included_document_names or include_review_items
    ]

    manifest = {
        "benchmark_name": benchmark_name,
        "dataset": {
            "dataset_id": stable_uuid(f"benchmark::{benchmark_name}"),
            "query_type": "fact_lookup",
            "generated_at": now_iso(),
        },
        "source_dataset_breakdown": dict(sorted(dataset_counter.items())),
        "snapshot_files": list(SNAPSHOT_REQUIRED_FILES) + [
            ALIGNMENT_CANDIDATES_FILE,
            ALIGNMENT_REVIEW_QUEUE_FILE,
            FILTER_REPORT_FILE,
        ],
        "stats": {
            "question_count": len(questions),
            "question_with_gold_span_count": accepted_item_count,
            "span_count": len(spans),
            "document_count": len(documents),
        },
    }

    write_jsonl(output_dir / "documents.jsonl", documents)
    write_jsonl(output_dir / "questions.jsonl", questions)
    write_jsonl(output_dir / "gold_spans.jsonl", spans)
    write_json(output_dir / "manifest.json", manifest)
    for auxiliary_name in (ALIGNMENT_CANDIDATES_FILE, ALIGNMENT_REVIEW_QUEUE_FILE, FILTER_REPORT_FILE):
        source_path = workspace_dir / auxiliary_name
        if source_path.exists():
            shutil.copy2(source_path, output_dir / auxiliary_name)

    return {
        "benchmark_name": benchmark_name,
        "dataset_id": manifest["dataset"]["dataset_id"],
        "question_count": len(questions),
        "question_with_gold_span_count": accepted_item_count,
        "span_count": len(spans),
        "document_count": len(documents),
        "include_review_items": include_review_items,
    }


def build_report(*, workspace_dir: Path) -> dict[str, Any]:
    """輸出目前 workspace 的整體 curation 狀態。

    參數：
    - `workspace_dir`：工作目錄。

    回傳：
    - `dict[str, Any]`：整體摘要。
    """

    prepared_items = read_jsonl(workspace_dir / PREPARED_ITEMS_FILE) if (workspace_dir / PREPARED_ITEMS_FILE).exists() else []
    filtered_items = read_jsonl(workspace_dir / FILTERED_ITEMS_FILE) if (workspace_dir / FILTERED_ITEMS_FILE).exists() else []
    alignment_rows = read_jsonl(workspace_dir / ALIGNMENT_CANDIDATES_FILE) if (workspace_dir / ALIGNMENT_CANDIDATES_FILE).exists() else []
    overrides = read_review_overrides(workspace_dir)

    status_counts = Counter(row.get("status", "unknown") for row in alignment_rows)
    approved_override_count = sum(1 for row in overrides.values() if row.get("decision") == "approved")
    report = {
        "prepared_item_count": len(prepared_items),
        "filtered_item_count": len(filtered_items),
        "alignment_item_count": len(alignment_rows),
        "status_counts": dict(sorted(status_counts.items())),
        "review_override_count": len(overrides),
        "approved_override_count": approved_override_count,
        "auto_match_ratio": round(status_counts.get("auto_matched", 0) / len(filtered_items), 6) if filtered_items else 0.0,
        "generated_at": now_iso(),
    }
    return report


def main() -> None:
    """CLI 主入口。

    參數：
    - 無。

    回傳：
    - `None`：將執行結果輸出到 stdout。
    """

    parser = build_parser()
    args = parser.parse_args()
    if args.command == "prepare-source":
        summary = prepare_source(
            dataset=args.dataset,
            input_path=Path(args.input_path).resolve(),
            workspace_dir=Path(args.workspace_dir).resolve(),
            limit_documents=args.limit_documents,
            limit_items=args.limit_items,
        )
    elif args.command == "filter-items":
        summary = filter_items(workspace_dir=Path(args.workspace_dir).resolve())
    elif args.command == "align-spans":
        summary = align_spans(
            workspace_dir=Path(args.workspace_dir).resolve(),
            area_id=args.area_id,
        )
    elif args.command == "build-snapshot":
        summary = build_snapshot(
            workspace_dir=Path(args.workspace_dir).resolve(),
            output_dir=Path(args.output_dir).resolve(),
            benchmark_name=args.benchmark_name,
            include_review_items=args.include_review_items,
        )
    elif args.command == "report":
        summary = build_report(workspace_dir=Path(args.workspace_dir).resolve())
    else:
        raise ValueError(f"不支援的指令：{args.command}")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
