# qmsum-query-summary-curated-pilot-v1

## 用途

此 package 提供英文 query-conditioned summary 的小型 curated pilot，供雙語 summary/compare benchmark lane 使用。

## 內容

- `manifest.json`
- `questions.jsonl`
- `source_documents/`
- `reference_run_summary.json`

## 備註

- retrieval scope 採 `explicit_document_ids`，但 repo 內先以 `document_file_names` 表示，執行 benchmark 時再解析成實際 area `document_id`。
