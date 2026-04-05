# dureader-robust-curated-v1-100

This directory is a reproducible `DuReader-robust` benchmark package that maps the official development split into the repository's existing retrieval evaluation contract.

[繁體中文版本](README.zh-TW.md)

## Purpose

This package exists so another engineer can reproduce the same `DuReader-robust 100` curation flow and inspect:

- how the official `DuReader-robust` `dev.json` wrapper was normalized into paragraph-level benchmark documents
- which questions survived the repository's `fact_lookup` curation rules
- how many gold spans were deterministic auto-aligns versus `OpenAI` review overrides
- the exact `production_like_v1` reference run metrics under the shared current baseline

## What's Included

- `manifest.json`: benchmark identity, package stats, and reference evaluation profile
- `documents.jsonl`: the logical benchmark document list used by the final `100` questions
- `questions.jsonl`: the final `100` benchmark questions
- `gold_spans.jsonl`: `display_text`-aligned gold spans
- `alignment_candidates.jsonl`: deterministic alignment outcomes for the oversampled workspace
- `alignment_review_queue.jsonl`: the review queue before any `OpenAI` pass; it is empty for this reference package
- `filter_report.json`: curation summary for the oversampled workspace
- `reference_run_summary.json`: the completed `production_like_v1` reference run summary
- `reproduce.md`: the step-by-step reproduction guide

## Reference Run

- Dataset: `dureader-robust-curated-v1-100`
- Dataset ID: `f4a91b45-64fa-5cd7-b815-9a454888bf9c`
- Area name used during creation: `dureader-robust-100`
- Area ID: `d9cd72a9-5684-47cc-ae17-088606160377`
- Reference run ID: `6befc441-39ba-4580-9d9c-f5d795158f1b`
- Evaluation profile: `production_like_v1`
- Item count: `100`
- Final document count: `100`
- Oversampled prepared item count: `220`
- Oversampled filtered item count: `220`
- Deterministic auto-matched count: `220`
- Approved `OpenAI` overrides: `0`

## Summary Metrics

| Stage | nDCG@10 | Recall@10 | MRR@10 | Precision@10 | Doc Coverage@10 |
| --- | ---: | ---: | ---: | ---: | ---: |
| recall | `0.8867` | `0.9800` | `0.8566` | `0.0990` | `0.9800` |
| rerank | `0.9677` | `1.0000` | `0.9570` | `0.1000` | `1.0000` |
| assembled | `0.9677` | `1.0000` | `0.9570` | `0.1000` | `1.0000` |

## Notes

- This package is repository-specific. It is not the original `DuReader-robust` leaderboard split.
- The official source file is `dureader_robust-data/dev.json`, which stores a SQuAD-style `data -> paragraphs -> qas` wrapper; this package materializes each paragraph into a standalone benchmark document.
- The final package keeps the deterministic first `100` approved items from the first `220` prepared questions.
- The reference package did not need an `OpenAI` review pass because `needs_review = 0`; if a future rerun produces a non-empty queue, route it through `review_external_benchmark_with_openai.py`.
- In the current baseline, `DuReader-robust 100` behaves as a near-ceiling Chinese extractive sanity check where rerank closes the remaining recall gap and assembler preserves that gain.
