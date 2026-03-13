"""Internal retrieval service 與 rerank provider 測試。"""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from app.auth.verifier import CurrentPrincipal
from app.core.settings import AppSettings
from app.db.models import Area, AreaUserRole, ChunkStructureKind, ChunkType, Document, DocumentChunk, DocumentStatus, Role
from app.services.reranking import (
    CohereRerankProvider,
    DeterministicRerankProvider,
    RerankInputDocument,
    build_rerank_provider,
)
from app.services.retrieval import (
    _build_rerank_document_text,
    _configure_postgres_hnsw_search,
    build_postgres_fts_recall_statement,
    retrieve_area_candidates,
)


def test_build_rerank_provider_supports_deterministic_and_cohere(app_settings) -> None:
    """rerank provider factory 應支援 deterministic 與 Cohere。"""

    deterministic_settings = app_settings.model_copy(update={"rerank_provider": "deterministic"})
    cohere_settings = app_settings.model_copy(
        update={"rerank_provider": "cohere", "cohere_api_key": "test-key", "rerank_model": "rerank-v3.5"}
    )

    deterministic_provider = build_rerank_provider(deterministic_settings)
    cohere_provider = build_rerank_provider(cohere_settings)

    assert isinstance(deterministic_provider, DeterministicRerankProvider)
    assert isinstance(cohere_provider, CohereRerankProvider)


def test_build_rerank_provider_rejects_unsupported_provider(app_settings) -> None:
    """不支援的 rerank provider 應明確失敗。"""

    settings = app_settings.model_copy(update={"rerank_provider": "unsupported"})

    try:
        build_rerank_provider(settings)
    except ValueError as exc:
        assert "不支援的 rerank provider" in str(exc)
    else:  # pragma: no cover - 失敗時才會進來。
        raise AssertionError("預期 build_rerank_provider 應拋出 ValueError。")


def test_build_rerank_provider_requires_cohere_api_key(app_settings) -> None:
    """使用 Cohere rerank 前必須提供 API key。"""

    settings = app_settings.model_copy(update={"rerank_provider": "cohere", "cohere_api_key": None})

    try:
        build_rerank_provider(settings)
    except ValueError as exc:
        assert "COHERE_API_KEY" in str(exc)
    else:  # pragma: no cover - 失敗時才會進來。
        raise AssertionError("預期缺少 COHERE_API_KEY 時應拋出 ValueError。")


def test_retrieve_area_candidates_filters_non_ready_and_parent_chunks(db_session, app_settings) -> None:
    """retrieval 應只回 ready 文件的 child chunks，並保留 rerank metadata。"""

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
                content="這是一段中文檢索內容 中文檢索",
                content_preview="這是一段中文檢索內容 中文檢索",
                char_count=15,
                start_offset=0,
                end_offset=15,
                embedding=[0.1] * app_settings.embedding_dimensions,
                fts_document="這是一段中文檢索內容 中文檢索",
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

    result = retrieve_area_candidates(
        session=db_session,
        principal=CurrentPrincipal(sub="user-reader", groups=("/group/reader",)),
        settings=app_settings,
        area_id=area.id,
        query="中文檢索",
    )

    assert [candidate.chunk_id for candidate in result.candidates] == ["chunk-ready-child"]
    assert result.candidates[0].source == "hybrid"
    assert result.candidates[0].rrf_rank == 1
    assert result.candidates[0].rerank_rank == 1
    assert result.candidates[0].rerank_applied is True
    assert result.trace.query == "中文檢索"
    assert result.trace.candidates[0].chunk_id == "chunk-ready-child"


def test_retrieve_area_candidates_reranks_only_top_n_and_keeps_rest_in_rrf_order(db_session, app_settings) -> None:
    """rerank 應只重排前 top-n 筆，其他結果維持原 RRF 順序。"""

    settings = app_settings.model_copy(update={"rerank_top_n": 2})
    area = Area(id="area-retrieval-rerank", name="Retrieval Rerank")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-reader", role=Role.reader))
    document = Document(
        id="document-rerank",
        area_id=area.id,
        file_name="rerank.md",
        content_type="text/markdown",
        file_size=100,
        storage_key="area/document-rerank/rerank.md",
        status=DocumentStatus.ready,
    )
    db_session.add(document)
    db_session.add_all(
        [
            DocumentChunk(
                id="chunk-alpha",
                document_id=document.id,
                parent_chunk_id=None,
                chunk_type=ChunkType.child,
                structure_kind=ChunkStructureKind.text,
                position=1,
                section_index=0,
                child_index=0,
                heading="Alpha",
                content="alpha",
                content_preview="alpha",
                char_count=5,
                start_offset=0,
                end_offset=5,
                embedding=[0.1] * settings.embedding_dimensions,
                fts_document="alpha",
            ),
            DocumentChunk(
                id="chunk-beta",
                document_id=document.id,
                parent_chunk_id=None,
                chunk_type=ChunkType.child,
                structure_kind=ChunkStructureKind.text,
                position=2,
                section_index=0,
                child_index=1,
                heading="Beta",
                content="alpha alpha alpha",
                content_preview="alpha alpha alpha",
                char_count=17,
                start_offset=6,
                end_offset=23,
                embedding=[0.11] * settings.embedding_dimensions,
                fts_document="alpha alpha alpha",
            ),
            DocumentChunk(
                id="chunk-gamma",
                document_id=document.id,
                parent_chunk_id=None,
                chunk_type=ChunkType.child,
                structure_kind=ChunkStructureKind.table,
                position=3,
                section_index=0,
                child_index=2,
                heading="Gamma",
                content="| item | value |\n| --- | --- |\n| alpha | 1 |",
                content_preview="| item | value |",
                char_count=46,
                start_offset=24,
                end_offset=70,
                embedding=[0.12] * settings.embedding_dimensions,
                fts_document="alpha",
            ),
        ]
    )
    db_session.commit()

    result = retrieve_area_candidates(
        session=db_session,
        principal=CurrentPrincipal(sub="user-reader", groups=("/group/reader",)),
        settings=settings,
        area_id=area.id,
        query="alpha",
    )

    assert [candidate.chunk_id for candidate in result.candidates] == ["chunk-beta", "chunk-alpha", "chunk-gamma"]
    assert result.candidates[0].rerank_rank == 1
    assert result.candidates[1].rerank_rank == 2
    assert result.candidates[2].rerank_rank is None
    assert result.candidates[2].rerank_applied is False
    assert result.trace.rerank_top_n == 2


def test_retrieve_area_candidates_falls_back_to_rrf_when_rerank_runtime_fails(
    db_session, app_settings, monkeypatch
) -> None:
    """rerank runtime 失敗時，retrieval 應回退到 RRF 結果。"""

    area = Area(id="area-retrieval-fallback", name="Retrieval Fallback")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-reader", role=Role.reader))
    document = Document(
        id="document-fallback",
        area_id=area.id,
        file_name="fallback.md",
        content_type="text/markdown",
        file_size=100,
        storage_key="area/document-fallback/fallback.md",
        status=DocumentStatus.ready,
    )
    db_session.add(document)
    db_session.add(
        DocumentChunk(
            id="chunk-fallback",
            document_id=document.id,
            parent_chunk_id=None,
            chunk_type=ChunkType.child,
            structure_kind=ChunkStructureKind.text,
            position=1,
            section_index=0,
            child_index=0,
            heading="Fallback",
            content="fallback alpha",
            content_preview="fallback alpha",
            char_count=14,
            start_offset=0,
            end_offset=14,
            embedding=[0.2] * app_settings.embedding_dimensions,
            fts_document="fallback alpha",
        )
    )
    db_session.commit()

    class FailingRerankProvider:
        """固定拋錯的 rerank provider 測試替身。"""

        def rerank(self, *, query: str, documents: list[RerankInputDocument], top_n: int):
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

    result = retrieve_area_candidates(
        session=db_session,
        principal=CurrentPrincipal(sub="user-reader", groups=("/group/reader",)),
        settings=app_settings,
        area_id=area.id,
        query="alpha",
    )

    assert [candidate.chunk_id for candidate in result.candidates] == ["chunk-fallback"]
    assert result.candidates[0].rerank_applied is False
    assert result.candidates[0].rerank_rank is None
    assert result.trace.candidates[0].rerank_applied is False


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


def test_build_rerank_document_text_truncates_to_cost_guardrail() -> None:
    """rerank 文件文字應受最大字元數限制。"""

    assert _build_rerank_document_text(content="  abcdef  ", max_chars=4) == "abcd"


def test_deterministic_rerank_provider_returns_stable_sorted_scores() -> None:
    """deterministic rerank provider 應回傳可重現且排序穩定的結果。"""

    provider = DeterministicRerankProvider()
    documents = [
        RerankInputDocument(candidate_id="a", text="alpha"),
        RerankInputDocument(candidate_id="b", text="alpha alpha"),
    ]

    first_scores = provider.rerank(query="alpha", documents=documents, top_n=2)
    second_scores = provider.rerank(query="alpha", documents=documents, top_n=2)

    assert [item.candidate_id for item in first_scores] == ["b", "a"]
    assert first_scores == second_scores


def test_internal_retrieval_pipeline_from_upload_to_rerank(client, app, db_session, app_settings) -> None:
    """upload -> inline ingest -> retrieval rerank 的近似 E2E 路徑應可重跑。"""

    area = Area(id="area-retrieval-e2e", name="Retrieval E2E")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-maintainer", role=Role.maintainer))
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-reader", role=Role.reader))
    db_session.commit()

    file_payload = b"# Intro\nalpha\n\n## Deep Dive\nalpha alpha alpha alpha\n"
    response = client.post(
        f"/areas/{area.id}/documents",
        headers={"Authorization": "Bearer test::user-maintainer::/group/maintainer"},
        files={"file": ("retrieval-e2e.md", file_payload, "text/markdown")},
    )

    assert response.status_code == 201
    document_id = response.json()["document"]["id"]

    session = app.state.session_factory()
    try:
        stored_children = session.scalars(select(DocumentChunk).where(DocumentChunk.document_id == document_id)).all()
        assert any(chunk.embedding is not None for chunk in stored_children if chunk.chunk_type == ChunkType.child)
        assert any(chunk.fts_document for chunk in stored_children if chunk.chunk_type == ChunkType.child)

        result = retrieve_area_candidates(
            session=session,
            principal=CurrentPrincipal(sub="user-reader", groups=("/group/reader",)),
            settings=app_settings,
            area_id=area.id,
            query="alpha",
        )
    finally:
        session.close()

    assert result.candidates
    assert result.trace.candidates
    assert any(candidate.rerank_applied for candidate in result.candidates[: app_settings.rerank_top_n])
