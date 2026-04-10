"""Worker 使用的 evidence units 生成、path 評分與 clustering。"""

from __future__ import annotations

import json
import re
import time
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import TYPE_CHECKING

from worker.core.settings import WorkerSettings
from worker.db import (
    ChunkStructureKind,
    EvidenceBuildStrategy,
    EvidenceClusterStrategy,
    EvidencePathQualityReason,
    EvidenceType,
)

if TYPE_CHECKING:
    from worker.db import DocumentChunk


# `目錄` 與其英文變體通常是 parser 誤把 TOC 當 section path 的主要訊號。
TOC_NOISE_TOKENS = ("目錄", "table of contents", "contents")
# 領導點與頁碼序列通常代表 TOC 噪音。
LEADER_DOTS_PATTERN = re.compile(r"\.{6,}|…{3,}")
# 常見頁碼或數字尾碼模式。
PAGE_NUMBER_PATTERN = re.compile(r"(?:^|\s)\d{1,4}(?:\s|$)")
# 中英混合句界切分。
SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[。！？!?;；\n])\s+")
# 用於估算 path 與內容重疊的 token pattern。
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9]+|[\u3400-\u4dbf\u4e00-\u9fff]{1,6}")
# deterministic fallback 不應把 evidence cluster 的控制欄位當作 evidence 內容。
SOURCE_METADATA_LINE_PREFIXES = (
    "Heading Path:",
    "Section Path:",
    "Cluster Strategy:",
    "Path Quality:",
)
# LLM evidence 失敗時最多重試次數；若全數失敗，文件索引應進入 failed，而不是改用 deterministic。
EVIDENCE_UNITS_LLM_MAX_RETRIES = 10


@dataclass(frozen=True, slots=True)
class PathQualityResult:
    """單一 parent 的 path 品質評分結果。"""

    score: float
    reason: EvidencePathQualityReason
    is_toc_like_noise: bool


@dataclass(frozen=True, slots=True)
class EvidenceCluster:
    """單一 evidence cluster 的來源上下文。"""

    parent_chunks: tuple[DocumentChunk, ...]
    child_chunks: tuple[DocumentChunk, ...]
    cluster_strategy: EvidenceClusterStrategy
    path_quality_score: float
    path_quality_reason: EvidencePathQualityReason
    heading_path: str | None
    section_path_text: str | None


@dataclass(frozen=True, slots=True)
class EvidenceUnitDraft:
    """尚未持久化的 evidence unit 草稿。"""

    evidence_type: EvidenceType
    evidence_text: str
    build_strategy: EvidenceBuildStrategy
    confidence: float
    cluster_strategy: EvidenceClusterStrategy
    path_quality_score: float
    path_quality_reason: EvidencePathQualityReason
    heading_path: str | None
    section_path_text: str | None
    parent_chunk_ids: tuple[str, ...]
    child_chunk_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EvidenceGenerationResult:
    """文件級 evidence generation 結果。"""

    drafts: tuple[EvidenceUnitDraft, ...]
    effective_strategy: EvidenceBuildStrategy | None
    fallback_reason: str | None


class EvidenceUnitProvider(ABC):
    """Evidence units provider 抽象介面。"""

    @abstractmethod
    def generate_units(
        self,
        *,
        file_name: str,
        cluster: EvidenceCluster,
        max_units: int,
        max_output_chars: int,
    ) -> list[EvidenceUnitDraft]:
        """根據 cluster 內容產生 evidence unit。

        參數：
        - `file_name`：目前文件檔名。
        - `cluster`：本次 evidence 生成的 cluster。
        - `max_units`：單一 cluster 允許的最大 evidence 數。
        - `max_output_chars`：單一 evidence 最大字元數。

        回傳：
        - `list[EvidenceUnitDraft]`：尚未持久化的 evidence unit 草稿。
        """


class DeterministicEvidenceUnitProvider(EvidenceUnitProvider):
    """規則式 evidence unit provider。"""

    def generate_units(
        self,
        *,
        file_name: str,
        cluster: EvidenceCluster,
        max_units: int,
        max_output_chars: int,
    ) -> list[EvidenceUnitDraft]:
        """以規則式方式建立 evidence units。

        參數：
        - `file_name`：目前文件檔名。
        - `cluster`：本次 evidence 生成的 cluster。
        - `max_units`：單一 cluster 允許的最大 evidence 數。
        - `max_output_chars`：單一 evidence 最大字元數。

        回傳：
        - `list[EvidenceUnitDraft]`：規則式生成的 evidence unit 草稿。
        """

        del file_name
        source_text = build_cluster_source_text(cluster=cluster, max_input_chars=6_000)
        snippets = _extract_candidate_snippets(source_text=source_text)
        drafts: list[EvidenceUnitDraft] = []
        seen_texts: set[str] = set()
        for snippet in snippets:
            evidence_type = _classify_evidence_type(snippet=snippet, cluster=cluster)
            normalized_snippet = _truncate_text(snippet, max_output_chars)
            if not normalized_snippet or normalized_snippet in seen_texts:
                continue
            seen_texts.add(normalized_snippet)
            drafts.append(
                _build_evidence_draft(
                    cluster=cluster,
                    evidence_type=evidence_type,
                    evidence_text=normalized_snippet,
                    build_strategy=EvidenceBuildStrategy.deterministic,
                    confidence=_deterministic_confidence(snippet=normalized_snippet, evidence_type=evidence_type),
                )
            )
            if len(drafts) >= max_units:
                break

        if drafts:
            return drafts

        fallback_text = _truncate_text(_normalize_text(cluster.parent_chunks[0].content), max_output_chars)
        if not fallback_text:
            return []
        return [
            _build_evidence_draft(
                cluster=cluster,
                evidence_type=EvidenceType.claim,
                evidence_text=fallback_text,
                build_strategy=EvidenceBuildStrategy.deterministic,
                confidence=0.35,
            )
        ]


class OpenAIEvidenceUnitProvider(EvidenceUnitProvider):
    """使用 OpenAI 產生 evidence units。"""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        max_output_tokens: int,
        reasoning_effort: str,
        text_verbosity: str,
        max_input_chars: int,
    ) -> None:
        """初始化 OpenAI evidence provider。

        參數：
        - `api_key`：OpenAI API key。
        - `model`：要使用的 chat model。
        - `max_output_tokens`：Responses API 輸出上限。
        - `reasoning_effort`：GPT-5 family reasoning effort。
        - `text_verbosity`：GPT-5 family text verbosity。
        - `max_input_chars`：送入模型的最大輸入字元數。

        回傳：
        - `None`：僅建立 client 與保存設定。
        """

        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("缺少 openai 套件，無法建立 evidence unit provider。") from exc

        self._client = OpenAI(api_key=api_key)
        self._model = model
        self._max_output_tokens = max_output_tokens
        self._reasoning_effort = reasoning_effort
        self._text_verbosity = text_verbosity
        self._max_input_chars = max_input_chars

    def generate_units(
        self,
        *,
        file_name: str,
        cluster: EvidenceCluster,
        max_units: int,
        max_output_chars: int,
    ) -> list[EvidenceUnitDraft]:
        """呼叫 OpenAI 產生 evidence units。

        參數：
        - `file_name`：目前文件檔名。
        - `cluster`：本次 evidence 生成的 cluster。
        - `max_units`：單一 cluster 允許的最大 evidence 數。
        - `max_output_chars`：單一 evidence 最大字元數。

        回傳：
        - `list[EvidenceUnitDraft]`：LLM 生成的 evidence unit 草稿。
        """

        source_text = build_cluster_source_text(cluster=cluster, max_input_chars=self._max_input_chars)
        system_prompt = (
            "You generate evidence units for retrieval. "
            "Return only strict JSON. Do not invent facts. "
            "Each evidence unit must be concise, citation-groundable, and useful for retrieval."
        )
        user_prompt = (
            f"File name: {file_name}\n"
            f"Max units: {max_units}\n"
            f"Max chars per unit: {max_output_chars}\n"
            "Allowed evidence_type values: claim, metric, procedure, table_finding, comparison_point\n"
            "Return JSON array only. Each item must be an object with keys: evidence_type, evidence_text, confidence.\n"
            "Compressed source:\n"
            f"{source_text}"
        )
        try:
            if _is_gpt5_family_model(self._model):
                response = self._client.responses.create(
                    model=self._model,
                    max_output_tokens=self._max_output_tokens,
                    reasoning={"effort": self._reasoning_effort},
                    text={"verbosity": self._text_verbosity},
                    instructions=system_prompt,
                    input=user_prompt,
                )
                content = _extract_response_output_text(response)
            else:
                response = self._client.chat.completions.create(
                    model=self._model,
                    max_completion_tokens=self._max_output_tokens,
                    temperature=0.1,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                )
                content = response.choices[0].message.content if response.choices else None
        except Exception as exc:  # pragma: no cover
            raise ValueError(f"evidence unit 生成失敗：{exc}") from exc

        if not isinstance(content, str) or not content.strip():
            raise ValueError("evidence unit 生成失敗：LLM 未回傳有效內容。")
        try:
            payload = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError("evidence unit 生成失敗：LLM 未回傳 JSON array。") from exc
        if not isinstance(payload, list):
            raise ValueError("evidence unit 生成失敗：LLM 回傳格式不是 JSON array。")

        drafts: list[EvidenceUnitDraft] = []
        for item in payload[:max_units]:
            if not isinstance(item, dict):
                continue
            type_value = str(item.get("evidence_type", "")).strip()
            text_value = _truncate_text(_normalize_text(str(item.get("evidence_text", ""))), max_output_chars)
            confidence_value = item.get("confidence", 0.0)
            if type_value not in {member.value for member in EvidenceType} or not text_value:
                continue
            try:
                confidence = max(0.0, min(float(confidence_value), 1.0))
            except (TypeError, ValueError):
                confidence = 0.5
            drafts.append(
                _build_evidence_draft(
                    cluster=cluster,
                    evidence_type=EvidenceType(type_value),
                    evidence_text=text_value,
                    build_strategy=EvidenceBuildStrategy.llm,
                    confidence=confidence,
                )
            )
        if not drafts:
            raise ValueError("evidence unit 生成失敗：LLM 未產生有效 evidence。")
        return drafts


def build_evidence_unit_provider(*, settings: WorkerSettings, strategy: EvidenceBuildStrategy) -> EvidenceUnitProvider:
    """依設定建立 evidence unit provider。

    參數：
    - `settings`：worker 執行期設定。
    - `strategy`：目標 build strategy。

    回傳：
    - `EvidenceUnitProvider`：可實際產生 evidence unit 的 provider。
    """

    if strategy == EvidenceBuildStrategy.deterministic:
        return DeterministicEvidenceUnitProvider()
    if strategy == EvidenceBuildStrategy.llm:
        if not settings.openai_api_key:
            raise ValueError("使用 LLM evidence units 前必須提供 OPENAI_API_KEY。")
        return OpenAIEvidenceUnitProvider(
            api_key=settings.openai_api_key,
            model=settings.evidence_units_model,
            max_output_tokens=settings.evidence_units_max_output_tokens,
            reasoning_effort=settings.evidence_units_reasoning_effort,
            text_verbosity=settings.evidence_units_text_verbosity,
            max_input_chars=settings.evidence_units_max_input_chars,
        )
    raise ValueError(f"不支援的 evidence build strategy：{strategy.value}")


def generate_evidence_units_for_document(
    *,
    settings: WorkerSettings,
    file_name: str,
    parent_chunks: list[DocumentChunk],
    child_chunks: list[DocumentChunk],
) -> EvidenceGenerationResult:
    """為整份文件產生 evidence units。

    參數：
    - `settings`：worker 執行期設定。
    - `file_name`：目前文件檔名。
    - `parent_chunks`：依文件順序排序的 parent chunks。
    - `child_chunks`：依文件順序排序的 child chunks。

    回傳：
    - `EvidenceGenerationResult`：文件級 evidence generation 結果。
    """

    if not settings.evidence_units_enabled:
        return EvidenceGenerationResult(drafts=(), effective_strategy=None, fallback_reason=None)

    requested_strategy = EvidenceBuildStrategy(settings.evidence_units_build_strategy.strip().lower())
    clusters = build_evidence_clusters(parent_chunks=parent_chunks, child_chunks=child_chunks)
    if not clusters:
        return EvidenceGenerationResult(drafts=(), effective_strategy=requested_strategy, fallback_reason="no_clusters")

    if requested_strategy in {EvidenceBuildStrategy.auto, EvidenceBuildStrategy.llm}:
        drafts = _generate_llm_with_retry(settings=settings, file_name=file_name, clusters=clusters)
        return EvidenceGenerationResult(
            drafts=tuple(drafts),
            effective_strategy=EvidenceBuildStrategy.llm,
            fallback_reason=None,
        )

    drafts = _generate_with_strategy(
        settings=settings,
        strategy=requested_strategy,
        file_name=file_name,
        clusters=clusters,
    )
    return EvidenceGenerationResult(drafts=tuple(drafts), effective_strategy=requested_strategy, fallback_reason=None)


def _generate_llm_with_retry(
    *,
    settings: WorkerSettings,
    file_name: str,
    clusters: list[EvidenceCluster],
) -> list[EvidenceUnitDraft]:
    """以 LLM 產生 evidence units，失敗時依失敗次數平方秒數退避重試。

    參數：
    - `settings`：worker 執行期設定。
    - `file_name`：目前文件檔名。
    - `clusters`：待處理的 evidence clusters。

    回傳：
    - `list[EvidenceUnitDraft]`：LLM 成功產生的 evidence 草稿。

    例外：
    - `ValueError`：LLM 在最大重試次數後仍失敗，或設定錯誤不適合重試。
    """

    last_error: Exception | None = None
    retries_performed = 0
    for retry_index in range(EVIDENCE_UNITS_LLM_MAX_RETRIES + 1):
        try:
            return _generate_with_strategy(
                settings=settings,
                strategy=EvidenceBuildStrategy.llm,
                file_name=file_name,
                clusters=clusters,
            )
        except Exception as exc:
            last_error = exc
            if not _is_retryable_llm_evidence_error(exc=exc) or retry_index >= EVIDENCE_UNITS_LLM_MAX_RETRIES:
                break
            failure_count = retry_index + 1
            retries_performed = failure_count
            time.sleep(failure_count**2)
    raise ValueError(
        f"evidence unit LLM 生成失敗，已重試 {retries_performed} 次：{last_error}"
    ) from last_error


def _is_retryable_llm_evidence_error(*, exc: Exception) -> bool:
    """判斷 LLM evidence 失敗是否適合重試。

    參數：
    - `exc`：LLM evidence generation 拋出的例外。

    回傳：
    - `bool`：可透過等待後重試修復時回傳真。
    """

    return "OPENAI_API_KEY" not in str(exc)


def build_evidence_clusters(
    *,
    parent_chunks: list[DocumentChunk],
    child_chunks: list[DocumentChunk],
) -> list[EvidenceCluster]:
    """依 parent/child 內容建立 evidence clusters。

    參數：
    - `parent_chunks`：依文件順序排序的 parent chunks。
    - `child_chunks`：依文件順序排序的 child chunks。

    回傳：
    - `list[EvidenceCluster]`：可供後續 provider 使用的 clusters。
    """

    child_by_parent_id: dict[str, list[DocumentChunk]] = {}
    for child_chunk in child_chunks:
        if child_chunk.parent_chunk_id is None:
            continue
        child_by_parent_id.setdefault(str(child_chunk.parent_chunk_id), []).append(child_chunk)

    clusters: list[EvidenceCluster] = []
    index = 0
    while index < len(parent_chunks):
        parent_chunk = parent_chunks[index]
        next_parent = parent_chunks[index + 1] if index + 1 < len(parent_chunks) else None
        path_result = score_path_quality(parent_chunk=parent_chunk, next_parent=next_parent)
        cluster_parent_chunks = [parent_chunk]
        cluster_strategy = EvidenceClusterStrategy.single_parent

        if next_parent is not None and _should_merge_adjacent_parents(
            left_parent=parent_chunk,
            right_parent=next_parent,
            left_quality=path_result,
        ):
            cluster_parent_chunks.append(next_parent)
            next_quality = score_path_quality(parent_chunk=next_parent, next_parent=None)
            cluster_strategy = _resolve_cluster_strategy(
                left_quality=path_result,
                right_quality=next_quality,
                left_parent=parent_chunk,
                right_parent=next_parent,
            )
            path_score = min(path_result.score, next_quality.score)
            path_reason = (
                path_result.reason
                if path_result.reason != EvidencePathQualityReason.ok
                else next_quality.reason
            )
            index += 1
        else:
            path_score = path_result.score
            path_reason = path_result.reason

        cluster_child_chunks = tuple(
            child_chunk
            for source_parent in cluster_parent_chunks
            for child_chunk in child_by_parent_id.get(str(source_parent.id), [])
        )
        if not cluster_child_chunks:
            index += 1
            continue
        clusters.append(
            EvidenceCluster(
                parent_chunks=tuple(cluster_parent_chunks),
                child_chunks=cluster_child_chunks,
                cluster_strategy=cluster_strategy,
                path_quality_score=path_score,
                path_quality_reason=path_reason,
                heading_path=cluster_parent_chunks[0].heading_path,
                section_path_text=cluster_parent_chunks[0].section_path_text,
            )
        )
        index += 1

    return clusters


def build_cluster_source_text(*, cluster: EvidenceCluster, max_input_chars: int) -> str:
    """建立 evidence cluster 的受控來源文字。

    參數：
    - `cluster`：本次 evidence 生成的 cluster。
    - `max_input_chars`：允許的最大輸入字元數。

    回傳：
    - `str`：可送入 provider 的受控來源文字。
    """

    sections: list[str] = [
        f"Heading Path: {_normalize_text(cluster.heading_path or '(missing)')}",
        f"Section Path: {_normalize_text(cluster.section_path_text or '(missing)')}",
        f"Cluster Strategy: {cluster.cluster_strategy.value}",
        f"Path Quality: {cluster.path_quality_score:.2f} ({cluster.path_quality_reason.value})",
    ]
    for index, parent_chunk in enumerate(cluster.parent_chunks, start=1):
        sections.append(
            "\n".join(
                [
                    f"[Parent {index}] Heading: {_normalize_text(parent_chunk.heading or '(no heading)')}",
                    f"[Parent {index}] Type: {parent_chunk.structure_kind.value}",
                    f"[Parent {index}] Content: {_truncate_text(_normalize_text(parent_chunk.content), 700)}",
                ]
            )
        )
    for index, child_chunk in enumerate(cluster.child_chunks, start=1):
        sections.append(
            "\n".join(
                [
                    f"[Child {index}] Heading: {_normalize_text(child_chunk.heading or '(no heading)')}",
                    f"[Child {index}] Content: {_truncate_text(_normalize_text(child_chunk.content), 240)}",
                ]
            )
        )
    candidate = "\n\n".join(sections)
    return _truncate_text(candidate, max_input_chars)


def score_path_quality(*, parent_chunk: DocumentChunk, next_parent: DocumentChunk | None) -> PathQualityResult:
    """計算單一 parent 的 path 品質分數。

    參數：
    - `parent_chunk`：要評分的 parent chunk。
    - `next_parent`：相鄰下一個 parent；用來判斷局部不穩定。

    回傳：
    - `PathQualityResult`：path 品質評分結果。
    """

    heading_path = _normalize_text(parent_chunk.heading_path or "")
    section_path_text = _normalize_text(parent_chunk.section_path_text or "")
    combined_path = " ".join(part for part in (heading_path, section_path_text) if part).strip()
    if not combined_path:
        return PathQualityResult(score=0.0, reason=EvidencePathQualityReason.missing_path, is_toc_like_noise=False)

    lowered_path = combined_path.casefold()
    if _contains_toc_noise(lowered_path) or _looks_like_toc_line(parent_chunk.content):
        return PathQualityResult(score=0.05, reason=EvidencePathQualityReason.toc_noise, is_toc_like_noise=True)

    score = 0.85
    reason = EvidencePathQualityReason.ok
    normalized_heading = _normalize_text(parent_chunk.heading or "")
    if len(combined_path) <= 4 or normalized_heading.casefold() in {"section", "content", "contents"}:
        score -= 0.35
        reason = EvidencePathQualityReason.generic_heading

    overlap_ratio = _token_overlap_ratio(left=combined_path, right=parent_chunk.content)
    if overlap_ratio < 0.05:
        score -= 0.25
        reason = EvidencePathQualityReason.low_content_overlap

    if next_parent is not None:
        next_path = _normalize_text(next_parent.heading_path or next_parent.section_path_text or "")
        if next_path and combined_path and combined_path != next_path and overlap_ratio < 0.12:
            score -= 0.15
            reason = EvidencePathQualityReason.unstable_path

    return PathQualityResult(score=max(0.0, min(score, 1.0)), reason=reason, is_toc_like_noise=False)


def _generate_with_strategy(
    *,
    settings: WorkerSettings,
    strategy: EvidenceBuildStrategy,
    file_name: str,
    clusters: list[EvidenceCluster],
) -> list[EvidenceUnitDraft]:
    """使用指定策略對多個 cluster 產生 evidence drafts。

    參數：
    - `settings`：worker 執行期設定。
    - `strategy`：本輪使用的 build strategy。
    - `file_name`：目前文件檔名。
    - `clusters`：待處理的 evidence clusters。

    回傳：
    - `list[EvidenceUnitDraft]`：依文件順序平鋪後的 evidence drafts。
    """

    provider = build_evidence_unit_provider(settings=settings, strategy=strategy)
    max_units = max(1, settings.evidence_units_max_units_per_parent)

    if strategy != EvidenceBuildStrategy.llm or len(clusters) <= 1:
        drafts: list[EvidenceUnitDraft] = []
        for cluster in clusters:
            drafts.extend(
                provider.generate_units(
                    file_name=file_name,
                    cluster=cluster,
                    max_units=max_units,
                    max_output_chars=settings.evidence_units_max_output_chars,
                )
            )
        return drafts

    max_workers = max(1, min(settings.evidence_units_llm_parallelism, len(clusters)))
    with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="evidence-unit") as executor:
        results = executor.map(
            lambda cluster: provider.generate_units(
                file_name=file_name,
                cluster=cluster,
                max_units=max_units,
                max_output_chars=settings.evidence_units_max_output_chars,
            ),
            clusters,
        )
    drafts = [draft for result in results for draft in result]
    return drafts


def _build_evidence_draft(
    *,
    cluster: EvidenceCluster,
    evidence_type: EvidenceType,
    evidence_text: str,
    build_strategy: EvidenceBuildStrategy,
    confidence: float,
) -> EvidenceUnitDraft:
    """建立帶完整 source 映射的 evidence draft。

    參數：
    - `cluster`：本次 evidence 所屬 cluster。
    - `evidence_type`：evidence 類型。
    - `evidence_text`：evidence 文字。
    - `build_strategy`：產生 evidence 的 build strategy。
    - `confidence`：evidence 可信度。

    回傳：
    - `EvidenceUnitDraft`：包含 source 映射的 evidence 草稿。
    """

    return EvidenceUnitDraft(
        evidence_type=evidence_type,
        evidence_text=evidence_text,
        build_strategy=build_strategy,
        confidence=confidence,
        cluster_strategy=cluster.cluster_strategy,
        path_quality_score=cluster.path_quality_score,
        path_quality_reason=cluster.path_quality_reason,
        heading_path=cluster.heading_path,
        section_path_text=cluster.section_path_text,
        parent_chunk_ids=tuple(str(parent_chunk.id) for parent_chunk in cluster.parent_chunks),
        child_chunk_ids=tuple(str(child_chunk.id) for child_chunk in cluster.child_chunks),
    )


def _extract_candidate_snippets(*, source_text: str) -> list[str]:
    """從 cluster 來源文字切出候選 evidence 片段。

    參數：
    - `source_text`：受控來源文字。

    回傳：
    - `list[str]`：可供 evidence 分類使用的片段。
    """

    snippets: list[str] = []
    for section in source_text.splitlines():
        normalized_section = _normalize_text(section)
        if normalized_section.startswith(SOURCE_METADATA_LINE_PREFIXES):
            continue
        if not normalized_section or normalized_section.startswith("[Child") or normalized_section.startswith("[Parent"):
            content = normalized_section.split(":", 1)[-1].strip()
        else:
            content = normalized_section
        for fragment in SENTENCE_SPLIT_PATTERN.split(content):
            normalized_fragment = _normalize_text(fragment)
            if len(normalized_fragment) < 18:
                continue
            snippets.append(normalized_fragment)
    return snippets


def _classify_evidence_type(*, snippet: str, cluster: EvidenceCluster) -> EvidenceType:
    """依片段內容推估 evidence 類型。

    參數：
    - `snippet`：候選片段。
    - `cluster`：所屬 cluster。

    回傳：
    - `EvidenceType`：推估出的 evidence 類型。
    """

    lowered = snippet.casefold()
    if any(token in lowered for token in ("compare", "difference", "versus", "相比", "差異", "較", "高於", "低於")):
        return EvidenceType.comparison_point
    if any(token in lowered for token in ("step", "procedure", "流程", "步驟", "先", "再", "然後")):
        return EvidenceType.procedure
    if any(token in lowered for token in ("table", "欄", "row", "column", "表", "表格")) or any(
        parent_chunk.structure_kind == ChunkStructureKind.table for parent_chunk in cluster.parent_chunks
    ):
        return EvidenceType.table_finding
    if re.search(r"\d", snippet) or any(token in lowered for token in ("%", "percent", "率", "數量", "指標", "metric")):
        return EvidenceType.metric
    return EvidenceType.claim


def _deterministic_confidence(*, snippet: str, evidence_type: EvidenceType) -> float:
    """依 snippet 與 evidence 類型估算規則式 confidence。

    參數：
    - `snippet`：候選 evidence 文字。
    - `evidence_type`：推估 evidence 類型。

    回傳：
    - `float`：0 到 1 之間的 confidence。
    """

    score = 0.5
    if evidence_type in {EvidenceType.metric, EvidenceType.table_finding, EvidenceType.comparison_point}:
        score += 0.15
    if re.search(r"\d", snippet):
        score += 0.1
    if len(snippet) >= 48:
        score += 0.05
    return max(0.0, min(score, 0.95))


def _should_merge_adjacent_parents(
    *,
    left_parent: DocumentChunk,
    right_parent: DocumentChunk,
    left_quality: PathQualityResult,
) -> bool:
    """判斷兩個相鄰 parents 是否應聚成同一 cluster。

    參數：
    - `left_parent`：左側 parent。
    - `right_parent`：右側 parent。
    - `left_quality`：左側 parent 的 path 品質結果。

    回傳：
    - `bool`：若應合併則回傳真。
    """

    same_path = bool(left_parent.heading_path and left_parent.heading_path == right_parent.heading_path)
    near_position = abs(left_parent.position - right_parent.position) <= 2
    table_text_pair = {
        left_parent.structure_kind.value,
        right_parent.structure_kind.value,
    } == {"table", "text"}
    content_overlap = _token_overlap_ratio(left=left_parent.content, right=right_parent.content)
    if same_path and near_position:
        return True
    if left_quality.score < 0.4 and near_position and (table_text_pair or content_overlap >= 0.18):
        return True
    return False


def _resolve_cluster_strategy(
    *,
    left_quality: PathQualityResult,
    right_quality: PathQualityResult,
    left_parent: DocumentChunk,
    right_parent: DocumentChunk,
) -> EvidenceClusterStrategy:
    """依 parent/path 狀態決定 cluster strategy。

    參數：
    - `left_quality`：左側 parent 的 path 品質。
    - `right_quality`：右側 parent 的 path 品質。
    - `left_parent`：左側 parent。
    - `right_parent`：右側 parent。

    回傳：
    - `EvidenceClusterStrategy`：本次 cluster strategy。
    """

    if {
        left_parent.structure_kind.value,
        right_parent.structure_kind.value,
    } == {"table", "text"}:
        return EvidenceClusterStrategy.table_text_coupling
    if min(left_quality.score, right_quality.score) >= 0.7:
        return EvidenceClusterStrategy.path_aware
    if _token_overlap_ratio(left=left_parent.content, right=right_parent.content) >= 0.18:
        return EvidenceClusterStrategy.content_similarity_fallback
    return EvidenceClusterStrategy.adjacency_fallback


def _contains_toc_noise(value: str) -> bool:
    """判斷 path 文字是否命中 TOC 噪音。

    參數：
    - `value`：已正規化的 path 文字。

    回傳：
    - `bool`：若命中 TOC 噪音則回傳真。
    """

    return any(token in value for token in TOC_NOISE_TOKENS)


def _looks_like_toc_line(value: str) -> bool:
    """判斷內容是否像目錄列。

    參數：
    - `value`：原始內容文字。

    回傳：
    - `bool`：若像目錄列則回傳真。
    """

    normalized = _normalize_text(value)
    return bool(LEADER_DOTS_PATTERN.search(normalized) and PAGE_NUMBER_PATTERN.search(normalized))


def _token_overlap_ratio(*, left: str, right: str) -> float:
    """估算兩段文字的 token overlap ratio。

    參數：
    - `left`：左側文字。
    - `right`：右側文字。

    回傳：
    - `float`：0 到 1 的重疊比例。
    """

    left_tokens = set(TOKEN_PATTERN.findall(left.casefold()))
    right_tokens = set(TOKEN_PATTERN.findall(right.casefold()))
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / max(len(left_tokens), 1)


def _normalize_text(value: str) -> str:
    """將多餘空白壓平為單行文字。

    參數：
    - `value`：原始文字。

    回傳：
    - `str`：壓平後的文字。
    """

    return " ".join(value.split()).strip()


def _truncate_text(value: str, max_chars: int) -> str:
    """依字元數裁切文字。

    參數：
    - `value`：原始文字。
    - `max_chars`：允許的最大字元數。

    回傳：
    - `str`：裁切後文字。
    """

    if max_chars <= 0:
        return ""
    if len(value) <= max_chars:
        return value
    if max_chars <= 1:
        return value[:max_chars]
    return value[: max_chars - 1].rstrip() + "…"


def _extract_response_output_text(response: object) -> str | None:
    """從 OpenAI Responses API 回傳中抽取文字。

    參數：
    - `response`：OpenAI Responses API 回傳。

    回傳：
    - `str | None`：可見文字；若無則回傳空值。
    """

    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str):
        return output_text
    output_items = getattr(response, "output", None)
    if not isinstance(output_items, list):
        return None
    for item in output_items:
        if getattr(item, "type", None) != "message":
            continue
        for content_item in getattr(item, "content", []):
            text_value = getattr(content_item, "text", None)
            if isinstance(text_value, str):
                return text_value
    return None


def _is_gpt5_family_model(model: str) -> bool:
    """判斷模型是否屬於 GPT-5 family。

    參數：
    - `model`：模型名稱。

    回傳：
    - `bool`：若屬於 GPT-5 family 則回傳真。
    """

    return model.strip().lower().startswith("gpt-5")
