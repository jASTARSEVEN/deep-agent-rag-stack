"""Worker parser provider 測試。"""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
import sys

from worker.parsers import PdfParserConfig, parse_document


# 可被 PyPDFLoader 正常擷取文字的最小 PDF 測試樣本。
MINIMAL_TEXT_PDF = b"""%PDF-1.1
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 144] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>
endobj
4 0 obj
<< /Length 73 >>
stream
BT
/F1 18 Tf
50 100 Td
(Deep Agent PDF local parser sample) Tj
ET
endstream
endobj
5 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
xref
0 6
0000000000 65535 f 
0000000010 00000 n 
0000000063 00000 n 
0000000122 00000 n 
0000000248 00000 n 
0000000371 00000 n 
trailer
<< /Root 1 0 R /Size 6 >>
startxref
441
%%EOF
"""


def test_parse_document_supports_local_pdf_loader() -> None:
    """local PDF provider 應能以 LangChain loader 擷取文字。"""

    parsed = parse_document(
        file_name="sample.pdf",
        payload=MINIMAL_TEXT_PDF,
        pdf_config=PdfParserConfig(provider="local"),
    )

    assert parsed.source_format == "pdf"
    assert len(parsed.blocks) == 1
    assert parsed.blocks[0].block_kind == "text"
    assert "Deep Agent PDF local parser sample" in parsed.blocks[0].content


def test_parse_document_uses_llamaparse_markdown_and_forwards_flags(monkeypatch) -> None:
    """llamaparse provider 應正確轉發設定，並沿用既有 Markdown parser。"""

    captured_kwargs: dict[str, object] = {}

    @dataclass
    class _FakeDocument:
        """模擬 LlamaParse 回傳文件。"""

        text: str

    class FakeLlamaParse:
        """模擬 LlamaParse client，記錄建構參數。"""

        def __init__(self, **kwargs) -> None:
            captured_kwargs.update(kwargs)

        def load_data(self, _path: str) -> list[_FakeDocument]:
            return [_FakeDocument("# Heading\n\n| Name | Score |\n| --- | --- |\n| Alice | 95 |")]

    monkeypatch.setitem(sys.modules, "llama_parse", SimpleNamespace(LlamaParse=FakeLlamaParse))

    parsed = parse_document(
        file_name="sample.pdf",
        payload=MINIMAL_TEXT_PDF,
        pdf_config=PdfParserConfig(
            provider="llamaparse",
            llamaparse_api_key="test-key",
            llamaparse_do_not_cache=True,
            llamaparse_merge_continued_tables=True,
        ),
    )

    assert captured_kwargs["api_key"] == "test-key"
    assert captured_kwargs["result_type"] == "markdown"
    assert captured_kwargs["do_not_cache"] is True
    assert captured_kwargs["merge_tables_across_pages_in_markdown"] is True
    assert [block.block_kind for block in parsed.blocks] == ["table"]
    assert parsed.blocks[0].heading == "Heading"
    assert "| Alice | 95 |" in parsed.blocks[0].content


def test_parse_document_cleans_llamaparse_page_noise(monkeypatch) -> None:
    """llamaparse Markdown 中的常見頁碼與分隔符應在 parse 前被清理。"""

    @dataclass
    class _FakeDocument:
        """模擬 LlamaParse 回傳文件。"""

        text: str

    class FakeLlamaParse:
        """回傳含頁碼噪音的 LlamaParse client。"""

        def __init__(self, **kwargs) -> None:
            del kwargs

        def load_data(self, _path: str) -> list[_FakeDocument]:
            return [_FakeDocument("Page 1 of 2\n\n# Heading\n\n---\n\nUseful paragraph\n\nPage 2")]

    monkeypatch.setitem(sys.modules, "llama_parse", SimpleNamespace(LlamaParse=FakeLlamaParse))

    parsed = parse_document(
        file_name="sample.pdf",
        payload=MINIMAL_TEXT_PDF,
        pdf_config=PdfParserConfig(provider="llamaparse", llamaparse_api_key="test-key"),
    )

    assert len(parsed.blocks) == 1
    assert parsed.blocks[0].heading == "Heading"
    assert parsed.blocks[0].content == "Useful paragraph"


def test_parse_document_rejects_llamaparse_without_api_key() -> None:
    """缺少 LlamaParse API key 時應明確失敗。"""

    try:
        parse_document(
            file_name="sample.pdf",
            payload=MINIMAL_TEXT_PDF,
            pdf_config=PdfParserConfig(provider="llamaparse"),
        )
    except ValueError as exc:
        assert "LLAMAPARSE_API_KEY" in str(exc)
    else:  # pragma: no cover - 失敗時才會進來。
        raise AssertionError("預期缺少 API key 時應拋出 ValueError。")
