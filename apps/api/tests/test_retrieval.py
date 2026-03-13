"""Internal retrieval service 測試。"""

from fastapi import HTTPException
from sqlalchemy.dialects import postgresql

from app.auth.verifier import CurrentPrincipal
from app.db.models import Area, AreaUserRole, ChunkStructureKind, ChunkType, Document, DocumentChunk, DocumentStatus, Role
from app.services.retrieval import (
    _configure_postgres_hnsw_search,
    build_postgres_fts_recall_statement,
    retrieve_area_candidates,
)


def test_retrieve_area_candidates_filters_non_ready_and_parent_chunks(db_session, app_settings) -> None:
    """retrieval 應只回 ready 文件的 child chunks。"""

    area = Area(id="area-retrieval-ready", name="Retrieval Ready")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-reader", role=Role.reader))
    ready_document = Document(
        id="document-ready",
        area_id=area.id,
        file_name="ready.md",
        content_type="text/markdown",
        file_size=100,
        storage_key="area/document-ready/ready.md",
        status=DocumentStatus.ready,
    )
    uploaded_document = Document(
        id="document-uploaded",
        area_id=area.id,
        file_name="uploaded.md",
        content_type="text/markdown",
        file_size=100,
        storage_key="area/document-uploaded/uploaded.md",
        status=DocumentStatus.uploaded,
    )
    db_session.add_all([ready_document, uploaded_document])
    db_session.add_all(
        [
            DocumentChunk(
                id="chunk-parent",
                document_id=ready_document.id,
                parent_chunk_id=None,
                chunk_type=ChunkType.parent,
                structure_kind=ChunkStructureKind.text,
                position=0,
                section_index=0,
                child_index=None,
                heading="Parent",
                content="中文檢索 parent",
                content_preview="中文檢索 parent",
                char_count=11,
                start_offset=0,
                end_offset=11,
            ),
            DocumentChunk(
                id="chunk-ready-child",
                document_id=ready_document.id,
                parent_chunk_id="chunk-parent",
                chunk_type=ChunkType.child,
                structure_kind=ChunkStructureKind.text,
                position=1,
                section_index=0,
                child_index=0,
                heading="Ready Child",
                content="這是一段中文檢索內容",
                content_preview="這是一段中文檢索內容",
                char_count=10,
                start_offset=0,
                end_offset=10,
                embedding=[0.1] * app_settings.embedding_dimensions,
                fts_document="這是一段中文檢索內容",
            ),
            DocumentChunk(
                id="chunk-uploaded-child",
                document_id=uploaded_document.id,
                parent_chunk_id=None,
                chunk_type=ChunkType.child,
                structure_kind=ChunkStructureKind.text,
                position=0,
                section_index=0,
                child_index=0,
                heading="Uploaded Child",
                content="這是一段不該被看到的內容",
                content_preview="這是一段不該被看到的內容",
                char_count=12,
                start_offset=0,
                end_offset=12,
                embedding=[0.2] * app_settings.embedding_dimensions,
                fts_document="這是一段不該被看到的內容",
            ),
        ]
    )
    db_session.commit()

    candidates = retrieve_area_candidates(
        session=db_session,
        principal=CurrentPrincipal(sub="user-reader", groups=("/group/reader",)),
        settings=app_settings,
        area_id=area.id,
        query="中文檢索",
    )

    assert [candidate.chunk_id for candidate in candidates] == ["chunk-ready-child"]
    assert candidates[0].source == "hybrid"


def test_retrieve_area_candidates_returns_same_404_for_missing_and_unauthorized(db_session, app_settings) -> None:
    """未授權 area 與不存在 area 的 retrieval 都應回相同 404。"""

    area = Area(id="area-retrieval-secret", name="Retrieval Secret")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-admin", role=Role.admin))
    db_session.commit()

    outsider = CurrentPrincipal(sub="user-outsider", groups=("/group/outsider",))

    unauthorized_error: HTTPException | None = None
    missing_error: HTTPException | None = None
    try:
        retrieve_area_candidates(
            session=db_session,
            principal=outsider,
            settings=app_settings,
            area_id=area.id,
            query="secret",
        )
    except HTTPException as exc:
        unauthorized_error = exc

    try:
        retrieve_area_candidates(
            session=db_session,
            principal=outsider,
            settings=app_settings,
            area_id="missing-area",
            query="secret",
        )
    except HTTPException as exc:
        missing_error = exc

    assert unauthorized_error is not None
    assert missing_error is not None
    assert getattr(unauthorized_error, "status_code", None) == 404
    assert getattr(missing_error, "status_code", None) == 404
    assert getattr(unauthorized_error, "detail", None) == getattr(missing_error, "detail", None)


def test_build_postgres_fts_recall_statement_uses_project_text_search_config(app_settings) -> None:
    """FTS query builder 應使用專案指定的 text search config。"""

    statement = build_postgres_fts_recall_statement(settings=app_settings, area_id="area-1", query="中文 檢索")
    compiled = statement.compile(dialect=postgresql.dialect())
    compiled_sql = str(compiled)

    assert "websearch_to_tsquery" in compiled_sql
    assert "deep_agent_jieba" in str(compiled.params.values())
    assert "ts_rank_cd" in compiled_sql
    assert "@@" in compiled_sql


def test_configure_postgres_hnsw_search_sets_iterative_scan_and_ef_search(app_settings) -> None:
    """HNSW 查詢前應設定 iterative scan 與 ef_search。"""

    statements: list[tuple[str, dict[str, object] | None]] = []

    class FakeSession:
        """記錄 SQL 設定語句的最小 session 替身。"""

        def execute(self, statement, params=None) -> None:
            """記錄 execute 呼叫內容。

            參數：
            - `statement`：待執行 SQLAlchemy statement。
            - `params`：statement 綁定參數。

            回傳：
            - `None`：此替身只記錄呼叫，不實際執行 SQL。
            """

            statements.append((str(statement), params))

    _configure_postgres_hnsw_search(session=FakeSession(), settings=app_settings)  # type: ignore[arg-type]

    assert statements == [
        ("SET LOCAL hnsw.iterative_scan = 'strict_order'", None),
        ("SET LOCAL hnsw.ef_search = :ef_search", {"ef_search": app_settings.retrieval_hnsw_ef_search}),
    ]
