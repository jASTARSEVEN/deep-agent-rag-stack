# Reproduce

## English

1. Download `data/test-00000-of-00001.parquet` from `ethanhao2077/cnewsum-processed`.
2. Read the parquet in original order and keep the first 10 rows.
3. Write each `article` into a source document and keep the paired `summary` as `reference_answer`.
4. Use `source_example_id` and `source_record_index` to verify the original row.

## 繁體中文

1. 從 `ethanhao2077/cnewsum-processed` 下載 `data/test-00000-of-00001.parquet`。
2. 依原始順序讀取 parquet，保留前 `10` 筆。
3. 把每筆 `article` 寫成 source document，並把配對的 `summary` 保留成 `reference_answer`。
4. 透過 `source_example_id` 與 `source_record_index` 回查原始 row。
