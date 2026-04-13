# qmsum-query-summary-curated-pilot-v1

## 用途

從 QMSum 官方 test split 提取的 `10` 題 query-conditioned summary 真實資料 package。

## 資料來源與還原依據

- 上游資料集：QMSum 官方 test split。
- 上游檔案：Yale-LILY 官方 repo 的 `data/ALL/jsonl/test.jsonl`。
- 抽取規則：依原始會議順序，從 `specific_query_list` 取前 `10` 題。
- 每題都保存 `source_record_index`、`source_example_id` 與 `source_mapping.query_index`，可直接回對原始 row。
