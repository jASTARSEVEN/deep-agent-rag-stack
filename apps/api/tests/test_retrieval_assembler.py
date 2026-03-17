"""Table-aware retrieval assembler 測試。"""

from pathlib import Path
from tempfile import mkdtemp
from uuid import uuid4, UUID

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.auth.verifier import CurrentPrincipal
from app.core.settings import AppSettings
from app.db.base import Base
from app.db.models import Area, AreaUserRole, ChunkStructureKind, ChunkType, Document, DocumentChunk, DocumentStatus, Role
from app.main import create_app
from app.services.retrieval import RetrievalCandidate, RetrievalResult, RetrievalTrace, retrieve_area_candidates
from app.services.retrieval_assembler import (
    AssembledRetrievalResult,
    _load_child_chunks,
    _load_parent_chunks,
    assemble_retrieval_result,
)


def _uuid() -> str:
    """建立測試用 UUID 字串。"""

    return str(uuid4())


def test_assemble_retrieval_result_merges_text_children_with_same_parent(db_session, app_settings) -> None:
    """同一 parent 的多個 text children 應合併為單一 context。"""

    area = Area(id="area-assemble-text", name="Assemble Text")
    document = Document(
        id="document-assemble-text",
        area_id=area.id,
        file_name="text.md",
        content_type="text/markdown",
        file_size=100,
        storage_key="area/document-assemble-text/text.md",
        status=DocumentStatus.ready,
    )
    parent = DocumentChunk(
        id="parent-assemble-text",
        document_id=document.id,
        parent_chunk_id=None,
        chunk_type=ChunkType.parent,
        structure_kind=ChunkStructureKind.text,
        position=0,
        section_index=0,
        child_index=None,
        heading="Section",
        content="alpha intro\n\nalpha details",
        content_preview="alpha intro",
        char_count=27,
        start_offset=0,
        end_offset=27,
    )
    child_one = DocumentChunk(
        id="child-assemble-text-1",
        document_id=document.id,
        parent_chunk_id=parent.id,
        chunk_type=ChunkType.child,
        structure_kind=ChunkStructureKind.text,
        position=1,
        section_index=0,
        child_index=0,
        heading="Section",
        content="alpha intro",
        content_preview="alpha intro",
        char_count=11,
        start_offset=0,
        end_offset=11,
        embedding=[0.1] * app_settings.embedding_dimensions,
    )
    child_two = DocumentChunk(
        id="child-assemble-text-2",
        document_id=document.id,
        parent_chunk_id=parent.id,
        chunk_type=ChunkType.child,
        structure_kind=ChunkStructureKind.text,
        position=2,
        section_index=0,
        child_index=1,
        heading="Section",
        content="alpha details",
        content_preview="alpha details",
        char_count=13,
        start_offset=13,
        end_offset=26,
        embedding=[0.1] * app_settings.embedding_dimensions,
    )
    db_session.add_all([area, document, parent, child_one, child_two])
    db_session.commit()

    retrieval_result = RetrievalResult(
        candidates=[
            _build_candidate(child_one, source="hybrid"),
            _build_candidate(child_two, source="hybrid"),
        ],
        trace=_build_trace(query="alpha"),
    )

    assembled = assemble_retrieval_result(session=db_session, settings=app_settings, retrieval_result=retrieval_result)

    assert len(assembled.assembled_contexts) == 1
    assert assembled.assembled_contexts[0].chunk_ids == [child_one.id, child_two.id]
    assert assembled.assembled_contexts[0].assembled_text == "alpha intro\n\nalpha details"
    assert [citation.chunk_id for citation in assembled.citations] == [child_one.id, child_two.id]
    assert assembled.trace.assembler.kept_chunk_ids == [child_one.id, child_two.id]


def test_load_chunk_helpers_normalize_uuid_keys_to_strings(monkeypatch) -> None:
    """chunk 補查 helper 應將 ORM 的 UUID 識別碼正規化為字串 key。

    參數：
    - `monkeypatch`：pytest monkeypatch fixture。

    回傳：
    - `None`：以斷言驗證 UUID/string lookup 相容性。
    """

    child_id = uuid4()
    parent_id = uuid4()

    class _FakeScalarResult:
        """模擬 SQLAlchemy scalar result。"""

        def __init__(self, values):
            self._values = values

        def all(self):
            """回傳預設 values。"""

            return self._values

    class _FakeSession:
        """模擬僅支援 scalars() 的 session。"""

        def __init__(self, values):
            self._values = values

        def scalars(self, _statement):
            """忽略 statement，直接回傳預設 chunks。"""

            return _FakeScalarResult(self._values)

    child = DocumentChunk(
        id=child_id,  # type: ignore[arg-type]
        document_id=uuid4(),  # type: ignore[arg-type]
        parent_chunk_id=parent_id,  # type: ignore[arg-type]
        chunk_type=ChunkType.child,
        structure_kind=ChunkStructureKind.text,
        position=1,
        section_index=0,
        child_index=0,
        heading="UUID Section",
        content="uuid content",
        content_preview="uuid content",
        char_count=12,
        start_offset=0,
        end_offset=12,
        embedding=[0.1] * 8,
    )
    parent = DocumentChunk(
        id=parent_id,  # type: ignore[arg-type]
        document_id=uuid4(),  # type: ignore[arg-type]
        parent_chunk_id=None,
        chunk_type=ChunkType.parent,
        structure_kind=ChunkStructureKind.text,
        position=0,
        section_index=0,
        child_index=None,
        heading="UUID Section",
        content="uuid content",
        content_preview="uuid content",
        char_count=12,
        start_offset=0,
        end_offset=12,
    )

    child_lookup = _load_child_chunks(session=_FakeSession([child]), chunk_ids=[str(child_id)])
    parent_lookup = _load_parent_chunks(session=_FakeSession([parent]), parent_chunk_ids=[str(parent_id)])

    assert list(child_lookup.keys()) == [str(child_id)]
    assert list(parent_lookup.keys()) == [str(parent_id)]
    assert child_lookup[str(child_id)] is child
    assert parent_lookup[str(parent_id)] is parent


def test_assemble_retrieval_result_merges_table_children_with_single_header(db_session, app_settings) -> None:
    """同一 parent 的 table children 合併時應只保留一次表頭。"""

    area = Area(id="area-assemble-table", name="Assemble Table")
    document = Document(
        id="document-assemble-table",
        area_id=area.id,
        file_name="table.md",
        content_type="text/markdown",
        file_size=100,
        storage_key="area/document-assemble-table/table.md",
        status=DocumentStatus.ready,
    )
    parent = DocumentChunk(
        id="parent-assemble-table",
        document_id=document.id,
        parent_chunk_id=None,
        chunk_type=ChunkType.parent,
        structure_kind=ChunkStructureKind.table,
        position=0,
        section_index=0,
        child_index=None,
        heading="Table Section",
        content="| item | value |\n| --- | --- |\n| alpha | 1 |\n| beta | 2 |",
        content_preview="| item | value |",
        char_count=60,
        start_offset=0,
        end_offset=60,
    )
    child_one = DocumentChunk(
        id="child-assemble-table-1",
        document_id=document.id,
        parent_chunk_id=parent.id,
        chunk_type=ChunkType.child,
        structure_kind=ChunkStructureKind.table,
        position=1,
        section_index=0,
        child_index=0,
        heading="Table Section",
        content="| item | value |\n| --- | --- |\n| alpha | 1 |",
        content_preview="| item | value |",
        char_count=46,
        start_offset=0,
        end_offset=46,
        embedding=[0.1] * app_settings.embedding_dimensions,
    )
    child_two = DocumentChunk(
        id="child-assemble-table-2",
        document_id=document.id,
        parent_chunk_id=parent.id,
        chunk_type=ChunkType.child,
        structure_kind=ChunkStructureKind.table,
        position=2,
        section_index=0,
        child_index=1,
        heading="Table Section",
        content="| item | value |\n| --- | --- |\n| beta | 2 |",
        content_preview="| item | value |",
        char_count=45,
        start_offset=47,
        end_offset=92,
        embedding=[0.1] * app_settings.embedding_dimensions,
    )
    db_session.add_all([area, document, parent, child_one, child_two])
    db_session.commit()

    retrieval_result = RetrievalResult(
        candidates=[
            _build_candidate(child_two, source="hybrid", rrf_rank=1),
            _build_candidate(child_one, source="hybrid", rrf_rank=2),
        ],
        trace=_build_trace(query="table"),
    )

    assembled = assemble_retrieval_result(session=db_session, settings=app_settings, retrieval_result=retrieval_result)

    assert len(assembled.assembled_contexts) == 1
    assert assembled.assembled_contexts[0].chunk_ids == [child_one.id, child_two.id]
    assert assembled.assembled_contexts[0].assembled_text.count("| item | value |") == 1
    assert "| alpha | 1 |" in assembled.assembled_contexts[0].assembled_text
    assert "| beta | 2 |" in assembled.assembled_contexts[0].assembled_text


def test_assemble_retrieval_result_keeps_text_and_table_separate(db_session, app_settings) -> None:
    """text 與 table 命中不可混成同一 context。"""

    area = Area(id="area-assemble-mixed", name="Assemble Mixed")
    document = Document(
        id="document-assemble-mixed",
        area_id=area.id,
        file_name="mixed.md",
        content_type="text/markdown",
        file_size=100,
        storage_key="area/document-assemble-mixed/mixed.md",
        status=DocumentStatus.ready,
    )
    text_parent = DocumentChunk(
        id="parent-assemble-text-mixed",
        document_id=document.id,
        parent_chunk_id=None,
        chunk_type=ChunkType.parent,
        structure_kind=ChunkStructureKind.text,
        position=0,
        section_index=0,
        child_index=None,
        heading="Text",
        content="alpha paragraph",
        content_preview="alpha paragraph",
        char_count=15,
        start_offset=0,
        end_offset=15,
    )
    table_parent = DocumentChunk(
        id="parent-assemble-table-mixed",
        document_id=document.id,
        parent_chunk_id=None,
        chunk_type=ChunkType.parent,
        structure_kind=ChunkStructureKind.table,
        position=1,
        section_index=1,
        child_index=None,
        heading="Table",
        content="| item | value |\n| --- | --- |\n| alpha | 1 |",
        content_preview="| item | value |",
        char_count=46,
        start_offset=17,
        end_offset=63,
    )
    text_child = DocumentChunk(
        id="child-assemble-text-mixed",
        document_id=document.id,
        parent_chunk_id=text_parent.id,
        chunk_type=ChunkType.child,
        structure_kind=ChunkStructureKind.text,
        position=2,
        section_index=0,
        child_index=0,
        heading="Text",
        content="alpha paragraph",
        content_preview="alpha paragraph",
        char_count=15,
        start_offset=0,
        end_offset=15,
        embedding=[0.1] * app_settings.embedding_dimensions,
    )
    table_child = DocumentChunk(
        id="child-assemble-table-mixed",
        document_id=document.id,
        parent_chunk_id=table_parent.id,
        chunk_type=ChunkType.child,
        structure_kind=ChunkStructureKind.table,
        position=3,
        section_index=1,
        child_index=0,
        heading="Table",
        content="| item | value |\n| --- | --- |\n| alpha | 1 |",
        content_preview="| item | value |",
        char_count=46,
        start_offset=17,
        end_offset=63,
        embedding=[0.1] * app_settings.embedding_dimensions,
    )
    db_session.add_all([area, document, text_parent, table_parent, text_child, table_child])
    db_session.commit()

    retrieval_result = RetrievalResult(
        candidates=[
            _build_candidate(text_child, source="vector"),
            _build_candidate(table_child, source="fts", rrf_rank=2, vector_rank=None, fts_rank=1),
        ],
        trace=_build_trace(query="alpha"),
    )

    assembled = assemble_retrieval_result(session=db_session, settings=app_settings, retrieval_result=retrieval_result)

    assert len(assembled.assembled_contexts) == 2
    assert [context.structure_kind for context in assembled.assembled_contexts] == [
        ChunkStructureKind.text,
        ChunkStructureKind.table,
    ]


def test_assemble_retrieval_result_enforces_budget_and_trace(db_session, app_settings) -> None:
    """assembler 應依 context、children 與字元 budget 留下 trace。"""

    settings = app_settings.model_copy(
        update={
            "assembler_max_contexts": 1,
            "assembler_max_chars_per_context": 19,
            "assembler_max_children_per_parent": 2,
        }
    )
    area = Area(id="area-assemble-budget", name="Assemble Budget")
    document = Document(
        id="document-assemble-budget",
        area_id=area.id,
        file_name="budget.md",
        content_type="text/markdown",
        file_size=100,
        storage_key="area/document-assemble-budget/budget.md",
        status=DocumentStatus.ready,
    )
    parent_one = DocumentChunk(
        id="parent-budget-1",
        document_id=document.id,
        parent_chunk_id=None,
        chunk_type=ChunkType.parent,
        structure_kind=ChunkStructureKind.text,
        position=0,
        section_index=0,
        child_index=None,
        heading="Budget A",
        content="alpha one\n\nalpha two\n\nalpha three",
        content_preview="alpha one",
        char_count=31,
        start_offset=0,
        end_offset=31,
    )
    parent_two = DocumentChunk(
        id="parent-budget-2",
        document_id=document.id,
        parent_chunk_id=None,
        chunk_type=ChunkType.parent,
        structure_kind=ChunkStructureKind.text,
        position=1,
        section_index=1,
        child_index=None,
        heading="Budget B",
        content="beta final",
        content_preview="beta final",
        char_count=10,
        start_offset=33,
        end_offset=43,
    )
    child_one = _build_ready_child(
        app_settings=settings,
        document_id=document.id,
        parent_chunk_id=parent_one.id,
        chunk_id="child-budget-1",
        position=2,
        section_index=0,
        child_index=0,
        heading="Budget A",
        content="alpha one",
        start_offset=0,
        end_offset=9,
    )
    child_two = _build_ready_child(
        app_settings=settings,
        document_id=document.id,
        parent_chunk_id=parent_one.id,
        chunk_id="child-budget-2",
        position=3,
        section_index=0,
        child_index=1,
        heading="Budget A",
        content="alpha two",
        start_offset=11,
        end_offset=20,
    )
    child_three = _build_ready_child(
        app_settings=settings,
        document_id=document.id,
        parent_chunk_id=parent_one.id,
        chunk_id="child-budget-3",
        position=4,
        section_index=0,
        child_index=2,
        heading="Budget A",
        content="alpha three",
        start_offset=22,
        end_offset=33,
    )
    child_four = _build_ready_child(
        app_settings=settings,
        document_id=document.id,
        parent_chunk_id=parent_two.id,
        chunk_id="child-budget-4",
        position=5,
        section_index=1,
        child_index=0,
        heading="Budget B",
        content="beta final",
        start_offset=35,
        end_offset=45,
    )
    db_session.add_all([area, document, parent_one, parent_two, child_one, child_two, child_three, child_four])
    db_session.commit()

    retrieval_result = RetrievalResult(
        candidates=[
            _build_candidate(child_one, source="hybrid"),
            _build_candidate(child_two, source="hybrid", rrf_rank=2),
            _build_candidate(child_three, source="hybrid", rrf_rank=3),
            _build_candidate(child_four, source="hybrid", rrf_rank=4),
        ],
        trace=_build_trace(query="alpha"),
    )

    assembled = assemble_retrieval_result(session=db_session, settings=settings, retrieval_result=retrieval_result)

    assert len(assembled.assembled_contexts) == 1
    assert assembled.assembled_contexts[0].chunk_ids == [child_one.id, child_two.id]
    assert len(assembled.assembled_contexts[0].assembled_text) == 19
    assert assembled.trace.assembler.dropped_chunk_ids == [child_three.id, child_four.id]
    assert assembled.trace.assembler.contexts[0].truncated is True


def test_assemble_retrieval_result_preserves_citation_offsets(db_session, app_settings) -> None:
    """citation metadata 應保留原始 child offsets。"""

    area = Area(id="area-assemble-citation", name="Assemble Citation")
    document = Document(
        id="document-assemble-citation",
        area_id=area.id,
        file_name="citation.md",
        content_type="text/markdown",
        file_size=100,
        storage_key="area/document-assemble-citation/citation.md",
        status=DocumentStatus.ready,
    )
    parent = DocumentChunk(
        id="parent-assemble-citation",
        document_id=document.id,
        parent_chunk_id=None,
        chunk_type=ChunkType.parent,
        structure_kind=ChunkStructureKind.text,
        position=0,
        section_index=0,
        child_index=None,
        heading="Citation",
        content="alpha excerpt",
        content_preview="alpha excerpt",
        char_count=13,
        start_offset=0,
        end_offset=13,
    )
    child = _build_ready_child(
        app_settings=app_settings,
        document_id=document.id,
        parent_chunk_id=parent.id,
        chunk_id="child-assemble-citation",
        position=1,
        section_index=0,
        child_index=0,
        heading="Citation",
        content="alpha excerpt",
        start_offset=2,
        end_offset=11,
    )
    db_session.add_all([area, document, parent, child])
    db_session.commit()

    assembled = assemble_retrieval_result(
        session=db_session,
        settings=app_settings,
        retrieval_result=RetrievalResult(
            candidates=[_build_candidate(child, source="hybrid")],
            trace=_build_trace(query="alpha"),
        ),
    )

    assert assembled.citations[0].start_offset == 2
    assert assembled.citations[0].end_offset == 11
    assert assembled.citations[0].excerpt == "alpha excerpt"


def test_assemble_retrieval_result_works_after_rerank_fallback(db_session, app_settings, monkeypatch) -> None:
    """rerank fail-open fallback 後仍應可組裝 assembler 結果。"""

    area = Area(id="area-assemble-fallback", name="Assemble Fallback")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-reader", role=Role.reader))
    document = Document(
        id="document-assemble-fallback",
        area_id=area.id,
        file_name="fallback.md",
        content_type="text/markdown",
        file_size=100,
        storage_key="area/document-assemble-fallback/fallback.md",
        status=DocumentStatus.ready,
    )
    parent = DocumentChunk(
        id="parent-assemble-fallback",
        document_id=document.id,
        parent_chunk_id=None,
        chunk_type=ChunkType.parent,
        structure_kind=ChunkStructureKind.text,
        position=0,
        section_index=0,
        child_index=None,
        heading="Fallback",
        content="fallback alpha",
        content_preview="fallback alpha",
        char_count=14,
        start_offset=0,
        end_offset=14,
    )
    child = _build_ready_child(
        app_settings=app_settings,
        document_id=document.id,
        parent_chunk_id=parent.id,
        chunk_id="child-assemble-fallback",
        position=1,
        section_index=0,
        child_index=0,
        heading="Fallback",
        content="fallback alpha",
        start_offset=0,
        end_offset=14,
    )
    db_session.add_all([document, parent, child])
    db_session.commit()

    class FailingRerankProvider:
        """固定拋錯的 rerank provider 測試替身。"""

        def rerank(self, *, query: str, documents: list[object], top_n: int):
            """模擬 provider runtime failure。

            參數：
            - `query`：使用者查詢文字。
            - `documents`：送入 provider 的文件清單。
            - `top_n`：最多回傳筆數。

            回傳：
            - 不會回傳；固定拋出錯誤。
            """

            raise RuntimeError("boom")

    monkeypatch.setattr("app.services.retrieval.build_rerank_provider", lambda settings: FailingRerankProvider())

    retrieval_result = retrieve_area_candidates(
        session=db_session,
        principal=CurrentPrincipal(sub="user-reader", groups=("/group/reader",)),
        settings=app_settings,
        area_id=area.id,
        query="alpha",
    )
    assembled = assemble_retrieval_result(session=db_session, settings=app_settings, retrieval_result=retrieval_result)

    assert retrieval_result.candidates[0].rerank_applied is False
    assert assembled.assembled_contexts[0].chunk_ids == [child.id]


def test_upload_to_assembly_pipeline_supports_markdown_and_html() -> None:
    """upload -> ingest -> retrieval -> assembly 應可處理 Markdown 與 HTML。"""

    markdown_settings = _build_pipeline_settings(
        chunk_table_preserve_max_chars=40,
        chunk_table_max_rows_per_child=1,
    )
    markdown_assembled = _run_upload_to_assembly_flow(
        settings=markdown_settings,
        file_name="pipeline.md",
        content_type="text/markdown",
        payload=(
            b"# Intro\nalpha paragraph\n\n## Table\n| item | value |\n| --- | --- |\n"
            b"| alpha | 1 |\n| beta | 2 |\n"
        ),
        query="alpha",
    )
    assert markdown_assembled.assembled_contexts
    assert any(context.structure_kind == ChunkStructureKind.table for context in markdown_assembled.assembled_contexts)
    assert any(citation.structure_kind == ChunkStructureKind.table for citation in markdown_assembled.citations)

    html_settings = _build_pipeline_settings()
    html_assembled = _run_upload_to_assembly_flow(
        settings=html_settings,
        file_name="pipeline.html",
        content_type="text/html",
        payload=(
            b"<h1>Intro</h1><p>alpha paragraph</p><h2>Table</h2>"
            b"<table><tr><th>item</th><th>value</th></tr><tr><td>alpha</td><td>1</td></tr></table>"
        ),
        query="alpha",
    )
    assert html_assembled.assembled_contexts
    assert any(context.structure_kind == ChunkStructureKind.table for context in html_assembled.assembled_contexts)


def _build_candidate(
    chunk: DocumentChunk,
    *,
    source: str,
    rrf_rank: int = 1,
    vector_rank: int | None = 1,
    fts_rank: int | None = 1,
) -> RetrievalCandidate:
    """建立測試用 retrieval candidate。

    參數：
    - `chunk`：對應的 child chunk。
    - `source`：candidate 來源。
    - `rrf_rank`：RRF 排名。
    - `vector_rank`：vector recall 排名。
    - `fts_rank`：FTS recall 排名。

    回傳：
    - `RetrievalCandidate`：供 assembler 測試使用的 candidate。
    """

    return RetrievalCandidate(
        document_id=chunk.document_id,
        chunk_id=chunk.id,
        parent_chunk_id=chunk.parent_chunk_id,
        structure_kind=chunk.structure_kind,
        heading=chunk.heading,
        content=chunk.content,
        start_offset=chunk.start_offset,
        end_offset=chunk.end_offset,
        source=source,
        vector_rank=vector_rank,
        fts_rank=fts_rank,
        rrf_rank=rrf_rank,
        rrf_score=1.0 / (60 + rrf_rank),
        rerank_rank=rrf_rank,
        rerank_score=1.0,
        rerank_applied=True,
    )


def _build_trace(*, query: str) -> RetrievalTrace:
    """建立測試用 retrieval trace。

    參數：
    - `query`：查詢文字。

    回傳：
    - `RetrievalTrace`：最小 trace 結構。
    """

    return RetrievalTrace(
        query=query,
        vector_top_k=8,
        fts_top_k=8,
        max_candidates=12,
        rerank_top_n=6,
        candidates=[],
    )


def _build_ready_child(
    *,
    app_settings: AppSettings,
    document_id: str,
    parent_chunk_id: str,
    chunk_id: str,
    position: int,
    section_index: int,
    child_index: int,
    heading: str,
    content: str,
    start_offset: int,
    end_offset: int,
) -> DocumentChunk:
    """建立測試用 ready child chunk。

    參數：
    - `app_settings`：測試設定，用於 embedding 維度。
    - `document_id`：文件識別碼。
    - `parent_chunk_id`：parent chunk 識別碼。
    - `chunk_id`：child chunk 識別碼。
    - `position`：chunk 排序位置。
    - `section_index`：section 順序。
    - `child_index`：parent 下 child 順序。
    - `heading`：段落標題。
    - `content`：chunk 內容。
    - `start_offset`：起始 offset。
    - `end_offset`：結束 offset。

    回傳：
    - `DocumentChunk`：可直接寫入資料庫的 child chunk。
    """

    return DocumentChunk(
        id=chunk_id,
        document_id=document_id,
        parent_chunk_id=parent_chunk_id,
        chunk_type=ChunkType.child,
        structure_kind=ChunkStructureKind.table if content.strip().startswith("|") else ChunkStructureKind.text,
        position=position,
        section_index=section_index,
        child_index=child_index,
        heading=heading,
        content=content,
        content_preview=content[:120],
        char_count=len(content),
        start_offset=start_offset,
        end_offset=end_offset,
        embedding=[0.1] * app_settings.embedding_dimensions,
    )


def _build_pipeline_settings(**updates: object) -> AppSettings:
    """建立 upload -> assembly 測試使用的設定。

    參數：
    - `updates`：要覆蓋的設定欄位。

    回傳：
    - `AppSettings`：供近似 E2E 使用的測試設定。
    """

    temp_root = Path(mkdtemp(prefix="deep-agent-rag-stack-api-"))
    base_settings = AppSettings(
        API_SERVICE_NAME="deep-agent-api-test",
        API_VERSION="0.1.0-test",
        API_HOST="127.0.0.1",
        API_PORT=18000,
        API_CORS_ORIGINS="http://localhost:13000",
        DATABASE_URL=f"sqlite+pysqlite:///{temp_root / 'test.db'}",
        DATABASE_ECHO=False,
        REDIS_URL="redis://redis:6379/0",
        STORAGE_BACKEND="filesystem",
        MINIO_ENDPOINT="http://minio:9000",
        MINIO_ACCESS_KEY="minio",
        MINIO_SECRET_KEY="minio123",
        MINIO_BUCKET="documents",
        LOCAL_STORAGE_PATH=temp_root / "storage",
        MAX_UPLOAD_SIZE_BYTES=2048,
        CHUNK_MIN_PARENT_SECTION_LENGTH=10,
        CHUNK_TARGET_CHILD_SIZE=40,
        CHUNK_CHILD_OVERLAP=0,
        CHUNK_CONTENT_PREVIEW_LENGTH=120,
        CHUNK_TXT_PARENT_GROUP_SIZE=4,
        CHUNK_TABLE_PRESERVE_MAX_CHARS=4000,
        CHUNK_TABLE_MAX_ROWS_PER_CHILD=20,
        CELERY_BROKER_URL="redis://redis:6379/0",
        CELERY_RESULT_BACKEND="redis://redis:6379/1",
        INGEST_INLINE_MODE=True,
        EMBEDDING_PROVIDER="deterministic",
        EMBEDDING_MODEL="text-embedding-3-small",
        EMBEDDING_DIMENSIONS=1536,
        RETRIEVAL_VECTOR_TOP_K=8,
        RETRIEVAL_FTS_TOP_K=8,
        RETRIEVAL_MAX_CANDIDATES=12,
        RETRIEVAL_RRF_K=60,
        RETRIEVAL_HNSW_EF_SEARCH=100,
        RERANK_PROVIDER="deterministic",
        RERANK_MODEL="rerank-v3.5",
        RERANK_TOP_N=6,
        RERANK_MAX_CHARS_PER_DOC=2000,
        ASSEMBLER_MAX_CONTEXTS=6,
        ASSEMBLER_MAX_CHARS_PER_CONTEXT=2500,
        ASSEMBLER_MAX_CHILDREN_PER_PARENT=3,
        KEYCLOAK_URL="http://keycloak:8080",
        KEYCLOAK_ISSUER="http://localhost:18080/realms/deep-agent-dev",
        KEYCLOAK_JWKS_URL="http://keycloak:8080/realms/deep-agent-dev/protocol/openid-connect/certs",
        KEYCLOAK_GROUPS_CLAIM="groups",
        AUTH_TEST_MODE=True,
    )
    return base_settings.model_copy(update=updates)


def _run_upload_to_assembly_flow(
    *,
    settings: AppSettings,
    file_name: str,
    content_type: str,
    payload: bytes,
    query: str,
) -> AssembledRetrievalResult:
    """執行 upload -> retrieval -> assembly 的近似 E2E 流程。

    參數：
    - `settings`：此次測試使用的 API 設定。
    - `file_name`：上傳檔名。
    - `content_type`：上傳 MIME 類型。
    - `payload`：上傳檔案內容。
    - `query`：檢索查詢文字。

    回傳：
    - `AssembledRetrievalResult`：組裝後的 contexts 與 citations。
    """

    application = create_app(settings)
    Base.metadata.create_all(bind=application.state.engine)
    try:
        session = application.state.session_factory()
        area = Area(id=_uuid(), name="Pipeline")
        area_id = area.id
        session.add(area)
        session.add(AreaUserRole(area_id=area_id, user_sub="user-maintainer", role=Role.maintainer))
        session.add(AreaUserRole(area_id=area_id, user_sub="user-reader", role=Role.reader))
        session.commit()
        session.close()

        with TestClient(application) as client:
            response = client.post(
                f"/areas/{area_id}/documents",
                headers={"Authorization": "Bearer test::user-maintainer::/group/maintainer"},
                files={"file": (file_name, payload, content_type)},
            )
            assert response.status_code == 201
            document_id = response.json()["document"]["id"]

        session = application.state.session_factory()
        try:
            stored_document = session.get(Document, document_id)
            assert stored_document is not None
            assert stored_document.status == DocumentStatus.ready
            stored_chunks = session.scalars(select(DocumentChunk).where(DocumentChunk.document_id == document_id)).all()
            assert any(chunk.chunk_type == ChunkType.child for chunk in stored_chunks)

            retrieval_result = retrieve_area_candidates(
                session=session,
                principal=CurrentPrincipal(sub="user-reader", groups=("/group/reader",)),
                settings=settings,
                area_id=area_id,
                query=query,
            )
            return assemble_retrieval_result(session=session, settings=settings, retrieval_result=retrieval_result)
        finally:
            session.close()
    finally:
        Base.metadata.drop_all(bind=application.state.engine)
        application.state.engine.dispose()
