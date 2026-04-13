# qmsum-query-summary-curated-pilot-v1

## Purpose

10 real QMSum query-conditioned summary items extracted from the official test split.

## Provenance

- Upstream dataset: QMSum official test split.
- Upstream file: `data/ALL/jsonl/test.jsonl` in the official Yale-LILY repository.
- Extraction rule: preserve original meeting order and take the first 10 `specific_query_list` items.
- Each item stores `source_record_index`, `source_example_id`, and `source_mapping.query_index` for exact trace-back.
