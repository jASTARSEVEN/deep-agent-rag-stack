# summary-compare-bilingual-curated-pilot-v1

## Purpose

This suite bundles the bilingual curated pilot packages for the new summary/compare benchmark lane.

It is designed to produce two primary benchmark scores:

- `summary_benchmark_score`
- `compare_benchmark_score`

## What's Included

- `manifest.json`: suite manifest with the package list
- five curated pilot packages:
  - `qmsum-query-summary-curated-pilot-v1`
  - `multinews-multi-doc-summary-curated-pilot-v1`
  - `cocotrip-compare-curated-pilot-v1`
  - `drcd-query-summary-curated-pilot-v1`
  - `ttnews-multi-doc-summary-curated-pilot-v1`

## How to Run

```bash
python -m app.scripts.run_summary_compare_benchmark \
  --area-id <AREA_ID> \
  --dataset-dir benchmarks/summary-compare-bilingual-curated-pilot-v1 \
  --actor-sub <USER_SUB> \
  --output-path artifacts/summary-compare-bilingual-curated-pilot-v1.json
```
