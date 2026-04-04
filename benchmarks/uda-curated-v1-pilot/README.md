# uda-curated-v1-pilot

This directory is a reproducible pilot benchmark package that maps an official `UDA-Benchmark` sample subset onto the repository's existing retrieval evaluation contract.

[繁體中文版本](README.zh-TW.md)

## Purpose

This package exists to let another engineer reproduce the same pilot benchmark flow and inspect:

- which official `UDA-Benchmark` sample questions survived the current `fact_lookup` curation rules
- how many items could be auto-aligned to system `display_text`
- how many additional items were promoted through an `OpenAI API` review pass
- the reference run metrics for the expanded `26`-item pilot

## What's Included

- `manifest.json`: benchmark identity and dataset stats
- `documents.jsonl`: the logical benchmark document list
- `questions.jsonl`: the curated pilot questions
- `gold_spans.jsonl`: gold spans aligned to system `display_text` offsets
- `alignment_candidates.jsonl`: raw alignment outcomes before manual review
- `alignment_review_queue.jsonl`: items that could not be auto-approved
- `filter_report.json`: item filtering summary
- `review_overrides.jsonl`: manually approved span overrides used to build the final snapshot
- `reference_run_summary.json`: the completed reference run id, config snapshot, and summary metrics
- `review_overrides.jsonl`: final approved span overrides used to build the snapshot
- `openai_review_log.jsonl`: the `OpenAI API` review log for the LLM-reviewed subset
- `bge_core_profiles_summary.json`: apples-to-apples BGE assembled metrics for the four current-head profiles
- `reproduce.md`: step-by-step reproduction guide

## Reference Run

- Dataset: `uda-curated-v1-pilot`
- Dataset ID: `3d779672-b561-5d64-aa76-035d37d4e0b4`
- Area name used during creation: `uda-pilot`
- Area ID: `58afaf23-423d-4526-b90d-43ea19711eaf`
- Reference run ID: `593638b8-a3c7-4471-ba56-7d242a8e65fa`
- Evaluation profile: `production_like_v1`
- Item count: `26`
- Auto-matched ratio during curation: `0.346154`
- `OpenAI` review approvals: `21`
- Final override count: `25`

## Summary Metrics

| Stage | nDCG@10 | Recall@10 | MRR@10 | Precision@10 | Doc Coverage@10 |
| --- | ---: | ---: | ---: | ---: | ---: |
| recall | 0.3127 | 0.5000 | 0.2483 | 0.0577 | 0.7308 |
| rerank | 0.7353 | 0.8462 | 0.7083 | 0.0885 | 0.9615 |
| assembled | 0.5288 | 0.6538 | 0.4968 | 0.0692 | 0.9615 |

## BGE Core Profiles

| Profile | Recall@10 | nDCG@10 | MRR@10 |
| --- | ---: | ---: | ---: |
| `production_like_v1` | 0.6538 | 0.5288 | 0.4968 |
| `qasper_guarded_assembler_v2_bge` | 0.6538 | 0.5288 | 0.4968 |
| `qasper_guarded_evidence_synopsis_v2_bge` | 0.6538 | 0.5264 | 0.4936 |
| `qasper_guarded_evidence_synopsis_v3_bge` | 0.6538 | 0.5288 | 0.4968 |

## Notes

- This is a pilot benchmark derived from official `UDA-Benchmark` sample artifacts, not the full `UDA-QA` leaderboard setup.
- The source scope is intentionally limited to `extended_qa_info_bench` plus `src_doc_files_example` from the official repository.
- `JKHY_2015` is ingested as an extracted markdown file (`JKHY_2015.md`) so the pilot can stay within the repository's upload-size constraints while preserving the same question source.
- The final `26` questions come from three lanes:
  - `9` auto-matched items
  - `21` `OpenAI API` review approvals
  - `4` additional deterministic span overrides on top of the LLM pass
- On the refreshed `26`-item dataset, `assembler_v2` and `qasper_v3` tie the baseline on UDA nDCG@10, while `generic_v1` is slightly lower.
