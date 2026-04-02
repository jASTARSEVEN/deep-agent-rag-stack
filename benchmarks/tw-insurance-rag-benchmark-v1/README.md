# tw-insurance-rag-benchmark-v1

Public-facing benchmark package for reproducing the retrieval evaluation results reported by this repository.

[繁體中文版本](README.zh-TW.md)

## Purpose

This package exists so external readers can inspect the benchmark inputs, rebuild the evaluation dataset, and rerun the retrieval benchmark instead of trusting only the summary metrics shown in the project root README.

## Contents

- `manifest.json`: snapshot identity, commit, migration version, source-document checksums, and reference run metadata
- `source_documents/`: packaged benchmark source files
- `parser_artifacts/`: parser-stage artifacts copied from object storage
- `parser_artifacts_manifest.jsonl`: parser artifact inventory with checksums
- `documents.jsonl`: benchmark document metadata
- `document_display_text.jsonl`: full `display_text` snapshots for offset verification
- `document_chunks.jsonl`: parent/child chunk snapshots for chunk-level inspection
- `questions.jsonl`: evaluation questions
- `gold_spans.jsonl`: evidence spans aligned to `display_text` offsets
- `per_query.jsonl`: per-question evaluation results for the reference run
- `runs.jsonl`: exported run summaries
- `reference_run_report.json`: full report payload for the reference run
- `dataset_card.md`: dataset scope, field definitions, and limitations
- `reproduce.md`: reproduction workflow

## How to Reproduce

1. Start the project stack and run migrations.
2. Upload the four benchmark source documents and wait until they are `ready`.
3. Run the reproduction script:
   - `AREA_ID=<target-area-id> ./scripts/reproduce_benchmark.sh`
4. Inspect the generated outputs:
   - `benchmarks/tw-insurance-rag-benchmark-v1/reproduced_run_report.json`
   - `benchmarks/tw-insurance-rag-benchmark-v1/reproduced_compare_report.json`
5. If you need manual control, the equivalent commands are documented in `reproduce.md`.

## Public Release Notes

This package now includes the four original PDF/XLSX source files under `source_documents/`, together with parser-stage artifacts and the database-backed snapshot artifacts needed for chunk and offset inspection.

## Troubleshooting

- If import fails with missing documents, verify that the target area already contains the four source files and that all of them are in `ready` status.
- If span offsets do not match, confirm that the source files and parser path match the versions recorded in `manifest.json`.
- If rerun metrics drift, inspect `per_query.jsonl` before concluding that the benchmark is invalid; parser, rerank model, or chunking changes can affect a small subset of queries first.
