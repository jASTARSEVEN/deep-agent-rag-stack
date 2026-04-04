# uda-curated-v1-100

This directory is a reproducible `UDA` benchmark package built from the official full-source `nq` subset and aligned to the repository's existing retrieval evaluation contract.

[繁體中文版本](README.zh-TW.md)

## Purpose

This package exists so another engineer can reproduce the same `UDA 100` curation flow and inspect:

- how the official `UDA` `nq` subset was normalized through the repository's helper CLI
- which questions survived the current `fact_lookup` curation rules
- how many items were approved through deterministic alignment alone
- the exact `qasper_guarded_query_focus_v1` reference run metrics

## What's Included

- `manifest.json`: benchmark identity, package stats, and reference evaluation profile
- `documents.jsonl`: the logical benchmark document list used by the final `100` questions
- `questions.jsonl`: the final `100` benchmark questions
- `gold_spans.jsonl`: `display_text`-aligned gold spans
- `alignment_candidates.jsonl`: deterministic alignment outcomes for the oversampled workspace
- `alignment_review_queue.jsonl`: the unresolved queue before optional review
- `filter_report.json`: curation summary for the oversampled workspace
- `reference_run_summary.json`: the completed `qasper_guarded_query_focus_v1` reference run summary
- `reproduce.md`: the step-by-step reproduction guide

## Reference Run

- Dataset: `uda-curated-v1-100`
- Dataset ID: `3cca653e-ffd5-5ab8-8464-27aaac194bb4`
- Area name used during creation: `uda-100`
- Area ID: `2edabc25-1a54-43ab-b987-efd4e040114f`
- Reference run ID: `0274c530-8171-4f0f-bd86-bce82c15f5d7`
- Evaluation profile: `qasper_guarded_query_focus_v1`
- Item count: `100`
- Final document count: `45`
- Oversampled filtered item count: `140`
- Deterministic auto-matched count: `102`
- Approved `OpenAI` overrides: `0`

## Summary Metrics

| Stage | nDCG@10 | Recall@10 | MRR@10 | Precision@10 | Doc Coverage@10 |
| --- | ---: | ---: | ---: | ---: | ---: |
| recall | 0.4544 | 0.6500 | 0.3956 | 0.0660 | 1.0000 |
| rerank | 0.6802 | 0.8200 | 0.6347 | 0.0820 | 1.0000 |
| assembled | 0.6816 | 0.8300 | 0.6336 | 0.0830 | 1.0000 |

## Notes

- This package uses the official `UDA-QA` `wiki_nq_docs` source zip plus the official `bench_nq_qa.json` benchmark annotations.
- No LLM review was needed for the final package because the oversampled workspace already yielded `102` deterministic approvals.
- The final package is the deterministic first `100` approved items from the oversampled workspace.
