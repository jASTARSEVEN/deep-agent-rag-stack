"""Worker 使用的 document synopsis 生成與輸入壓縮。"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from worker.core.settings import WorkerSettings

if TYPE_CHECKING:
    from worker.db import DocumentChunk


# CJK 字元偵測，用來決定 synopsis 輸出語言。
_CJK_PATTERN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
# 壓縮多餘空白，避免 synopsis prompt 被 parser 噪音放大。
_WHITESPACE_PATTERN = re.compile(r"\s+")


class DocumentSynopsisProvider(ABC):
    """Document synopsis provider 抽象介面。"""

    @abstractmethod
    def generate_synopsis(
        self,
        *,
        file_name: str,
        source_text: str,
        output_language: str,
        max_output_chars: int,
    ) -> str:
        """根據受控來源文字產生 document synopsis。

        參數：
        - `file_name`：目前文件檔名。
        - `source_text`：已做全 parent coverage 壓縮的輸入文字。
        - `output_language`：期望輸出語言，正式支援 `zh-TW` 與 `en`。
        - `max_output_chars`：允許的 synopsis 最大字元數。

        回傳：
        - `str`：可持久化的 document synopsis 文字。
        """


class DeterministicDocumentSynopsisProvider(DocumentSynopsisProvider):
    """供測試與離線環境使用的穩定 synopsis provider。"""

    def generate_synopsis(
        self,
        *,
        file_name: str,
        source_text: str,
        output_language: str,
        max_output_chars: int,
    ) -> str:
        """以規則式方式建立固定格式 synopsis。

        參數：
        - `file_name`：目前文件檔名。
        - `source_text`：已做全 parent coverage 壓縮的輸入文字。
        - `output_language`：期望輸出語言，正式支援 `zh-TW` 與 `en`。
        - `max_output_chars`：允許的 synopsis 最大字元數。

        回傳：
        - `str`：固定格式且長度受控的 synopsis。
        """

        headings = _extract_source_lines(source_text=source_text, prefix="Heading:")
        table_points = _extract_source_lines(source_text=source_text, prefix="Table/Structure:")
        body_points = _extract_source_lines(source_text=source_text, prefix="Excerpt:")

        if output_language == "zh-TW":
            synopsis = "\n".join(
                [
                    f"主題：{_truncate_text(_normalize_inline_text(file_name), 80)}",
                    "重要章節：" + ("；".join(headings[:4]) if headings else "未提供明確章節標題。"),
                    "主要結論：" + (body_points[0] if body_points else "未提供足夠內容。"),
                    "表格與結構重點：" + ("；".join(table_points[:3]) if table_points else "未偵測到明確表格重點。"),
                ]
            )
        else:
            synopsis = "\n".join(
                [
                    f"Topic: {_truncate_text(_normalize_inline_text(file_name), 80)}",
                    "Key sections: " + ("; ".join(headings[:4]) if headings else "No explicit section headings were detected."),
                    "Main conclusions: " + (body_points[0] if body_points else "No sufficient body content was detected."),
                    "Tables and structure: " + ("; ".join(table_points[:3]) if table_points else "No explicit table highlights were detected."),
                ]
            )
        return _finalize_synopsis_text(synopsis=synopsis, max_output_chars=max_output_chars)


class OpenAIDocumentSynopsisProvider(DocumentSynopsisProvider):
    """使用 OpenAI Chat Completions 生成 document synopsis。"""

    def __init__(self, *, api_key: str, model: str) -> None:
        """初始化 OpenAI synopsis provider。

        參數：
        - `api_key`：OpenAI API key。
        - `model`：要使用的 chat model 名稱。

        回傳：
        - `None`：此建構子只負責建立 client 與保存設定。
        """

        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - 依賴缺失時於執行期明確失敗。
            raise RuntimeError("缺少 openai 套件，無法建立 document synopsis provider。") from exc

        self._client = OpenAI(api_key=api_key)
        self._model = model

    def generate_synopsis(
        self,
        *,
        file_name: str,
        source_text: str,
        output_language: str,
        max_output_chars: int,
    ) -> str:
        """呼叫 OpenAI 產生長度受控的 document synopsis。

        參數：
        - `file_name`：目前文件檔名。
        - `source_text`：已做全 parent coverage 壓縮的輸入文字。
        - `output_language`：期望輸出語言，正式支援 `zh-TW` 與 `en`。
        - `max_output_chars`：允許的 synopsis 最大字元數。

        回傳：
        - `str`：經驗證與長度控制後的 synopsis 文字。
        """

        language_label = "台灣繁體中文" if output_language == "zh-TW" else "English"
        system_prompt = (
            "You generate document-level synopses for retrieval. "
            "Keep the output factual, compact, and grounded only in the provided source summary."
        )
        user_prompt = (
            f"File name: {file_name}\n"
            f"Output language: {language_label}\n"
            f"Maximum characters: {max_output_chars}\n\n"
            "Write a document synopsis with exactly these sections in the requested language:\n"
            "1. Topic\n"
            "2. Key sections\n"
            "3. Main conclusions\n"
            "4. Tables and structure highlights\n\n"
            "Rules:\n"
            "- Stay within the maximum characters.\n"
            "- Use plain text only.\n"
            "- Do not invent facts not present in the source.\n"
            "- If the source is incomplete, state that conservatively.\n\n"
            "Compressed source:\n"
            f"{source_text}"
        )
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                temperature=0.1,
                max_completion_tokens=max(256, min(1200, max_output_chars)),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
        except Exception as exc:  # pragma: no cover - network/provider failure path.
            raise ValueError(f"document synopsis 生成失敗：{exc}") from exc

        content = response.choices[0].message.content if response.choices else None
        if not isinstance(content, str) or not content.strip():
            raise ValueError("document synopsis 生成失敗：LLM 未回傳有效內容。")
        return _finalize_synopsis_text(synopsis=content, max_output_chars=max_output_chars)


def build_document_synopsis_provider(settings: WorkerSettings) -> DocumentSynopsisProvider:
    """依照設定建立 document synopsis provider。

    參數：
    - `settings`：worker 執行期設定。

    回傳：
    - `DocumentSynopsisProvider`：對應的 synopsis provider。
    """

    provider = settings.document_synopsis_provider.strip().lower()
    if provider == "deterministic":
        return DeterministicDocumentSynopsisProvider()
    if provider == "openai":
        if not settings.openai_api_key:
            raise ValueError("使用 OpenAI document synopsis 前必須提供 OPENAI_API_KEY。")
        return OpenAIDocumentSynopsisProvider(
            api_key=settings.openai_api_key,
            model=settings.document_synopsis_model,
        )
    raise ValueError(f"不支援的 document synopsis provider：{settings.document_synopsis_provider}")


def build_document_synopsis_source_text(
    *,
    file_name: str,
    parent_chunks: list[DocumentChunk],
    max_input_chars: int,
) -> str:
    """以全 parent coverage 方式建立 synopsis 輸入文字。

    參數：
    - `file_name`：目前文件檔名。
    - `parent_chunks`：依文件順序排列的 parent chunks。
    - `max_input_chars`：允許的最大輸入字元數。

    回傳：
    - `str`：可送入 synopsis provider 的受控來源文字。
    """

    if not parent_chunks:
        raise ValueError("document synopsis 來源不可缺少 parent chunks。")

    normalized_file_name = _normalize_inline_text(file_name)
    headings = [chunk.heading for chunk in parent_chunks]
    has_tables = any(str(chunk.structure_kind.value) == "table" for chunk in parent_chunks)
    for heading_chars, content_chars in ((72, 200), (48, 120), (32, 72), (20, 40)):
        sections: list[str] = [
            f"File: {normalized_file_name}",
            f"Parent count: {len(parent_chunks)}",
            f"Contains table parents: {'yes' if has_tables else 'no'}",
        ]
        for index, chunk in enumerate(parent_chunks, start=1):
            structure_label = "table" if str(chunk.structure_kind.value) == "table" else "text"
            heading = _truncate_text(_normalize_inline_text(chunk.heading or "(no heading)"), heading_chars)
            content = _truncate_text(_normalize_inline_text(chunk.content), content_chars)
            sections.append(
                "\n".join(
                    [
                        f"[{index}] Type: {structure_label}",
                        f"Heading: {heading}",
                        f"Excerpt: {content}",
                        f"Table/Structure: {'Contains table-like structure.' if structure_label == 'table' else 'Primarily narrative text.'}",
                    ]
                )
            )
        candidate = "\n\n".join(sections)
        if len(candidate) <= max_input_chars:
            return candidate

    return _truncate_text(candidate, max_input_chars)


def detect_synopsis_language(*, parent_chunks: list[DocumentChunk], file_name: str) -> str:
    """依文件內容與檔名偵測 synopsis 預設輸出語言。

    參數：
    - `parent_chunks`：依文件順序排列的 parent chunks。
    - `file_name`：目前文件檔名。

    回傳：
    - `str`：`zh-TW` 或 `en`。
    """

    combined_text = "\n".join(filter(None, [file_name, *[(chunk.heading or "") + "\n" + chunk.content for chunk in parent_chunks[:6]]]))
    return "zh-TW" if _CJK_PATTERN.search(combined_text) else "en"


def _extract_source_lines(*, source_text: str, prefix: str) -> list[str]:
    """從 synopsis 壓縮輸入中抽出指定前綴的行。"""

    lines: list[str] = []
    for raw_line in source_text.splitlines():
        if not raw_line.startswith(prefix):
            continue
        line = raw_line.removeprefix(prefix).strip()
        if line:
            lines.append(line)
    return lines


def _normalize_inline_text(value: str) -> str:
    """將文字壓縮為適合單行 synopsis 的格式。"""

    return _WHITESPACE_PATTERN.sub(" ", value).strip()


def _truncate_text(value: str, max_chars: int) -> str:
    """以字元數裁切文字，避免超出受控 budget。"""

    if max_chars <= 0:
        return ""
    if len(value) <= max_chars:
        return value
    if max_chars <= 1:
        return value[:max_chars]
    return value[: max_chars - 1].rstrip() + "…"


def _finalize_synopsis_text(*, synopsis: str, max_output_chars: int) -> str:
    """清理並驗證 synopsis 最終文字。"""

    normalized_synopsis = synopsis.strip()
    if not normalized_synopsis:
        raise ValueError("document synopsis 生成失敗：輸出為空白。")
    return _truncate_text(normalized_synopsis, max_output_chars)
