# Phase 8A Summary / Compare Checkpoint

## Purpose

This package defines the fixed Phase 8A checkpoint dataset for summary and compare runtime validation.

It is designed for the `python -m app.scripts.run_summary_compare_checkpoint` flow and focuses on:

- single-document overview summaries
- section-focused summaries
- multi-document theme summaries
- cross-document comparisons

## How to use

1. Upload the files in [`source_documents`](./source_documents) into a single Knowledge Area.
2. Wait until all files reach `ready`.
3. Run the checkpoint CLI against that area and this dataset directory.

Example:

```bash
python -m app.scripts.run_summary_compare_checkpoint \
  --area-id <AREA_ID> \
  --dataset-dir benchmarks/phase8a-summary-compare-v1 \
  --actor-sub <USER_SUB> \
  --judge-model gpt-5.4-mini \
  --output-path artifacts/phase8a-summary-compare-report.json
```

## Dataset shape

- `manifest.json`: dataset metadata
- `questions.jsonl`: fixed checkpoint items
- `source_documents/`: reference source files for local setup

`gold_span_refs` use a quote-first contract so the runner can resolve offsets against the actual `display_text` stored in the target area.
