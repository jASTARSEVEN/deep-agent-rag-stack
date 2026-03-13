"""將 retrieval candidates 組裝為 chat-ready context 與 citation metadata。"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.settings import AppSettings
from app.db.models import ChunkStructureKind, ChunkType, DocumentChunk
from app.services.retrieval import RetrievalCandidate, RetrievalResult, RetrievalTrace


@dataclass(slots=True)
class Citation:
    """單一 assembler citation 資料。"""

    # citation 所屬文件識別碼。
    document_id: str
    # citation 所屬 parent chunk 識別碼。
    parent_chunk_id: str | None
    # citation 對應的 child chunk 識別碼。
    chunk_id: str
    # citation 所屬段落標題。
    heading: str | None
    # citation 內容結構型別。
    structure_kind: ChunkStructureKind
    # citation 在 normalized text 的起始 offset。
    start_offset: int
    # citation 在 normalized text 的結束 offset。
    end_offset: int
    # citation 摘錄文字。
    excerpt: str


@dataclass(slots=True)
class AssembledContext:
    """組裝後的單一 prompt-ready context。"""

    # context 所屬文件識別碼。
    document_id: str
    # context 所屬 parent chunk 識別碼。
    parent_chunk_id: str | None
    # 合併進此 context 的 child chunk 識別碼。
    chunk_ids: list[str]
    # context 內容結構型別。
    structure_kind: ChunkStructureKind
    # context 所屬段落標題。
    heading: str | None
    # 組裝後可直接送入後續 chat 的文字。
    assembled_text: str
    # context 來源，可能為 vector、fts 或 hybrid。
    source: str
    # context 在 normalized text 的起始 offset。
    start_offset: int
    # context 在 normalized text 的結束 offset。
    end_offset: int


@dataclass(slots=True)
class AssemblerContextTrace:
    """單一組裝 context 的 trace metadata。"""

    # context 在回傳列表中的順序。
    context_index: int
    # context 所屬 parent chunk 識別碼。
    parent_chunk_id: str | None
    # 保留在此 context 的 child chunk 識別碼。
    kept_chunk_ids: list[str]
    # 因 children 上限被捨棄的 child chunk 識別碼。
    dropped_chunk_ids: list[str]
    # 此 context 是否發生文字裁切。
    truncated: bool


@dataclass(slots=True)
class AssemblerTrace:
    """assembler 執行過程的 trace metadata。"""

    # 最多保留的 assembled contexts 數量。
    max_contexts: int
    # 每個 assembled context 的最大字元數。
    max_chars_per_context: int
    # 同一 parent 最多保留的 child 數量。
    max_children_per_parent: int
    # 被保留的 child chunk 識別碼。
    kept_chunk_ids: list[str]
    # 被捨棄的 child chunk 識別碼。
    dropped_chunk_ids: list[str]
    # 各 assembled context 的 trace。
    contexts: list[AssemblerContextTrace]


@dataclass(slots=True)
class AssembledRetrievalTrace:
    """整合 retrieval 與 assembler 的 trace metadata。"""

    # 原始 retrieval trace。
    retrieval: RetrievalTrace
    # assembler trace。
    assembler: AssemblerTrace


@dataclass(slots=True)
class AssembledRetrievalResult:
    """assembler 的完整輸出結果。"""

    # 組裝後的 contexts。
    assembled_contexts: list[AssembledContext]
    # citation-ready metadata。
    citations: list[Citation]
    # retrieval + assembler trace。
    trace: AssembledRetrievalTrace


@dataclass(slots=True)
class _CandidateRecord:
    """assembler 使用的候選 chunk 補查結果。"""

    # retrieval candidate 的原始順序。
    order: int
    # retrieval candidate。
    candidate: RetrievalCandidate
    # 資料庫補查出的 child chunk。
    chunk: DocumentChunk


def assemble_retrieval_result(
    *,
    session: Session,
    settings: AppSettings,
    retrieval_result: RetrievalResult,
) -> AssembledRetrievalResult:
    """將 rerank 後的 retrieval result 組裝為 chat-ready contexts。

    參數：
    - `session`：目前資料庫 session。
    - `settings`：API 執行期設定。
    - `retrieval_result`：已完成 SQL gate、recall、RRF 與 rerank 的 retrieval 結果。

    回傳：
    - `AssembledRetrievalResult`：組裝後的 contexts、citations 與 trace。
    """

    if not retrieval_result.candidates:
        return AssembledRetrievalResult(
            assembled_contexts=[],
            citations=[],
            trace=AssembledRetrievalTrace(
                retrieval=retrieval_result.trace,
                assembler=AssemblerTrace(
                    max_contexts=settings.assembler_max_contexts,
                    max_chars_per_context=settings.assembler_max_chars_per_context,
                    max_children_per_parent=settings.assembler_max_children_per_parent,
                    kept_chunk_ids=[],
                    dropped_chunk_ids=[],
                    contexts=[],
                ),
            ),
        )

    candidate_ids = [candidate.chunk_id for candidate in retrieval_result.candidates]
    chunk_by_id = _load_child_chunks(session=session, chunk_ids=candidate_ids)
    parent_chunk_by_id = _load_parent_chunks(
        session=session,
        parent_chunk_ids=[candidate.parent_chunk_id for candidate in retrieval_result.candidates if candidate.parent_chunk_id],
    )

    grouped_records: OrderedDict[tuple[str, str | None, ChunkStructureKind], list[_CandidateRecord]] = OrderedDict()
    for order, candidate in enumerate(retrieval_result.candidates):
        chunk = chunk_by_id.get(candidate.chunk_id)
        if chunk is None:
            raise ValueError(f"找不到 retrieval candidate 對應的 child chunk：{candidate.chunk_id}")
        group_key = (candidate.document_id, candidate.parent_chunk_id, candidate.structure_kind)
        grouped_records.setdefault(group_key, []).append(_CandidateRecord(order=order, candidate=candidate, chunk=chunk))

    assembled_contexts: list[AssembledContext] = []
    citations: list[Citation] = []
    kept_chunk_ids: list[str] = []
    dropped_chunk_ids: list[str] = []
    context_traces: list[AssemblerContextTrace] = []

    for records in grouped_records.values():
        if len(assembled_contexts) >= settings.assembler_max_contexts:
            dropped_chunk_ids.extend(record.candidate.chunk_id for record in records)
            continue

        sorted_records = sorted(
            records,
            key=lambda record: (
                record.chunk.child_index if record.chunk.child_index is not None else -1,
                record.order,
            ),
        )
        kept_records = sorted_records[: settings.assembler_max_children_per_parent]
        dropped_records = sorted_records[settings.assembler_max_children_per_parent :]

        if not kept_records:
            dropped_chunk_ids.extend(record.candidate.chunk_id for record in records)
            continue

        parent_chunk = parent_chunk_by_id.get(kept_records[0].candidate.parent_chunk_id or "")
        assembled_text, truncated = _build_assembled_text(
            records=kept_records,
            max_chars=settings.assembler_max_chars_per_context,
        )
        context_source = _resolve_context_source(records=kept_records)
        heading = kept_records[0].candidate.heading or (parent_chunk.heading if parent_chunk is not None else None)
        start_offset = min(record.candidate.start_offset for record in kept_records)
        end_offset = max(record.candidate.end_offset for record in kept_records)
        chunk_ids = [record.candidate.chunk_id for record in kept_records]

        assembled_contexts.append(
            AssembledContext(
                document_id=kept_records[0].candidate.document_id,
                parent_chunk_id=kept_records[0].candidate.parent_chunk_id,
                chunk_ids=chunk_ids,
                structure_kind=kept_records[0].candidate.structure_kind,
                heading=heading,
                assembled_text=assembled_text,
                source=context_source,
                start_offset=start_offset,
                end_offset=end_offset,
            )
        )
        citations.extend(
            Citation(
                document_id=record.candidate.document_id,
                parent_chunk_id=record.candidate.parent_chunk_id,
                chunk_id=record.candidate.chunk_id,
                heading=record.candidate.heading or heading,
                structure_kind=record.candidate.structure_kind,
                start_offset=record.candidate.start_offset,
                end_offset=record.candidate.end_offset,
                excerpt=record.candidate.content,
            )
            for record in kept_records
        )
        kept_chunk_ids.extend(chunk_ids)
        dropped_chunk_ids.extend(record.candidate.chunk_id for record in dropped_records)
        context_traces.append(
            AssemblerContextTrace(
                context_index=len(assembled_contexts) - 1,
                parent_chunk_id=kept_records[0].candidate.parent_chunk_id,
                kept_chunk_ids=chunk_ids,
                dropped_chunk_ids=[record.candidate.chunk_id for record in dropped_records],
                truncated=truncated,
            )
        )

    return AssembledRetrievalResult(
        assembled_contexts=assembled_contexts,
        citations=citations,
        trace=AssembledRetrievalTrace(
            retrieval=retrieval_result.trace,
            assembler=AssemblerTrace(
                max_contexts=settings.assembler_max_contexts,
                max_chars_per_context=settings.assembler_max_chars_per_context,
                max_children_per_parent=settings.assembler_max_children_per_parent,
                kept_chunk_ids=kept_chunk_ids,
                dropped_chunk_ids=dropped_chunk_ids,
                contexts=context_traces,
            ),
        ),
    )


def _load_child_chunks(*, session: Session, chunk_ids: list[str]) -> dict[str, DocumentChunk]:
    """依 chunk ids 補查 child chunk。

    參數：
    - `session`：目前資料庫 session。
    - `chunk_ids`：要補查的 child chunk ids。

    回傳：
    - `dict[str, DocumentChunk]`：以 chunk id 為鍵的 child chunk 對照表。
    """

    if not chunk_ids:
        return {}

    chunks = session.scalars(
        select(DocumentChunk).where(
            DocumentChunk.id.in_(chunk_ids),
            DocumentChunk.chunk_type == ChunkType.child,
        )
    ).all()
    return {chunk.id: chunk for chunk in chunks}


def _load_parent_chunks(*, session: Session, parent_chunk_ids: list[str]) -> dict[str, DocumentChunk]:
    """依 parent chunk ids 補查 parent chunk。

    參數：
    - `session`：目前資料庫 session。
    - `parent_chunk_ids`：要補查的 parent chunk ids。

    回傳：
    - `dict[str, DocumentChunk]`：以 parent chunk id 為鍵的對照表。
    """

    if not parent_chunk_ids:
        return {}

    parent_chunks = session.scalars(
        select(DocumentChunk).where(
            DocumentChunk.id.in_(parent_chunk_ids),
            DocumentChunk.chunk_type == ChunkType.parent,
        )
    ).all()
    return {chunk.id: chunk for chunk in parent_chunks}


def _build_assembled_text(*, records: list[_CandidateRecord], max_chars: int) -> tuple[str, bool]:
    """建立單一 context 的 assembled text。

    參數：
    - `records`：同一組 context 的候選 child chunks。
    - `max_chars`：單一 context 可用的最大字元數。

    回傳：
    - `tuple[str, bool]`：組裝後文字與是否發生裁切。
    """

    if records[0].candidate.structure_kind == ChunkStructureKind.table:
        assembled_text = _merge_table_records(records=records)
    else:
        assembled_text = "\n\n".join(record.candidate.content.strip() for record in records if record.candidate.content.strip())

    normalized_text = assembled_text.strip()
    if len(normalized_text) <= max_chars:
        return normalized_text, False
    return normalized_text[:max_chars], True


def _merge_table_records(*, records: list[_CandidateRecord]) -> str:
    """將多個 table row-group child 合併為單一 table context。

    參數：
    - `records`：同一 parent 下、已依 child 順序排序的 table child chunks。

    回傳：
    - `str`：只保留一次表頭的 Markdown table 內容。
    """

    merged_lines: list[str] = []
    for index, record in enumerate(records):
        lines = [line.rstrip() for line in record.candidate.content.strip().splitlines() if line.strip()]
        if not lines:
            continue
        if index == 0 or len(lines) < 3:
            merged_lines.extend(lines)
            continue
        merged_lines.extend(lines[2:])
    return "\n".join(merged_lines).strip()


def _resolve_context_source(*, records: list[_CandidateRecord]) -> str:
    """決定 assembled context 的來源欄位。

    參數：
    - `records`：同一 context 的候選 child chunks。

    回傳：
    - `str`：`vector`、`fts` 或 `hybrid`。
    """

    sources = {record.candidate.source for record in records}
    if "hybrid" in sources or len(sources) > 1:
        return "hybrid"
    return next(iter(sources), "fts")
