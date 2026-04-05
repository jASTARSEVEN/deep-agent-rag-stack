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
    BGERerankProvider,
    CohereRerankProvider,
    DeterministicRerankProvider,
    EasypinexHostRerankProvider,
    QwenRerankProvider,
    RerankInputDocument,
    RerankScore,
    _score_with_bge_reranker,
    _score_with_qwen_reranker,
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


def test_build_rerank_provider_supports_deterministic_bge_qwen_cohere_and_easypinex_host(app_settings) -> None:
    """rerank provider factory 應支援 deterministic、BGE、Qwen、Cohere 與 easypinex-host。"""

    deterministic_settings = app_settings.model_copy(update={"rerank_provider": "deterministic"})
    bge_settings = app_settings.model_copy(
        update={"rerank_provider": "bge", "rerank_model": "BAAI/bge-reranker-v2-m3"}
    )
    qwen_settings = app_settings.model_copy(
        update={"rerank_provider": "qwen", "rerank_model": "Qwen/Qwen3-Reranker-0.6B"}
    )
    cohere_settings = app_settings.model_copy(
        update={"rerank_provider": "cohere", "cohere_api_key": "test-key", "rerank_model": "rerank-v3.5"}
    )
    easypinex_host_settings = app_settings.model_copy(
        update={
            "rerank_provider": "easypinex-host",
            "easypinex_host_rerank_base_url": "http://helper.local:8000",
            "easypinex_host_rerank_api_key": "helper-key",
            "rerank_model": "BAAI/bge-reranker-v2-m3",
        }
    )

    deterministic_provider = build_rerank_provider(deterministic_settings)
    bge_provider = build_rerank_provider(bge_settings)
    qwen_provider = build_rerank_provider(qwen_settings)
    cohere_provider = build_rerank_provider(cohere_settings)
    easypinex_host_provider = build_rerank_provider(easypinex_host_settings)

    assert isinstance(deterministic_provider, DeterministicRerankProvider)
    assert isinstance(bge_provider, BGERerankProvider)
    assert isinstance(qwen_provider, QwenRerankProvider)
    assert isinstance(cohere_provider, CohereRerankProvider)
    assert isinstance(easypinex_host_provider, EasypinexHostRerankProvider)


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


def test_build_rerank_provider_requires_easypinex_host_base_url_and_api_key(app_settings) -> None:
    """使用 easypinex-host rerank 前必須同時提供 base URL 與 API key。"""

    missing_base_url_settings = app_settings.model_copy(
        update={
            "rerank_provider": "easypinex-host",
            "easypinex_host_rerank_base_url": None,
            "easypinex_host_rerank_api_key": "helper-key",
        }
    )
    missing_api_key_settings = app_settings.model_copy(
        update={
            "rerank_provider": "easypinex-host",
            "easypinex_host_rerank_base_url": "http://helper.local:8000",
            "easypinex_host_rerank_api_key": None,
        }
    )

    try:
        build_rerank_provider(missing_base_url_settings)
    except ValueError as exc:
        assert "EASYPINEX_HOST_RERANK_BASE_URL" in str(exc)
    else:  # pragma: no cover - 失敗時才會進來。
        raise AssertionError("預期缺少 EASYPINEX_HOST_RERANK_BASE_URL 時應拋出 ValueError。")

    try:
        build_rerank_provider(missing_api_key_settings)
    except ValueError as exc:
        assert "EASYPINEX_HOST_RERANK_API_KEY" in str(exc)
    else:  # pragma: no cover - 失敗時才會進來。
        raise AssertionError("預期缺少 EASYPINEX_HOST_RERANK_API_KEY 時應拋出 ValueError。")


def test_easypinex_host_rerank_provider_posts_contract_and_parses_scores(monkeypatch) -> None:
    """easypinex-host rerank provider 應使用 `/v1/rerank` contract 並解析 `score` 欄位。"""

    captured_request: dict[str, object] = {}

    def fake_urlopen(request, timeout):  # noqa: ANN001
        """記錄 easypinex-host request 並回傳最小成功 payload。"""

        headers = {key.lower(): value for key, value in request.header_items()}
        captured_request["timeout"] = timeout
        captured_request["url"] = request.full_url
        captured_request["method"] = request.get_method()
        captured_request["authorization"] = headers.get("authorization")
        captured_request["content_type"] = headers.get("content-type")
        captured_request["payload"] = request.data.decode("utf-8")

        class _Response:
            """最小可用的 HTTP response 測試替身。"""

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                del exc_type, exc, tb
                return False

            def read(self) -> bytes:
                return b'{\"results\": [{\"index\": 1, \"score\": 0.97}, {\"index\": 0, \"score\": 0.41}]}'

        return _Response()

    monkeypatch.setattr("app.services.reranking.urlopen", fake_urlopen)

    provider = EasypinexHostRerankProvider(
        base_url="http://helper.local:8000/",
        api_key="helper-key",
        model="BAAI/bge-reranker-v2-m3",
        timeout_seconds=42.0,
    )
    results = provider.rerank(
        query="部署 rerank",
        documents=[
            RerankInputDocument(candidate_id="doc-1", text="alpha"),
            RerankInputDocument(candidate_id="doc-2", text="beta"),
        ],
        top_n=2,
    )

    assert [item.candidate_id for item in results] == ["doc-2", "doc-1"]
    assert captured_request["timeout"] == 42.0
    assert captured_request["url"] == "http://helper.local:8000/v1/rerank"
    assert captured_request["method"] == "POST"
    assert captured_request["authorization"] == "Bearer helper-key"
    assert captured_request["content_type"] == "application/json"
    assert captured_request["payload"] == (
        '{"model": "BAAI/bge-reranker-v2-m3", "query": "\\u90e8\\u7f72 rerank", '
        '"documents": ["alpha", "beta"], "top_n": 2, "return_documents": false, "normalize": true}'
    )


def test_bge_rerank_provider_delegates_to_bge_runtime(monkeypatch) -> None:
    """BGE rerank provider 應委派給 BGE runtime helper 並回傳排序結果。"""

    captured_arguments: dict[str, object] = {}

    def fake_score_with_bge_reranker(*, query, documents, top_n, model_name):  # noqa: ANN001
        captured_arguments["query"] = query
        captured_arguments["documents"] = documents
        captured_arguments["top_n"] = top_n
        captured_arguments["model_name"] = model_name
        return [
            RerankScore(candidate_id="doc-2", score=0.9),
            RerankScore(candidate_id="doc-1", score=0.4),
        ]

    monkeypatch.setattr("app.services.reranking._score_with_bge_reranker", fake_score_with_bge_reranker)

    provider = BGERerankProvider(model="BAAI/bge-reranker-v2-m3")
    results = provider.rerank(
        query="what is panda",
        documents=[
            RerankInputDocument(candidate_id="doc-1", text="alpha"),
            RerankInputDocument(candidate_id="doc-2", text="beta"),
        ],
        top_n=2,
    )

    assert [item.candidate_id for item in results] == ["doc-2", "doc-1"]
    assert captured_arguments["model_name"] == "BAAI/bge-reranker-v2-m3"
    assert captured_arguments["top_n"] == 2


def test_qwen_rerank_provider_delegates_to_qwen_runtime(monkeypatch) -> None:
    """Qwen rerank provider 應委派給 Qwen runtime helper 並回傳排序結果。"""

    captured_arguments: dict[str, object] = {}

    def fake_score_with_qwen_reranker(*, query, documents, top_n, model_name):  # noqa: ANN001
        captured_arguments["query"] = query
        captured_arguments["documents"] = documents
        captured_arguments["top_n"] = top_n
        captured_arguments["model_name"] = model_name
        return [
            RerankScore(candidate_id="doc-2", score=0.8),
            RerankScore(candidate_id="doc-1", score=0.3),
        ]

    monkeypatch.setattr("app.services.reranking._score_with_qwen_reranker", fake_score_with_qwen_reranker)

    provider = QwenRerankProvider(model="Qwen/Qwen3-Reranker-0.6B")
    results = provider.rerank(
        query="which document",
        documents=[
            RerankInputDocument(candidate_id="doc-1", text="alpha"),
            RerankInputDocument(candidate_id="doc-2", text="beta"),
        ],
        top_n=2,
    )

    assert [item.candidate_id for item in results] == ["doc-2", "doc-1"]
    assert captured_arguments["model_name"] == "Qwen/Qwen3-Reranker-0.6B"
    assert captured_arguments["top_n"] == 2


def test_score_with_bge_reranker_sorts_sigmoid_scores(monkeypatch) -> None:
    """BGE score helper 應將模型分數正規化後排序。"""

    class FakeTensor:
        """最小 tensor 測試替身。"""

        def __init__(self, values: list[float]) -> None:
            self._values = values

        def view(self, *_args) -> "FakeTensor":
            return self

        def detach(self) -> "FakeTensor":
            return self

        def cpu(self) -> "FakeTensor":
            return self

        def float(self) -> "FakeTensor":
            return self

        def tolist(self) -> list[float]:
            return list(self._values)

    class FakeNoGrad:
        """模擬 torch.no_grad() context manager。"""

        def __enter__(self) -> None:
            return None

        def __exit__(self, exc_type, exc, tb) -> bool:
            del exc_type, exc, tb
            return False

    class FakeTorchModule:
        """最小 torch 測試替身。"""

        @staticmethod
        def no_grad() -> FakeNoGrad:
            return FakeNoGrad()

        @staticmethod
        def sigmoid(tensor: FakeTensor) -> FakeTensor:
            del tensor
            return FakeTensor([0.2, 0.9, 0.6])

    class FakeTokenizer:
        """最小 tokenizer 測試替身。"""

        def __call__(self, pairs, *, padding, truncation, return_tensors, max_length):  # noqa: ANN001
            del padding, truncation, return_tensors, max_length
            assert pairs[0][0] == "which document"
            return {"input_ids": [1, 2, 3]}

    class FakeModel:
        """最小 model 測試替身。"""

        def __call__(self, **inputs):  # noqa: ANN003, ANN001
            del inputs

            class FakeOutput:
                """最小 logits 輸出替身。"""

                logits = FakeTensor([1.0, 3.0, 2.0])

            return FakeOutput()

    monkeypatch.setattr(
        "app.services.reranking._load_bge_reranker_runtime",
        lambda model_name: (FakeTokenizer(), FakeModel(), "cpu", FakeTorchModule()),
    )

    results = _score_with_bge_reranker(
        query="which document",
        documents=[
            RerankInputDocument(candidate_id="doc-1", text="alpha"),
            RerankInputDocument(candidate_id="doc-2", text="beta"),
            RerankInputDocument(candidate_id="doc-3", text="gamma"),
        ],
        top_n=2,
        model_name="BAAI/bge-reranker-v2-m3",
    )

    assert [item.candidate_id for item in results] == ["doc-2", "doc-3"]
    assert results[0].score == pytest.approx(0.9)


def test_score_with_qwen_reranker_formats_inputs_and_sorts_scores(monkeypatch) -> None:
    """Qwen score helper 應套用官方格式並依 yes 機率排序。"""

    class FakeTensor:
        """最小 tensor 測試替身。"""

        def __init__(self, values):
            self._values = values

        def __getitem__(self, key):  # noqa: ANN001
            if isinstance(key, tuple) and len(key) == 3:
                rows, last_index, columns = key
                del rows, columns
                if last_index == -1:
                    return FakeTensor([row[last_index] for row in self._values])
            if isinstance(key, tuple) and len(key) == 2:
                rows, column = key
                del rows
                if isinstance(column, int):
                    return FakeTensor([row[column] for row in self._values])
            raise TypeError("測試替身只支援欄位切片。")

        def exp(self) -> "FakeTensor":
            return self

        def detach(self) -> "FakeTensor":
            return self

        def cpu(self) -> "FakeTensor":
            return self

        def float(self) -> "FakeTensor":
            return self

        def tolist(self):
            return list(self._values)

    class FakeNoGrad:
        """模擬 torch.no_grad() context manager。"""

        def __enter__(self) -> None:
            return None

        def __exit__(self, exc_type, exc, tb) -> bool:
            del exc_type, exc, tb
            return False

    class FakeTorchModule:
        """最小 torch 測試替身。"""

        class nn:
            """最小 nn namespace。"""

            class functional:
                """最小 functional namespace。"""

                @staticmethod
                def log_softmax(tensor: FakeTensor, dim: int) -> FakeTensor:
                    del dim
                    return tensor

        @staticmethod
        def no_grad() -> FakeNoGrad:
            return FakeNoGrad()

        @staticmethod
        def stack(tensors, dim: int):  # noqa: ANN001
            del dim
            first_tensor, second_tensor = tensors
            return FakeTensor(
                [
                    [first_value, second_value]
                    for first_value, second_value in zip(first_tensor.tolist(), second_tensor.tolist(), strict=True)
                ]
            )

    class FakeTokenizer:
        """最小 tokenizer 測試替身。"""

        def __call__(
            self,
            inputs,
            *,
            padding=False,
            truncation=None,
            return_attention_mask=True,
            max_length=None,
            return_tensors=None,
        ):  # noqa: ANN001
            del padding, truncation, return_attention_mask, max_length, return_tensors
            if isinstance(inputs, list) and inputs and isinstance(inputs[0], str):
                assert "<Instruct>:" in inputs[0]
                return {"input_ids": [[11, 12], [21, 22]]}
            raise AssertionError("測試替身只預期收到格式化後的字串列表。")

        def pad(self, inputs, *, padding, return_tensors, max_length=None):  # noqa: ANN001
            del padding, return_tensors, max_length
            return {"input_ids": inputs["input_ids"]}

    class FakeModel:
        """最小 model 測試替身。"""

        def __call__(self, **inputs):  # noqa: ANN003, ANN001
            del inputs

            class FakeOutput:
                """最小 logits 輸出替身。"""

                logits = FakeTensor(
                    [
                        [[0.1, 0.8]],
                        [[0.1, 0.4]],
                    ]
                )

            return FakeOutput()

    monkeypatch.setattr(
        "app.services.reranking._load_qwen_reranker_runtime",
        lambda model_name: (
            FakeTokenizer(),
            FakeModel(),
            "cpu",
            FakeTorchModule(),
            [1, 2],
            [3, 4],
            0,
            1,
        ),
    )

    results = _score_with_qwen_reranker(
        query="which document",
        documents=[
            RerankInputDocument(candidate_id="doc-1", text="alpha"),
            RerankInputDocument(candidate_id="doc-2", text="beta"),
        ],
        top_n=2,
        model_name="Qwen/Qwen3-Reranker-0.6B",
    )

    assert [item.candidate_id for item in results] == ["doc-1", "doc-2"]
    assert results[0].score == pytest.approx(0.8)


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
    assert result.trace.query_focus_applied is False
    assert result.trace.query_focus_language == "zh-TW"
    assert result.trace.focus_query == "中文檢索"
    assert result.trace.rerank_query == "中文檢索"
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


def test_build_evidence_synopsis_generic_variant_does_not_add_benchmark_specific_bridges() -> None:
    """generic_v1 不應補上 benchmark-specific bridge phrasing。"""

    dataset_synopsis = build_evidence_synopsis(
        heading="Experimental Studies ::: Dataset and Evaluation Metrics",
        content="It contains 17,833 sentences, 826,987 characters and 2,714 question-answer pairs.",
        variant="generic_v1",
    )
    metric_synopsis = build_evidence_synopsis(
        heading="實驗設計",
        content="本文比較困惑度、R@3、延遲與能耗等面向。",
        variant="generic_v1",
    )

    assert "dataset-alias questions" not in dataset_synopsis
    assert "question-answer pair statistics" not in dataset_synopsis
    assert "被統整的具體任務型別或問題型別" not in metric_synopsis
    assert "不同模型之間被比較的面向" not in metric_synopsis


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


def test_retrieve_area_candidates_generic_synopsis_does_not_include_benchmark_bridge_phrasing(
    db_session, app_settings, monkeypatch
) -> None:
    """generic synopsis variant 啟用時，rerank 文件不應包含 benchmark bridge phrasing。"""

    settings = app_settings.model_copy(
        update={
            "retrieval_evidence_synopsis_enabled": True,
            "retrieval_evidence_synopsis_variant": "generic_v1",
        }
    )
    area = Area(id=_uuid(), name="Retrieval Generic Evidence Synopsis")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-reader", role=Role.reader))
    document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="evidence-synopsis-generic.md",
        content_type="text/markdown",
        file_size=100,
        storage_key="area/document-evidence-synopsis-generic/evidence-synopsis-generic.md",
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
    assert "Evidence synopsis:" in captured_documents[0].text
    assert "dataset-alias questions" not in captured_documents[0].text
    assert "question-answer pair statistics" not in captured_documents[0].text


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


def test_retrieve_area_candidates_applies_query_focus_to_rerank_query_and_trace(
    db_session, app_settings, monkeypatch
) -> None:
    """query focus 啟用時，rerank query 與 trace 應帶入 planner 結果。"""

    settings = app_settings.model_copy(
        update={
            "retrieval_query_focus_enabled": True,
            "retrieval_evidence_synopsis_variant": "generic_v1",
        }
    )
    area = Area(id=_uuid(), name="Retrieval Query Focus")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-reader", role=Role.reader))
    document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="query-focus.md",
        content_type="text/markdown",
        file_size=100,
        storage_key="area/document-query-focus/query-focus.md",
        status=DocumentStatus.ready,
    )
    parent = DocumentChunk(
        id=_uuid(),
        document_id=document.id,
        parent_chunk_id=None,
        chunk_type=ChunkType.parent,
        structure_kind=ChunkStructureKind.table,
        position=0,
        section_index=0,
        child_index=None,
        heading="三、 文件申請資格",
        content="文件申請 研究助理 專案成員",
        content_preview="文件申請 研究助理 專案成員",
        char_count=len("文件申請 研究助理 專案成員"),
        start_offset=0,
        end_offset=len("文件申請 研究助理 專案成員"),
    )
    child = DocumentChunk(
        id=_uuid(),
        document_id=document.id,
        parent_chunk_id=parent.id,
        chunk_type=ChunkType.child,
        structure_kind=ChunkStructureKind.table,
        position=1,
        section_index=0,
        child_index=0,
        heading="三、 文件申請資格",
        content="文件申請 研究助理 專案成員",
        content_preview="文件申請 研究助理 專案成員",
        char_count=len("文件申請 研究助理 專案成員"),
        start_offset=0,
        end_offset=len("文件申請 研究助理 專案成員"),
        embedding=[0.1] * settings.embedding_dimensions,
    )
    db_session.add_all([document, parent, child])
    db_session.commit()

    captured_queries: list[str] = []

    class CapturingRerankProvider:
        """記錄 query focus rerank query 的測試替身。"""

        def rerank(self, *, query: str, documents: list[RerankInputDocument], top_n: int) -> list:
            """保存 rerank query 並回傳固定分數。

            參數：
            - `query`：送進 rerank 的 query。
            - `documents`：送入 rerank 的 parent-level 文件。
            - `top_n`：最多回傳筆數。

            回傳：
            - `list[RerankScore]`：依輸入順序建立的固定分數結果。
            """

            del top_n
            captured_queries.append(query)
            return [type("Score", (), {"candidate_id": document.candidate_id, "score": 1.0})() for document in documents]

    monkeypatch.setattr("app.services.retrieval.build_rerank_provider", lambda settings: CapturingRerankProvider())

    result = retrieve_area_candidates(
        session=db_session,
        principal=CurrentPrincipal(sub="user-reader", groups=("/group/reader",)),
        settings=settings,
        area_id=area.id,
        query="文件申請資格有哪些？",
    )

    assert captured_queries
    assert captured_queries[0].startswith("文件申請資格有哪些？\nNeed:")
    assert result.trace.query_focus_applied is True
    assert result.trace.query_focus_language == "zh-TW"
    assert result.trace.query_focus_intents == ["eligibility_or_actor", "enumeration_or_inventory"]
    assert result.trace.query_focus_slots["target_field"] == "資格或責任對象 / 項目清單或列舉內容"
    assert result.trace.query_focus_variant == "generic_field_focus_v1"
    assert result.trace.query_focus_rule_family == "generic"
    assert result.trace.evidence_synopsis_variant == "generic_v1"
    assert "資格或責任對象" in result.trace.focus_query
    assert result.trace.rerank_query == captured_queries[0]


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
