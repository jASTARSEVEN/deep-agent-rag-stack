# Benchmark 重現指南

## 目的

此文件說明如何從原始專案與 benchmark snapshot 重新建置環境、匯入資料並重跑 benchmark。  
目標不是只讓外部讀者看到 summary metrics，而是能實際驗證本專案的 retrieval pipeline 是否可在相同條件下重現接近結果。

## 先備條件

- 已取得本 repository 對應 commit
- 已取得 benchmark package：
  - `source_documents/`
  - `parser_artifacts/`
  - `parser_artifacts_manifest.jsonl`
  - `documents.jsonl`
  - `document_display_text.jsonl`
  - `document_chunks.jsonl`
  - `questions.jsonl`
  - `gold_spans.jsonl`
  - `per_query.jsonl`
  - `runs.jsonl`
  - `manifest.json`
  - 原始 4 份文件
- 本機已安裝 Docker 與 Docker Compose
- 若使用預設 PDF parser provider `opendataloader`，執行 worker 的主機需具備 `Java 11+`

## 一鍵重現流程

在文件已上傳且進入 `ready` 後，可直接執行：

- `AREA_ID=<target-area-id> ./scripts/reproduce_benchmark.sh`

此腳本會依序執行：

1. 匯入 snapshot 到指定 area
2. 以 `production_like_v1` 重跑 benchmark
3. 輸出 `reproduced_run_report.json`
4. 使用 compare CLI 將新 run 與 `reference_run_report.json` 做差異比對
5. 輸出 `reproduced_compare_report.json`

可透過環境變數覆寫：

- `SNAPSHOT_DIR`
- `DATASET_NAME`
- `ACTOR_SUB`
- `TOP_K`
- `EVALUATION_PROFILE`
- `REPORT_OUTPUT_PATH`
- `COMPARE_OUTPUT_PATH`

## 手動重現流程

1. 檢出 `manifest.json` 指定的 git commit。
2. 依專案根目錄說明建立 `.env`，並確認 `DATABASE_URL`、`REDIS_URL`、`MINIO_*`、`OPENAI_*`、`COHERE_*` 可用。
3. 啟動基礎服務：
   - `./scripts/compose.sh up --build`
4. 執行 migration：
   - `./scripts/compose.sh exec api python -m app.db.migration_runner`
5. 確認資料庫 schema 與 `manifest.json` 中的 `alembic_version` 一致。
6. 於對應 area 上傳 4 份原始文件，等待文件狀態進入 `ready`。
7. 使用匯入腳本建立 evaluation dataset：
   - `PYTHONPATH=apps/api/src python -m app.scripts.import_benchmark_snapshot --snapshot-dir benchmarks/tw-insurance-rag-benchmark-v1 --area-id <target-area-id> --dataset-name tw-insurance-rag-benchmark-v1`
8. 執行 benchmark run：
   - `PYTHONPATH=apps/api/src python -m app.scripts.run_retrieval_eval run --dataset-id bb10c343-7d7c-4ae3-b78b-a513759867f2 --top-k 10 --evaluation-profile production_like_v1`
9. 產出 compare report：
   - `PYTHONPATH=apps/api/src python -m app.scripts.compare_benchmark_runs --reference-report benchmarks/tw-insurance-rag-benchmark-v1/reference_run_report.json --candidate-run-id <new-run-id>`
10. 若 summary 接近但單題有差異，再用 compare report 與 `per_query.jsonl` 檢查差異題目。

若需要從自己的資料庫重新匯出同格式 package，可使用：

- `PYTHONPATH=apps/api/src python -m app.scripts.export_benchmark_snapshot --dataset-id bb10c343-7d7c-4ae3-b78b-a513759867f2 --output-dir /tmp/tw-insurance-rag-benchmark-v1 --benchmark-name tw-insurance-rag-benchmark-v1`

## 建議比對順序

若外部審查者要判定結果是否可信，建議按以下順序比對：

1. `manifest.json`
   - commit SHA
   - `alembic_version`
   - parser / embedding / rerank provider
   - `config_snapshot`
2. `documents.jsonl`
   - 原始檔名、檔案大小、SHA-256 是否一致
3. `questions.jsonl`
   - 題數與題目文字是否一致
4. `gold_spans.jsonl`
   - 主要 evidence span 是否能對回相同文件與相近文字
5. `runs.jsonl`
   - summary metrics 是否在可接受偏差內
6. `per_query.jsonl`
   - 差異是否集中在少數題目

## 可能導致無法精確重現的因素

- PDF / XLSX parser 版本不同
- OpenDataLoader / Unstructured 行為更新
- embedding model 或 rerank model 版本改變
- chunking guardrails 變更
- source documents 不是完全相同檔案
- area / document 匯入順序造成 document id 不同

## 若要更高精度重現

若需要更接近「資料庫中的既有 snapshot」，建議額外公開：

- `documents.display_text`
- `document_chunks`
- parser artifacts
- benchmark import/export script

## 目前已提供的重現工具

- `python -m app.scripts.import_benchmark_snapshot`
- `python -m app.scripts.export_benchmark_snapshot`
- `python -m app.scripts.compare_benchmark_runs`
- `./scripts/reproduce_benchmark.sh`
