# tw-insurance-rag-benchmark-v1

## 文件定位

此文件描述 `tw-insurance-rag-benchmark-v1` 的資料內容、欄位定義、評估用途與目前限制。  
此 benchmark 的正式準據是從專案資料庫匯出的 evaluation dataset snapshot，而不是人工整理的外部試算表。

## Benchmark 目的

本 benchmark 用於驗證本專案 retrieval pipeline 在以下三個階段的正確性：

- `recall`
- `rerank`
- `assembled`

它特別用來檢查：

- 是否能命中正確文件與核心證據
- `Parent_Chunk_ID` / `Child_Chunk_ID` 對應的 assembled context 是否仍保有可引用證據
- citation grounding 是否能對回 `display_text` offsets

## Snapshot 身分

- benchmark 名稱：`tw-insurance-rag-benchmark-v1`
- dataset id：`bb10c343-7d7c-4ae3-b78b-a513759867f2`
- dataset name：`tw-insurance-rag-benchmark-v1`
- area id：`d62d8a2d-22f4-416f-958f-2a15ebdad426`
- area name：`我的第一個知識區域`
- query type：`fact_lookup`
- language：`zh-TW`
- snapshot 匯出來源：專案資料庫 `retrieval_eval_*` 與 `documents`

## 來源文件

本 benchmark 目前使用 4 份文件：

1. `個人保險保單服務暨契約變更手冊(114年9月版).pdf`
2. `理賠審核原則.xlsx`
3. `新契約個人保險投保規則手冊-核保及行政篇(114年9月版).pdf`
4. `新契約個人保險投保規則手冊-商品篇(114年9月版).pdf`

目前原始文件已直接打包於 `source_documents/`。  
外部重建 ingest 時應優先使用此目錄下的檔案，而不是依賴其他工作區副本。

## 資料規模

- 文件數：`4`
- 題目數：`30`
- gold spans：`30`
- retrieval miss：`0`
- ready 文件數：`4`

文件題數分布：

- `理賠審核原則.xlsx`：`10`
- `個人保險保單服務暨契約變更手冊(114年9月版).pdf`：`8`
- `新契約個人保險投保規則手冊-商品篇(114年9月版).pdf`：`6`
- `新契約個人保險投保規則手冊-核保及行政篇(114年9月版).pdf`：`6`

## 檔案說明

### `documents.jsonl`

每行一份文件，欄位如下：

- `document_id`：資料庫中的文件識別碼
- `file_name`：原始檔名
- `content_type`：上傳時記錄的 MIME type
- `file_size`：原始檔大小，單位為 bytes
- `status`：文件狀態；本 snapshot 均為 `ready`
- `created_at`：文件建立時間
- `area_id`：文件所屬 area

### `document_display_text.jsonl`

每行一份文件的全文顯示文字 snapshot，欄位如下：

- `document_id`
- `file_name`
- `display_text`
- `display_text_length`
- `normalized_text_length`

此檔用於讓外部讀者驗證 `gold_spans.jsonl` 中的 offsets 是否能正確對回文字內容。

### `document_chunks.jsonl`

每行一個 parent 或 child chunk，欄位如下：

- `chunk_id`
- `document_id`
- `parent_chunk_id`
- `chunk_type`
- `structure_kind`
- `position`
- `section_index`
- `child_index`
- `heading`
- `char_count`
- `start_offset`
- `end_offset`
- `content_preview`
- `content`

此檔用於讓外部讀者檢查 chunk tree、表格切分與 assembled context 所依據的 chunk 邊界。

### `parser_artifacts/` 與 `parser_artifacts_manifest.jsonl`

`parser_artifacts/` 目錄直接保存 benchmark 文件的 parser 中間產物；  
`parser_artifacts_manifest.jsonl` 則記錄每個 artifact 的對應文件、provider、檔名、路徑、大小與 SHA-256。

目前包含：

- `opendataloader.json`
- `opendataloader.cleaned.md`
- `xlsx.extracted.html`

此層用於讓外部讀者區分問題到底出在：

- 原始文件
- parser 輸出
- `display_text`
- chunking / assembler

### `questions.jsonl`

每行一題 evaluation item，欄位如下：

- `question_id`：題目識別碼
- `dataset_id`：所屬 dataset
- `query_type`：目前固定為 `fact_lookup`
- `language`：目前固定為 `zh_tw`
- `question`：題目文字
- `notes`：可選補充說明
- `created_at`：建立時間
- `updated_at`：最後更新時間

### `gold_spans.jsonl`

每行一筆 gold evidence span，欄位如下：

- `span_id`：span 識別碼
- `question_id`：對應題目識別碼
- `document_id`：對應文件識別碼
- `file_name`：對應文件檔名
- `start_offset`：在 `documents.display_text` 中的起始 offset
- `end_offset`：在 `documents.display_text` 中的結束 offset
- `relevance_grade`：相關性等級；目前主要使用 `3`
- `is_retrieval_miss`：是否為 retrieval miss
- `span_text`：依 offset 從資料庫 `display_text` 擷取的證據文字
- `created_at`：建立時間
- `updated_at`：最後更新時間

### `per_query.jsonl`

每行為單一題目的完整 benchmark 結果，欄位如下：

- `item_id`
- `query_text`
- `language`
- `retrieval_miss`
- `gold_spans`
- `recall`
- `rerank`
- `assembled`
- `baseline_delta`

此檔用於外部審查單題表現，避免只看 summary metrics。

### `runs.jsonl`

每行為單次 benchmark run，欄位如下：

- `run_id`
- `dataset_id`
- `dataset_name`
- `area_id`
- `evaluation_profile`
- `status`
- `total_items`
- `config_snapshot`
- `summary_metrics`
- `created_at`
- `completed_at`

### `reference_run_report.json`

這是 reference run 的完整報表快照，欄位如下：

- `run`
- `dataset`
- `summary_metrics`
- `breakdowns`
- `per_query`
- `baseline_compare`

此檔用於保留完整 run artifact，避免資料庫中的 run records 被刪除後，只剩下 summary 與逐題片段。

## 目前公開的基準結果

主要對外引用的 run：

- run id：`e2b12fa7-894f-4b94-8069-3ad4c11e44d8`
- evaluation profile：`production_like_v1`
- total items：`30`
- completed at：`2026-04-01T12:47:03.349267+00:00`

摘要結果：

- `recall`：`nDCG@k=0.602`、`Recall@k=0.867`、`MRR@k=0.526`
- `rerank`：`nDCG@k=0.813`、`Recall@k=0.867`、`MRR@k=0.794`
- `assembled`：`nDCG@k=0.813`、`Recall@k=0.867`、`MRR@k=0.794`

## 已知限制

- 此 benchmark 目前只覆蓋 `zh-TW` 與 `fact_lookup`
- `span_text` 來自當前資料庫中的 `display_text`；若 parser provider 或 chunking 邏輯改變，重建後的 offsets 可能不同
- 本 snapshot 沒有直接附上 `document_chunks`、parser artifacts 與 `display_text` 全文；若要追求更高精度重現，建議後續補充

## 發佈建議

正式對外發佈時，建議至少包含：

- 本目錄全部 `jsonl`
- `source_documents/`
- `parser_artifacts/`
- `manifest.json`
- 本文件
- `reproduce.md`
