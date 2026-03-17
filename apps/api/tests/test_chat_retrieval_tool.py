"""`retrieve_area_contexts_tool` 與其 payload helper 測試。"""

from uuid import uuid4

from app.auth.verifier import CurrentPrincipal
from app.chat.tools.retrieval import (
    build_agent_tool_context_payload,
    build_assembled_context_payload,
    build_chat_citations,
    build_tool_call_output_summary,
    retrieve_area_contexts_tool,
)
from app.services.retrieval import RetrievalTrace
from app.services.retrieval_assembler import (
    AssembledContext,
    AssembledRetrievalResult,
    AssembledRetrievalTrace,
    AssemblerContextTrace,
    AssemblerTrace,
)
from app.db.models import Area, AreaUserRole, ChunkStructureKind, ChunkType, Document, DocumentChunk, DocumentStatus, Role


def _uuid() -> str:
    """建立測試用 UUID 字串。

    參數：
    - 無。

    回傳：
    - `str`：新的 UUID 字串。
    """

    return str(uuid4())


def test_retrieve_area_contexts_tool_returns_context_level_contract(db_session, app_settings) -> None:
    """tool 應回傳 assembled-context level 的 contexts、citations 與 trace。

    參數：
    - `db_session`：測試資料庫 session fixture。
    - `app_settings`：測試設定 fixture。

    回傳：
    - `None`：以斷言驗證 tool contract。
    """

    area = Area(id=_uuid(), name="Tool Contract")
    document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="tool-contract.md",
        content_type="text/markdown",
        file_size=100,
        storage_key="area/document-tool-contract/tool-contract.md",
        status=DocumentStatus.ready,
    )
    parent = DocumentChunk(
        id=_uuid(),
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
        id=_uuid(),
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
        id=_uuid(),
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
    db_session.add_all(
        [
            area,
            AreaUserRole(area_id=area.id, user_sub="user-reader", role=Role.reader),
            document,
            parent,
            child_one,
            child_two,
        ]
    )
    db_session.commit()

    result = retrieve_area_contexts_tool(
        session=db_session,
        principal=CurrentPrincipal(sub="user-reader", groups=("/group/reader",)),
        settings=app_settings,
        area_id=area.id,
        question="alpha",
    )

    assert len(result.assembled_contexts) == 1
    assert result.assembled_contexts[0].chunk_ids == [child_one.id, child_two.id]
    assert result.assembled_contexts[0].assembled_text == "alpha intro\n\nalpha details"
    assert len(result.citations) == 1
    assert result.citations[0].context_index == 0
    assert result.citations[0].document_id == document.id
    assert result.citations[0].parent_chunk_id == parent.id
    assert result.citations[0].child_chunk_ids == [child_one.id, child_two.id]
    assert result.citations[0].heading == "Section"
    assert result.citations[0].structure_kind == ChunkStructureKind.text
    assert result.citations[0].source == "hybrid"
    assert result.citations[0].excerpt == "alpha intro\n\nalpha details"
    assert result.citations[0].truncated is False
    assert result.trace["retrieval"]["query"] == "alpha"
    assert result.trace["assembler"]["kept_chunk_ids"] == [child_one.id, child_two.id]
    assert result.trace["assembler"]["contexts"][0]["context_index"] == 0
    assert result.trace["assembler"]["contexts"][0]["truncated"] is False


def test_retrieval_tool_payload_builders_follow_runtime_contract(db_session, app_settings) -> None:
    """payload helper 應輸出 runtime 與 debug UI 需要的固定欄位。

    參數：
    - `db_session`：測試資料庫 session fixture。
    - `app_settings`：測試設定 fixture。

    回傳：
    - `None`：以斷言驗證 helper contract。
    """

    settings = app_settings.model_copy(update={"assembler_max_chars_per_context": 10})
    area = Area(id=_uuid(), name="Tool Payload")
    document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="tool-payload.md",
        content_type="text/markdown",
        file_size=100,
        storage_key="area/document-tool-payload/tool-payload.md",
        status=DocumentStatus.ready,
    )
    parent = DocumentChunk(
        id=_uuid(),
        document_id=document.id,
        parent_chunk_id=None,
        chunk_type=ChunkType.parent,
        structure_kind=ChunkStructureKind.text,
        position=0,
        section_index=0,
        child_index=None,
        heading="Payload Section",
        content="alpha intro\n\nalpha details",
        content_preview="alpha intro",
        char_count=27,
        start_offset=0,
        end_offset=27,
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
        heading="Payload Section",
        content="alpha intro",
        content_preview="alpha intro",
        char_count=11,
        start_offset=0,
        end_offset=11,
        embedding=[0.1] * settings.embedding_dimensions,
    )
    db_session.add_all(
        [
            area,
            AreaUserRole(area_id=area.id, user_sub="user-reader", role=Role.reader),
            document,
            parent,
            child,
        ]
    )
    db_session.commit()

    result = retrieve_area_contexts_tool(
        session=db_session,
        principal=CurrentPrincipal(sub="user-reader", groups=("/group/reader",)),
        settings=settings,
        area_id=area.id,
        question="alpha",
    )

    assembled_payload = build_assembled_context_payload(result)
    llm_payload = build_agent_tool_context_payload(result)
    summary_payload = build_tool_call_output_summary(result)

    assert assembled_payload == [
        {
            "context_index": 0,
            "document_id": document.id,
            "parent_chunk_id": parent.id,
            "child_chunk_ids": [child.id],
            "structure_kind": "text",
            "heading": "Payload Section",
            "excerpt": "alpha intr",
            "assembled_text": "alpha intr",
            "source": "hybrid",
            "start_offset": 0,
            "end_offset": 11,
            "truncated": True,
        }
    ]
    assert llm_payload == [{"heading": "Payload Section", "assembled_text": "alpha intr"}]
    assert summary_payload == {
        "contexts_count": 1,
        "citations_count": 1,
        "contexts": [
            {
                "context_index": 0,
                "document_id": document.id,
                "parent_chunk_id": parent.id,
                "child_chunk_ids": [child.id],
                "heading": "Payload Section",
                "structure_kind": "text",
                "source": "hybrid",
                "truncated": True,
                "excerpt": "alpha intr",
            }
        ],
    }


def test_retrieval_tool_payload_builders_accept_none() -> None:
    """payload helper 在缺少 tool result 時應回傳安全的空結構。

    參數：
    - 無。

    回傳：
    - `None`：以斷言驗證空值處理。
    """

    assert build_assembled_context_payload(None) == []
    assert build_agent_tool_context_payload(None) == []
    assert build_tool_call_output_summary(None) == {
        "contexts_count": 0,
        "citations_count": 0,
        "contexts": [],
    }


def test_build_chat_citations_normalizes_uuid_ids() -> None:
    """citation builder 應接受 PostgreSQL `UUID` 並正規化為字串。

    參數：
    - 無。

    回傳：
    - `None`：以斷言驗證 UUID 正規化。
    """

    document_id = uuid4()
    parent_chunk_id = uuid4()
    child_chunk_ids = [uuid4(), uuid4()]
    assembled_result = AssembledRetrievalResult(
        assembled_contexts=[
            AssembledContext(
                document_id=document_id,  # type: ignore[arg-type]
                parent_chunk_id=parent_chunk_id,  # type: ignore[arg-type]
                chunk_ids=child_chunk_ids,  # type: ignore[arg-type]
                structure_kind=ChunkStructureKind.text,
                heading="UUID Section",
                assembled_text="uuid normalize",
                source="hybrid",
                start_offset=0,
                end_offset=14,
            )
        ],
        citations=[],
        trace=AssembledRetrievalTrace(
            retrieval=RetrievalTrace(
                query="uuid normalize",
                vector_top_k=8,
                fts_top_k=8,
                max_candidates=8,
                rerank_top_n=8,
                candidates=[],
            ),
            assembler=AssemblerTrace(
                max_contexts=4,
                max_chars_per_context=4000,
                max_children_per_parent=4,
                kept_chunk_ids=[str(item) for item in child_chunk_ids],
                dropped_chunk_ids=[],
                contexts=[
                    AssemblerContextTrace(
                        context_index=0,
                        parent_chunk_id=str(parent_chunk_id),
                        kept_chunk_ids=[str(item) for item in child_chunk_ids],
                        dropped_chunk_ids=[],
                        truncated=False,
                    )
                ],
            ),
        ),
    )

    citations = build_chat_citations(assembled_result=assembled_result, max_items=4)

    assert len(citations) == 1
    assert citations[0].document_id == str(document_id)
    assert citations[0].parent_chunk_id == str(parent_chunk_id)
    assert citations[0].child_chunk_ids == [str(item) for item in child_chunk_ids]
