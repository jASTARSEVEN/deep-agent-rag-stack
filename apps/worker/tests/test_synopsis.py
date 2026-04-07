"""Document synopsis 壓縮與 provider 測試。"""

from types import SimpleNamespace

from worker.synopsis import (
    DeterministicDocumentSynopsisProvider,
    build_document_synopsis_source_text,
)


def _build_parent_chunk(*, heading: str, content: str, structure_kind: str = "text"):
    """建立 synopsis 測試使用的最小 parent chunk 替身。

    參數：
    - `heading`：parent heading。
    - `content`：parent content。
    - `structure_kind`：內容結構型別。

    回傳：
    - 具備 synopsis helper 所需欄位的測試替身。
    """

    return SimpleNamespace(
        heading=heading,
        content=content,
        structure_kind=SimpleNamespace(value=structure_kind),
    )


def test_build_document_synopsis_source_text_keeps_all_parent_headings() -> None:
    """全 parent coverage 壓縮應保留每個 parent 的 heading。"""

    source_text = build_document_synopsis_source_text(
        file_name="policy.md",
        parent_chunks=[
            _build_parent_chunk(heading="Overview", content="Alpha body " * 20),
            _build_parent_chunk(heading="Budget Table", content="| item | value |", structure_kind="table"),
            _build_parent_chunk(heading="Conclusion", content="Beta closing " * 20),
        ],
        max_input_chars=1200,
    )

    assert "Heading: Overview" in source_text
    assert "Heading: Budget Table" in source_text
    assert "Heading: Conclusion" in source_text


def test_deterministic_document_synopsis_provider_respects_output_cap() -> None:
    """deterministic synopsis provider 應輸出固定結構且長度受控。"""

    provider = DeterministicDocumentSynopsisProvider()

    synopsis = provider.generate_synopsis(
        file_name="policy.md",
        source_text=(
            "Heading: Overview\n"
            "Excerpt: Alpha overview.\n"
            "Table/Structure: Primarily narrative text.\n\n"
            "Heading: Budget\n"
            "Excerpt: Budget summary.\n"
            "Table/Structure: Contains table-like structure."
        ),
        output_language="en",
        max_output_chars=180,
    )

    assert "Topic:" in synopsis
    assert "Key sections:" in synopsis
    assert len(synopsis) <= 180
