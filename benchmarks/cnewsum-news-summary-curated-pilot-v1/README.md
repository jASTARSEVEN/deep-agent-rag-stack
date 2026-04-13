# cnewsum-news-summary-curated-pilot-v1

## Purpose

10 real CNewSum news summarization items extracted from the processed test split.

## Provenance

- Upstream dataset: CNewSum processed test split.
- Upstream source: Hugging Face dataset `ethanhao2077/cnewsum-processed`.
- Extraction rule: take the first 10 rows from `data/test-00000-of-00001.parquet`.
- Each item stores the original dataset `id`, zero-based row index, and processed `label`.
