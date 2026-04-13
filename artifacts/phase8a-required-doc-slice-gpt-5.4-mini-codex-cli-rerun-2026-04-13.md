# Phase 8A Summary / Compare Checkpoint

- Passed: `False`
- Benchmark: `phase8a-summary-compare-v1` `1.0.0`
- Area ID: `bae3f8a6-7ff0-4278-a8e6-db2ead558b10`
- Judge Model: `offline-codex`
- Thinking Mode: `True`
- Answer Path: `deepagents_unified`
- Item Count: `3`

## Aggregate Metrics

- Task Type Accuracy: `1.0000`
- Summary Strategy Accuracy: `1.0000`
- Required Document Coverage: `1.0000`
- Citation Coverage: `1.0000`
- Section Coverage: `1.0000`
- Fallback Rate: `0.0000`
- Avg Faithfulness: `5.0000`
- Avg Overall Score: `4.9167`
- p95 Latency: `12.8594`
- Timeout Count: `0`

## Gates

- `task_type_accuracy`: PASS (actual=1.0000 >= threshold=1.0000)
- `summary_strategy_accuracy`: PASS (actual=1.0000 >= threshold=0.8750)
- `required_document_coverage`: PASS (actual=1.0000 >= threshold=0.9000)
- `citation_coverage`: PASS (actual=1.0000 >= threshold=0.9000)
- `section_coverage`: PASS (actual=1.0000 >= threshold=0.8000)
- `fallback_rate`: PASS (actual=0.0000 <= threshold=0.1000)
- `avg_faithfulness_to_citations`: PASS (actual=5.0000 >= threshold=4.5000)
- `avg_overall_score`: PASS (actual=4.9167 >= threshold=4.2000)
- `min_per_item_overall_score`: PASS (actual=4.7500 >= threshold=3.0000)
- `p95_latency_seconds`: PASS (actual=12.8594 <= threshold=30.0000)
- `timeout_count`: PASS (actual=0.0000 == threshold=0.0000)
- `hard_blocker_failures`: FAIL (actual=1.0000 == threshold=0.0000)

## Recommendations

- 無

## Failed Items

- `compare-zh-1`: blockers=insufficient_evidence_not_acknowledged; overall=5.00