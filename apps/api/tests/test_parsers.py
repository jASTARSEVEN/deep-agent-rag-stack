"""API inline ingest parser 測試。"""

from __future__ import annotations

from app.services.parsers import parse_document


def test_parse_document_normalizes_markdown_table_spacing_and_delimiter() -> None:
    """Markdown table 應在 inline ingest parse 階段壓縮多餘空白與 delimiter 長度。"""

    parsed = parse_document(
        file_name="table.md",
        payload=(
            "# 規範\n\n"
            "| 當事人實際年齡          | 行為能力   | 簽名規範        |\n"
            "| ---------------- | ------ | ----------- |\n"
            "| 未滿 7 足歲          | 無行為能力  | 法定代理人代當事人簽名 |\n"
            "| 未成年者             |        | +法定代理人本人簽名  |\n"
        ).encode("utf-8"),
    )

    assert len(parsed.blocks) == 1
    assert parsed.blocks[0].block_kind == "table"
    assert parsed.blocks[0].content == "\n".join(
        [
            "| 當事人實際年齡 | 行為能力 | 簽名規範 |",
            "| --- | --- | --- |",
            "| 未滿 7 足歲 | 無行為能力 | 法定代理人代當事人簽名 |",
            "| 未成年者 |  | +法定代理人本人簽名 |",
        ]
    )
