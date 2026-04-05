# msmarco-curated-v1-100

This directory is a reproducible `MS MARCO` benchmark package that maps the official QA validation split into the repository's existing retrieval benchmark contract.

[繁體中文版本](README.zh-TW.md)

## Purpose

This package exists so another engineer can reproduce the same `MS MARCO 100` curation flow and inspect:

- how the official `MS MARCO v1.1` validation rows were normalized into snippet-bundle documents
- how many questions survived the repository's `fact_lookup` curation rules
- how many gold spans were auto-aligned versus recovered through the `OpenAI` review step
- the exact `production_like_v1` reference run metrics under the current shared rerun baseline

## What's Included

- `manifest.json`: benchmark identity, package stats, and reference evaluation profile
- `documents.jsonl`: the logical benchmark document list used by the final `100` questions
- `questions.jsonl`: the final `100` benchmark questions
- `gold_spans.jsonl`: `display_text`-aligned gold spans
- `alignment_candidates.jsonl`: deterministic alignment outcomes for the oversampled workspace
- `alignment_review_queue.jsonl`: the unresolved queue before `OpenAI` review
- `filter_report.json`: curation summary for the oversampled workspace
- `review_overrides.jsonl`: approved span overrides from the `OpenAI` review pass
- `openai_review_log.jsonl`: the `OpenAI` review evidence log
- `reference_run_summary.json`: the completed `production_like_v1` reference run summary
- `reproduce.md`: the step-by-step reproduction guide

## Reference Run

- Dataset: `msmarco-curated-v1-100`
- Dataset ID: `4669417e-6276-54ae-89b3-95fcb7652096`
- Area name used during creation: `msmarco-100`
- Area ID: `4a7a8c05-4aa2-403f-b101-d24ff28d1308`
- Reference run ID: `5e9de20b-4781-4711-a69e-03157e61d68a`
- Evaluation profile: `production_like_v1`
- Item count: `100`
- Final document count: `100`
- Oversampled prepared item count: `180`
- Oversampled filtered item count: `154`
- Deterministic auto-matched count: `103`
- Approved `OpenAI` overrides: `47`
- Review-approved items included in the final `100`: `33`

## Summary Metrics

| Stage | nDCG@10 | Recall@10 | MRR@10 | Precision@10 | Doc Coverage@10 |
| --- | ---: | ---: | ---: | ---: | ---: |
| recall | 0.7825 | 0.9900 | 0.7092 | 0.1110 | 1.0000 |
| rerank | 0.9674 | 1.0000 | 0.9550 | 0.1050 | 1.0000 |
| assembled | 0.9674 | 1.0000 | 0.9550 | 0.1050 | 1.0000 |

## Notes

- This package is built from the official `MS MARCO v1.1` validation QA rows, but the repository materializes each selected row into a standalone snippet-bundle document rather than attempting to reconstruct full source websites.
- The curation strategy intentionally aligns answer strings first, then lets `OpenAI` recover exact quotes only for ambiguous rows, so `gold_spans.jsonl` still contains verbatim evidence offsets instead of paraphrased answers.
- The final package keeps the deterministic first `100` approved items after review; approved items beyond that cutoff are intentionally excluded.
