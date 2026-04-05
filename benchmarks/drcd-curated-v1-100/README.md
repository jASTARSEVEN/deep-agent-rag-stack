# drcd-curated-v1-100

This directory is a reproducible `DRCD` benchmark package that maps the official Traditional Chinese reading-comprehension dataset into the repository's retrieval evaluation contract.

[繁體中文版本](README.zh-TW.md)

## Purpose

This package exists so another engineer can reproduce the same `DRCD 100` curation flow and inspect:

- how the official `voidful/DRCD` `dev` split was normalized into repository-local markdown source documents
- which questions survived the repository's `fact_lookup` curation rules
- how many items were aligned deterministically versus sent to the `OpenAI` review queue
- the exact `production_like_v1` reference run metrics under the current shared baseline

## What's Included

- `manifest.json`: benchmark identity, package stats, and reference evaluation profile
- `documents.jsonl`: the logical benchmark document list used by the final `100` questions
- `questions.jsonl`: the final `100` benchmark questions
- `gold_spans.jsonl`: `display_text`-aligned gold spans
- `alignment_candidates.jsonl`: deterministic alignment outcomes for the oversampled workspace
- `alignment_review_queue.jsonl`: the unresolved queue before optional `OpenAI` review
- `filter_report.json`: curation summary for the oversampled workspace
- `review_overrides.jsonl`: approved span overrides from the `OpenAI` review pass
- `openai_review_log.jsonl`: the `OpenAI` review evidence log
- `reference_run_summary.json`: the completed `production_like_v1` reference run summary
- `reproduce.md`: the step-by-step reproduction guide

## Reference Run

- Dataset: `drcd-curated-v1-100`
- Dataset ID: `e82455ac-45fc-501e-a13d-333552c4a2ab`
- Area name used during creation: `drcd-100`
- Area ID: `eb3d79be-220a-4658-9ecd-76ccaaf334f8`
- Reference run ID: `400921aa-3882-4504-8f3c-accf9054930e`
- Evaluation profile: `production_like_v1`
- Item count: `100`
- Final document count: `6`
- Oversampled prepared item count: `400`
- Oversampled filtered item count: `400`
- Deterministic auto-matched count: `400`
- Review queue item count: `0`
- Approved `OpenAI` overrides: `0`

## Summary Metrics

| Stage | nDCG@10 | Recall@10 | MRR@10 | Precision@10 | Doc Coverage@10 |
| --- | ---: | ---: | ---: | ---: | ---: |
| recall | 0.9543 | 0.9900 | 0.9420 | 0.0990 | 1.0000 |
| rerank | 0.8650 | 0.9700 | 0.8308 | 0.0970 | 1.0000 |
| assembled | 0.8650 | 0.9700 | 0.8308 | 0.0970 | 1.0000 |

## Notes

- This package is built from `hf://voidful/DRCD/default/dev` and keeps Traditional Chinese source text instead of converting it to simplified Chinese or a retrieval-only surrogate format.
- The final package keeps the deterministic first `100` approved items from the oversampled workspace; because `alignment_review_queue` was empty, the `OpenAI` review pass ran as a no-op and produced empty log / override files.
- `DRCD 100` behaves as a high-signal Chinese lexical retrieval check in the current stack: recall is near ceiling, while rerank slightly degrades ordering.
