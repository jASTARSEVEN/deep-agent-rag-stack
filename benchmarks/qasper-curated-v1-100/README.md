# qasper-curated-v1-100

This directory is a reproducible `QASPER` benchmark package for a `100`-question external retrieval set while keeping the repository's existing evaluation contract.

[繁體中文版本](README.zh-TW.md)

## Purpose

This package exists so another engineer can reproduce the same `QASPER 100` curation flow and inspect:

- the oversampled `50`-paper source scope used to build the package
- which questions survived the repository's `fact_lookup` curation rules
- which items were auto-aligned versus promoted through the `OpenAI` review step
- the exact `production_like_v1` reference run metrics

## What's Included

- `manifest.json`: benchmark identity, package stats, and reference evaluation profile
- `documents.jsonl`: the logical benchmark document list used by the final `100` questions
- `questions.jsonl`: the final `100` benchmark questions
- `gold_spans.jsonl`: `display_text`-aligned gold spans
- `alignment_candidates.jsonl`: alignment outcomes for the oversampled workspace
- `alignment_review_queue.jsonl`: the unresolved deterministic queue before LLM review
- `filter_report.json`: curation summary for the oversampled workspace
- `review_overrides.jsonl`: approved span overrides from the `OpenAI` review pass
- `openai_review_log.jsonl`: the `OpenAI` review evidence log
- `reference_run_summary.json`: the completed `production_like_v1` reference run summary
- `reproduce.md`: the step-by-step reproduction guide

## Reference Run

- Dataset: `qasper-curated-v1-100`
- Dataset ID: `e836874e-5183-5f09-8241-eddb155adab1`
- Area name used during creation: `qasper-100`
- Area ID: `204b0f87-bbbd-4549-ae3b-8064e535b453`
- Reference run ID: `6c4636ce-85da-456c-a8b3-059b4650b1ae`
- Evaluation profile: `production_like_v1`
- Item count: `100`
- Final document count: `42`
- Oversampled filtered item count: `132`
- Deterministic auto-matched count: `122`
- Approved `OpenAI` overrides: `2`

## Summary Metrics

| Stage | nDCG@10 | Recall@10 | MRR@10 | Precision@10 | Doc Coverage@10 |
| --- | ---: | ---: | ---: | ---: | ---: |
| recall | 0.1901 | 0.3600 | 0.1413 | 0.0390 | 0.7300 |
| rerank | 0.3533 | 0.5300 | 0.2983 | 0.0580 | 0.8300 |
| assembled | 0.3797 | 0.5900 | 0.3142 | 0.0640 | 0.8200 |

## Notes

- This package is not the original `QASPER` leaderboard split. It is a repository-specific `fact_lookup` benchmark anchored to system `display_text` offsets.
- The final package is the deterministic first `100` approved items from the oversampled workspace; approved items beyond that cutoff are intentionally excluded.
- The review contract remains strict: only exact quotes mapped back to offsets are allowed into `review_overrides.jsonl`.
