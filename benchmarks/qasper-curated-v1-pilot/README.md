# qasper-curated-v1-pilot

This directory is a reproducible pilot benchmark package that maps a small `QASPER` subset onto the repository's existing retrieval evaluation contract.

[繁體中文版本](README.zh-TW.md)

## Purpose

This package exists to let another engineer reproduce the same pilot benchmark flow and inspect:

- which `QASPER` subset was kept after `fact_lookup` curation
- how many questions were auto-aligned to `display_text`
- which items still needed manual review
- the exact reference run configuration and summary metrics

## What's Included

- `manifest.json`: benchmark identity and dataset stats
- `documents.jsonl`: the logical benchmark document list
- `questions.jsonl`: the curated pilot questions
- `gold_spans.jsonl`: gold spans aligned to system `display_text` offsets
- `alignment_candidates.jsonl`: alignment outcomes for all kept items
- `alignment_review_queue.jsonl`: items that were not auto-approved
- `filter_report.json`: item filtering summary
- `reference_run_summary.json`: the completed reference run id, config snapshot, and summary metrics
- `reproduce.md`: step-by-step reproduction guide

## Reference Run

- Dataset: `qasper-curated-v1-pilot`
- Dataset ID: `db6d581c-2feb-5914-afb8-b4f1fa2092e2`
- Area name used during creation: `qasper-pilot`
- Reference run ID: `6f1150df-1343-4905-a417-7334ea87c9d6`
- Evaluation profile: `production_like_v1`
- Item count: `27`
- Auto-matched ratio during curation: `0.931034`

## Summary Metrics

| Stage | nDCG@10 | Recall@10 | MRR@10 | Precision@10 | Doc Coverage@10 |
| --- | ---: | ---: | ---: | ---: | ---: |
| recall | 0.2920 | 0.5556 | 0.2062 | 0.0630 | 0.9630 |
| rerank | 0.4590 | 0.5556 | 0.4228 | 0.0593 | 0.9630 |
| assembled | 0.4489 | 0.5556 | 0.4105 | 0.0593 | 0.9630 |

## Notes

- This is a pilot benchmark, not a full `QASPER` leaderboard result.
- Gold truth is anchored to this repository's `display_text` offsets, not original dataset offsets.
- One item remained in `needs_review` and one item was rejected during curation; neither is included in the final snapshot scores.
