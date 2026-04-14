# Phase 8A Summary / Compare Checkpoint

- Passed: `False`
- Benchmark: `phase8a-summary-compare-v1` `1.0.0`
- Area ID: `bae3f8a6-7ff0-4278-a8e6-db2ead558b10`
- Judge Model: `offline-codex`
- Thinking Mode: `True`
- Answer Path: `deepagents_unified`
- Item Count: `16`

## Aggregate Metrics

- Task Type Accuracy: `1.0000`
- Summary Strategy Accuracy: `1.0000`
- Required Document Coverage: `1.0000`
- Citation Coverage: `1.0000`
- Section Coverage: `1.0000`
- Fallback Rate: `0.0000`
- Avg Faithfulness: `4.6250`
- Avg Overall Score: `4.5625`
- p95 Latency: `21.8645`
- Timeout Count: `0`

## Gates

- `task_type_accuracy`: PASS (actual=1.0000 >= threshold=1.0000)
- `summary_strategy_accuracy`: PASS (actual=1.0000 >= threshold=0.8750)
- `required_document_coverage`: PASS (actual=1.0000 >= threshold=0.9000)
- `citation_coverage`: PASS (actual=1.0000 >= threshold=0.9000)
- `section_coverage`: PASS (actual=1.0000 >= threshold=0.8000)
- `fallback_rate`: PASS (actual=0.0000 <= threshold=0.1000)
- `avg_faithfulness_to_citations`: PASS (actual=4.6250 >= threshold=4.5000)
- `avg_overall_score`: PASS (actual=4.5625 >= threshold=4.2000)
- `min_per_item_overall_score`: FAIL (actual=2.2500 >= threshold=3.0000)
- `p95_latency_seconds`: PASS (actual=21.8645 <= threshold=30.0000)
- `timeout_count`: PASS (actual=0.0000 == threshold=0.0000)
- `hard_blocker_failures`: FAIL (actual=2.0000 == threshold=0.0000)

## Recommendations

- 優先收緊 synthesis 與 compare 文案，避免回答超出 citations 可支持的內容。
- 檢查 map/reduce 是否有遺漏 required claims 或 compare axes，必要時增加 refine 或 coverage guardrail。
- 檢查 section recall 與 section synopsis 命中情況，避免 section-focused 題目抓到錯章節。

## Failed Items

- `theme-en-1`: blockers=none; overall=2.25
- `compare-zh-1`: blockers=insufficient_evidence_not_acknowledged; overall=5.00
- `compare-mixed-1`: blockers=insufficient_evidence_not_acknowledged; overall=4.75