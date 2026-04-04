"""retrieval query focus planner 與 query-side 對齊 helper。"""

from __future__ import annotations

from dataclasses import dataclass
import re

from app.core.settings import AppSettings


# `query_focus_v1` 表示目前唯一支援的 query focus planner 變體。
QUERY_FOCUS_VARIANT_V1 = "query_focus_v1"

# `zh-TW` 表示繁體中文 query language。
QUERY_LANGUAGE_ZH_TW = "zh-TW"
# `en` 表示英文 query language。
QUERY_LANGUAGE_EN = "en"
# `mixed` 表示中英混合 query language。
QUERY_LANGUAGE_MIXED = "mixed"

# `amount_max` 表示累計最高投保金額或上限類意圖。
QUERY_INTENT_AMOUNT_MAX = "amount_max"
# `age_range` 表示投保年齡或可投保歲數類意圖。
QUERY_INTENT_AGE_RANGE = "age_range"
# `payment_term` 表示繳費年期或繳別限制類意圖。
QUERY_INTENT_PAYMENT_TERM = "payment_term"
# `deadline` 表示申請期限或時效類意圖。
QUERY_INTENT_DEADLINE = "deadline"
# `eligibility_identity` 表示身分資格或申請限制類意圖。
QUERY_INTENT_ELIGIBILITY_IDENTITY = "eligibility_identity"
# `count_total` 表示總數、規模或 total count 類意圖。
QUERY_INTENT_COUNT_TOTAL = "count_total"
# `comparison_axis` 表示兩個設定或方案的比較意圖。
QUERY_INTENT_COMPARISON_AXIS = "comparison_axis"

# 本模組正式支援的 intents。
SUPPORTED_QUERY_FOCUS_INTENTS = (
    QUERY_INTENT_AMOUNT_MAX,
    QUERY_INTENT_AGE_RANGE,
    QUERY_INTENT_PAYMENT_TERM,
    QUERY_INTENT_DEADLINE,
    QUERY_INTENT_ELIGIBILITY_IDENTITY,
    QUERY_INTENT_COUNT_TOTAL,
    QUERY_INTENT_COMPARISON_AXIS,
)

# CJK script 偵測 pattern。
_CJK_PATTERN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
# Latin script 偵測 pattern。
_LATIN_PATTERN = re.compile(r"[A-Za-z]")
# 空白正規化 pattern。
_WHITESPACE_PATTERN = re.compile(r"\s+")
# query token 抽取 pattern；會同時保留英文詞與 CJK 片段。
_QUERY_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]*|[\u3400-\u4dbf\u4e00-\u9fff]+")


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
    QUERY_INTENT_AMOUNT_MAX: QueryFocusIntentSpec(
        intent=QUERY_INTENT_AMOUNT_MAX,
        trigger_phrases=("累計最高", "最高投保金額", "最高保額", "上限"),
        target_field="最高投保金額",
        evidence_terms=("累計最高", "最高投保金額", "投保金額", "上限"),
        rerank_brief="Need: 精確的最高投保金額或上限欄位。",
    ),
    QUERY_INTENT_AGE_RANGE: QueryFocusIntentSpec(
        intent=QUERY_INTENT_AGE_RANGE,
        trigger_phrases=("幾歲", "投保年齡", "年齡限制", "可投保"),
        target_field="投保年齡",
        evidence_terms=("投保年齡", "年齡限制", "可投保"),
        rerank_brief="Need: 精確的投保年齡或年齡限制欄位。",
    ),
    QUERY_INTENT_PAYMENT_TERM: QueryFocusIntentSpec(
        intent=QUERY_INTENT_PAYMENT_TERM,
        trigger_phrases=("各年期", "年期", "繳費年期", "繳別"),
        target_field="繳費年期",
        evidence_terms=("繳費年期", "年期", "繳別"),
        rerank_brief="Need: 精確的繳費年期或繳別欄位。",
    ),
    QUERY_INTENT_DEADLINE: QueryFocusIntentSpec(
        intent=QUERY_INTENT_DEADLINE,
        trigger_phrases=("申請時間", "期限", "時效", "多久內"),
        target_field="申請時間",
        evidence_terms=("申請時間", "期限", "時效", "提出申請"),
        rerank_brief="Need: 精確的申請時間或期限欄位。",
    ),
    QUERY_INTENT_ELIGIBILITY_IDENTITY: QueryFocusIntentSpec(
        intent=QUERY_INTENT_ELIGIBILITY_IDENTITY,
        trigger_phrases=("身分限制", "資格限制", "誰可以", "誰可", "要保人", "被保險人"),
        target_field="身分限制",
        evidence_terms=("身分限制", "資格限制", "要保人", "被保險人", "同一人"),
        rerank_brief="Need: 精確的資格限制或身分限制欄位。",
    ),
}

# 英文 query focus intents registry。
QUERY_FOCUS_SPECS_EN: dict[str, QueryFocusIntentSpec] = {
    QUERY_INTENT_COUNT_TOTAL: QueryFocusIntentSpec(
        intent=QUERY_INTENT_COUNT_TOTAL,
        trigger_phrases=("how many", "in total", "total", "overall", "count"),
        target_field="total count",
        evidence_terms=("total count", "in total", "both generated and true", "reviews"),
        rerank_brief="Need: exact total count evidence, including both generated and true reviews.",
    ),
    QUERY_INTENT_COMPARISON_AXIS: QueryFocusIntentSpec(
        intent=QUERY_INTENT_COMPARISON_AXIS,
        trigger_phrases=("perform better", "better", "better in", "single-domain", "multi-domain", "compared with"),
        target_field="comparison result",
        evidence_terms=("comparison", "perform better", "single-domain", "multi-domain", "performance"),
        rerank_brief="Need: direct comparison evidence between the two settings.",
    ),
}

# mixed query 會同時使用中英 registry。
QUERY_FOCUS_SPECS_MIXED: dict[str, QueryFocusIntentSpec] = {
    **QUERY_FOCUS_SPECS_ZH_TW,
    **QUERY_FOCUS_SPECS_EN,
}

# zh-TW action token 候選。
QUERY_ACTION_TOKENS_ZH_TW = ("投保", "申請", "借款", "理賠", "變更")
# en action token 候選。
QUERY_ACTION_TOKENS_EN = ("evaluate", "perform", "compare", "count", "measure")

# zh-TW qualifier token 候選。
QUERY_QUALIFIER_TOKENS_ZH_TW = ("各年期", "網路保險", "累計", "最高", "多久內", "可投保")
# en qualifier token 候選。
QUERY_QUALIFIER_TOKENS_EN = ("in total", "both generated and true", "single-domain", "multi-domain")

# zh-TW domain object token 候選。
QUERY_DOMAIN_OBJECT_TOKENS_ZH_TW = ("保單借款", "更約權", "投保", "保險")
# en domain object token 候選。
QUERY_DOMAIN_OBJECT_TOKENS_EN = ("reviews", "amazon mechanical turk", "setting", "performance")


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
    )
    if not enabled or variant != QUERY_FOCUS_VARIANT_V1 or not normalized_query:
        return baseline_plan

    specs = _get_query_focus_specs(language=language)
    lowered_query = normalized_query.casefold()
    matched_specs = tuple(
        spec for spec in specs.values() if any(trigger.casefold() in lowered_query for trigger in spec.trigger_phrases)
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
    product_name = _extract_product_name(
        normalized_query=normalized_query,
        lowered_query=lowered_query,
        language=language,
        matched_specs=matched_specs,
    )
    if product_name:
        slots["product_name"] = product_name

    action_tokens = _get_language_phrase_candidates(
        language=language,
        zh_candidates=QUERY_ACTION_TOKENS_ZH_TW,
        en_candidates=QUERY_ACTION_TOKENS_EN,
    )
    action = _extract_first_phrase(
        lowered_query=lowered_query,
        original_query=normalized_query,
        phrases=action_tokens,
    )
    if action:
        slots["action"] = action

    target_fields = [spec.target_field for spec in matched_specs if spec.target_field]
    if target_fields:
        slots["target_field"] = " / ".join(dict.fromkeys(target_fields))

    qualifier_tokens = _get_language_phrase_candidates(
        language=language,
        zh_candidates=QUERY_QUALIFIER_TOKENS_ZH_TW,
        en_candidates=QUERY_QUALIFIER_TOKENS_EN,
    )
    qualifier = _extract_all_phrases(lowered_query=lowered_query, original_query=normalized_query, phrases=qualifier_tokens)
    if qualifier:
        slots["qualifier"] = " / ".join(qualifier)

    domain_tokens = _get_language_phrase_candidates(
        language=language,
        zh_candidates=QUERY_DOMAIN_OBJECT_TOKENS_ZH_TW,
        en_candidates=QUERY_DOMAIN_OBJECT_TOKENS_EN,
    )
    domain_object = _extract_all_phrases(lowered_query=lowered_query, original_query=normalized_query, phrases=domain_tokens)
    if domain_object:
        slots["domain_object"] = " / ".join(domain_object)

    return slots


def _extract_product_name(
    *,
    normalized_query: str,
    lowered_query: str,
    language: str,
    matched_specs: tuple[QueryFocusIntentSpec, ...],
) -> str | None:
    """抽取 query 開頭的產品或主語片段。

    參數：
    - `normalized_query`：正規化後的原始 query。
    - `lowered_query`：正規化並 casefold 後的 query。
    - `language`：planner 判定的語言。
    - `matched_specs`：本次命中的 intents。

    回傳：
    - `str | None`：若成功抽到主語片段則回傳，否則回空值。
    """

    if language not in {QUERY_LANGUAGE_ZH_TW, QUERY_LANGUAGE_MIXED}:
        return None

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
    return prefix.strip() or None


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


def _extract_first_phrase(*, lowered_query: str, original_query: str, phrases: tuple[str, ...]) -> str | None:
    """找出 query 中第一個命中的短語。

    參數：
    - `lowered_query`：正規化並 casefold 後的 query。
    - `original_query`：原始 query。
    - `phrases`：待檢查的短語候選。

    回傳：
    - `str | None`：命中的第一個短語；若未命中則回空值。
    """

    for phrase in phrases:
        index = lowered_query.find(phrase.casefold())
        if index >= 0:
            return original_query[index : index + len(phrase)]
    return None


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
    if slots.get("product_name") or slots.get("domain_object"):
        confidence += 0.20
    if slots.get("qualifier") or slots.get("action"):
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
    for slot_name in ("product_name", "domain_object", "action", "target_field", "qualifier"):
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
