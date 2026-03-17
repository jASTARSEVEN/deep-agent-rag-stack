"""Documents、chunks 與 ingest jobs API 測試。"""

from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from app.db.models import (
    Area,
    AreaUserRole,
    ChunkStructureKind,
    ChunkType,
    Document,
    DocumentChunk,
    DocumentStatus,
    IngestJob,
    IngestJobStatus,
    Role,
)


# 管理者測試 token。
ADMIN_TOKEN = "Bearer test::user-admin::/group/admin"

# 維護者測試 token。
MAINTAINER_TOKEN = "Bearer test::user-maintainer::/group/maintainer"

# 讀者測試 token。
READER_TOKEN = "Bearer test::user-reader::/group/reader"

# 無授權測試 token。
OUTSIDER_TOKEN = "Bearer test::user-outsider::/group/outsider"

# 測試 local PDF provider 路徑的最小 PDF 樣本。
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


def _uuid() -> str:
    """建立測試用 UUID 字串。"""

    return str(uuid4())


def test_upload_document_creates_chunks_and_inline_ready(client, db_session, app_settings) -> None:
    """maintainer 上傳 md 後應建立 parent-child chunks，並在 inline ingest 下轉為 ready。"""

    area = Area(id=_uuid(), name="Maintainer Docs")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-maintainer", role=Role.maintainer))
    db_session.commit()

    file_payload = f"# Intro\n{'A' * 320}\n\n## Detail\n{'B' * 340}\n".encode()
    response = client.post(
        f"/areas/{area.id}/documents",
        headers={"Authorization": MAINTAINER_TOKEN},
        files={"file": ("notes.md", file_payload, "text/markdown")},
    )

    assert response.status_code == 201
    response_payload = response.json()
    assert response_payload["document"]["file_name"] == "notes.md"
    assert response_payload["document"]["status"] == "ready"
    assert response_payload["document"]["chunk_summary"] == {
        "total_chunks": 4,
        "parent_chunks": 2,
        "child_chunks": 2,
        "last_indexed_at": response_payload["document"]["chunk_summary"]["last_indexed_at"],
    }
    assert response_payload["job"]["status"] == "succeeded"
    assert response_payload["job"]["stage"] == "succeeded"
    assert response_payload["job"]["chunk_summary"]["child_chunks"] == 2

    stored_document = db_session.get(Document, response_payload["document"]["id"])
    stored_job = db_session.get(IngestJob, response_payload["job"]["id"])
    stored_chunks = db_session.query(DocumentChunk).filter(DocumentChunk.document_id == response_payload["document"]["id"]).all()
    assert stored_document is not None
    assert stored_document.status == DocumentStatus.ready
    assert stored_document.file_size == len(file_payload)
    assert stored_document.indexed_at is not None
    assert stored_job is not None
    assert stored_job.status == IngestJobStatus.succeeded
    assert stored_job.parent_chunk_count == 2
    assert stored_job.child_chunk_count == 2
    assert len(stored_chunks) == 4
    assert {chunk.structure_kind for chunk in stored_chunks} == {ChunkStructureKind.text}
    child_chunks = [chunk for chunk in stored_chunks if chunk.chunk_type == ChunkType.child]
    assert child_chunks
    assert all(chunk.embedding is not None for chunk in child_chunks)
    assert (Path(app_settings.local_storage_path) / stored_document.storage_key).exists()


def test_upload_document_preserves_langchain_child_offsets(client, db_session) -> None:
    """inline ingest 應將 LangChain child splitter 的 offsets 正確寫入資料庫。"""

    area = Area(id=_uuid(), name="Maintainer Offsets")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-maintainer", role=Role.maintainer))
    db_session.commit()

    repeated_sentence = ("alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu " * 14).strip()
    file_payload = f"# Intro\n{repeated_sentence}".encode()
    response = client.post(
        f"/areas/{area.id}/documents",
        headers={"Authorization": MAINTAINER_TOKEN},
        files={"file": ("offsets.md", file_payload, "text/markdown")},
    )

    assert response.status_code == 201
    payload = response.json()

    stored_children = (
        db_session.query(DocumentChunk)
        .filter(DocumentChunk.document_id == payload["document"]["id"], DocumentChunk.chunk_type == "child")
        .order_by(DocumentChunk.position.asc())
        .all()
    )
    parent = (
        db_session.query(DocumentChunk)
        .filter(DocumentChunk.document_id == payload["document"]["id"], DocumentChunk.chunk_type == "parent")
        .order_by(DocumentChunk.position.asc())
        .one()
    )
    assert len(stored_children) >= 2
    for index, child in enumerate(stored_children):
        assert child.child_index == index
        assert child.start_offset < child.end_offset
        assert child.content == child.content.strip()
        assert child.char_count == len(child.content)
        relative_start = child.start_offset - parent.start_offset
        relative_end = child.end_offset - parent.start_offset
        assert parent.content[relative_start:relative_end] == child.content


def test_upload_document_truncates_chunk_heading_and_preview(client, db_session, app_settings) -> None:
    """inline ingest 寫入 chunk 時應裁切過長 heading 與 content preview，避免超出 schema。"""

    app_settings.chunk_content_preview_length = 400
    area = Area(id=_uuid(), name="Long Heading Docs")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-maintainer", role=Role.maintainer))
    db_session.commit()

    long_heading = "H" * 320
    long_body = "A" * 420
    file_payload = f"# {long_heading}\n{long_body}\n".encode()
    response = client.post(
        f"/areas/{area.id}/documents",
        headers={"Authorization": MAINTAINER_TOKEN},
        files={"file": ("long-heading.md", file_payload, "text/markdown")},
    )

    assert response.status_code == 201
    payload = response.json()
    stored_chunks = (
        db_session.query(DocumentChunk)
        .filter(DocumentChunk.document_id == payload["document"]["id"])
        .order_by(DocumentChunk.position.asc())
        .all()
    )
    assert stored_chunks
    assert all(chunk.heading == long_heading[:255] for chunk in stored_chunks)
    assert all(len(chunk.content_preview) == 255 for chunk in stored_chunks)


def test_upload_markdown_table_creates_table_chunks(client, db_session) -> None:
    """含 Markdown table 的文件應建立 table structure_kind chunks。"""

    area = Area(id=_uuid(), name="Maintainer Markdown Tables")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-maintainer", role=Role.maintainer))
    db_session.commit()

    file_payload = "\n".join(
        [
            "# Report",
            "Summary paragraph",
            "",
            "| Name | Score |",
            "| --- | ---: |",
            "| Alice | 95 |",
            "| Bob | 88 |",
            "",
            "Closing paragraph",
        ]
    ).encode()
    response = client.post(
        f"/areas/{area.id}/documents",
        headers={"Authorization": MAINTAINER_TOKEN},
        files={"file": ("report.md", file_payload, "text/markdown")},
    )

    assert response.status_code == 201
    payload = response.json()
    stored_chunks = (
        db_session.query(DocumentChunk)
        .filter(DocumentChunk.document_id == payload["document"]["id"])
        .order_by(DocumentChunk.position.asc())
        .all()
    )
    assert any(chunk.structure_kind == ChunkStructureKind.table for chunk in stored_chunks)
    table_parent = next(
        chunk
        for chunk in stored_chunks
        if chunk.chunk_type == "parent" and chunk.structure_kind == ChunkStructureKind.table
    )
    assert "| Alice | 95 |" in table_parent.content


def test_upload_html_table_creates_table_chunks(client, db_session) -> None:
    """含 HTML table 的文件應建立 table structure_kind chunks。"""

    area = Area(id=_uuid(), name="Maintainer HTML Tables")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-maintainer", role=Role.maintainer))
    db_session.commit()

    file_payload = b"""
    <h1>Quarterly Report</h1>
    <p>Summary paragraph</p>
    <table>
      <tr><th>Name</th><th>Score</th></tr>
      <tr><td>Alice</td><td>95</td></tr>
      <tr><td>Bob</td><td>88</td></tr>
    </table>
    <p>Closing note</p>
    """
    response = client.post(
        f"/areas/{area.id}/documents",
        headers={"Authorization": MAINTAINER_TOKEN},
        files={"file": ("report.html", file_payload, "text/html")},
    )

    assert response.status_code == 201
    payload = response.json()
    stored_chunks = (
        db_session.query(DocumentChunk)
        .filter(DocumentChunk.document_id == payload["document"]["id"])
        .order_by(DocumentChunk.position.asc())
        .all()
    )
    assert any(chunk.structure_kind == ChunkStructureKind.table for chunk in stored_chunks)


def test_upload_xlsx_creates_table_chunks_via_unstructured(client, db_session, monkeypatch) -> None:
    """含 XLSX worksheet 的文件應建立 table structure_kind chunks。"""

    @dataclass
    class _FakeMetadata:
        """模擬 Unstructured worksheet metadata。"""

        page_name: str
        text_as_html: str

    @dataclass
    class _FakeElement:
        """模擬 Unstructured worksheet element。"""

        metadata: _FakeMetadata
        text: str

    monkeypatch.setattr(
        "app.services.parsers._extract_xlsx_elements_with_unstructured",
        lambda *, payload: [
            _FakeElement(
                metadata=_FakeMetadata(
                    page_name="Quarterly Budget",
                    text_as_html=(
                        "<table><tr><th>Name</th><th>Score</th></tr>"
                        "<tr><td>Alice</td><td>95</td></tr>"
                        "<tr><td>Bob</td><td>88</td></tr></table>"
                    ),
                ),
                text="Name Score Alice 95 Bob 88",
            )
        ],
    )

    area = Area(id=_uuid(), name="Maintainer XLSX Tables")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-maintainer", role=Role.maintainer))
    db_session.commit()

    response = client.post(
        f"/areas/{area.id}/documents",
        headers={"Authorization": MAINTAINER_TOKEN},
        files={
            "file": (
                "report.xlsx",
                b"fake-xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["document"]["status"] == "ready"
    stored_chunks = (
        db_session.query(DocumentChunk)
        .filter(DocumentChunk.document_id == payload["document"]["id"])
        .order_by(DocumentChunk.position.asc())
        .all()
    )
    assert any(chunk.structure_kind == ChunkStructureKind.table for chunk in stored_chunks)
    table_parent = next(
        chunk
        for chunk in stored_chunks
        if chunk.chunk_type == ChunkType.parent and chunk.structure_kind == ChunkStructureKind.table
    )
    assert table_parent.heading == "Quarterly Budget"
    assert "Alice" in table_parent.content


def test_upload_pdf_uses_local_parser_and_becomes_ready(client, db_session, monkeypatch) -> None:
    """local PDF parser 應能以 Unstructured local 路徑讓 PDF 在 inline ingest 下轉為 ready。"""

    @dataclass
    class _FakeMetadata:
        """模擬 Unstructured element metadata。"""

        text_as_html: str | None = None

    @dataclass
    class _FakeElement:
        """模擬 Unstructured PDF element。"""

        category: str
        text: str
        metadata: _FakeMetadata

    monkeypatch.setattr(
        "app.services.parsers._extract_pdf_elements_with_unstructured",
        lambda *, payload: [
            _FakeElement(category="Title", text="Guide", metadata=_FakeMetadata()),
            _FakeElement(
                category="NarrativeText",
                text="Deep Agent PDF local parser sample",
                metadata=_FakeMetadata(),
            ),
        ],
    )

    area = Area(id=_uuid(), name="Maintainer PDF Docs")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-maintainer", role=Role.maintainer))
    db_session.commit()

    response = client.post(
        f"/areas/{area.id}/documents",
        headers={"Authorization": MAINTAINER_TOKEN},
        files={"file": ("guide.pdf", MINIMAL_TEXT_PDF, "application/pdf")},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["document"]["status"] == "ready"
    assert payload["document"]["file_name"] == "guide.pdf"
    assert payload["document"]["chunk_summary"]["total_chunks"] == 2

    stored_chunks = (
        db_session.query(DocumentChunk)
        .filter(DocumentChunk.document_id == payload["document"]["id"])
        .order_by(DocumentChunk.position.asc())
        .all()
    )
    assert len(stored_chunks) == 2
    assert all(chunk.structure_kind == ChunkStructureKind.text for chunk in stored_chunks)
    assert any("Deep Agent PDF local parser sample" in chunk.content for chunk in stored_chunks)


def test_upload_pdf_uses_llamaparse_markdown_when_enabled(client, db_session, app_settings, monkeypatch) -> None:
    """llamaparse provider 應能將 Markdown 結果交回既有 parser 與 chunk tree。"""

    app_settings.pdf_parser_provider = "llamaparse"
    app_settings.llamaparse_api_key = "test-key"
    monkeypatch.setattr(
        "app.services.parsers._extract_pdf_markdown_with_llamaparse",
        lambda *, payload, pdf_config: "# PDF Report\n\n| Name | Score |\n| --- | --- |\n| Alice | 95 |",
    )
    area = Area(id=_uuid(), name="Maintainer PDF Tables")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-maintainer", role=Role.maintainer))
    db_session.commit()

    response = client.post(
        f"/areas/{area.id}/documents",
        headers={"Authorization": MAINTAINER_TOKEN},
        files={"file": ("report.pdf", MINIMAL_TEXT_PDF, "application/pdf")},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["document"]["status"] == "ready"
    stored_chunks = (
        db_session.query(DocumentChunk)
        .filter(DocumentChunk.document_id == payload["document"]["id"])
        .order_by(DocumentChunk.position.asc())
        .all()
    )
    assert any(chunk.structure_kind == ChunkStructureKind.table for chunk in stored_chunks)


def test_upload_pdf_clusters_text_table_text_when_llamaparse_enabled(client, db_session, app_settings, monkeypatch) -> None:
    """llamaparse PDF 的 `text -> table -> text` 應落成單一 parent cluster 與混合 children。"""

    app_settings.pdf_parser_provider = "llamaparse"
    app_settings.llamaparse_api_key = "test-key"
    app_settings.chunk_min_parent_section_length = 800
    monkeypatch.setattr(
        "app.services.parsers._extract_pdf_markdown_with_llamaparse",
        lambda *, payload, pdf_config: (
            "# Overview\n\nIntro note\n\n| Name | Score |\n| --- | --- |\n| Alice | 95 |\n\nClosing note"
        ),
    )
    area = Area(id=_uuid(), name="Maintainer PDF Cluster")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-maintainer", role=Role.maintainer))
    db_session.commit()

    response = client.post(
        f"/areas/{area.id}/documents",
        headers={"Authorization": MAINTAINER_TOKEN},
        files={"file": ("cluster.pdf", MINIMAL_TEXT_PDF, "application/pdf")},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["document"]["status"] == "ready"

    stored_chunks = (
        db_session.query(DocumentChunk)
        .filter(DocumentChunk.document_id == payload["document"]["id"])
        .order_by(DocumentChunk.position.asc())
        .all()
    )
    parent_chunks = [chunk for chunk in stored_chunks if chunk.chunk_type == ChunkType.parent]
    child_chunks = [chunk for chunk in stored_chunks if chunk.chunk_type == ChunkType.child]
    assert len(parent_chunks) == 1
    assert [chunk.structure_kind for chunk in child_chunks] == [
        ChunkStructureKind.text,
        ChunkStructureKind.table,
        ChunkStructureKind.text,
    ]
    assert [chunk.child_index for chunk in child_chunks] == [0, 1, 2]


def test_upload_pdf_marks_failed_when_llamaparse_missing_key(client, db_session, app_settings) -> None:
    """llamaparse provider 缺少 API key 時應呈現受控失敗。"""

    app_settings.pdf_parser_provider = "llamaparse"
    app_settings.llamaparse_api_key = None
    area = Area(id=_uuid(), name="Maintainer PDF Missing Key")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-maintainer", role=Role.maintainer))
    db_session.commit()

    response = client.post(
        f"/areas/{area.id}/documents",
        headers={"Authorization": MAINTAINER_TOKEN},
        files={"file": ("secure.pdf", MINIMAL_TEXT_PDF, "application/pdf")},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["document"]["status"] == "failed"
    assert "LLAMAPARSE_API_KEY" in (payload["job"]["error_message"] or "")
    assert payload["document"]["chunk_summary"]["total_chunks"] == 0


def test_upload_document_rejects_reader(client, db_session) -> None:
    """reader 不可上傳文件。"""

    area = Area(id=_uuid(), name="Reader Docs")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-reader", role=Role.reader))
    db_session.commit()

    response = client.post(
        f"/areas/{area.id}/documents",
        headers={"Authorization": READER_TOKEN},
        files={"file": ("notes.md", b"content", "text/markdown")},
    )

    assert response.status_code == 403


def test_upload_document_returns_same_404_for_unauthorized_and_missing_area(client, db_session) -> None:
    """outsider 對既有與不存在 area 上傳都應回相同 404。"""

    area = Area(id=_uuid(), name="Secret Docs")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-admin", role=Role.admin))
    db_session.commit()

    unauthorized_response = client.post(
        f"/areas/{area.id}/documents",
        headers={"Authorization": OUTSIDER_TOKEN},
        files={"file": ("notes.md", b"content", "text/markdown")},
    )
    missing_response = client.post(
        "/areas/missing-area/documents",
        headers={"Authorization": OUTSIDER_TOKEN},
        files={"file": ("notes.md", b"content", "text/markdown")},
    )

    assert unauthorized_response.status_code == 404
    assert missing_response.status_code == 404
    assert unauthorized_response.json() == missing_response.json()


def test_upload_document_rejects_empty_file(client, db_session) -> None:
    """空檔案應被 upload validator 擋下。"""

    area = Area(id=_uuid(), name="Empty Docs")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-admin", role=Role.admin))
    db_session.commit()

    response = client.post(
        f"/areas/{area.id}/documents",
        headers={"Authorization": ADMIN_TOKEN},
        files={"file": ("empty.md", b"", "text/markdown")},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "上傳檔案不可為空。"


def test_upload_document_rejects_oversized_file(client, db_session) -> None:
    """超過大小限制的檔案應被拒絕。"""

    area = Area(id=_uuid(), name="Large Docs")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-admin", role=Role.admin))
    db_session.commit()

    response = client.post(
        f"/areas/{area.id}/documents",
        headers={"Authorization": ADMIN_TOKEN},
        files={"file": ("large.md", b"x" * 2048, "text/markdown")},
    )

    assert response.status_code == 413


def test_upload_document_rejects_unknown_extension(client, db_session) -> None:
    """未知副檔名應在 API 驗證階段被拒絕。"""

    area = Area(id=_uuid(), name="Unknown Docs")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-admin", role=Role.admin))
    db_session.commit()

    response = client.post(
        f"/areas/{area.id}/documents",
        headers={"Authorization": ADMIN_TOKEN},
        files={"file": ("archive.zip", b"fake", "application/zip")},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "目前不支援此檔案類型。"


def test_upload_docx_creates_chunks_via_unstructured(client, db_session, monkeypatch) -> None:
    """DOCX 應能透過 Unstructured 轉為 ready 並建立 chunks。"""

    @dataclass
    class _FakeMetadata:
        """模擬 Unstructured office metadata。"""

        text_as_html: str | None = None

    @dataclass
    class _FakeElement:
        """模擬 Unstructured office element。"""

        category: str
        text: str
        metadata: _FakeMetadata

    area = Area(id=_uuid(), name="DOCX Docs")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-admin", role=Role.admin))
    db_session.commit()

    monkeypatch.setattr(
        "app.services.parsers._extract_docx_elements_with_unstructured",
        lambda *, payload: [
            _FakeElement(category="Title", text="Project Plan", metadata=_FakeMetadata()),
            _FakeElement(category="NarrativeText", text="Executive summary", metadata=_FakeMetadata()),
            _FakeElement(
                category="Table",
                text="Owner Status Alice Ready",
                metadata=_FakeMetadata(
                    text_as_html=(
                        "<table><tr><th>Owner</th><th>Status</th></tr>"
                        "<tr><td>Alice</td><td>Ready</td></tr></table>"
                    )
                ),
            ),
        ],
    )

    response = client.post(
        f"/areas/{area.id}/documents",
        headers={"Authorization": ADMIN_TOKEN},
        files={"file": ("deck.docx", b"PK\x03\x04", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["document"]["status"] == "ready"
    assert payload["job"]["status"] == "succeeded"
    assert payload["document"]["chunk_summary"]["total_chunks"] > 0


def test_upload_pptx_creates_chunks_via_unstructured(client, db_session, monkeypatch) -> None:
    """PPTX 應能透過 Unstructured 轉為 ready 並建立文字 chunks。"""

    @dataclass
    class _FakeMetadata:
        """模擬 Unstructured office metadata。"""

        text_as_html: str | None = None

    @dataclass
    class _FakeElement:
        """模擬 Unstructured office element。"""

        category: str
        text: str
        metadata: _FakeMetadata

    area = Area(id=_uuid(), name="PPTX Docs")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-admin", role=Role.admin))
    db_session.commit()

    monkeypatch.setattr(
        "app.services.parsers._extract_pptx_elements_with_unstructured",
        lambda *, payload: [
            _FakeElement(category="Title", text="Quarterly Review", metadata=_FakeMetadata()),
            _FakeElement(category="ListItem", text="Revenue up 15%", metadata=_FakeMetadata()),
            _FakeElement(category="ListItem", text="Margin stable", metadata=_FakeMetadata()),
        ],
    )

    response = client.post(
        f"/areas/{area.id}/documents",
        headers={"Authorization": ADMIN_TOKEN},
        files={
            "file": (
                "deck.pptx",
                b"PK\x03\x04",
                "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            )
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["document"]["status"] == "ready"
    assert payload["job"]["status"] == "succeeded"
    assert payload["document"]["chunk_summary"]["total_chunks"] > 0


def test_list_documents_returns_only_area_documents_with_chunk_summary(client, db_session) -> None:
    """area 文件列表只應回傳指定 area 內的文件與其 chunk 摘要。"""

    visible_area = Area(id=_uuid(), name="Visible")
    hidden_area = Area(id=_uuid(), name="Hidden")
    visible_document_id = _uuid()
    hidden_document_id = _uuid()
    db_session.add_all([visible_area, hidden_area])
    db_session.add_all(
        [
            AreaUserRole(area_id=visible_area.id, user_sub="user-reader", role=Role.reader),
            AreaUserRole(area_id=hidden_area.id, user_sub="user-admin", role=Role.admin),
            Document(
                id=visible_document_id,
                area_id=visible_area.id,
                file_name="visible.md",
                content_type="text/markdown",
                file_size=10,
                storage_key="visible",
                status=DocumentStatus.ready,
            ),
            Document(
                id=hidden_document_id,
                area_id=hidden_area.id,
                file_name="hidden.md",
                content_type="text/markdown",
                file_size=12,
                storage_key="hidden",
                status=DocumentStatus.ready,
            ),
            DocumentChunk(
                document_id=visible_document_id,
                parent_chunk_id=None,
                chunk_type="parent",
                structure_kind=ChunkStructureKind.text,
                position=0,
                section_index=0,
                child_index=None,
                heading="Visible",
                content="Visible section",
                content_preview="Visible section",
                char_count=15,
                start_offset=0,
                end_offset=15,
            ),
        ]
    )
    db_session.commit()

    response = client.get(f"/areas/{visible_area.id}/documents", headers={"Authorization": READER_TOKEN})

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == [visible_document_id]
    assert response.json()["items"][0]["chunk_summary"]["parent_chunks"] == 1


def test_document_detail_returns_same_404_for_unauthorized_and_missing(client, db_session) -> None:
    """未授權與不存在的 document 都應回相同 404。"""

    area = Area(id=_uuid(), name="Secret")
    document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="secret.md",
        content_type="text/markdown",
        file_size=9,
        storage_key="secret",
        status=DocumentStatus.ready,
    )
    db_session.add(area)
    db_session.add(document)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-admin", role=Role.admin))
    db_session.commit()

    unauthorized_response = client.get(f"/documents/{document.id}", headers={"Authorization": OUTSIDER_TOKEN})
    missing_response = client.get("/documents/missing-document", headers={"Authorization": OUTSIDER_TOKEN})

    assert unauthorized_response.status_code == 404
    assert missing_response.status_code == 404
    assert unauthorized_response.json() == missing_response.json()


def test_ingest_job_detail_returns_same_404_for_unauthorized_and_missing(client, db_session) -> None:
    """未授權與不存在的 ingest job 都應回相同 404。"""

    area = Area(id=_uuid(), name="Secret Job")
    document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="secret.md",
        content_type="text/markdown",
        file_size=9,
        storage_key="secret",
        status=DocumentStatus.ready,
    )
    job = IngestJob(id=_uuid(), document_id=document.id, status=IngestJobStatus.succeeded)
    db_session.add_all([area, document, job])
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-admin", role=Role.admin))
    db_session.commit()

    unauthorized_response = client.get(f"/ingest-jobs/{job.id}", headers={"Authorization": OUTSIDER_TOKEN})
    missing_response = client.get("/ingest-jobs/missing-job", headers={"Authorization": OUTSIDER_TOKEN})

    assert unauthorized_response.status_code == 404
    assert missing_response.status_code == 404
    assert unauthorized_response.json() == missing_response.json()


def test_reindex_document_replaces_existing_chunks(client, db_session, app_settings) -> None:
    """reindex 應清掉舊 chunks，並以新內容重建 chunk tree。"""

    area = Area(id=_uuid(), name="Reindex Docs")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-admin", role=Role.admin))
    db_session.commit()

    original_payload = f"# Intro\n{'A' * 320}\n".encode()
    upload_response = client.post(
        f"/areas/{area.id}/documents",
        headers={"Authorization": ADMIN_TOKEN},
        files={"file": ("notes.md", original_payload, "text/markdown")},
    )
    upload_payload = upload_response.json()
    document_id = upload_payload["document"]["id"]

    original_chunk_ids = {
        chunk.id for chunk in db_session.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).all()
    }
    stored_document = db_session.get(Document, document_id)
    assert stored_document is not None
    (Path(app_settings.local_storage_path) / stored_document.storage_key).write_bytes(
        f"# Intro\n{'C' * 320}\n\n## Next\n{'D' * 340}\n".encode()
    )

    reindex_response = client.post(f"/documents/{document_id}/reindex", headers={"Authorization": ADMIN_TOKEN})

    assert reindex_response.status_code == 200
    reindex_payload = reindex_response.json()
    assert reindex_payload["document"]["status"] == "ready"
    assert reindex_payload["job"]["status"] == "succeeded"
    assert reindex_payload["document"]["chunk_summary"]["parent_chunks"] == 2

    refreshed_chunk_ids = {
        chunk.id for chunk in db_session.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).all()
    }
    assert original_chunk_ids.isdisjoint(refreshed_chunk_ids)


def test_reindex_document_returns_same_404_for_unauthorized_and_missing(client, db_session) -> None:
    """未授權與不存在的 reindex 操作都應回相同 404。"""

    area = Area(id=_uuid(), name="Reindex Secret")
    document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="secret.md",
        content_type="text/markdown",
        file_size=9,
        storage_key="secret",
        status=DocumentStatus.ready,
    )
    db_session.add_all([area, document])
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-admin", role=Role.admin))
    db_session.commit()

    unauthorized_response = client.post(f"/documents/{document.id}/reindex", headers={"Authorization": OUTSIDER_TOKEN})
    missing_response = client.post("/documents/missing-document/reindex", headers={"Authorization": OUTSIDER_TOKEN})

    assert unauthorized_response.status_code == 404
    assert missing_response.status_code == 404
    assert unauthorized_response.json() == missing_response.json()


def test_delete_document_removes_storage_chunks_and_record(client, db_session, app_settings) -> None:
    """刪除文件時應一併移除 storage、chunks 與 document record。"""

    area = Area(id=_uuid(), name="Delete Docs")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-admin", role=Role.admin))
    db_session.commit()

    upload_response = client.post(
        f"/areas/{area.id}/documents",
        headers={"Authorization": ADMIN_TOKEN},
        files={"file": ("notes.md", b"# Intro\ncontent\n", "text/markdown")},
    )
    document_id = upload_response.json()["document"]["id"]

    stored_document = db_session.get(Document, document_id)
    assert stored_document is not None
    storage_path = Path(app_settings.local_storage_path) / stored_document.storage_key
    assert storage_path.exists()

    delete_response = client.delete(f"/documents/{document_id}", headers={"Authorization": ADMIN_TOKEN})

    assert delete_response.status_code == 204
    db_session.expire_all()
    assert db_session.get(Document, document_id) is None
    assert db_session.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).count() == 0
    assert not storage_path.exists()


def test_delete_document_returns_same_404_for_unauthorized_and_missing(client, db_session) -> None:
    """未授權與不存在的 delete 操作都應回相同 404。"""

    area = Area(id=_uuid(), name="Delete Secret")
    document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="secret.md",
        content_type="text/markdown",
        file_size=9,
        storage_key="secret",
        status=DocumentStatus.ready,
    )
    db_session.add_all([area, document])
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-admin", role=Role.admin))
    db_session.commit()

    unauthorized_response = client.delete(f"/documents/{document.id}", headers={"Authorization": OUTSIDER_TOKEN})
    missing_response = client.delete("/documents/missing-document", headers={"Authorization": OUTSIDER_TOKEN})

    assert unauthorized_response.status_code == 404
    assert missing_response.status_code == 404
    assert unauthorized_response.json() == missing_response.json()
