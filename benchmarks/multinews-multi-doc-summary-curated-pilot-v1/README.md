# multinews-multi-doc-summary-curated-pilot-v1

## Purpose

10 real Multi-News items extracted from the official test set.

## Provenance

- Upstream dataset: Multi-News official test split.
- Upstream files: `data/test.src.cleaned` and `data/test.tgt` from the dataset repo.
- Extraction rule: preserve original line order and take the first 10 rows.
- Each item stores the original line index in `source_record_index`.
