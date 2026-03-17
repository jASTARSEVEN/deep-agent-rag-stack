"""Worker ingest task 與 chunk tree 測試。"""

from dataclasses import dataclass
from pathlib import Path

from worker.chunking import ChunkingConfig, build_chunk_tree
from worker.core.settings import WorkerSettings
from worker.db import (
    Base,
    ChunkStructureKind,
    ChunkType,
    Document,
    DocumentChunk,
    DocumentStatus,
    IngestJob,
    IngestJobStatus,
    create_database_engine,
    create_session_factory,
)
from worker.parsers import ParsedBlock, ParsedDocument, parse_document
from worker.tasks.ingest import process_document_ingest


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


def build_settings(tmp_path: Path) -> WorkerSettings:
    """建立 worker 測試用設定。

    參數：
    - `tmp_path`：pytest 提供的暫存目錄。

    回傳：
    - `WorkerSettings`：供 worker 測試使用的設定物件。
    """

    return WorkerSettings(
        WORKER_SERVICE_NAME="deep-agent-worker-test",
        DATABASE_URL=f"sqlite+pysqlite:///{tmp_path / 'worker.sqlite'}",
        CELERY_BROKER_URL="redis://redis:6379/0",
        CELERY_RESULT_BACKEND="redis://redis:6379/1",
        STORAGE_BACKEND="filesystem",
        LOCAL_STORAGE_PATH=tmp_path / "storage",
        MINIO_ENDPOINT="http://minio:9000",
        MINIO_ACCESS_KEY="minio",
        MINIO_SECRET_KEY="minio123",
        MINIO_BUCKET="documents",
        CHUNK_MIN_PARENT_SECTION_LENGTH=300,
        CHUNK_TARGET_CHILD_SIZE=800,
        CHUNK_CHILD_OVERLAP=120,
        CHUNK_CONTENT_PREVIEW_LENGTH=120,
        CHUNK_TXT_PARENT_GROUP_SIZE=4,
        CHUNK_TABLE_PRESERVE_MAX_CHARS=4000,
        CHUNK_TABLE_MAX_ROWS_PER_CHILD=20,
        PDF_PARSER_PROVIDER="local",
        LLAMAPARSE_API_KEY="",
        LLAMAPARSE_DO_NOT_CACHE=True,
        LLAMAPARSE_MERGE_CONTINUED_TABLES=False,
        EMBEDDING_PROVIDER="deterministic",
        EMBEDDING_MODEL="text-embedding-3-small",
        EMBEDDING_DIMENSIONS=1536,
    )


def build_chunking_config(settings: WorkerSettings) -> ChunkingConfig:
    """將 worker 設定轉為 chunking config。

    參數：
    - `settings`：worker 測試設定。

    回傳：
    - `ChunkingConfig`：供測試直接呼叫 chunking 使用的參數物件。
    """

    return ChunkingConfig(
        min_parent_section_length=settings.chunk_min_parent_section_length,
        target_child_chunk_size=settings.chunk_target_child_size,
        child_chunk_overlap=settings.chunk_child_overlap,
        content_preview_length=settings.chunk_content_preview_length,
        txt_parent_group_size=settings.chunk_txt_parent_group_size,
        table_preserve_max_chars=settings.chunk_table_preserve_max_chars,
        table_max_rows_per_child=settings.chunk_table_max_rows_per_child,
    )


def seed_job(
    session_factory,
    *,
    file_name: str,
    payload: bytes,
    status=DocumentStatus.uploaded,
    job_status=IngestJobStatus.queued,
):
    """建立測試用 document/job 與對應原始檔。

    參數：
    - `session_factory`：用來建立測試資料庫 session 的 factory。
    - `file_name`：測試文件檔名。
    - `payload`：測試文件原始內容。
    - `status`：文件初始狀態。
    - `job_status`：ingest job 初始狀態。

    回傳：
    - 包含 `Document` 與 `IngestJob` 的 tuple。
    """

    with session_factory() as session:
        document = Document(
            id="document-1",
            area_id="area-1",
            file_name=file_name,
            content_type="text/markdown",
            file_size=len(payload),
            storage_key="area-1/document-1/" + file_name,
            status=status,
        )
        job = IngestJob(id="job-1", document_id=document.id, status=job_status)
        session.add_all([document, job])
        session.commit()
        return document, job


def test_process_document_ingest_updates_ready_and_writes_chunks(monkeypatch, tmp_path: Path) -> None:
    """支援的 md 文件應推進到 ready/succeeded，並寫入 parent-child chunks。"""

    settings = build_settings(tmp_path)
    monkeypatch.setattr("worker.tasks.ingest.get_settings", lambda: settings)
    engine = create_database_engine(settings)
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    payload = f"# Title\n{'A' * 320}\n\n## Next\n{'B' * 340}".encode()
    document, job = seed_job(session_factory, file_name="notes.md", payload=payload)
    storage_path = Path(settings.local_storage_path) / document.storage_key
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    storage_path.write_bytes(payload)

    result = process_document_ingest(job.id)

    with session_factory() as session:
        refreshed_document = session.get(Document, document.id)
        refreshed_job = session.get(IngestJob, job.id)
        refreshed_chunks = session.query(DocumentChunk).filter(DocumentChunk.document_id == document.id).all()
        assert result == "succeeded"
        assert refreshed_document is not None
        assert refreshed_document.status == DocumentStatus.ready
        assert refreshed_document.indexed_at is not None
        assert refreshed_job is not None
        assert refreshed_job.status == IngestJobStatus.succeeded
        assert refreshed_job.stage == "succeeded"
        assert refreshed_job.parent_chunk_count == 2
        assert refreshed_job.child_chunk_count == 2
        assert len(refreshed_chunks) == 4
        assert {chunk.structure_kind for chunk in refreshed_chunks} == {ChunkStructureKind.text}
        child_chunks = [chunk for chunk in refreshed_chunks if chunk.chunk_type == ChunkType.child]
        assert child_chunks
        assert all(chunk.embedding is not None for chunk in child_chunks)


def test_process_document_ingest_supports_local_pdf(monkeypatch, tmp_path: Path) -> None:
    """local PDF provider 應能以 Unstructured local 路徑將 PDF 推進到 ready。"""

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
        "worker.parsers._extract_pdf_elements_with_unstructured",
        lambda *, payload: [
            _FakeElement(category="Title", text="Guide", metadata=_FakeMetadata()),
            _FakeElement(
                category="NarrativeText",
                text="Deep Agent PDF local parser sample",
                metadata=_FakeMetadata(),
            ),
        ],
    )

    settings = build_settings(tmp_path)
    monkeypatch.setattr("worker.tasks.ingest.get_settings", lambda: settings)
    engine = create_database_engine(settings)
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    document, job = seed_job(session_factory, file_name="deck.pdf", payload=MINIMAL_TEXT_PDF)
    storage_path = Path(settings.local_storage_path) / document.storage_key
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    storage_path.write_bytes(MINIMAL_TEXT_PDF)

    result = process_document_ingest(job.id)

    with session_factory() as session:
        refreshed_document = session.get(Document, document.id)
        refreshed_job = session.get(IngestJob, job.id)
        refreshed_chunks = session.query(DocumentChunk).filter(DocumentChunk.document_id == document.id).all()
        assert result == "succeeded"
        assert refreshed_document is not None
        assert refreshed_document.status == DocumentStatus.ready
        assert refreshed_job is not None
        assert refreshed_job.status == IngestJobStatus.succeeded
        assert any("Deep Agent PDF local parser sample" in chunk.content for chunk in refreshed_chunks)


def test_process_document_ingest_supports_xlsx(monkeypatch, tmp_path: Path) -> None:
    """XLSX parser 應能將 worksheet 推進到 ready 並寫出 table-aware chunks。"""

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

    settings = build_settings(tmp_path)
    monkeypatch.setattr("worker.tasks.ingest.get_settings", lambda: settings)
    monkeypatch.setattr(
        "worker.parsers._extract_xlsx_elements_with_unstructured",
        lambda *, payload: [
            _FakeElement(
                metadata=_FakeMetadata(
                    page_name="Budget",
                    text_as_html=(
                        "<table><tr><th>Name</th><th>Score</th></tr>"
                        "<tr><td>Alice</td><td>95</td></tr></table>"
                    ),
                ),
                text="Name Score Alice 95",
            )
        ],
    )
    engine = create_database_engine(settings)
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    payload = b"fake-xlsx"
    document, job = seed_job(session_factory, file_name="budget.xlsx", payload=payload)
    storage_path = Path(settings.local_storage_path) / document.storage_key
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    storage_path.write_bytes(payload)

    result = process_document_ingest(job.id)

    with session_factory() as session:
        refreshed_document = session.get(Document, document.id)
        refreshed_job = session.get(IngestJob, job.id)
        refreshed_chunks = session.query(DocumentChunk).filter(DocumentChunk.document_id == document.id).all()
        assert result == "succeeded"
        assert refreshed_document is not None
        assert refreshed_document.status == DocumentStatus.ready
        assert refreshed_job is not None
        assert refreshed_job.status == IngestJobStatus.succeeded
        assert any(chunk.structure_kind == ChunkStructureKind.table for chunk in refreshed_chunks)
        assert refreshed_job.parent_chunk_count == 1
        assert refreshed_job.child_chunk_count == 1
        assert len(refreshed_chunks) == 2
        assert refreshed_chunks[0].content


def test_process_document_ingest_supports_docx(monkeypatch, tmp_path: Path) -> None:
    """DOCX parser 應能將文件推進到 ready 並寫出 text/table chunks。"""

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

    settings = build_settings(tmp_path)
    monkeypatch.setattr("worker.tasks.ingest.get_settings", lambda: settings)
    monkeypatch.setattr(
        "worker.parsers._extract_docx_elements_with_unstructured",
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
    engine = create_database_engine(settings)
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    payload = b"fake-docx"
    document, job = seed_job(session_factory, file_name="plan.docx", payload=payload)
    storage_path = Path(settings.local_storage_path) / document.storage_key
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    storage_path.write_bytes(payload)

    result = process_document_ingest(job.id)

    with session_factory() as session:
        refreshed_document = session.get(Document, document.id)
        refreshed_job = session.get(IngestJob, job.id)
        refreshed_chunks = session.query(DocumentChunk).filter(DocumentChunk.document_id == document.id).all()
        assert result == "succeeded"
        assert refreshed_document is not None
        assert refreshed_document.status == DocumentStatus.ready
        assert refreshed_job is not None
        assert refreshed_job.status == IngestJobStatus.succeeded
        assert any(chunk.structure_kind == ChunkStructureKind.table for chunk in refreshed_chunks)


def test_process_document_ingest_supports_pptx(monkeypatch, tmp_path: Path) -> None:
    """PPTX parser 應能將文件推進到 ready 並寫出文字 chunks。"""

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

    settings = build_settings(tmp_path)
    monkeypatch.setattr("worker.tasks.ingest.get_settings", lambda: settings)
    monkeypatch.setattr(
        "worker.parsers._extract_pptx_elements_with_unstructured",
        lambda *, payload: [
            _FakeElement(category="Title", text="Quarterly Review", metadata=_FakeMetadata()),
            _FakeElement(category="ListItem", text="Revenue up 15%", metadata=_FakeMetadata()),
        ],
    )
    engine = create_database_engine(settings)
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    payload = b"fake-pptx"
    document, job = seed_job(session_factory, file_name="review.pptx", payload=payload)
    storage_path = Path(settings.local_storage_path) / document.storage_key
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    storage_path.write_bytes(payload)

    result = process_document_ingest(job.id)

    with session_factory() as session:
        refreshed_document = session.get(Document, document.id)
        refreshed_job = session.get(IngestJob, job.id)
        refreshed_chunks = session.query(DocumentChunk).filter(DocumentChunk.document_id == document.id).all()
        assert result == "succeeded"
        assert refreshed_document is not None
        assert refreshed_document.status == DocumentStatus.ready
        assert refreshed_job is not None
        assert refreshed_job.status == IngestJobStatus.succeeded
        assert all(chunk.structure_kind == ChunkStructureKind.text for chunk in refreshed_chunks)


def test_process_document_ingest_supports_llamaparse_pdf(monkeypatch, tmp_path: Path) -> None:
    """llamaparse provider 應能將 Markdown 結果交回既有 chunking 流程。"""

    settings = build_settings(tmp_path)
    settings.pdf_parser_provider = "llamaparse"
    settings.llamaparse_api_key = "test-key"
    monkeypatch.setattr("worker.tasks.ingest.get_settings", lambda: settings)
    monkeypatch.setattr(
        "worker.parsers._extract_pdf_markdown_with_llamaparse",
        lambda *, payload, pdf_config: "# PDF Report\n\n| Name | Score |\n| --- | --- |\n| Alice | 95 |",
    )
    engine = create_database_engine(settings)
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    document, job = seed_job(session_factory, file_name="deck.pdf", payload=MINIMAL_TEXT_PDF)
    storage_path = Path(settings.local_storage_path) / document.storage_key
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    storage_path.write_bytes(MINIMAL_TEXT_PDF)

    result = process_document_ingest(job.id)

    with session_factory() as session:
        refreshed_document = session.get(Document, document.id)
        refreshed_job = session.get(IngestJob, job.id)
        refreshed_chunks = session.query(DocumentChunk).filter(DocumentChunk.document_id == document.id).all()
        assert result == "succeeded"
        assert refreshed_document is not None
        assert refreshed_document.status == DocumentStatus.ready
        assert refreshed_job is not None
        assert refreshed_job.status == IngestJobStatus.succeeded
        assert any(chunk.structure_kind == ChunkStructureKind.table for chunk in refreshed_chunks)


def test_process_document_ingest_truncates_chunk_heading_and_preview(monkeypatch, tmp_path: Path) -> None:
    """ingest 寫入 chunk 時應裁切過長 heading 與 content preview，避免超出 schema。"""

    settings = build_settings(tmp_path)
    settings.chunk_content_preview_length = 400
    monkeypatch.setattr("worker.tasks.ingest.get_settings", lambda: settings)
    engine = create_database_engine(settings)
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    long_heading = "H" * 320
    long_body = "A" * 420
    payload = f"# {long_heading}\n{long_body}".encode()
    document, job = seed_job(session_factory, file_name="long-heading.md", payload=payload)
    storage_path = Path(settings.local_storage_path) / document.storage_key
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    storage_path.write_bytes(payload)

    result = process_document_ingest(job.id)

    with session_factory() as session:
        stored_chunks = (
            session.query(DocumentChunk)
            .filter(DocumentChunk.document_id == document.id)
            .order_by(DocumentChunk.position.asc())
            .all()
        )
        assert result == "succeeded"
        assert stored_chunks
        assert all(chunk.heading == long_heading[:255] for chunk in stored_chunks)
        assert all(len(chunk.content_preview) == 255 for chunk in stored_chunks)


def test_process_document_ingest_marks_failed_for_llamaparse_missing_key(monkeypatch, tmp_path: Path) -> None:
    """llamaparse provider 缺少 API key 時應轉為受控 failed。"""

    settings = build_settings(tmp_path)
    settings.pdf_parser_provider = "llamaparse"
    monkeypatch.setattr("worker.tasks.ingest.get_settings", lambda: settings)
    engine = create_database_engine(settings)
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    document, job = seed_job(session_factory, file_name="deck.pdf", payload=MINIMAL_TEXT_PDF)
    storage_path = Path(settings.local_storage_path) / document.storage_key
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    storage_path.write_bytes(MINIMAL_TEXT_PDF)

    result = process_document_ingest(job.id)

    with session_factory() as session:
        refreshed_document = session.get(Document, document.id)
        refreshed_job = session.get(IngestJob, job.id)
        refreshed_chunk_count = session.query(DocumentChunk).filter(DocumentChunk.document_id == document.id).count()
        assert result == "failed"
        assert refreshed_document is not None
        assert refreshed_document.status == DocumentStatus.failed
        assert refreshed_job is not None
        assert refreshed_job.status == IngestJobStatus.failed
        assert refreshed_job.error_message is not None
        assert (
            "LLAMAPARSE_API_KEY" in refreshed_job.error_message
            or "llama-parse" in refreshed_job.error_message.lower()
        )
        assert refreshed_chunk_count == 0


def test_process_document_ingest_skips_non_queued_job(monkeypatch, tmp_path: Path) -> None:
    """非 queued 的 job 不應重複處理。"""

    settings = build_settings(tmp_path)
    monkeypatch.setattr("worker.tasks.ingest.get_settings", lambda: settings)
    engine = create_database_engine(settings)
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    document, job = seed_job(
        session_factory,
        file_name="notes.md",
        payload=b"# Title\ncontent",
        job_status=IngestJobStatus.processing,
    )

    result = process_document_ingest(job.id)

    with session_factory() as session:
        refreshed_document = session.get(Document, document.id)
        refreshed_job = session.get(IngestJob, job.id)
        assert result == "job-skipped"
        assert refreshed_document is not None
        assert refreshed_document.status == DocumentStatus.uploaded
        assert refreshed_job is not None
        assert refreshed_job.status == IngestJobStatus.processing


def test_reprocessing_replaces_existing_chunks(monkeypatch, tmp_path: Path) -> None:
    """同一文件再處理時應替換舊 chunks，而不是殘留舊資料。"""

    settings = build_settings(tmp_path)
    monkeypatch.setattr("worker.tasks.ingest.get_settings", lambda: settings)
    engine = create_database_engine(settings)
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    document, job = seed_job(session_factory, file_name="notes.md", payload=b"# Title\ncontent")
    storage_path = Path(settings.local_storage_path) / document.storage_key
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    storage_path.write_bytes(b"# Title\ncontent")

    assert process_document_ingest(job.id) == "succeeded"

    with session_factory() as session:
        original_chunk_ids = {
            chunk.id for chunk in session.query(DocumentChunk).filter(DocumentChunk.document_id == document.id).all()
        }
        refreshed_document = session.get(Document, document.id)
        assert refreshed_document is not None
        refreshed_document.status = DocumentStatus.uploaded
        second_job = IngestJob(id="job-2", document_id=document.id, status=IngestJobStatus.queued)
        session.add(second_job)
        session.commit()

    storage_path.write_bytes(b"# Title\nupdated\n\n## Next\nmore")
    assert process_document_ingest("job-2") == "succeeded"

    with session_factory() as session:
        refreshed_chunk_ids = {
            chunk.id for chunk in session.query(DocumentChunk).filter(DocumentChunk.document_id == document.id).all()
        }
        assert original_chunk_ids.isdisjoint(refreshed_chunk_ids)


def test_build_chunk_tree_merges_short_parent_with_following_section() -> None:
    """過短 parent section 應在切 child 前先與後續 section 合併。"""

    text = "# Short\nshort\n\n## Long\n" + ("A" * 400)

    settings = build_settings(Path("/tmp"))
    result = build_chunk_tree(
        parsed_document=parse_document(file_name="notes.md", payload=text.encode()),
        config=build_chunking_config(settings),
    )

    assert len(result.parent_chunks) == 1
    assert result.parent_chunks[0].heading == "Short / Long"
    assert "short" in result.parent_chunks[0].content
    assert "A" * 50 in result.parent_chunks[0].content
    assert len(result.child_chunks) == 1


def test_build_chunk_tree_keeps_merging_until_parent_reaches_threshold() -> None:
    """過短 parent 應持續合併，而不是只做一次相鄰合併。"""

    text = "# One\n" + ("A" * 260) + "\n\n## Two\n" + ("B" * 280) + "\n\n## Three\n" + ("C" * 300)

    settings = build_settings(Path("/tmp"))
    settings.chunk_min_parent_section_length = 800
    result = build_chunk_tree(
        parsed_document=parse_document(file_name="notes.md", payload=text.encode()),
        config=build_chunking_config(settings),
    )

    assert len(result.parent_chunks) == 1
    assert result.parent_chunks[0].heading == "One / Two / Three"
    assert len(result.parent_chunks[0].content) >= 800


def test_build_chunk_tree_uses_langchain_child_splitter_with_stable_offsets() -> None:
    """LangChain child splitter 應保留穩定順序與正確 offsets。"""

    repeated_sentence = ("alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu " * 20).strip()
    text = f"# Intro\n{repeated_sentence}"

    settings = build_settings(Path("/tmp"))
    settings.chunk_target_child_size = 120
    settings.chunk_child_overlap = 20

    result = build_chunk_tree(
        parsed_document=parse_document(file_name="notes.md", payload=text.encode()),
        config=build_chunking_config(settings),
    )

    assert len(result.parent_chunks) == 1
    assert len(result.child_chunks) >= 2

    parent = result.parent_chunks[0]
    previous_end = -1
    for index, child in enumerate(result.child_chunks):
        assert child.child_index == index
        assert child.content == child.content.strip()
        assert child.start_offset < child.end_offset
        assert child.start_offset >= parent.start_offset
        assert child.end_offset <= parent.end_offset
        relative_start = child.start_offset - parent.start_offset
        relative_end = child.end_offset - parent.start_offset
        assert parent.content[relative_start:relative_end] == child.content
        assert child.start_offset > previous_end - settings.chunk_child_overlap
        previous_end = child.end_offset


def test_build_chunk_tree_preserves_markdown_table_as_table_parent() -> None:
    """Markdown table 應形成獨立 table parent，且不與前後文字合併。"""

    text = "\n".join(
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
    )

    settings = build_settings(Path("/tmp"))
    settings.chunk_min_parent_section_length = 500
    result = build_chunk_tree(
        parsed_document=parse_document(file_name="report.md", payload=text.encode()),
        config=build_chunking_config(settings),
    )

    assert len(result.parent_chunks) == 3
    assert [chunk.structure_kind for chunk in result.parent_chunks] == ["text", "table", "text"]


def test_build_chunk_tree_consolidates_short_pdf_text_blocks_with_same_heading() -> None:
    """PDF source 的同 heading 短 text blocks 應在 parent 建立前先 consolidation。"""

    parsed_document = ParsedDocument(
        normalized_text="Intro A\n\nIntro B\n\n| Name | Score |\n| --- | --- |\n| Alice | 95 |",
        source_format="pdf",
        blocks=[
            ParsedBlock(
                block_kind="text",
                heading="Overview",
                content="Intro A",
                start_offset=0,
                end_offset=7,
            ),
            ParsedBlock(
                block_kind="text",
                heading="Overview",
                content="Intro B",
                start_offset=9,
                end_offset=16,
            ),
            ParsedBlock(
                block_kind="table",
                heading="Overview",
                content="| Name | Score |\n| --- | --- |\n| Alice | 95 |",
                start_offset=18,
                end_offset=64,
            ),
        ],
    )

    settings = build_settings(Path("/tmp"))
    settings.chunk_min_parent_section_length = 800
    result = build_chunk_tree(parsed_document=parsed_document, config=build_chunking_config(settings))

    assert len(result.parent_chunks) == 2
    assert result.parent_chunks[0].structure_kind == "text"
    assert result.parent_chunks[0].content == "Intro A\n\nIntro B"
    assert result.parent_chunks[1].structure_kind == "table"
    table_parent = result.parent_chunks[1]
    assert table_parent.heading == "Overview"
    assert "| Alice | 95 |" in table_parent.content


def test_build_chunk_tree_clusters_pdf_text_table_text_under_same_heading() -> None:
    """PDF 的 `text -> table -> text` 短區塊應合併為單一 parent cluster。"""

    parsed_document = ParsedDocument(
        normalized_text="Intro note\n\n| Name | Score |\n| --- | --- |\n| Alice | 95 |\n\nClosing note",
        source_format="pdf",
        blocks=[
            ParsedBlock(
                block_kind="text",
                heading="Overview",
                content="Intro note",
                start_offset=0,
                end_offset=10,
            ),
            ParsedBlock(
                block_kind="table",
                heading="Overview",
                content="| Name | Score |\n| --- | --- |\n| Alice | 95 |",
                start_offset=12,
                end_offset=58,
            ),
            ParsedBlock(
                block_kind="text",
                heading="Overview",
                content="Closing note",
                start_offset=60,
                end_offset=72,
            ),
        ],
    )

    settings = build_settings(Path("/tmp"))
    settings.chunk_min_parent_section_length = 800
    result = build_chunk_tree(parsed_document=parsed_document, config=build_chunking_config(settings))

    assert len(result.parent_chunks) == 1
    parent = result.parent_chunks[0]
    assert parent.structure_kind == "text"
    assert parent.heading == "Overview"
    assert "Intro note" in parent.content
    assert "| Alice | 95 |" in parent.content
    assert "Closing note" in parent.content

    assert [chunk.structure_kind for chunk in result.child_chunks] == ["text", "table", "text"]
    assert [chunk.child_index for chunk in result.child_chunks] == [0, 1, 2]
    for child in result.child_chunks:
        relative_start = child.start_offset - parent.start_offset
        relative_end = child.end_offset - parent.start_offset
        assert parent.content[relative_start:relative_end] == child.content


def test_build_chunk_tree_splits_large_table_by_row_group_and_repeats_header() -> None:
    """大型表格應依 row groups 切成多個 table child，且每個 child 重複表頭。"""

    rows = [f"| item-{index} | value-{index} |" for index in range(5)]
    table_text = "\n".join(
        [
            "| Name | Value |",
            "| --- | --- |",
            *rows,
        ]
    )

    settings = build_settings(Path("/tmp"))
    settings.chunk_table_preserve_max_chars = 10
    settings.chunk_table_max_rows_per_child = 2
    result = build_chunk_tree(
        parsed_document=parse_document(file_name="table.md", payload=table_text.encode()),
        config=build_chunking_config(settings),
    )

    assert len(result.parent_chunks) == 1
    assert result.parent_chunks[0].structure_kind == "table"
    assert len(result.child_chunks) == 3
    for child in result.child_chunks:
        assert child.structure_kind == "table"
        assert child.content.splitlines()[0] == "| Name | Value |"
        assert child.content.splitlines()[1] == "| --- | --- |"
    assert "| item-0 | value-0 |" in result.child_chunks[0].content
    assert "| item-2 | value-2 |" in result.child_chunks[1].content
    assert "| item-4 | value-4 |" in result.child_chunks[2].content


def test_process_document_ingest_supports_html_table_blocks(monkeypatch, tmp_path: Path) -> None:
    """HTML 文件中的 table 應被辨識為 table structure_kind。"""

    settings = build_settings(tmp_path)
    monkeypatch.setattr("worker.tasks.ingest.get_settings", lambda: settings)
    engine = create_database_engine(settings)
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    payload = b"""
    <h1>Quarterly Report</h1>
    <p>Summary paragraph</p>
    <table>
      <tr><th>Name</th><th>Score</th></tr>
      <tr><td>Alice</td><td>95</td></tr>
      <tr><td>Bob</td><td>88</td></tr>
    </table>
    <p>Closing note</p>
    """
    document, job = seed_job(session_factory, file_name="report.html", payload=payload)
    storage_path = Path(settings.local_storage_path) / document.storage_key
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    storage_path.write_bytes(payload)

    result = process_document_ingest(job.id)

    with session_factory() as session:
        refreshed_chunks = (
            session.query(DocumentChunk)
            .filter(DocumentChunk.document_id == document.id)
            .order_by(DocumentChunk.position.asc())
            .all()
        )
        assert result == "succeeded"
        assert any(chunk.structure_kind == ChunkStructureKind.table for chunk in refreshed_chunks)
