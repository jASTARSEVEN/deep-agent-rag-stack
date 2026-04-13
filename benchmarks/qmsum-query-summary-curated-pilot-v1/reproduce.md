# Reproduce

## English

1. Download the official `test.jsonl` from the Yale-LILY QMSum repository.
2. Parse each meeting row and keep the first 10 `specific_query_list` entries in original order.
3. Render the corresponding `meeting_transcripts` into `source_documents/qmsum-meeting-XX.md`.
4. Use the stored `source_record_index` and `source_mapping.query_index` to verify each question against the raw JSONL.

## 繁體中文

1. 從 Yale-LILY 官方 QMSum repo 下載 `test.jsonl`。
2. 逐筆解析 meeting row，依原始順序保留前 `10` 個 `specific_query_list` 題目。
3. 把對應的 `meeting_transcripts` 轉成 `source_documents/qmsum-meeting-XX.md`。
4. 透過每題保存的 `source_record_index` 與 `source_mapping.query_index` 回查原始 JSONL。
