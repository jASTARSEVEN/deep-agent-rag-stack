# cocotrip-compare-curated-pilot-v1

## Purpose

10 real CoCoTrip-derived compare items extracted from the official annotation file.

## Provenance

- Upstream dataset: CoCoTrip annotations from the official CoCoSum repository.
- Upstream file: `data/anno.json`.
- Extraction rule: preserve original `test` order and take the first 10 entries.
- Each item stores the original test index plus `entity_a_id` and `entity_b_id`.
