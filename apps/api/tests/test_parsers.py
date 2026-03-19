"""API inline ingest parser 測試。"""

from __future__ import annotations

from app.services.parsers import _parse_markdown_text, parse_document


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


def test_parse_document_pdf_markdown_relaxes_short_table_delimiter_cells() -> None:
    """PDF Markdown 的短 delimiter cell 仍應被辨識並正規化為 canonical table。"""

    parsed = _parse_markdown_text(
        text=(
            "版次：114 年 9 月版    66    修訂日期：114.9.1\n\n"
            "| 1    | 集體彙繳件保費折扣                           | ○         |   |\n"
            "| ---- | ----------------------------------- | --------- | - |\n"
            "| 2    | 「個人保險契約審閱期間」規定                      | ○         |   |\n"
            "| 共通規定 | 4                                   | 「投保聲明書」規定 | ○ |\n"
        ),
        source_format="pdf",
    )

    assert len(parsed.blocks) == 2
    assert parsed.blocks[0].block_kind == "text"
    assert parsed.blocks[1].block_kind == "table"
    assert parsed.blocks[1].content == "\n".join(
        [
            "| 1 | 集體彙繳件保費折扣 | ○ |  |",
            "| --- | --- | --- | --- |",
            "| 2 | 「個人保險契約審閱期間」規定 | ○ |  |",
            "| 共通規定 | 4 | 「投保聲明書」規定 | ○ |",
        ]
    )
