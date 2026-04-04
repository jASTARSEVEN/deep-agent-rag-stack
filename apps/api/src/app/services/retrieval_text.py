"""retrieval 與 assembler 共用的文字組裝 helper。"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.db.models import ChunkStructureKind


# `quantitative` 表示數量、規模與總量類 evidence category。
EVIDENCE_CATEGORY_QUANTITATIVE = "quantitative"
# `label_definition` 表示標籤、分類與 polarity 類 evidence category。
EVIDENCE_CATEGORY_LABEL_DEFINITION = "label_definition"
# `enumeration` 表示任務、階段、類型列舉類 evidence category。
EVIDENCE_CATEGORY_ENUMERATION = "enumeration"
# `metric_comparison` 表示評估指標與比較面向類 evidence category。
EVIDENCE_CATEGORY_METRIC_COMPARISON = "metric_comparison"
# `source_material` 表示來源資料、種子資源與起始語料類 evidence category。
EVIDENCE_CATEGORY_SOURCE_MATERIAL = "source_material"
# `generic_v1` 表示目前正式的通用型 synopsis 變體。
EVIDENCE_SYNOPSIS_VARIANT_GENERIC_V1 = "generic_v1"
# `qasper_v3` 表示依 miss analysis 補強 alias/task/metric framing 的 benchmark-gated 變體。
EVIDENCE_SYNOPSIS_VARIANT_QASPER_V3 = "qasper_v3"

# evidence synopsis 輸出的固定 category 順序。
EVIDENCE_CATEGORY_ORDER = (
    EVIDENCE_CATEGORY_QUANTITATIVE,
    EVIDENCE_CATEGORY_LABEL_DEFINITION,
    EVIDENCE_CATEGORY_ENUMERATION,
    EVIDENCE_CATEGORY_METRIC_COMPARISON,
    EVIDENCE_CATEGORY_SOURCE_MATERIAL,
)

# Arabic digits 與常見百分比/小數/分隔符的數值訊號 pattern。
_ARABIC_NUMERIC_PATTERN = re.compile(r"\b\d[\d,./%％]*\b")
# 中文數字訊號 pattern；僅作為 quantity 類 evidence 的輔助判斷。
_CJK_NUMERIC_PATTERN = re.compile(r"[零〇一二三四五六七八九十百千萬億兩壹貳參肆伍陸柒捌玖拾佰仟]+")


@dataclass(frozen=True, slots=True)
class EvidenceSynopsisLanguageProfile:
    """evidence synopsis 的單一語言 profile。

    此結構將「語言無關的 evidence 類別」與「語言特定的 lexical signal / 文案」
    分離，讓未來新增語言時只需新增 profile，而不必複製整條判斷流程。
    """

    language_code: str  # 語言代碼，例如 `en` 或 `zh-TW`。
    synopsis_templates: dict[str, str]  # 各 evidence category 的本地化輸出文案。
    language_hint_tokens: tuple[str, ...]  # 用來推估輸出語言的語言提示詞。
    script_hint_pattern: str | None  # 用來推估輸出語言的 script regex。
    quantitative_anchor_tokens: tuple[str, ...]  # 數量/規模類 evidence 的 anchor token。
    label_anchor_tokens: tuple[str, ...]  # 標籤/分類類 evidence 的 anchor token。
    label_group_tokens: tuple[str, ...]  # polarity / 群組 / annotation 類 evidence 的輔助 token。
    enumeration_scope_tokens: tuple[str, ...]  # 任務/類型/階段列舉的 scope token。
    enumeration_list_tokens: tuple[str, ...]  # 表示列舉結構的 token。
    metric_tokens: tuple[str, ...]  # 評估指標與比較面向 token。
    source_tokens: tuple[str, ...]  # 來源資料、起始語料與種子資源 token。


# 英文 evidence synopsis profile；作為預設 fallback。
EVIDENCE_LANGUAGE_PROFILE_EN = EvidenceSynopsisLanguageProfile(
    language_code="en",
    synopsis_templates={
        EVIDENCE_CATEGORY_QUANTITATIVE: "This passage highlights quantitative evidence such as counts, totals, sizes, or other numeric facts.",
        EVIDENCE_CATEGORY_LABEL_DEFINITION: "This passage defines labeled categories or polarity-style groupings used in the source material or method.",
        EVIDENCE_CATEGORY_ENUMERATION: "This passage enumerates named tasks, categories, stages, or question types.",
        EVIDENCE_CATEGORY_METRIC_COMPARISON: "This passage lists evaluation metrics, comparison axes, or measured operational characteristics.",
        EVIDENCE_CATEGORY_SOURCE_MATERIAL: "This passage identifies the source material, seed resource, or starting corpus used in the approach.",
    },
    language_hint_tokens=(
        "dataset",
        "corpus",
        "label",
        "category",
        "task",
        "metric",
        "source",
        "question type",
        "precision",
        "recall",
    ),
    script_hint_pattern=r"[A-Za-z]",
    quantitative_anchor_tokens=(
        "dataset",
        "corpus",
        "sample",
        "samples",
        "record",
        "records",
        "sentence",
        "sentences",
        "character",
        "characters",
        "pair",
        "pairs",
        "example",
        "examples",
        "instance",
        "instances",
        "document",
        "documents",
    ),
    label_anchor_tokens=("label", "labels", "class", "classes", "category", "categories", "polarity", "polarities"),
    label_group_tokens=("positive", "negative", "seed", "lexicon", "annotation", "annotated", "group", "word", "words"),
    enumeration_scope_tokens=(
        "task",
        "tasks",
        "question type",
        "question types",
        "types of questions",
        "category",
        "categories",
        "stage",
        "stages",
        "step",
        "steps",
    ),
    enumeration_list_tokens=("namely", "including", "includes", "such as", ",", ";", "\n- ", "\n* "),
    metric_tokens=("precision", "recall", "f1", "mrr", "ndcg", "latency", "throughput", "energy", "accuracy", "perplexity", "auc", "map", "r@", "p@"),
    source_tokens=("starting point", "source corpus", "source dataset", "seed resource", "built from", "derived from", "initialized from", "based on", "we use the", "we used the", "using the"),
)

# 繁體中文 evidence synopsis profile；用於 `zh-TW` 文件/段落的本地化輸出。
EVIDENCE_LANGUAGE_PROFILE_ZH_TW = EvidenceSynopsisLanguageProfile(
    language_code="zh-TW",
    synopsis_templates={
        EVIDENCE_CATEGORY_QUANTITATIVE: "此段落包含數量、總量、規模或其他數值型事實。",
        EVIDENCE_CATEGORY_LABEL_DEFINITION: "此段落定義標籤類別、極性分組或其他分類規則。",
        EVIDENCE_CATEGORY_ENUMERATION: "此段落列舉任務、類別、階段、步驟或問題型別。",
        EVIDENCE_CATEGORY_METRIC_COMPARISON: "此段落列出評估指標、比較面向或操作特性。",
        EVIDENCE_CATEGORY_SOURCE_MATERIAL: "此段落指出方法使用的來源資料、種子資源或起始語料。",
    },
    language_hint_tokens=(
        "資料集",
        "語料",
        "標籤",
        "類別",
        "類型",
        "任務",
        "問題型別",
        "指標",
        "來源",
        "召回率",
        "精確率",
    ),
    script_hint_pattern=r"[\u3400-\u4dbf\u4e00-\u9fff]",
    quantitative_anchor_tokens=("資料集", "語料", "樣本", "紀錄", "句", "句子", "字元", "字符", "問答對", "文件", "份", "筆", "條", "個", "題", "案例"),
    label_anchor_tokens=("標籤", "類別", "分類", "極性", "群組", "標註"),
    label_group_tokens=("正向", "負向", "正面", "負面", "種子", "詞典", "詞彙", "字詞", "群組", "標註"),
    enumeration_scope_tokens=("任務", "問題型別", "問題類型", "類別", "類型", "階段", "步驟", "流程"),
    enumeration_list_tokens=("包括", "包含", "例如", "如下", "分為", "分成", "依序", "有：", "如下：", "、", "，", "；"),
    metric_tokens=("精確率", "精準率", "查準率", "召回率", "查全率", "準確率", "延遲", "吞吐量", "能耗", "困惑度", "mrr", "ndcg", "f1", "auc", "map", "r@", "p@"),
    source_tokens=("來源資料", "來源語料", "來源資料集", "起始語料", "起始資料集", "種子資源", "取自", "來自", "基於", "依據", "建立於"),
)

# 目前支援的 evidence synopsis 語言 profiles；未來新增語言時以新增 profile 為主。
EVIDENCE_LANGUAGE_PROFILES = (
    EVIDENCE_LANGUAGE_PROFILE_EN,
    EVIDENCE_LANGUAGE_PROFILE_ZH_TW,
)


def merge_chunk_contents(*, structure_kind: ChunkStructureKind, contents: list[str]) -> str:
    """依 chunk 結構型別合併多筆 child content。

    參數：
    - `structure_kind`：chunk 內容結構型別。
    - `contents`：同一 parent 下、已依既定順序排列的 child content。

    回傳：
    - `str`：合併後的文字；table 只保留一次表頭。
    """

    normalized_contents = [content.strip() for content in contents if content and content.strip()]
    if not normalized_contents:
        return ""
    if structure_kind == ChunkStructureKind.table:
        return _merge_table_contents(contents=normalized_contents)
    return "\n\n".join(normalized_contents).strip()


def build_rerank_document_text(
    *,
    heading: str | None,
    content: str,
    max_chars: int,
    evidence_synopsis: str | None = None,
) -> str:
    """建立送進 rerank provider 的文件文字。

    參數：
    - `heading`：此文件片段的標題；允許為空值。
    - `content`：已組裝完成的正文內容。
    - `max_chars`：允許送入 rerank 的最大字元數。
    - `evidence_synopsis`：benchmark/profile-gated 的補充摘要文字；允許為空值。

    回傳：
    - `str`：帶有 `Header:` / `Content:` 前綴且受成本 guardrail 限制的文字。
    """

    normalized_heading = (heading or "").strip()
    normalized_content = content.strip()
    normalized_synopsis = (evidence_synopsis or "").strip()
    sections = [f"Header: {normalized_heading}".strip()]
    if normalized_synopsis:
        sections.append(f"Evidence synopsis:\n{normalized_synopsis}")
    sections.append(f"Content:\n{normalized_content}")
    structured_text = "\n".join(section for section in sections if section).strip()
    if len(structured_text) <= max_chars:
        return structured_text
    return structured_text[:max_chars]

def build_evidence_synopsis(
    *,
    heading: str | None,
    content: str,
    variant: str = EVIDENCE_SYNOPSIS_VARIANT_GENERIC_V1,
) -> str:
    """為 benchmark/profile-gated rerank 產生語言感知的 fact-oriented 補充摘要。

    架構說明：
    - evidence 類別判斷採語言無關流程。
    - 各語言的 lexical signal 與輸出文案由 language profile registry 提供。
    - 目前正式支援 `en` 與 `zh-TW`；未來新增語言時，原則上只需新增 profile。
    - `variant` 僅用於 benchmark/profile-gated 的 phrasing 擴充，不得污染 production defaults。

    參數：
    - `heading`：候選片段標題；允許為空值。
    - `content`：候選正文內容。
    - `variant`：synopsis 變體；預設為 `generic_v1`。

    回傳：
    - `str`：若命中 fact-heavy signal，依推定語言回傳本地化 synopsis；否則回空字串。
    """

    normalized_heading = (heading or "").strip()
    normalized_content = content.strip()
    normalized_heading_lower = normalized_heading.casefold()
    normalized_content_lower = normalized_content.casefold()
    categories = _build_evidence_signal_categories(
        normalized_heading=normalized_heading_lower,
        normalized_content=normalized_content_lower,
    )
    if not categories:
        return ""

    output_profile = _select_output_language_profile(
        normalized_heading=normalized_heading_lower,
        normalized_content=normalized_content_lower,
    )
    synopsis_lines = [output_profile.synopsis_templates[category] for category in categories]
    synopsis_lines.extend(
        _build_variant_specific_synopsis_lines(
            normalized_heading=normalized_heading_lower,
            normalized_content=normalized_content_lower,
            output_profile=output_profile,
            categories=categories,
            variant=variant,
        )
    )
    deduplicated_lines = list(dict.fromkeys(line for line in synopsis_lines if line.strip()))
    return "\n".join(f"- {line}" for line in deduplicated_lines).strip()


def _merge_table_contents(*, contents: list[str]) -> str:
    """將多個 table row-group child 合併為單一 table 文字。

    參數：
    - `contents`：同一 parent 下、已依 child 順序排列的 table child content。

    回傳：
    - `str`：只保留一次表頭的 Markdown table。
    """

    merged_lines: list[str] = []
    for index, content in enumerate(contents):
        lines = [line.rstrip() for line in content.splitlines() if line.strip()]
        if not lines:
            continue
        if index == 0 or len(lines) < 3:
            merged_lines.extend(lines)
            continue
        merged_lines.extend(lines[2:])
    return "\n".join(merged_lines).strip()


def _build_evidence_signal_categories(*, normalized_heading: str, normalized_content: str) -> tuple[str, ...]:
    """依內容推導命中的 evidence category 順序。

    參數：
    - `normalized_heading`：已標準化且 casefold 後的標題。
    - `normalized_content`：已標準化且 casefold 後的正文。

    回傳：
    - `tuple[str, ...]`：依固定輸出順序排列的 evidence categories。
    """

    detected_categories: list[str] = []
    if _looks_quantitative_fact(normalized_heading=normalized_heading, normalized_content=normalized_content):
        detected_categories.append(EVIDENCE_CATEGORY_QUANTITATIVE)
    if _looks_label_definition_fact(normalized_heading=normalized_heading, normalized_content=normalized_content):
        detected_categories.append(EVIDENCE_CATEGORY_LABEL_DEFINITION)
    if _looks_enumeration_fact(normalized_heading=normalized_heading, normalized_content=normalized_content):
        detected_categories.append(EVIDENCE_CATEGORY_ENUMERATION)
    if _looks_metric_comparison_fact(normalized_heading=normalized_heading, normalized_content=normalized_content):
        detected_categories.append(EVIDENCE_CATEGORY_METRIC_COMPARISON)
    if _looks_source_material_fact(normalized_heading=normalized_heading, normalized_content=normalized_content):
        detected_categories.append(EVIDENCE_CATEGORY_SOURCE_MATERIAL)
    return tuple(category for category in EVIDENCE_CATEGORY_ORDER if category in detected_categories)


def _build_variant_specific_synopsis_lines(
    *,
    normalized_heading: str,
    normalized_content: str,
    output_profile: EvidenceSynopsisLanguageProfile,
    categories: tuple[str, ...],
    variant: str,
) -> list[str]:
    """依指定 variant 產生額外的 benchmark-gated synopsis lines。

    參數：
    - `normalized_heading`：已標準化且 casefold 後的標題。
    - `normalized_content`：已標準化且 casefold 後的正文。
    - `output_profile`：此次輸出語言 profile。
    - `categories`：已命中的 evidence categories。
    - `variant`：要套用的 synopsis 變體。

    回傳：
    - `list[str]`：額外附加的 synopsis lines；若 variant 無額外規則則回空列表。
    """

    if variant != EVIDENCE_SYNOPSIS_VARIANT_QASPER_V3:
        return []
    if output_profile.language_code == "en":
        return _build_qasper_v3_english_synopsis_lines(
            normalized_heading=normalized_heading,
            normalized_content=normalized_content,
            categories=categories,
        )
    if output_profile.language_code == "zh-TW":
        return _build_qasper_v3_traditional_chinese_synopsis_lines(
            normalized_heading=normalized_heading,
            normalized_content=normalized_content,
            categories=categories,
        )
    return []


def _build_qasper_v3_english_synopsis_lines(
    *,
    normalized_heading: str,
    normalized_content: str,
    categories: tuple[str, ...],
) -> list[str]:
    """建立 `qasper_v3` 的英文補充 synopsis lines。

    參數：
    - `normalized_heading`：已標準化且 casefold 後的標題。
    - `normalized_content`：已標準化且 casefold 後的正文。
    - `categories`：已命中的 evidence categories。

    回傳：
    - `list[str]`：英文 variant-specific synopsis lines。
    """

    extra_lines: list[str] = []
    combined = f"{normalized_heading}\n{normalized_content}"

    if EVIDENCE_CATEGORY_QUANTITATIVE in categories and _looks_dataset_alias_bridge_target(combined=combined):
        extra_lines.append(
            "This passage may answer task-dataset size or dataset-alias questions, including question-answer pair statistics."
        )
    if EVIDENCE_CATEGORY_ENUMERATION in categories:
        extra_lines.append(
            "This passage states the specific task types or question types being unified."
        )
    if EVIDENCE_CATEGORY_LABEL_DEFINITION in categories:
        extra_lines.append(
            "This passage states the supervision labels or label schema available in the dataset."
        )
    if EVIDENCE_CATEGORY_METRIC_COMPARISON in categories:
        extra_lines.append(
            "This passage states the aspects compared across models, including evaluation metrics and operational characteristics."
        )
    if EVIDENCE_CATEGORY_SOURCE_MATERIAL in categories:
        extra_lines.append(
            "This passage states which dataset or corpus is used as the starting point."
        )

    return extra_lines


def _build_qasper_v3_traditional_chinese_synopsis_lines(
    *,
    normalized_heading: str,
    normalized_content: str,
    categories: tuple[str, ...],
) -> list[str]:
    """建立 `qasper_v3` 的繁體中文補充 synopsis lines。

    參數：
    - `normalized_heading`：已標準化且 casefold 後的標題。
    - `normalized_content`：已標準化且 casefold 後的正文。
    - `categories`：已命中的 evidence categories。

    回傳：
    - `list[str]`：繁體中文 variant-specific synopsis lines。
    """

    extra_lines: list[str] = []
    combined = f"{normalized_heading}\n{normalized_content}"

    if EVIDENCE_CATEGORY_QUANTITATIVE in categories and _looks_dataset_alias_bridge_target(combined=combined):
        extra_lines.append(
            "此段落可能回答任務資料集規模、資料集別名或問答對統計等問題。"
        )
    if EVIDENCE_CATEGORY_ENUMERATION in categories:
        extra_lines.append(
            "此段落指出被統整的具體任務型別或問題型別。"
        )
    if EVIDENCE_CATEGORY_LABEL_DEFINITION in categories:
        extra_lines.append(
            "此段落指出資料集中可用於監督的標籤或標籤結構。"
        )
    if EVIDENCE_CATEGORY_METRIC_COMPARISON in categories:
        extra_lines.append(
            "此段落指出不同模型之間被比較的面向，包括評估指標與操作特性。"
        )
    if EVIDENCE_CATEGORY_SOURCE_MATERIAL in categories:
        extra_lines.append(
            "此段落指出哪個資料集或語料被用作起始來源。"
        )

    return extra_lines


def _select_output_language_profile(
    *,
    normalized_heading: str,
    normalized_content: str,
) -> EvidenceSynopsisLanguageProfile:
    """依內容訊號選擇 synopsis 輸出語言 profile。

    參數：
    - `normalized_heading`：已標準化且 casefold 後的標題。
    - `normalized_content`：已標準化且 casefold 後的正文。

    回傳：
    - `EvidenceSynopsisLanguageProfile`：此次應使用的輸出語言 profile。
    """

    combined = f"{normalized_heading}\n{normalized_content}"
    scored_profiles = sorted(
        (
            (_language_score(profile=profile, combined=combined), index, profile)
            for index, profile in enumerate(EVIDENCE_LANGUAGE_PROFILES)
        ),
        reverse=True,
    )
    best_score, _, best_profile = scored_profiles[0]
    if best_score <= 0:
        return EVIDENCE_LANGUAGE_PROFILE_EN
    return best_profile


def _language_score(*, profile: EvidenceSynopsisLanguageProfile, combined: str) -> int:
    """計算單一語言 profile 與內容的相符分數。

    參數：
    - `profile`：候選語言 profile。
    - `combined`：標題與正文合併後的標準化文字。

    回傳：
    - `int`：相符分數；分數越高表示越適合作為輸出語言。
    """

    token_score = sum(1 for token in profile.language_hint_tokens if token and token in combined)
    script_score = 0
    if profile.script_hint_pattern and re.search(profile.script_hint_pattern, combined):
        script_score = 2
    return token_score + script_score


def _looks_quantitative_fact(*, normalized_heading: str, normalized_content: str) -> bool:
    """判斷內容是否偏向通用型數量/規模事實。

    參數：
    - `normalized_heading`：已標準化且 casefold 後的標題。
    - `normalized_content`：已標準化且 casefold 後的正文。

    回傳：
    - `bool`：若內容同時包含數量 anchor 與數值訊號，回傳 `True`。
    """

    combined = f"{normalized_heading}\n{normalized_content}"
    has_count_anchor = _contains_profile_tokens(combined=combined, attribute_name="quantitative_anchor_tokens")
    has_numeric_anchor = _contains_numeric_signal(text=combined)
    return has_count_anchor and has_numeric_anchor


def _looks_label_definition_fact(*, normalized_heading: str, normalized_content: str) -> bool:
    """判斷內容是否偏向通用型 label/category 定義事實。

    參數：
    - `normalized_heading`：已標準化且 casefold 後的標題。
    - `normalized_content`：已標準化且 casefold 後的正文。

    回傳：
    - `bool`：若內容同時包含分類 anchor 與群組/annotation 訊號，回傳 `True`。
    """

    combined = f"{normalized_heading}\n{normalized_content}"
    has_label_signal = _contains_profile_tokens(combined=combined, attribute_name="label_anchor_tokens")
    has_group_signal = _contains_profile_tokens(combined=combined, attribute_name="label_group_tokens")
    return has_label_signal and has_group_signal


def _looks_enumeration_fact(*, normalized_heading: str, normalized_content: str) -> bool:
    """判斷內容是否偏向通用型列舉事實。

    參數：
    - `normalized_heading`：已標準化且 casefold 後的標題。
    - `normalized_content`：已標準化且 casefold 後的正文。

    回傳：
    - `bool`：若內容同時包含列舉 scope 與 list 訊號，回傳 `True`。
    """

    combined = f"{normalized_heading}\n{normalized_content}"
    has_scope_anchor = _contains_profile_tokens(combined=combined, attribute_name="enumeration_scope_tokens")
    has_list_signal = _contains_profile_tokens(combined=normalized_content, attribute_name="enumeration_list_tokens")
    return has_scope_anchor and has_list_signal


def _looks_metric_comparison_fact(*, normalized_heading: str, normalized_content: str) -> bool:
    """判斷內容是否偏向通用型 metrics/comparison facts。

    參數：
    - `normalized_heading`：已標準化且 casefold 後的標題。
    - `normalized_content`：已標準化且 casefold 後的正文。

    回傳：
    - `bool`：若內容提到常見評估指標、比較軸或操作特徵，回傳 `True`。
    """

    combined = f"{normalized_heading}\n{normalized_content}"
    return _contains_profile_tokens(combined=combined, attribute_name="metric_tokens")


def _looks_source_material_fact(*, normalized_heading: str, normalized_content: str) -> bool:
    """判斷內容是否偏向通用型來源資料/起始語料事實。

    參數：
    - `normalized_heading`：已標準化且 casefold 後的標題。
    - `normalized_content`：已標準化且 casefold 後的正文。

    回傳：
    - `bool`：若內容像是在指出方法使用的來源資料，回傳 `True`。
    """

    combined = f"{normalized_heading}\n{normalized_content}"
    return _contains_profile_tokens(combined=combined, attribute_name="source_tokens")


def _contains_profile_tokens(*, combined: str, attribute_name: str) -> bool:
    """檢查任一語言 profile 的指定 token 集是否命中文字。

    參數：
    - `combined`：已標準化後的待檢查文字。
    - `attribute_name`：`EvidenceSynopsisLanguageProfile` 上的 token 欄位名稱。

    回傳：
    - `bool`：若任一 profile 的對應 token 集命中，回傳 `True`。
    """

    return any(_contains_any_token(text=combined, tokens=getattr(profile, attribute_name)) for profile in EVIDENCE_LANGUAGE_PROFILES)


def _contains_any_token(*, text: str, tokens: tuple[str, ...]) -> bool:
    """判斷文字是否命中任一 token。

    參數：
    - `text`：待檢查文字。
    - `tokens`：候選 token 集。

    回傳：
    - `bool`：若任一 token 存在於文字中，回傳 `True`。
    """

    return any(token in text for token in tokens if token)


def _contains_numeric_signal(*, text: str) -> bool:
    """判斷文字是否帶有可視為數量/規模 evidence 的數值訊號。

    參數：
    - `text`：待檢查文字。

    回傳：
    - `bool`：若命中 Arabic digits 或中文數字訊號，回傳 `True`。
    """

    return bool(_ARABIC_NUMERIC_PATTERN.search(text) or _CJK_NUMERIC_PATTERN.search(text))


def _looks_dataset_alias_bridge_target(*, combined: str) -> bool:
    """判斷內容是否值得加上 dataset-alias bridge 類 phrasing。

    參數：
    - `combined`：標題與正文合併後的標準化文字。

    回傳：
    - `bool`：若內容像是 dataset size / dataset and metrics / task dataset 類統計描述，回傳 `True`。
    """

    return any(
        token in combined
        for token in (
            "dataset and evaluation metrics",
            "question-answer pairs",
            "types of questions",
            "task dataset",
            "sentences",
            "characters",
            "資料集與評估指標",
            "資料集和評估指標",
            "問答對",
            "問題型別",
            "問題類型",
            "任務資料集",
            "句子",
            "字元",
            "字符",
        )
    )
