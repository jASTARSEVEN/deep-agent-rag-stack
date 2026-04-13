# Reproduce

## English

1. Load `suolyer/lcsts` from Hugging Face.
2. Read the official `test` split and keep the first 10 rows.
3. Remove the instruction prefix from `input` before writing the source document.
4. Use `source_example_id` and `source_record_index` as the stable lookup key, then verify the raw LCSTS id via `source_mapping.original_id`.

## 繁體中文

1. 從 Hugging Face 載入 `suolyer/lcsts`。
2. 讀取官方 `test` split，保留前 `10` 筆。
3. 寫 source document 前先移除 `input` 的 instruction 前綴。
4. 透過 `source_example_id` 與 `source_record_index` 回查每筆提取結果，原始 LCSTS `id` 則用 `source_mapping.original_id` 驗證。
