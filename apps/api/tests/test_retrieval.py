"""Internal retrieval service 與 rerank provider 測試。"""

from email.message import Message
from uuid import uuid4
from urllib.error import HTTPError

from fastapi import HTTPException
import pytest
from sqlalchemy import Integer, String, select

from app.auth.verifier import CurrentPrincipal
from app.db.models import Area, AreaUserRole, ChunkStructureKind, ChunkType, Document, DocumentChunk, DocumentStatus, Role
from app.db.sql_types import DEFAULT_EMBEDDING_DIMENSIONS, Vector
from app.services.reranking import (
    CohereRerankProvider,
    DeterministicRerankProvider,
    RerankInputDocument,
    build_rerank_provider,
)
from app.services.retrieval_text import build_evidence_synopsis, build_rerank_document_text
from app.services.retrieval import (
    _build_match_chunks_rpc_statement,
    _apply_python_rrf,
    _apply_ranking_policy,
    RankedChunkMatch,
    retrieve_area_candidates,
)


def _uuid() -> str:
    """建立測試用 UUID 字串。"""

    return str(uuid4())


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


def test_cohere_rerank_retries_only_on_http_429(monkeypatch) -> None:
    """Cohere rerank 只應在 HTTP 429 時等待並重試。"""

    call_count = {"value": 0}
    sleep_calls: list[float] = []
    headers = Message()
    headers["Retry-After"] = "1.5"

    def fake_urlopen(request, timeout):  # noqa: ANN001
        """前兩次回 429，第三次成功。"""

        del request, timeout
        call_count["value"] += 1
        if call_count["value"] < 3:
            raise HTTPError(
                url="https://api.cohere.com/v2/rerank",
                code=429,
                msg="Too Many Requests",
                hdrs=headers,
                fp=None,
            )

        class _Response:
            """最小可用的 HTTP response 測試替身。"""

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                del exc_type, exc, tb
                return False

            def read(self) -> bytes:
                return b'{\"results\": [{\"index\": 0, \"relevance_score\": 0.9}]}'

        return _Response()

    monkeypatch.setattr("app.services.reranking.urlopen", fake_urlopen)
    monkeypatch.setattr("app.services.reranking.time.sleep", lambda seconds: sleep_calls.append(seconds))
    monkeypatch.setattr("app.services.reranking.random.uniform", lambda left, right: 1.1)

    provider = CohereRerankProvider(
        api_key="test-key",
        model="rerank-v3.5",
        retry_on_429_attempts=2,
        retry_on_429_backoff_seconds=2.0,
    )
    result = provider.rerank(
        query="alpha",
        documents=[RerankInputDocument(candidate_id="doc-1", text="alpha")],
        top_n=1,
    )

    assert [item.candidate_id for item in result] == ["doc-1"]
    assert call_count["value"] == 3
    assert sleep_calls == [pytest.approx(1.65), pytest.approx(1.65)]


def test_cohere_rerank_does_not_retry_non_429_http_error(monkeypatch) -> None:
    """Cohere rerank 不得對非 429 HTTP 錯誤重試。"""

    call_count = {"value": 0}
    sleep_calls: list[float] = []

    def fake_urlopen(request, timeout):  # noqa: ANN001
        """固定回 500，模擬非可重試錯誤。"""

        del request, timeout
        call_count["value"] += 1
        raise HTTPError(
            url="https://api.cohere.com/v2/rerank",
            code=500,
            msg="Internal Server Error",
            hdrs=Message(),
            fp=None,
        )

    monkeypatch.setattr("app.services.reranking.urlopen", fake_urlopen)
    monkeypatch.setattr("app.services.reranking.time.sleep", lambda seconds: sleep_calls.append(seconds))
    monkeypatch.setattr("app.services.reranking.random.uniform", lambda left, right: 1.1)

    provider = CohereRerankProvider(
        api_key="test-key",
        model="rerank-v3.5",
        retry_on_429_attempts=3,
        retry_on_429_backoff_seconds=2.0,
    )

    try:
        provider.rerank(
            query="alpha",
            documents=[RerankInputDocument(candidate_id="doc-1", text="alpha")],
            top_n=1,
        )
    except RuntimeError as exc:
        assert "Cohere rerank API 呼叫失敗" in str(exc)
    else:  # pragma: no cover - 失敗時才會進來。
        raise AssertionError("預期 Cohere 非 429 錯誤應直接失敗。")

    assert call_count["value"] == 1
    assert sleep_calls == []


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


def test_build_match_chunks_rpc_statement_uses_postgres_bind_types() -> None:
    """`match_chunks` RPC statement 應明確綁定 PostgreSQL 參數型別。"""

    statement = _build_match_chunks_rpc_statement()
    bind_params = statement._bindparams
    query_embedding_type = bind_params["query_embedding"].type

    assert Vector is not None
    assert isinstance(query_embedding_type, Vector)
    assert getattr(query_embedding_type, "dim", None) == DEFAULT_EMBEDDING_DIMENSIONS
    assert isinstance(bind_params["query_text"].type, String)
    assert isinstance(bind_params["area_id"].type, String)
    assert isinstance(bind_params["vector_top_k"].type, Integer)
    assert isinstance(bind_params["fts_top_k"].type, Integer)


def test_retrieve_area_candidates_filters_non_ready_and_parent_chunks(db_session, app_settings) -> None:
    """retrieval 應只回 ready 文件的 child chunks，並保留 rerank metadata。"""

    area = Area(id=_uuid(), name="Retrieval Ready")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-reader", role=Role.reader))
    ready_document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="ready.md",
        content_type="text/markdown",
        file_size=100,
        storage_key="area/document-ready/ready.md",
        status=DocumentStatus.ready,
    )
    uploaded_document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="uploaded.md",
        content_type="text/markdown",
        file_size=100,
        storage_key="area/document-uploaded/uploaded.md",
        status=DocumentStatus.uploaded,
    )
    db_session.add_all([ready_document, uploaded_document])
    ready_parent = DocumentChunk(
        id=_uuid(),
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
    )
    ready_child = DocumentChunk(
        id=_uuid(),
        document_id=ready_document.id,
        parent_chunk_id=ready_parent.id,
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
    )
    uploaded_child = DocumentChunk(
        id=_uuid(),
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
    )
    db_session.add_all([ready_parent, ready_child, uploaded_child])
    db_session.commit()

    result = retrieve_area_candidates(
        session=db_session,
        principal=CurrentPrincipal(sub="user-reader", groups=("/group/reader",)),
        settings=app_settings,
        area_id=area.id,
        query="中文檢索",
    )

    assert [candidate.chunk_id for candidate in result.candidates] == [ready_child.id]
    assert result.candidates[0].source == "hybrid"
    assert result.candidates[0].rrf_rank == 1
    assert result.candidates[0].rerank_rank == 1
    assert result.candidates[0].rerank_applied is True
    assert result.trace.query == "中文檢索"
    assert result.trace.candidates[0].chunk_id == ready_child.id


def test_retrieve_area_candidates_reranks_only_top_n_and_keeps_rest_in_rrf_order(db_session, app_settings) -> None:
    """rerank 應只重排前 top-n 筆，其他結果維持原 RRF 順序。"""

    settings = app_settings.model_copy(update={"rerank_top_n": 2})
    area = Area(id=_uuid(), name="Retrieval Rerank")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-reader", role=Role.reader))
    document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="rerank.md",
        content_type="text/markdown",
        file_size=100,
        storage_key="area/document-rerank/rerank.md",
        status=DocumentStatus.ready,
    )
    db_session.add(document)
    alpha_chunk = DocumentChunk(
        id=_uuid(),
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
    )
    beta_chunk = DocumentChunk(
        id=_uuid(),
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
    )
    gamma_chunk = DocumentChunk(
        id=_uuid(),
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
    )
    db_session.add_all([alpha_chunk, beta_chunk, gamma_chunk])
    db_session.commit()

    result = retrieve_area_candidates(
        session=db_session,
        principal=CurrentPrincipal(sub="user-reader", groups=("/group/reader",)),
        settings=settings,
        area_id=area.id,
        query="alpha",
    )

    assert [candidate.chunk_id for candidate in result.candidates] == [beta_chunk.id, alpha_chunk.id, gamma_chunk.id]
    assert result.candidates[0].rerank_rank == 1
    assert result.candidates[1].rerank_rank == 2
    assert result.candidates[2].rerank_rank is None
    assert result.candidates[2].rerank_applied is False


def test_apply_ranking_policy_downranks_table_of_contents_noise(db_session, app_settings) -> None:
    """ranking policy 應降低目錄噪音，避免商品 query 被目錄優先吃掉。"""

    document = Document(
        id=_uuid(),
        area_id=_uuid(),
        file_name="product-handbook.md",
        content_type="text/markdown",
        file_size=100,
        storage_key="tests/product-handbook.md",
        status=DocumentStatus.ready,
    )
    toc_chunk = DocumentChunk(
        id=_uuid(),
        document_id=document.id,
        parent_chunk_id=None,
        chunk_type=ChunkType.child,
        structure_kind=ChunkStructureKind.text,
        position=0,
        section_index=0,
        child_index=0,
        heading="目錄",
        content="十六、 保利美美元利率變動型終身壽險(NUIW6502)..................................................................123",
        content_preview="十六、 保利美美元利率變動型終身壽險(NUIW6502)..................................................................123",
        char_count=88,
        start_offset=100,
        end_offset=136,
    )
    body_chunk = DocumentChunk(
        id=_uuid(),
        document_id=document.id,
        parent_chunk_id=None,
        chunk_type=ChunkType.child,
        structure_kind=ChunkStructureKind.table,
        position=1,
        section_index=1,
        child_index=0,
        heading="保利美美元利率變動型終身壽險",
        content="本險累計最高投保金額：美元 65 萬元。",
        content_preview="本險累計最高投保金額：美元 65 萬元。",
        char_count=21,
        start_offset=1000,
        end_offset=1021,
    )

    ranked = _apply_ranking_policy(
        matches=[
            RankedChunkMatch(chunk=toc_chunk, vector_rank=1, fts_rank=1, rrf_rank=1, rrf_score=0.032),
            RankedChunkMatch(chunk=body_chunk, vector_rank=2, fts_rank=2, rrf_rank=2, rrf_score=0.031),
        ],
        query="保利美美元利率變動型終身壽險其累計最高投保金額為何",
        settings=app_settings,
    )

    assert ranked[0].chunk.id == body_chunk.id


def test_retrieve_area_candidates_falls_back_to_rrf_when_rerank_runtime_fails(
    db_session, app_settings, monkeypatch, caplog
) -> None:
    """rerank runtime 失敗時，retrieval 應回退到 RRF 結果。"""

    area = Area(id=_uuid(), name="Retrieval Fallback")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-reader", role=Role.reader))
    document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="fallback.md",
        content_type="text/markdown",
        file_size=100,
        storage_key="area/document-fallback/fallback.md",
        status=DocumentStatus.ready,
    )
    db_session.add(document)
    fallback_chunk = DocumentChunk(
        id=_uuid(),
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
    )
    db_session.add(fallback_chunk)
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

    assert [candidate.chunk_id for candidate in result.candidates] == [fallback_chunk.id]
    assert result.candidates[0].rerank_applied is False
    assert result.candidates[0].rerank_rank is None
    assert result.candidates[0].rerank_fallback_reason == "provider_error"
    assert result.trace.candidates[0].rerank_applied is False
    assert result.trace.candidates[0].rerank_fallback_reason == "provider_error"
    assert "Retrieval rerank provider failed; falling back to RRF order." in caplog.text


def test_retrieve_area_candidates_returns_same_404_for_missing_and_unauthorized(db_session, app_settings) -> None:
    """未授權 area 與不存在 area 的 retrieval 都應回相同 404。"""

    area = Area(id=_uuid(), name="Retrieval Secret")
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


def test_build_rerank_document_text_adds_prefixes_and_truncates_to_cost_guardrail() -> None:
    """rerank 文件文字應帶有 header/content 前綴並受最大字元數限制。"""

    assert (
        build_rerank_document_text(heading=" Intro ", content="  abcdef  ", max_chars=128)
        == "Header: Intro\nContent:\nabcdef"
    )
    assert (
        build_rerank_document_text(
            heading="Intro",
            content="abcdef",
            evidence_synopsis="- quantitative evidence",
            max_chars=128,
        )
        == "Header: Intro\nEvidence synopsis:\n- quantitative evidence\nContent:\nabcdef"
    )
    assert build_rerank_document_text(heading="Intro", content="abcdef", max_chars=10) == "Header: In"


def test_build_evidence_synopsis_emits_fact_oriented_hints() -> None:
    """evidence synopsis 應能為 fact-heavy 片段產生較像答案的提示。"""

    dataset_synopsis = build_evidence_synopsis(
        heading="Experimental Studies ::: Dataset and Evaluation Metrics",
        content="It contains 17,833 sentences, 826,987 characters and 2,714 question-answer pairs.",
    )
    metric_synopsis = build_evidence_synopsis(
        heading="Experimental Setup",
        content="For each model, we examined word-level perplexity, R@3 in next-word prediction, latency (ms/q), and energy usage (mJ/q).",
    )

    assert "quantitative evidence" in dataset_synopsis
    assert "dataset alias" not in dataset_synopsis
    assert "evaluation metrics" in metric_synopsis


def test_build_evidence_synopsis_qasper_v3_adds_alias_task_and_metric_bridges() -> None:
    """qasper_v3 應補強 alias / task / metric framing bridge。"""

    dataset_alias_synopsis = build_evidence_synopsis(
        heading="Experimental Studies ::: Dataset and Evaluation Metrics",
        content="It contains 17,833 sentences, 826,987 characters and 2,714 question-answer pairs.",
        variant="qasper_v3",
    )
    task_synopsis = build_evidence_synopsis(
        heading="Experimental Studies ::: Dataset and Evaluation Metrics",
        content="There are three types of questions, namely tumor size, proximal resection margin and distal resection margin.",
        variant="qasper_v3",
    )
    metric_synopsis = build_evidence_synopsis(
        heading="Experimental Setup",
        content="We compare perplexity, R@3, latency, and energy usage across language models.",
        variant="qasper_v3",
    )

    assert "dataset-alias questions" in dataset_alias_synopsis
    assert "task types or question types being unified" in task_synopsis
    assert "aspects compared across models" in metric_synopsis


def test_build_evidence_synopsis_qasper_v3_supports_traditional_chinese_bridges() -> None:
    """qasper_v3 應補上繁體中文的 alias / task / metric bridge phrasing。"""

    dataset_alias_synopsis = build_evidence_synopsis(
        heading="資料集與評估指標",
        content="此 QA-CTS 資料集包含 17,833 句、826,987 字元與 2,714 組問答對。",
        variant="qasper_v3",
    )
    task_synopsis = build_evidence_synopsis(
        heading="實驗研究",
        content="此任務包括腫瘤大小、近端切緣與遠端切緣三種問題型別。",
        variant="qasper_v3",
    )
    metric_synopsis = build_evidence_synopsis(
        heading="實驗設計",
        content="本文比較困惑度、R@3、延遲與能耗等面向。",
        variant="qasper_v3",
    )

    assert "任務資料集規模、資料集別名或問答對統計" in dataset_alias_synopsis
    assert "被統整的具體任務型別或問題型別" in task_synopsis
    assert "不同模型之間被比較的面向" in metric_synopsis


def test_build_evidence_synopsis_supports_traditional_chinese_with_localized_output() -> None:
    """evidence synopsis 應能支援繁體中文並輸出本地化提示。"""

    zh_synopsis = build_evidence_synopsis(
        heading="資料集與評估指標",
        content="此資料集包含 17,833 句、826,987 字元與 2,714 組問答對，並比較召回率、精確率與延遲。",
    )

    assert "此段落包含數量" in zh_synopsis
    assert "此段落列出評估指標" in zh_synopsis
    assert "This passage" not in zh_synopsis


def test_retrieve_area_candidates_uses_parent_level_rerank_documents(db_session, app_settings, monkeypatch) -> None:
    """rerank 應以 parent-level 組裝文字為輸入，且帶有固定前綴。"""

    area = Area(id=_uuid(), name="Retrieval Parent Rerank")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-reader", role=Role.reader))
    document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="parent-rerank.md",
        content_type="text/markdown",
        file_size=100,
        storage_key="area/document-parent-rerank/parent-rerank.md",
        status=DocumentStatus.ready,
    )
    db_session.add(document)

    parent_one = DocumentChunk(
        id=_uuid(),
        document_id=document.id,
        parent_chunk_id=None,
        chunk_type=ChunkType.parent,
        structure_kind=ChunkStructureKind.text,
        position=0,
        section_index=0,
        child_index=None,
        heading="Section One",
        content="alpha intro\n\nalpha details",
        content_preview="alpha intro",
        char_count=27,
        start_offset=0,
        end_offset=27,
    )
    child_one = DocumentChunk(
        id=_uuid(),
        document_id=document.id,
        parent_chunk_id=parent_one.id,
        chunk_type=ChunkType.child,
        structure_kind=ChunkStructureKind.text,
        position=1,
        section_index=0,
        child_index=0,
        heading="Section One",
        content="alpha intro",
        content_preview="alpha intro",
        char_count=11,
        start_offset=0,
        end_offset=11,
        embedding=[0.1] * app_settings.embedding_dimensions,
    )
    child_two = DocumentChunk(
        id=_uuid(),
        document_id=document.id,
        parent_chunk_id=parent_one.id,
        chunk_type=ChunkType.child,
        structure_kind=ChunkStructureKind.text,
        position=2,
        section_index=0,
        child_index=1,
        heading="Section One",
        content="alpha details",
        content_preview="alpha details",
        char_count=13,
        start_offset=13,
        end_offset=26,
        embedding=[0.1] * app_settings.embedding_dimensions,
    )
    parent_two = DocumentChunk(
        id=_uuid(),
        document_id=document.id,
        parent_chunk_id=None,
        chunk_type=ChunkType.parent,
        structure_kind=ChunkStructureKind.text,
        position=3,
        section_index=1,
        child_index=None,
        heading="Section Two",
        content="beta only",
        content_preview="beta only",
        char_count=9,
        start_offset=28,
        end_offset=37,
    )
    child_three = DocumentChunk(
        id=_uuid(),
        document_id=document.id,
        parent_chunk_id=parent_two.id,
        chunk_type=ChunkType.child,
        structure_kind=ChunkStructureKind.text,
        position=4,
        section_index=1,
        child_index=0,
        heading="Section Two",
        content="beta only",
        content_preview="beta only",
        char_count=9,
        start_offset=28,
        end_offset=37,
        embedding=[0.2] * app_settings.embedding_dimensions,
    )
    db_session.add_all([parent_one, child_one, child_two, parent_two, child_three])
    db_session.commit()

    captured_documents: list[RerankInputDocument] = []

    class CapturingRerankProvider:
        """記錄 rerank 輸入的測試替身。"""

        def rerank(self, *, query: str, documents: list[RerankInputDocument], top_n: int) -> list:
            """保存輸入並回傳固定分數。

            參數：
            - `query`：使用者查詢文字。
            - `documents`：送入 rerank 的 parent-level 文件。
            - `top_n`：最多回傳筆數。

            回傳：
            - `list[RerankScore]`：依輸入順序建立的固定分數結果。
            """

            del query
            del top_n
            captured_documents.extend(documents)
            return [
                type("Score", (), {"candidate_id": document.candidate_id, "score": float(len(documents) - index)})()
                for index, document in enumerate(documents)
            ]

    monkeypatch.setattr("app.services.retrieval.build_rerank_provider", lambda settings: CapturingRerankProvider())

    result = retrieve_area_candidates(
        session=db_session,
        principal=CurrentPrincipal(sub="user-reader", groups=("/group/reader",)),
        settings=app_settings,
        area_id=area.id,
        query="alpha",
    )

    assert len(captured_documents) == 2
    assert captured_documents[0].text == "Header: Section One\nContent:\nalpha intro\n\nalpha details"
    assert captured_documents[1].text == "Header: Section Two\nContent:\nbeta only"
    assert result.candidates[0].chunk_id == child_one.id
    assert result.candidates[1].chunk_id == child_two.id
    assert result.candidates[0].rerank_rank == 1
    assert result.candidates[1].rerank_rank == 1


def test_retrieve_area_candidates_includes_evidence_synopsis_in_rerank_documents(
    db_session, app_settings, monkeypatch
) -> None:
    """evidence synopsis lane 啟用時，rerank 文件應包含 fact-oriented synopsis。"""

    settings = app_settings.model_copy(update={"retrieval_evidence_synopsis_enabled": True})
    area = Area(id=_uuid(), name="Retrieval Evidence Synopsis")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-reader", role=Role.reader))
    document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="evidence-synopsis.md",
        content_type="text/markdown",
        file_size=100,
        storage_key="area/document-evidence-synopsis/evidence-synopsis.md",
        status=DocumentStatus.ready,
    )
    db_session.add(document)

    parent = DocumentChunk(
        id=_uuid(),
        document_id=document.id,
        parent_chunk_id=None,
        chunk_type=ChunkType.parent,
        structure_kind=ChunkStructureKind.text,
        position=0,
        section_index=0,
        child_index=None,
        heading="Experimental Studies ::: Dataset and Evaluation Metrics",
        content="It contains 17,833 sentences, 826,987 characters and 2,714 question-answer pairs.",
        content_preview="It contains 17,833 sentences, 826,987 characters and 2,714 question-answer pairs.",
        char_count=81,
        start_offset=0,
        end_offset=81,
    )
    child = DocumentChunk(
        id=_uuid(),
        document_id=document.id,
        parent_chunk_id=parent.id,
        chunk_type=ChunkType.child,
        structure_kind=ChunkStructureKind.text,
        position=1,
        section_index=0,
        child_index=0,
        heading="Experimental Studies ::: Dataset and Evaluation Metrics",
        content="It contains 17,833 sentences, 826,987 characters and 2,714 question-answer pairs.",
        content_preview="It contains 17,833 sentences, 826,987 characters and 2,714 question-answer pairs.",
        char_count=81,
        start_offset=0,
        end_offset=81,
        embedding=[0.1] * settings.embedding_dimensions,
    )
    db_session.add_all([parent, child])
    db_session.commit()

    captured_documents: list[RerankInputDocument] = []

    class CapturingRerankProvider:
        """記錄 rerank 文件輸入的測試替身。"""

        def rerank(self, *, query: str, documents: list[RerankInputDocument], top_n: int) -> list:
            """保存輸入並回傳固定分數。

            參數：
            - `query`：使用者查詢文字。
            - `documents`：送入 rerank 的 parent-level 文件。
            - `top_n`：最多回傳筆數。

            回傳：
            - `list[RerankScore]`：依輸入順序建立的固定分數結果。
            """

            del query, top_n
            captured_documents.extend(documents)
            return [type("Score", (), {"candidate_id": document.candidate_id, "score": 1.0})() for document in documents]

    monkeypatch.setattr("app.services.retrieval.build_rerank_provider", lambda settings: CapturingRerankProvider())

    retrieve_area_candidates(
        session=db_session,
        principal=CurrentPrincipal(sub="user-reader", groups=("/group/reader",)),
        settings=settings,
        area_id=area.id,
        query="How big is QA-CTS task dataset?",
    )

    assert len(captured_documents) == 1
    assert "Evidence synopsis:" in captured_documents[0].text
    assert "quantitative evidence" in captured_documents[0].text


def test_retrieve_area_candidates_includes_qasper_v3_bridge_phrasing_in_rerank_documents(
    db_session, app_settings, monkeypatch
) -> None:
    """qasper_v3 variant 啟用時，rerank 文件應包含 alias/task bridge phrasing。"""

    settings = app_settings.model_copy(
        update={
            "retrieval_evidence_synopsis_enabled": True,
            "retrieval_evidence_synopsis_variant": "qasper_v3",
        }
    )
    area = Area(id=_uuid(), name="Retrieval Evidence Synopsis V3")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-reader", role=Role.reader))
    document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="evidence-synopsis-v3.md",
        content_type="text/markdown",
        file_size=100,
        storage_key="area/document-evidence-synopsis-v3/evidence-synopsis-v3.md",
        status=DocumentStatus.ready,
    )
    db_session.add(document)

    parent = DocumentChunk(
        id=_uuid(),
        document_id=document.id,
        parent_chunk_id=None,
        chunk_type=ChunkType.parent,
        structure_kind=ChunkStructureKind.text,
        position=0,
        section_index=0,
        child_index=None,
        heading="Experimental Studies ::: Dataset and Evaluation Metrics",
        content="It contains 17,833 sentences, 826,987 characters and 2,714 question-answer pairs.",
        content_preview="It contains 17,833 sentences, 826,987 characters and 2,714 question-answer pairs.",
        char_count=81,
        start_offset=0,
        end_offset=81,
    )
    child = DocumentChunk(
        id=_uuid(),
        document_id=document.id,
        parent_chunk_id=parent.id,
        chunk_type=ChunkType.child,
        structure_kind=ChunkStructureKind.text,
        position=1,
        section_index=0,
        child_index=0,
        heading="Experimental Studies ::: Dataset and Evaluation Metrics",
        content="It contains 17,833 sentences, 826,987 characters and 2,714 question-answer pairs.",
        content_preview="It contains 17,833 sentences, 826,987 characters and 2,714 question-answer pairs.",
        char_count=81,
        start_offset=0,
        end_offset=81,
        embedding=[0.1] * settings.embedding_dimensions,
    )
    db_session.add_all([parent, child])
    db_session.commit()

    captured_documents: list[RerankInputDocument] = []

    class CapturingRerankProvider:
        """記錄 v3 rerank 文件輸入的測試替身。"""

        def rerank(self, *, query: str, documents: list[RerankInputDocument], top_n: int) -> list:
            """保存輸入並回傳固定分數。

            參數：
            - `query`：使用者查詢文字。
            - `documents`：送入 rerank 的 parent-level 文件。
            - `top_n`：最多回傳筆數。

            回傳：
            - `list[RerankScore]`：依輸入順序建立的固定分數結果。
            """

            del query, top_n
            captured_documents.extend(documents)
            return [type("Score", (), {"candidate_id": document.candidate_id, "score": 1.0})() for document in documents]

    monkeypatch.setattr("app.services.retrieval.build_rerank_provider", lambda settings: CapturingRerankProvider())

    retrieve_area_candidates(
        session=db_session,
        principal=CurrentPrincipal(sub="user-reader", groups=("/group/reader",)),
        settings=settings,
        area_id=area.id,
        query="How big is QA-CTS task dataset?",
    )

    assert len(captured_documents) == 1
    assert "dataset-alias questions" in captured_documents[0].text


def test_retrieve_area_candidates_includes_traditional_chinese_evidence_synopsis_in_rerank_documents(
    db_session, app_settings, monkeypatch
) -> None:
    """繁中 fact-heavy 片段在 evidence synopsis lane 應輸出繁中提示。"""

    settings = app_settings.model_copy(update={"retrieval_evidence_synopsis_enabled": True})
    area = Area(id=_uuid(), name="Retrieval Zh-TW Evidence Synopsis")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-reader", role=Role.reader))
    document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="evidence-synopsis-zh-tw.md",
        content_type="text/markdown",
        file_size=100,
        storage_key="area/document-evidence-synopsis-zh-tw/evidence-synopsis-zh-tw.md",
        status=DocumentStatus.ready,
    )
    db_session.add(document)

    parent = DocumentChunk(
        id=_uuid(),
        document_id=document.id,
        parent_chunk_id=None,
        chunk_type=ChunkType.parent,
        structure_kind=ChunkStructureKind.text,
        position=0,
        section_index=0,
        child_index=None,
        heading="資料集與評估指標",
        content="此資料集包含 17,833 句、826,987 字元與 2,714 組問答對，並比較召回率、精確率與延遲。",
        content_preview="此資料集包含 17,833 句、826,987 字元與 2,714 組問答對。",
        char_count=50,
        start_offset=0,
        end_offset=50,
    )
    child = DocumentChunk(
        id=_uuid(),
        document_id=document.id,
        parent_chunk_id=parent.id,
        chunk_type=ChunkType.child,
        structure_kind=ChunkStructureKind.text,
        position=1,
        section_index=0,
        child_index=0,
        heading="資料集與評估指標",
        content="此資料集包含 17,833 句、826,987 字元與 2,714 組問答對，並比較召回率、精確率與延遲。",
        content_preview="此資料集包含 17,833 句、826,987 字元與 2,714 組問答對。",
        char_count=50,
        start_offset=0,
        end_offset=50,
        embedding=[0.1] * settings.embedding_dimensions,
    )
    db_session.add_all([parent, child])
    db_session.commit()

    captured_documents: list[RerankInputDocument] = []

    class CapturingRerankProvider:
        """記錄繁中 rerank 文件輸入的測試替身。"""

        def rerank(self, *, query: str, documents: list[RerankInputDocument], top_n: int) -> list:
            """保存輸入並回傳固定分數。

            參數：
            - `query`：使用者查詢文字。
            - `documents`：送入 rerank 的 parent-level 文件。
            - `top_n`：最多回傳筆數。

            回傳：
            - `list[RerankScore]`：依輸入順序建立的固定分數結果。
            """

            del query, top_n
            captured_documents.extend(documents)
            return [type("Score", (), {"candidate_id": document.candidate_id, "score": 1.0})() for document in documents]

    monkeypatch.setattr("app.services.retrieval.build_rerank_provider", lambda settings: CapturingRerankProvider())

    retrieve_area_candidates(
        session=db_session,
        principal=CurrentPrincipal(sub="user-reader", groups=("/group/reader",)),
        settings=settings,
        area_id=area.id,
        query="這個資料集規模多大？",
    )

    assert len(captured_documents) == 1
    assert "Evidence synopsis:" in captured_documents[0].text
    assert "此段落包含數量" in captured_documents[0].text
    assert "此段落列出評估指標" in captured_documents[0].text


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


def test_apply_python_rrf_merges_vector_and_fts_ranks_stably(app_settings) -> None:
    """Python RRF 應能穩定合併 vector 與 FTS ranks。"""

    document = Document(
        id=_uuid(),
        area_id=_uuid(),
        file_name="rrf.md",
        content_type="text/markdown",
        file_size=10,
        storage_key="area/rrf/rrf.md",
        status=DocumentStatus.ready,
    )
    vector_only = RankedChunkMatch(
        chunk=DocumentChunk(
            id=_uuid(),
            document_id=document.id,
            parent_chunk_id=None,
            chunk_type=ChunkType.child,
            structure_kind=ChunkStructureKind.text,
            position=2,
            section_index=0,
            child_index=1,
            heading="Vector",
            content="vector",
            content_preview="vector",
            char_count=6,
            start_offset=0,
            end_offset=6,
        ),
        vector_rank=1,
    )
    hybrid = RankedChunkMatch(
        chunk=DocumentChunk(
            id=_uuid(),
            document_id=document.id,
            parent_chunk_id=None,
            chunk_type=ChunkType.child,
            structure_kind=ChunkStructureKind.text,
            position=1,
            section_index=0,
            child_index=0,
            heading="Hybrid",
            content="hybrid",
            content_preview="hybrid",
            char_count=6,
            start_offset=7,
            end_offset=13,
        ),
        vector_rank=3,
        fts_rank=1,
    )
    fts_only = RankedChunkMatch(
        chunk=DocumentChunk(
            id=_uuid(),
            document_id=document.id,
            parent_chunk_id=None,
            chunk_type=ChunkType.child,
            structure_kind=ChunkStructureKind.text,
            position=3,
            section_index=0,
            child_index=2,
            heading="FTS",
            content="fts",
            content_preview="fts",
            char_count=3,
            start_offset=14,
            end_offset=17,
        ),
        fts_rank=2,
    )

    merged = _apply_python_rrf(matches=[vector_only, hybrid, fts_only], settings=app_settings)

    assert [match.chunk.heading for match in merged] == ["Hybrid", "Vector", "FTS"]
    assert [match.rrf_rank for match in merged] == [1, 2, 3]
    assert merged[0].rrf_score > merged[1].rrf_score > merged[2].rrf_score


def test_apply_ranking_policy_keeps_single_match_identity(app_settings) -> None:
    """ranking policy 在單一候選時應維持原候選內容。"""

    matches = [
        RankedChunkMatch(
            chunk=DocumentChunk(
                id=_uuid(),
                document_id=_uuid(),
                parent_chunk_id=None,
                chunk_type=ChunkType.child,
                structure_kind=ChunkStructureKind.text,
                position=1,
                section_index=0,
                child_index=0,
                heading="Policy",
                content="policy",
                content_preview="policy",
                char_count=6,
                start_offset=0,
                end_offset=6,
            ),
            vector_rank=1,
            rrf_rank=1,
            rrf_score=0.9,
        )
    ]

    ranked = _apply_ranking_policy(matches=matches, query="policy", settings=app_settings)

    assert len(ranked) == 1
    assert ranked[0] is matches[0]
