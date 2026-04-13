# Reproduce

## English

1. Download `data/anno.json` from the official CoCoSum repository.
2. Read the `test` split and take the first 10 entries in order.
3. Render `entity_a_summary` and `entity_b_summary` into the two source documents for each item.
4. Use `source_record_index`, `entity_a_id`, and `entity_b_id` to verify the original annotation entry.

## 繁體中文

1. 從官方 CoCoSum repo 下載 `data/anno.json`。
2. 讀取 `test` split，依順序取前 `10` 筆。
3. 把每筆的 `entity_a_summary` 與 `entity_b_summary` 分別寫成兩份 source documents。
4. 透過 `source_record_index`、`entity_a_id`、`entity_b_id` 回查原始標註。
