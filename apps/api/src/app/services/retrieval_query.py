"""retrieval query focus planner 與 query-side 對齊 helper。"""

from __future__ import annotations

from dataclasses import dataclass
import re

from app.core.settings import AppSettings


# `generic_field_focus_v1` 表示目前唯一正式支援的通用 query focus planner 變體。
QUERY_FOCUS_VARIANT_GENERIC_FIELD_V1 = "generic_field_focus_v1"
# `generic` 表示通用 evidence-field 規則家族。
QUERY_FOCUS_RULE_FAMILY_GENERIC = "generic"

# `zh-TW` 表示繁體中文 query language。
QUERY_LANGUAGE_ZH_TW = "zh-TW"
# `en` 表示英文 query language。
QUERY_LANGUAGE_EN = "en"
# `mixed` 表示中英混合 query language。
QUERY_LANGUAGE_MIXED = "mixed"

# `amount_or_limit` 表示金額、額度或上限類意圖。
QUERY_INTENT_AMOUNT_OR_LIMIT = "amount_or_limit"
# `date_or_deadline` 表示日期、期限或 time window 類意圖。
QUERY_INTENT_DATE_OR_DEADLINE = "date_or_deadline"
# `eligibility_or_actor` 表示資格、適用對象或責任角色類意圖。
QUERY_INTENT_ELIGIBILITY_OR_ACTOR = "eligibility_or_actor"
# `count_or_size` 表示數量、總數或規模類意圖。
QUERY_INTENT_COUNT_OR_SIZE = "count_or_size"
# `comparison_axis` 表示比較結果或比較面向類意圖。
QUERY_INTENT_COMPARISON_AXIS = "comparison_axis"
# `source_material` 表示來源資料、來源語料或 pretraining source 類意圖。
QUERY_INTENT_SOURCE_MATERIAL = "source_material"
# `metric_or_evaluation_axis` 表示評估指標或量測面向類意圖。
QUERY_INTENT_METRIC_OR_EVALUATION_AXIS = "metric_or_evaluation_axis"
# `label_or_annotation_schema` 表示標籤或標註規則類意圖。
QUERY_INTENT_LABEL_OR_ANNOTATION_SCHEMA = "label_or_annotation_schema"
# `enumeration_or_inventory` 表示清單、列舉或 inventory 類意圖。
QUERY_INTENT_ENUMERATION_OR_INVENTORY = "enumeration_or_inventory"

# 本模組正式支援的通用 intents。
SUPPORTED_QUERY_FOCUS_INTENTS = (
    QUERY_INTENT_AMOUNT_OR_LIMIT,
    QUERY_INTENT_DATE_OR_DEADLINE,
    QUERY_INTENT_ELIGIBILITY_OR_ACTOR,
    QUERY_INTENT_COUNT_OR_SIZE,
    QUERY_INTENT_COMPARISON_AXIS,
    QUERY_INTENT_SOURCE_MATERIAL,
    QUERY_INTENT_METRIC_OR_EVALUATION_AXIS,
    QUERY_INTENT_LABEL_OR_ANNOTATION_SCHEMA,
    QUERY_INTENT_ENUMERATION_OR_INVENTORY,
)

# CJK script 偵測 pattern。
_CJK_PATTERN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
# Latin script 偵測 pattern。
_LATIN_PATTERN = re.compile(r"[A-Za-z]")
# 空白正規化 pattern。
_WHITESPACE_PATTERN = re.compile(r"\s+")
# query token 抽取 pattern；會同時保留英文詞與 CJK 片段。
_QUERY_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]*|[\u3400-\u4dbf\u4e00-\u9fff]+")
# 英文 subject fallback token 抽取 pattern。
_ENGLISH_WORD_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]*")
# 英文比較對象抽取 pattern。
_ENGLISH_COMPARISON_PATTERN = re.compile(
    r"(?P<left>[A-Za-z0-9][A-Za-z0-9._/-]*)\s+(?:or|vs\.?|versus)\s+(?P<right>[A-Za-z0-9][A-Za-z0-9._/-]*)",
    re.IGNORECASE,
)
# 中文比較對象抽取 pattern。
_CJK_COMPARISON_PATTERN = re.compile(r"(?P<left>[^\s，。！？?、；]+)\s*(?:與|和|或|跟)\s*(?P<right>[^\s，。！？?、；]+)")

# 英文 subject fallback 停用詞。
ENGLISH_SUBJECT_STOPWORDS = {
    "a",
    "an",
    "are",
    "as",
    "at",
    "be",
    "can",
    "did",
    "do",
    "does",
    "for",
    "how",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "the",
    "their",
    "they",
    "this",
    "to",
    "was",
    "what",
    "when",
    "which",
    "who",
}


@dataclass(frozen=True, slots=True)
class QueryFocusPlan:
    """單次 retrieval 的 query focus planner 輸出。"""

    original_query: str
    normalized_query: str
    language: str
    confidence: float
    intents: tuple[str, ...]
    slots: dict[str, str]
    focus_query: str
    rerank_query: str
    applied: bool
    variant: str
    rule_family: str


@dataclass(frozen=True, slots=True)
class QueryFocusIntentSpec:
    """單一 query focus intent 的語言化規則定義。"""

    intent: str
    trigger_phrases: tuple[str, ...]
    target_field: str
    evidence_terms: tuple[str, ...]
    rerank_brief: str


# 繁體中文 query focus intents registry。
QUERY_FOCUS_SPECS_ZH_TW: dict[str, QueryFocusIntentSpec] = {
    QUERY_INTENT_AMOUNT_OR_LIMIT: QueryFocusIntentSpec(
        intent=QUERY_INTENT_AMOUNT_OR_LIMIT,
        trigger_phrases=("多少錢", "金額", "額度", "上限", "最高", "限額"),
        target_field="金額或上限",
        evidence_terms=("金額", "額度", "上限", "最高"),
        rerank_brief="Need: 精確的金額、額度或上限欄位。",
    ),
    QUERY_INTENT_DATE_OR_DEADLINE: QueryFocusIntentSpec(
        intent=QUERY_INTENT_DATE_OR_DEADLINE,
        trigger_phrases=("何時", "日期", "時間", "期限", "截止", "多久內"),
        target_field="日期或期限",
        evidence_terms=("日期", "時間", "期限", "截止"),
        rerank_brief="Need: 精確的日期、期限或 time window 欄位。",
    ),
    QUERY_INTENT_ELIGIBILITY_OR_ACTOR: QueryFocusIntentSpec(
        intent=QUERY_INTENT_ELIGIBILITY_OR_ACTOR,
        trigger_phrases=("誰可以", "資格", "條件", "適用對象", "身分", "角色", "負責"),
        target_field="資格或責任對象",
        evidence_terms=("資格", "條件", "適用對象", "責任對象"),
        rerank_brief="Need: 精確的資格、適用對象或責任角色欄位。",
    ),
    QUERY_INTENT_COUNT_OR_SIZE: QueryFocusIntentSpec(
        intent=QUERY_INTENT_COUNT_OR_SIZE,
        trigger_phrases=("多少", "幾個", "幾項", "規模", "數量", "總數", "大小"),
        target_field="數量或規模",
        evidence_terms=("數量", "規模", "總數", "大小"),
        rerank_brief="Need: 精確的數量、總數或規模 evidence。",
    ),
    QUERY_INTENT_COMPARISON_AXIS: QueryFocusIntentSpec(
        intent=QUERY_INTENT_COMPARISON_AXIS,
        trigger_phrases=("比較", "差異", "相比", "優於", "哪個較", "哪個更"),
        target_field="比較結果或比較面向",
        evidence_terms=("比較", "差異", "優於", "表現"),
        rerank_brief="Need: 直接的比較結果或比較面向 evidence。",
    ),
    QUERY_INTENT_SOURCE_MATERIAL: QueryFocusIntentSpec(
        intent=QUERY_INTENT_SOURCE_MATERIAL,
        trigger_phrases=("來源", "取自", "來自", "基於", "使用哪些資料", "使用什麼資料"),
        target_field="來源資料",
        evidence_terms=("來源資料", "資料來源", "來源語料", "起始資料"),
        rerank_brief="Need: 精確的來源資料、來源語料或起始來源 evidence。",
    ),
    QUERY_INTENT_METRIC_OR_EVALUATION_AXIS: QueryFocusIntentSpec(
        intent=QUERY_INTENT_METRIC_OR_EVALUATION_AXIS,
        trigger_phrases=("指標", "評估", "衡量", "量測", "怎麼評估", "表現"),
        target_field="評估指標或評估面向",
        evidence_terms=("評估", "指標", "衡量", "面向"),
        rerank_brief="Need: 精確的評估指標或評估面向 evidence。",
    ),
    QUERY_INTENT_LABEL_OR_ANNOTATION_SCHEMA: QueryFocusIntentSpec(
        intent=QUERY_INTENT_LABEL_OR_ANNOTATION_SCHEMA,
        trigger_phrases=("標籤", "標註", "註記", "分類", "類別", "規則"),
        target_field="標籤或標註規則",
        evidence_terms=("標籤", "標註", "分類", "規則"),
        rerank_brief="Need: 精確的標籤、類別或標註規則 evidence。",
    ),
    QUERY_INTENT_ENUMERATION_OR_INVENTORY: QueryFocusIntentSpec(
        intent=QUERY_INTENT_ENUMERATION_OR_INVENTORY,
        trigger_phrases=("哪些", "列出", "包含哪些", "種類", "型別", "步驟", "清單"),
        target_field="項目清單或列舉內容",
        evidence_terms=("列舉", "清單", "項目", "種類"),
        rerank_brief="Need: 完整的項目清單、列舉內容或 inventory evidence。",
    ),
}

# 英文 query focus intents registry。
QUERY_FOCUS_SPECS_EN: dict[str, QueryFocusIntentSpec] = {
    QUERY_INTENT_AMOUNT_OR_LIMIT: QueryFocusIntentSpec(
        intent=QUERY_INTENT_AMOUNT_OR_LIMIT,
        trigger_phrases=("how much", "amount", "limit", "maximum", "max"),
        target_field="amount or limit",
        evidence_terms=("amount", "limit", "maximum", "cap"),
        rerank_brief="Need: exact amount, limit, or cap evidence.",
    ),
    QUERY_INTENT_DATE_OR_DEADLINE: QueryFocusIntentSpec(
        intent=QUERY_INTENT_DATE_OR_DEADLINE,
        trigger_phrases=("when", "date", "deadline", "due", "how long"),
        target_field="date or deadline",
        evidence_terms=("date", "deadline", "due", "time window"),
        rerank_brief="Need: exact date, deadline, or time-window evidence.",
    ),
    QUERY_INTENT_ELIGIBILITY_OR_ACTOR: QueryFocusIntentSpec(
        intent=QUERY_INTENT_ELIGIBILITY_OR_ACTOR,
        trigger_phrases=("who can", "eligible", "eligibility", "requirement", "responsible", "role"),
        target_field="eligibility or actor",
        evidence_terms=("eligibility", "requirement", "actor", "responsible party"),
        rerank_brief="Need: direct eligibility, actor, or responsible-party evidence.",
    ),
    QUERY_INTENT_COUNT_OR_SIZE: QueryFocusIntentSpec(
        intent=QUERY_INTENT_COUNT_OR_SIZE,
        trigger_phrases=("how many", "count", "total", "size", "how large", "how big", "number of"),
        target_field="count or size",
        evidence_terms=("count", "size", "total", "number"),
        rerank_brief="Need: exact count, total, or size evidence.",
    ),
    QUERY_INTENT_COMPARISON_AXIS: QueryFocusIntentSpec(
        intent=QUERY_INTENT_COMPARISON_AXIS,
        trigger_phrases=("compare", "compared", "better", "difference", "versus", "vs", "outperform"),
        target_field="comparison result or axis",
        evidence_terms=("comparison", "difference", "performance", "versus"),
        rerank_brief="Need: direct comparison evidence between the compared settings.",
    ),
    QUERY_INTENT_SOURCE_MATERIAL: QueryFocusIntentSpec(
        intent=QUERY_INTENT_SOURCE_MATERIAL,
        trigger_phrases=("source", "data source", "source dataset", "source corpus", "based on", "derived from", "pretrained on"),
        target_field="source material",
        evidence_terms=("source material", "data source", "corpus", "dataset"),
        rerank_brief="Need: direct source-material, data-source, or pretraining-source evidence.",
    ),
    QUERY_INTENT_METRIC_OR_EVALUATION_AXIS: QueryFocusIntentSpec(
        intent=QUERY_INTENT_METRIC_OR_EVALUATION_AXIS,
        trigger_phrases=("metric", "metrics", "evaluate", "evaluation", "measure", "measured", "score"),
        target_field="metric or evaluation axis",
        evidence_terms=("metric", "evaluation", "measure", "score"),
        rerank_brief="Need: direct metric or evaluation-axis evidence.",
    ),
    QUERY_INTENT_LABEL_OR_ANNOTATION_SCHEMA: QueryFocusIntentSpec(
        intent=QUERY_INTENT_LABEL_OR_ANNOTATION_SCHEMA,
        trigger_phrases=("label", "labels", "annotation", "annotated", "schema", "class"),
        target_field="label or annotation schema",
        evidence_terms=("label", "annotation", "schema", "class"),
        rerank_brief="Need: direct label, class, or annotation-schema evidence.",
    ),
    QUERY_INTENT_ENUMERATION_OR_INVENTORY: QueryFocusIntentSpec(
        intent=QUERY_INTENT_ENUMERATION_OR_INVENTORY,
        trigger_phrases=("what are", "list", "types of", "categories of", "inventory", "stages"),
        target_field="inventory or enumeration",
        evidence_terms=("list", "inventory", "categories", "types"),
        rerank_brief="Need: complete inventory, list, or enumeration evidence.",
    ),
}

# mixed query 會同時使用中英 registry。
QUERY_FOCUS_SPECS_MIXED: dict[str, QueryFocusIntentSpec] = {
    **QUERY_FOCUS_SPECS_ZH_TW,
    **QUERY_FOCUS_SPECS_EN,
}

# zh-TW qualifier token 候選。
QUERY_QUALIFIER_TOKENS_ZH_TW = ("最高", "最低", "總計", "累計", "申請", "比較", "完整", "主要")
# en qualifier token 候選。
QUERY_QUALIFIER_TOKENS_EN = ("maximum", "minimum", "total", "overall", "main", "complete", "direct")


def build_query_focus_plan_from_settings(*, settings: AppSettings, query: str) -> QueryFocusPlan:
    """依應用程式設定建立 query focus plan。

    參數：
    - `settings`：目前應用程式設定。
    - `query`：原始 retrieval query。

    回傳：
    - `QueryFocusPlan`：已依設定與規則產生的 query focus plan。
    """

    return build_query_focus_plan(
        query=query,
        enabled=settings.retrieval_query_focus_enabled,
        variant=settings.retrieval_query_focus_variant,
        confidence_threshold=settings.retrieval_query_focus_confidence_threshold,
    )


def build_query_focus_plan(
    *,
    query: str,
    enabled: bool,
    variant: str,
    confidence_threshold: float,
) -> QueryFocusPlan:
    """依 query 與 planner 設定產生 query focus plan。

    參數：
    - `query`：原始 retrieval query。
    - `enabled`：是否啟用 query focus planner。
    - `variant`：planner 變體名稱。
    - `confidence_threshold`：planner 套用門檻。

    回傳：
    - `QueryFocusPlan`：planner 輸出；未套用時會保留原 query。
    """

    normalized_query = normalize_query_text(query=query)
    language = detect_query_language(query=normalized_query)
    baseline_plan = QueryFocusPlan(
        original_query=query,
        normalized_query=normalized_query,
        language=language,
        confidence=0.0,
        intents=(),
        slots={},
        focus_query=normalized_query,
        rerank_query=normalized_query,
        applied=False,
        variant=variant,
        rule_family=_resolve_query_focus_rule_family(variant=variant),
    )
    if not enabled or variant != QUERY_FOCUS_VARIANT_GENERIC_FIELD_V1 or not normalized_query:
        return baseline_plan

    specs = _get_query_focus_specs(language=language)
    lowered_query = normalized_query.casefold()
    matched_specs = tuple(
        spec
        for intent in SUPPORTED_QUERY_FOCUS_INTENTS
        if (spec := specs.get(intent)) is not None
        and any(trigger.casefold() in lowered_query for trigger in spec.trigger_phrases)
    )
    if not matched_specs:
        return baseline_plan

    slots = _extract_query_focus_slots(
        normalized_query=normalized_query,
        lowered_query=lowered_query,
        language=language,
        matched_specs=matched_specs,
    )
    confidence = _score_query_focus_confidence(slots=slots, matched_specs=matched_specs)
    focus_query = _build_focus_query(normalized_query=normalized_query, slots=slots, matched_specs=matched_specs)
    rerank_query = _build_rerank_query(normalized_query=normalized_query, matched_specs=matched_specs)
    applied = (
        confidence >= confidence_threshold
        and bool(slots)
        and _focus_query_adds_signal(original_query=normalized_query, focus_query=focus_query)
    )
    if not applied:
        focus_query = normalized_query
        rerank_query = normalized_query

    return QueryFocusPlan(
        original_query=query,
        normalized_query=normalized_query,
        language=language,
        confidence=confidence,
        intents=tuple(spec.intent for spec in matched_specs),
        slots=slots,
        focus_query=focus_query,
        rerank_query=rerank_query,
        applied=applied,
        variant=variant,
        rule_family=QUERY_FOCUS_RULE_FAMILY_GENERIC,
    )


def normalize_query_text(*, query: str) -> str:
    """正規化 query 的空白與前後空白。

    參數：
    - `query`：原始 query。

    回傳：
    - `str`：正規化後的 query。
    """

    return _WHITESPACE_PATTERN.sub(" ", query).strip()


def detect_query_language(*, query: str) -> str:
    """判斷 query 的主要語言類型。

    參數：
    - `query`：待判斷的 query。

    回傳：
    - `str`：`zh-TW`、`en` 或 `mixed`。
    """

    has_cjk = bool(_CJK_PATTERN.search(query))
    has_latin = bool(_LATIN_PATTERN.search(query))
    if has_cjk and has_latin:
        return QUERY_LANGUAGE_MIXED
    if has_cjk:
        return QUERY_LANGUAGE_ZH_TW
    return QUERY_LANGUAGE_EN


def extract_query_tokens(*, query: str) -> list[str]:
    """抽出 ranking 與 planner 共用的 query tokens。

    參數：
    - `query`：原始或 focus query。

    回傳：
    - `list[str]`：去重後的 query tokens。
    """

    normalized_query = normalize_query_text(query=query)
    if not normalized_query:
        return []

    tokens: list[str] = []
    seen: set[str] = set()
    for raw_token in _QUERY_TOKEN_PATTERN.findall(normalized_query.casefold()):
        if _CJK_PATTERN.search(raw_token):
            cjk_tokens = [raw_token]
            if len(raw_token) >= 2:
                cjk_tokens.extend(raw_token[index : index + 2] for index in range(len(raw_token) - 1))
            for token in cjk_tokens:
                if token not in seen:
                    seen.add(token)
                    tokens.append(token)
            continue
        if raw_token not in seen:
            seen.add(raw_token)
            tokens.append(raw_token)
    return tokens


def get_query_focus_boost_terms(*, intents: tuple[str, ...], language: str) -> tuple[str, ...]:
    """依目前命中的 intents 回傳 ranking policy 可用的 boost terms。

    參數：
    - `intents`：planner 命中的 intents。
    - `language`：planner 判定的語言。

    回傳：
    - `tuple[str, ...]`：供 ranking policy 小幅加分的欄位詞。
    """

    specs = _get_query_focus_specs(language=language)
    terms: list[str] = []
    seen: set[str] = set()
    for intent in intents:
        spec = specs.get(intent)
        if spec is None:
            continue
        candidates = (spec.target_field, *spec.evidence_terms[:2])
        for candidate in candidates:
            normalized_candidate = candidate.casefold()
            if normalized_candidate not in seen:
                seen.add(normalized_candidate)
                terms.append(candidate)
    return tuple(terms)


def _resolve_query_focus_rule_family(*, variant: str) -> str:
    """依 planner variant 回傳對應的規則家族名稱。

    參數：
    - `variant`：planner 變體名稱。

    回傳：
    - `str`：規則家族名稱；未知變體回空字串。
    """

    if variant == QUERY_FOCUS_VARIANT_GENERIC_FIELD_V1:
        return QUERY_FOCUS_RULE_FAMILY_GENERIC
    return ""


def _get_query_focus_specs(*, language: str) -> dict[str, QueryFocusIntentSpec]:
    """依語言選擇 planner intent registry。

    參數：
    - `language`：planner 判定的語言。

    回傳：
    - `dict[str, QueryFocusIntentSpec]`：對應語言的 intent specs。
    """

    if language == QUERY_LANGUAGE_ZH_TW:
        return QUERY_FOCUS_SPECS_ZH_TW
    if language == QUERY_LANGUAGE_EN:
        return QUERY_FOCUS_SPECS_EN
    return QUERY_FOCUS_SPECS_MIXED


def _extract_query_focus_slots(
    *,
    normalized_query: str,
    lowered_query: str,
    language: str,
    matched_specs: tuple[QueryFocusIntentSpec, ...],
) -> dict[str, str]:
    """依命中 intents 抽取最小 slot 集合。

    參數：
    - `normalized_query`：正規化後的原始 query。
    - `lowered_query`：正規化並 casefold 後的 query。
    - `language`：planner 判定的語言。
    - `matched_specs`：本次命中的 intents。

    回傳：
    - `dict[str, str]`：最小 slot 集合。
    """

    slots: dict[str, str] = {}
    subject = _extract_subject(
        normalized_query=normalized_query,
        lowered_query=lowered_query,
        language=language,
        matched_specs=matched_specs,
    )
    if subject:
        slots["subject"] = subject

    target_fields = [spec.target_field for spec in matched_specs if spec.target_field]
    if target_fields:
        slots["target_field"] = " / ".join(dict.fromkeys(target_fields))

    qualifier = _extract_qualifier(
        lowered_query=lowered_query,
        original_query=normalized_query,
        language=language,
    )
    if qualifier:
        slots["qualifier"] = qualifier

    comparison_target = _extract_comparison_target(
        normalized_query=normalized_query,
        matched_specs=matched_specs,
    )
    if comparison_target:
        slots["comparison_target"] = comparison_target

    return slots


def _extract_subject(
    *,
    normalized_query: str,
    lowered_query: str,
    language: str,
    matched_specs: tuple[QueryFocusIntentSpec, ...],
) -> str | None:
    """抽取 query 中的主語或主題片段。

    參數：
    - `normalized_query`：正規化後的原始 query。
    - `lowered_query`：正規化並 casefold 後的 query。
    - `language`：planner 判定的語言。
    - `matched_specs`：本次命中的 intents。

    回傳：
    - `str | None`：若成功抽到主題片段則回傳，否則回空值。
    """

    if language in {QUERY_LANGUAGE_ZH_TW, QUERY_LANGUAGE_MIXED}:
        prefixed_subject = _extract_prefixed_subject(
            normalized_query=normalized_query,
            lowered_query=lowered_query,
            matched_specs=matched_specs,
        )
        if prefixed_subject:
            return prefixed_subject
    if language in {QUERY_LANGUAGE_EN, QUERY_LANGUAGE_MIXED}:
        return _extract_subject_from_english_tokens(
            normalized_query=normalized_query,
            matched_specs=matched_specs,
        )
    return None


def _extract_prefixed_subject(
    *,
    normalized_query: str,
    lowered_query: str,
    matched_specs: tuple[QueryFocusIntentSpec, ...],
) -> str | None:
    """從 trigger phrase 前綴抽取中文主題片段。

    參數：
    - `normalized_query`：正規化後的原始 query。
    - `lowered_query`：正規化並 casefold 後的 query。
    - `matched_specs`：本次命中的 intents。

    回傳：
    - `str | None`：若成功抽到前綴主題則回傳，否則回空值。
    """

    trigger_positions = [
        lowered_query.find(trigger.casefold())
        for spec in matched_specs
        for trigger in spec.trigger_phrases
        if lowered_query.find(trigger.casefold()) > 0
    ]
    if not trigger_positions:
        return None

    prefix = normalized_query[: min(trigger_positions)].strip(" ，。！？?/:：-")
    prefix = prefix.rstrip("的")
    candidate = re.sub(r"(的)?(申請|使用|比較)$", "", prefix).strip()
    return candidate or None


def _extract_subject_from_english_tokens(
    *,
    normalized_query: str,
    matched_specs: tuple[QueryFocusIntentSpec, ...],
) -> str | None:
    """從英文 query token 萃取主語片段。

    參數：
    - `normalized_query`：正規化後的原始 query。
    - `matched_specs`：本次命中的 intents。

    回傳：
    - `str | None`：若成功抽到英文主語片段則回傳，否則回空值。
    """

    excluded_tokens = {
        token.casefold()
        for spec in matched_specs
        for phrase in spec.trigger_phrases
        for token in _ENGLISH_WORD_PATTERN.findall(phrase.casefold())
    }
    subject_tokens = [
        token
        for token in _ENGLISH_WORD_PATTERN.findall(normalized_query)
        if token.casefold() not in ENGLISH_SUBJECT_STOPWORDS and token.casefold() not in excluded_tokens
    ]
    if not subject_tokens:
        return None
    return " ".join(subject_tokens[:4]).strip() or None


def _extract_qualifier(*, lowered_query: str, original_query: str, language: str) -> str | None:
    """抽取 query 中的補充 qualifier。

    參數：
    - `lowered_query`：正規化並 casefold 後的 query。
    - `original_query`：正規化後的原始 query。
    - `language`：planner 判定的語言。

    回傳：
    - `str | None`：若命中 qualifier 短語則回傳，否則回空值。
    """

    qualifier_tokens = _get_language_phrase_candidates(
        language=language,
        zh_candidates=QUERY_QUALIFIER_TOKENS_ZH_TW,
        en_candidates=QUERY_QUALIFIER_TOKENS_EN,
    )
    qualifier = _extract_all_phrases(
        lowered_query=lowered_query,
        original_query=original_query,
        phrases=qualifier_tokens,
    )
    if not qualifier:
        return None
    return " / ".join(qualifier)


def _extract_comparison_target(
    *,
    normalized_query: str,
    matched_specs: tuple[QueryFocusIntentSpec, ...],
) -> str | None:
    """抽取 query 中的比較對象。

    參數：
    - `normalized_query`：正規化後的原始 query。
    - `matched_specs`：本次命中的 intents。

    回傳：
    - `str | None`：若命中比較對象則回傳，否則回空值。
    """

    if QUERY_INTENT_COMPARISON_AXIS not in {spec.intent for spec in matched_specs}:
        return None

    english_match = _ENGLISH_COMPARISON_PATTERN.search(normalized_query)
    if english_match is not None:
        left = english_match.group("left").strip()
        right = english_match.group("right").strip()
        return f"{left} / {right}"

    cjk_match = _CJK_COMPARISON_PATTERN.search(normalized_query)
    if cjk_match is not None:
        left = cjk_match.group("left").strip()
        right = cjk_match.group("right").strip()
        return f"{left} / {right}"
    return None


def _get_language_phrase_candidates(
    *,
    language: str,
    zh_candidates: tuple[str, ...],
    en_candidates: tuple[str, ...],
) -> tuple[str, ...]:
    """依語言回傳對應的 phrase 候選集合。

    參數：
    - `language`：planner 判定的語言。
    - `zh_candidates`：繁體中文候選集合。
    - `en_candidates`：英文候選集合。

    回傳：
    - `tuple[str, ...]`：依語言挑選或合併後的候選集合。
    """

    if language == QUERY_LANGUAGE_ZH_TW:
        return zh_candidates
    if language == QUERY_LANGUAGE_EN:
        return en_candidates
    return (*zh_candidates, *en_candidates)


def _extract_all_phrases(*, lowered_query: str, original_query: str, phrases: tuple[str, ...]) -> list[str]:
    """找出 query 中所有命中的短語。

    參數：
    - `lowered_query`：正規化並 casefold 後的 query。
    - `original_query`：原始 query。
    - `phrases`：待檢查的短語候選。

    回傳：
    - `list[str]`：依輸入順序回傳所有命中的短語。
    """

    matches: list[str] = []
    seen: set[str] = set()
    for phrase in phrases:
        index = lowered_query.find(phrase.casefold())
        if index < 0:
            continue
        raw_match = original_query[index : index + len(phrase)]
        normalized_match = raw_match.casefold()
        if normalized_match in seen:
            continue
        seen.add(normalized_match)
        matches.append(raw_match)
    return matches


def _score_query_focus_confidence(*, slots: dict[str, str], matched_specs: tuple[QueryFocusIntentSpec, ...]) -> float:
    """計算 planner confidence。

    參數：
    - `slots`：本次抽出的 slot 集合。
    - `matched_specs`：本次命中的 intents。

    回傳：
    - `float`：0 到 1 的 confidence 分數。
    """

    confidence = 0.0
    if matched_specs:
        confidence += 0.35
    if slots.get("target_field"):
        confidence += 0.25
    if slots.get("subject") or slots.get("comparison_target"):
        confidence += 0.20
    if slots.get("qualifier"):
        confidence += 0.20
    return min(confidence, 1.0)


def _build_focus_query(
    *,
    normalized_query: str,
    slots: dict[str, str],
    matched_specs: tuple[QueryFocusIntentSpec, ...],
) -> str:
    """建立 recall / ranking 使用的 focus query。

    參數：
    - `normalized_query`：正規化後的原始 query。
    - `slots`：planner 抽出的 slot 集合。
    - `matched_specs`：本次命中的 intents。

    回傳：
    - `str`：追加 evidence-facing 詞彙後的 focus query。
    """

    candidates = [normalized_query]
    for slot_name in ("subject", "target_field", "qualifier", "comparison_target"):
        slot_value = slots.get(slot_name)
        if slot_value:
            candidates.extend(part.strip() for part in slot_value.split(" / ") if part.strip())
    for spec in matched_specs:
        candidates.extend(spec.evidence_terms)

    deduplicated_terms: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        normalized_candidate = candidate.casefold()
        if normalized_candidate in seen:
            continue
        seen.add(normalized_candidate)
        deduplicated_terms.append(candidate)
    return " ".join(deduplicated_terms).strip()


def _build_rerank_query(*, normalized_query: str, matched_specs: tuple[QueryFocusIntentSpec, ...]) -> str:
    """建立 rerank provider 使用的 query。

    參數：
    - `normalized_query`：正規化後的原始 query。
    - `matched_specs`：本次命中的 intents。

    回傳：
    - `str`：`original query + one-line evidence brief` 形式的 rerank query。
    """

    rerank_briefs = list(dict.fromkeys(spec.rerank_brief for spec in matched_specs if spec.rerank_brief))
    if not rerank_briefs:
        return normalized_query
    one_line_brief = " ".join(rerank_briefs)[:180].strip()
    return f"{normalized_query}\n{one_line_brief}".strip()


def _focus_query_adds_signal(*, original_query: str, focus_query: str) -> bool:
    """判斷 focus query 是否真的新增 evidence-facing 訊號。

    參數：
    - `original_query`：原始 query。
    - `focus_query`：planner 產生的 focus query。

    回傳：
    - `bool`：若 focus query 新增了可辨識訊號則回傳 `True`。
    """

    original_tokens = set(extract_query_tokens(query=original_query))
    focus_tokens = set(extract_query_tokens(query=focus_query))
    return bool(focus_tokens.difference(original_tokens))
