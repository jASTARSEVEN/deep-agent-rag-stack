# lcsts-news-summary-curated-pilot-v1

## Purpose

10 real LCSTS Chinese news summarization items extracted from the official test split.

## Provenance

- Upstream dataset: LCSTS official test split.
- Upstream source: Hugging Face dataset `suolyer/lcsts`.
- Extraction rule: take the first 10 test rows and strip the shared instruction prefix from `input`.
- Each item stores the zero-based row index as the stable key and keeps the raw LCSTS `id` in `source_mapping.original_id`.
