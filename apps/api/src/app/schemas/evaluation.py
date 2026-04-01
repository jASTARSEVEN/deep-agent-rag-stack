"""Retrieval evaluation dataset、review 與 run API schema。"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.db.models import EvaluationLanguage, EvaluationQueryType, EvaluationRunStatus


class CreateEvaluationDatasetRequest(BaseModel):
    """建立 retrieval evaluation dataset 的請求 payload。"""

    name: str = Field(min_length=1, max_length=255)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        """拒絕只有空白的 dataset 名稱。

        參數：
        - `value`：原始輸入名稱。

        回傳：
        - `str`：去除首尾空白後的名稱。
        """

        stripped = value.strip()
        if not stripped:
            raise ValueError("dataset 名稱不可為空白。")
        return stripped


class CreateEvaluationItemRequest(BaseModel):
    """建立 retrieval evaluation 題目的請求 payload。"""

    query_text: str = Field(min_length=1)
    language: EvaluationLanguage
    query_type: EvaluationQueryType = EvaluationQueryType.fact_lookup
    notes: str | None = None

    @field_validator("query_text")
    @classmethod
    def validate_query_text(cls, value: str) -> str:
        """拒絕只有空白的 query。

        參數：
        - `value`：原始 query 文字。

        回傳：
        - `str`：清理後的 query。
        """

        stripped = value.strip()
        if not stripped:
            raise ValueError("query_text 不可為空白。")
        return stripped


class MarkEvaluationSpanRequest(BaseModel):
    """新增 gold source span 的請求 payload。"""

    document_id: UUID
    start_offset: int = Field(ge=0)
    end_offset: int = Field(gt=0)
    relevance_grade: int = Field()

    @field_validator("relevance_grade")
    @classmethod
    def validate_relevance_grade(cls, value: int) -> int:
        """限制 relevance 僅支援 2 或 3。

        參數：
        - `value`：使用者指定的 relevance。

        回傳：
        - `int`：驗證通過的 relevance。
        """

        if value not in {2, 3}:
            raise ValueError("relevance_grade 只支援 2 或 3。")
        return value

    @field_validator("end_offset")
    @classmethod
    def validate_offsets(cls, value: int, info) -> int:
        """確保結束 offset 大於起始 offset。

        參數：
        - `value`：結束 offset。
        - `info`：Pydantic validator context。

        回傳：
        - `int`：驗證通過的結束 offset。
        """

        start_offset = info.data.get("start_offset", 0)
        if value <= start_offset:
            raise ValueError("end_offset 必須大於 start_offset。")
        return value


class RunEvaluationDatasetRequest(BaseModel):
    """執行 benchmark run 的請求 payload。"""

    top_k: int = Field(default=10, ge=1, le=20)
    evaluation_profile: str = Field(default="production_like_v1", min_length=1, max_length=64)

    @field_validator("evaluation_profile")
    @classmethod
    def validate_evaluation_profile(cls, value: str) -> str:
        """限制 evaluation profile 僅接受已知 profile。"""

        allowed_profiles = {"production_like_v1", "deterministic_gate_v1"}
        if value not in allowed_profiles:
            raise ValueError("evaluation_profile 只支援 production_like_v1 或 deterministic_gate_v1。")
        return value


class EvaluationDatasetSummary(BaseModel):
    """Retrieval evaluation dataset 摘要。"""

    model_config = {"from_attributes": True}

    id: UUID
    area_id: UUID
    name: str
    query_type: EvaluationQueryType
    baseline_run_id: UUID | None
    created_by_sub: str
    created_at: datetime
    updated_at: datetime
    item_count: int


class EvaluationDatasetListResponse(BaseModel):
    """指定 area 的 dataset 清單。"""

    items: list[EvaluationDatasetSummary]


class EvaluationItemSpanResponse(BaseModel):
    """單一 gold span 回應。"""

    model_config = {"from_attributes": True}

    id: UUID
    document_id: UUID | None
    start_offset: int
    end_offset: int
    relevance_grade: int | None
    is_retrieval_miss: bool
    created_by_sub: str
    created_at: datetime


class EvaluationItemSummary(BaseModel):
    """單一 evaluation 題目摘要。"""

    model_config = {"from_attributes": True}

    id: UUID
    dataset_id: UUID
    query_type: EvaluationQueryType
    query_text: str
    language: EvaluationLanguage
    notes: str | None
    created_at: datetime
    updated_at: datetime
    spans: list[EvaluationItemSpanResponse]


class EvaluationDocumentSearchHit(BaseModel):
    """文件內搜尋命中的簡化結果。"""

    document_id: UUID
    document_name: str
    chunk_id: UUID
    heading: str | None
    start_offset: int
    end_offset: int
    excerpt: str


class EvaluationStageCandidate(BaseModel):
    """單一階段候選結果。"""

    document_id: UUID
    document_name: str
    parent_chunk_id: UUID | None
    child_chunk_ids: list[UUID]
    heading: str | None
    start_offset: int
    end_offset: int
    excerpt: str
    source: str
    rank: int
    vector_rank: int | None = None
    fts_rank: int | None = None
    rrf_rank: int | None = None
    rerank_rank: int | None = None
    matched_relevance: int | None


class EvaluationCandidateStageResponse(BaseModel):
    """單一評估階段回應。"""

    stage: str
    first_hit_rank: int | None
    full_hit_rank: int | None = None
    # 是否已成功套用 rerank provider；非 rerank stage 時固定為空值。
    rerank_applied: bool | None = None
    # rerank fail-open 的原因；非 rerank stage 或未 fallback 時固定為空值。
    fallback_reason: str | None = None
    items: list[EvaluationStageCandidate]


class EvaluationCandidatePreviewResponse(BaseModel):
    """人工複核用 candidate preview 回應。"""

    dataset: EvaluationDatasetSummary
    item: EvaluationItemSummary
    recall: EvaluationCandidateStageResponse
    rerank: EvaluationCandidateStageResponse
    assembled: EvaluationCandidateStageResponse
    document_search_hits: list[EvaluationDocumentSearchHit]


class EvaluationPreviewDebugRequest(BaseModel):
    """單題 preview 的臨時調參請求。"""

    top_k: int = Field(default=20, ge=1, le=300)
    retrieval_vector_top_k: int | None = Field(default=None, ge=1, le=300)
    retrieval_fts_top_k: int | None = Field(default=None, ge=1, le=300)
    retrieval_max_candidates: int | None = Field(default=None, ge=1, le=300)
    rerank_top_n: int | None = Field(default=None, ge=1, le=300)
    apply_rerank: bool = True


class EvaluationStageMetricSummary(BaseModel):
    """單一 stage 的 summary metrics。"""

    nDCG_at_k: float
    recall_at_k: float
    mrr_at_k: float
    precision_at_k: float
    document_coverage_at_k: float


class EvaluationSummaryByDimension(BaseModel):
    """依維度切分的 metrics。"""

    dimension: str
    value: str
    metrics: dict[str, EvaluationStageMetricSummary]


class EvaluationPerQueryStageDetail(BaseModel):
    """單題單階段明細。"""

    first_hit_rank: int | None
    matched_core_evidence: bool
    matched_relevance: int | None
    # 是否已成功套用 rerank provider；非 rerank stage 時固定為空值。
    rerank_applied: bool | None = None
    # rerank fail-open 的原因；非 rerank stage 或未 fallback 時固定為空值。
    fallback_reason: str | None = None


class EvaluationPerQueryDetail(BaseModel):
    """單題 benchmark 詳細結果。"""

    item_id: UUID
    query_text: str
    language: EvaluationLanguage
    retrieval_miss: bool
    gold_spans: list[EvaluationItemSpanResponse]
    recall: EvaluationPerQueryStageDetail
    rerank: EvaluationPerQueryStageDetail
    assembled: EvaluationPerQueryStageDetail
    baseline_delta: dict[str, float | None]


class EvaluationRunSummary(BaseModel):
    """單次 benchmark run 摘要。"""

    model_config = {"from_attributes": True}

    id: UUID
    dataset_id: UUID
    status: EvaluationRunStatus
    baseline_run_id: UUID | None
    created_by_sub: str
    total_items: int
    evaluation_profile: str
    config_snapshot: dict[str, object]
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None


class EvaluationRunReportResponse(BaseModel):
    """Benchmark run 完整報表。"""

    run: EvaluationRunSummary
    dataset: EvaluationDatasetSummary
    summary_metrics: dict[str, EvaluationStageMetricSummary]
    breakdowns: list[EvaluationSummaryByDimension]
    per_query: list[EvaluationPerQueryDetail]
    baseline_compare: dict[str, object] | None


class EvaluationDatasetDetailResponse(BaseModel):
    """Dataset 詳細資料。"""

    dataset: EvaluationDatasetSummary
    items: list[EvaluationItemSummary]
    runs: list[EvaluationRunSummary]
