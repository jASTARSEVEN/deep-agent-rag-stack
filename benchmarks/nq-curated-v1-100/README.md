# nq-curated-v1-100

This directory is a reproducible `Natural Questions` benchmark package that folds a curated `100`-question subset into the repository's existing retrieval evaluation contract.

[繁體中文版本](README.zh-TW.md)

## Purpose

This package exists so another engineer can reproduce the same `NQ 100` curation flow and inspect:

- the `Natural Questions` validation rows used to build the package
- which questions survived the repository's `fact_lookup` curation rules
- the deterministic `display_text` alignment outcomes
- the exact `production_like_v1` reference run metrics

## What's Included

- `manifest.json`: benchmark identity, package stats, and reference evaluation profile
- `documents.jsonl`: the logical benchmark document list used by the final `100` questions
- `questions.jsonl`: the final `100` benchmark questions
- `gold_spans.jsonl`: `display_text`-aligned gold spans
- `alignment_candidates.jsonl`: alignment outcomes for the oversampled workspace
- `alignment_review_queue.jsonl`: the deterministic review queue; it is empty for this reference package
- `filter_report.json`: curation summary for the oversampled workspace
- `reference_run_summary.json`: the completed `production_like_v1` reference run summary
- `reproduce.md`: the step-by-step reproduction guide

## Reference Run

- Dataset: `nq-curated-v1-100`
- Dataset ID: `c1fef25a-7f8a-59d0-8974-f44ace477600`
- Area name used during creation: `nq-100`
- Area ID: `9d89e5b3-3a31-43d6-9441-8d1de9dd6e0b`
- Reference run ID: `3e07bb70-7068-483c-81d0-35ad43092dfb`
- Evaluation profile: `production_like_v1`
- Item count: `100`
- Final document count: `100`
- Oversampled prepared item count: `260`
- Oversampled filtered item count: `250`
- Deterministic auto-matched count: `250`
- Approved `OpenAI` overrides: `0`

## Summary Metrics

| Stage | nDCG@10 | Recall@10 | MRR@10 | Precision@10 | Doc Coverage@10 |
| --- | ---: | ---: | ---: | ---: | ---: |
| recall | 0.5019 | 0.8100 | 0.4166 | 0.1110 | 0.9700 |
| rerank | 0.9569 | 0.9700 | 0.9525 | 0.0970 | 1.0000 |
| assembled | 0.7443 | 0.7500 | 0.7425 | 0.0750 | 1.0000 |

## Notes

- This package is repository-specific. It is not the original `Natural Questions` leaderboard split.
- The final package is the deterministic first `100` approved items from the oversampled workspace.
- The reference package did not need an `OpenAI` review pass because `needs_review = 0`; if a future rerun produces a non-empty review queue, route those items through `review_external_benchmark_with_openai.py`.
- The main signal in this run is the gap between `rerank` and `assembled`, which makes this package useful as an assembler regression sentinel.
