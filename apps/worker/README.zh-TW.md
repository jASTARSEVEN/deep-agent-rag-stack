# Worker 模組

[English README](README.md)

## 模組目的

此模組包含專案的 Celery worker。它目前提供最小 ingest 任務、文件狀態轉換與 parser routing 骨架，並保留後續 indexing 擴充空間。

## 啟動方式

- 本機 Python 執行：
  - `python -m venv .venv && source .venv/bin/activate`
  - `pip install -e .[dev]`
  - 若要使用 `PDF_PARSER_PROVIDER=marker`，請改用獨立 worker virtualenv 安裝 Marker：
    Bash：`uv venv ../../.worker-venv --python 3.12 && uv pip install --python ../../.worker-venv/bin/python -e .[dev] "marker-pdf>=1.9.2,<2.0.0"`
    PowerShell：`uv venv ../../.worker-venv --python 3.12; uv pip install --python ..\..\.worker-venv\Scripts\python.exe -e ".[dev]" "marker-pdf>=1.9.2,<2.0.0"`
  - 若從 repo 根目錄使用 Windows PowerShell，建議直接執行：
    安裝：`.\scripts\install-worker-marker.ps1`
    GPU 安裝：`.\scripts\install-worker-marker-gpu.ps1`
    啟動：`.\scripts\start-worker-marker.ps1`（會先啟動 Compose 依賴服務，再啟動本機 Marker worker）
  - `celery -A worker.celery_app.celery_app worker --loglevel=INFO`
- 本機健康檢查命令：
  - `python -m worker.scripts.healthcheck`
- Docker Compose：
  - `docker compose -f ../../infra/docker-compose.yml --env-file ../../.env up worker`

## 環境變數

- `WORKER_SERVICE_NAME`
- `DATABASE_URL`
- `CELERY_BROKER_URL`
- `CELERY_RESULT_BACKEND`
- `CELERY_WORKER_POOL`
- `CELERY_WORKER_CONCURRENCY`
- `CELERY_WORKER_PREFETCH_MULTIPLIER`
- `CELERY_WORKER_MAX_TASKS_PER_CHILD`
- `CELERY_TASK_ACKS_LATE`
- `CELERY_TASK_REJECT_ON_WORKER_LOST`
- `STORAGE_BACKEND`
- `MINIO_ENDPOINT`
- `MINIO_ACCESS_KEY`
- `MINIO_SECRET_KEY`
- `MINIO_SECURE`
- `MINIO_BUCKET`
- `LOCAL_STORAGE_PATH`
- `PDF_PARSER_PROVIDER`
- `MARKER_MODEL_CACHE_DIR`
- `MARKER_FORCE_OCR`
- `MARKER_STRIP_EXISTING_OCR`
- `MARKER_USE_LLM`
- `MARKER_LLM_SERVICE`
- `MARKER_OPENAI_API_KEY`
- `MARKER_OPENAI_MODEL`
- `MARKER_OPENAI_BASE_URL`
- `MARKER_DISABLE_IMAGE_EXTRACTION`
- `LLAMAPARSE_API_KEY`
- `LLAMAPARSE_DO_NOT_CACHE`
- `LLAMAPARSE_MERGE_CONTINUED_TABLES`
- `CHUNK_MIN_PARENT_SECTION_LENGTH`
- `CHUNK_TARGET_CHILD_SIZE`
- `CHUNK_CHILD_OVERLAP`
- `CHUNK_CONTENT_PREVIEW_LENGTH`
- `CHUNK_TXT_PARENT_GROUP_SIZE`
- `CHUNK_TABLE_PRESERVE_MAX_CHARS`
- `CHUNK_TABLE_MAX_ROWS_PER_CHILD`
- `EMBEDDING_PROVIDER`
- `EMBEDDING_MODEL`
- `EMBEDDING_MAX_BATCH_TEXTS`
- `EMBEDDING_RETRY_MAX_ATTEMPTS`
- `EMBEDDING_RETRY_BASE_DELAY_SECONDS`
- `EMBEDDING_DIMENSIONS`
- `OPENAI_API_KEY`

## 主要目錄結構

- `src/worker/celery_app.py`：Celery 應用程式進入點
- `src/worker/tasks`：health、ingest 與 indexing task 模組
- `src/worker/core`：worker 設定與共用輔助元件
- `src/worker/db.py`：worker 使用的最小 DB model 與 session helper
- `src/worker/storage.py`：物件儲存讀取抽象
- `src/worker/parsers.py`：最小 parser router
- `src/worker/scripts`：給操作人員使用的輔助腳本

## 對外介面

- Celery task：`worker.tasks.health.ping`
- Celery task：`worker.tasks.ingest.process_document_ingest`
- 健康檢查腳本：`python -m worker.scripts.healthcheck`

## 疑難排解

- 若 worker 無法連到 Redis，請確認 `CELERY_BROKER_URL`。
- 若 `marker` PDF ingest 在 Celery log 中出現 `Worker exited prematurely: signal 9 (SIGKILL)`，通常代表 prefork 子程序在重型 PDF runtime 期間被系統 OOM killer 終止；compose 預設已改為 `CELERY_WORKER_POOL=solo`、`CELERY_WORKER_CONCURRENCY=1`、`CELERY_WORKER_PREFETCH_MULTIPLIER=1`、`CELERY_WORKER_MAX_TASKS_PER_CHILD=1`，並搭配 `CELERY_TASK_ACKS_LATE=true`，讓 worker 同時間只會保有一個尚未完成的案件。
- `CELERY_TASK_REJECT_ON_WORKER_LOST=true` 會在 worker 行程異常中止時把尚未完成的案件退回 queue，避免案件在「尚未做完但已被視為接收」的狀態下遺失。
- 若 ingest task 無法更新資料庫，請確認 `DATABASE_URL` 指向與 API 相同的資料庫。
- 若正式環境無法讀取文件內容，請確認 `MINIO_*` 與 `MINIO_BUCKET` 一致。
- 若沒有 task 被註冊，請確認 `worker.tasks` 套件有被 Celery 載入。
- `TXT`、`Markdown`、`HTML` 與 `PDF` 目前都會建立 SQL-first 的 parent-child chunks。
- `PDF_PARSER_PROVIDER=marker` 是目前預設路徑；它會先用 Marker 將 PDF 轉成 Markdown，只持久化 `marker.cleaned.md`，再回接既有 Markdown parser 與 chunk tree。
- `marker-pdf` 刻意不放進共享 workspace 的解算圖，因為 `deepagents` 與 Marker 目前依賴彼此不相容的 `anthropic` 版本。若本機確定要走 Marker 路徑，請把它安裝到獨立 worker virtualenv，例如 `../../.worker-venv`。類 Unix shell 通常使用 `../../.worker-venv/bin/python`，Windows PowerShell 則要改用 `..\..\.worker-venv\Scripts\python.exe`。`./scripts/start-hybrid-worker.sh` 在 `PDF_PARSER_PROVIDER=marker` 時會自動優先挑選那個環境。
- `MARKER_MODEL_CACHE_DIR` 應指向可寫目錄，避免 Marker / Surya 模型下載落到受限的 cache 路徑；compose 預設會把這個目錄掛到 named volume，因此 worker 重啟或重建後模型 cache 不會遺失。
- 當 `MARKER_USE_LLM=true` 時，worker 現在會把 `MARKER_LLM_SERVICE`、`MARKER_OPENAI_API_KEY`、`MARKER_OPENAI_MODEL` 與 `MARKER_OPENAI_BASE_URL` 一起傳給 Marker 的 OpenAI-compatible LLM 設定。
- `PDF_PARSER_PROVIDER=local` 會使用 `Unstructured partition_pdf(strategy="fast")` 作為自架 fallback；`PDF_PARSER_PROVIDER=llamaparse` 則會先把 PDF 轉成 Markdown，再交給既有 Markdown parser 與 chunk tree。
- `.xlsx` 會使用 `unstructured.partition_xlsx`，優先採用 worksheet `text_as_html`，再回接既有 HTML table-aware parser 與 chunk tree。
- `.docx` 與 `.pptx` 會使用 `unstructured.partition_docx` / `partition_pptx`，再把 Unstructured elements 映射回既有 `text/table` block-aware parser contract。
- `LLAMAPARSE_DO_NOT_CACHE=true` 是企業文件建議的安全預設；`LLAMAPARSE_MERGE_CONTINUED_TABLES=false` 則讓跨頁表格合併維持 opt-in。
- 每次新的 ingest 執行前都會先清理文件範圍內的 `artifacts/` 前綴，避免殘留舊 parse 產物。
- `document_chunks` 已包含 `structure_kind=text|table`，可明確區分一般文字與表格內容。
- 文字 child 會由 `LangChain RecursiveCharacterTextSplitter` 切分；大型表格則依 row groups 切分並重複表頭。
- `ready` 現在代表 chunking 與 embedding 都已完成。
- worker 目前已負責 child chunk 的 embedding。
- OpenAI embeddings 現在會依 `EMBEDDING_MAX_BATCH_TEXTS` 分批送出；若單批仍因 request size 超限被拒絕，worker 會自動再將該批二分後重送。
- OpenAI embeddings 目前只會對暫時性失敗（例如 `429`、`5xx`、連線/timeout）做有限次 backoff retry；`400` 這類永久性錯誤會直接轉成受控 failed，避免 task 以 unexpected exception 結束。
- 本模組目前只啟用 LlamaParse 的標準 Markdown 轉換路徑，未來才會再評估 agentic mode。
- 尚未實作的檔案型別仍維持受控 `failed`。
- retrieval API、rerank 與 chat orchestration 不在此模組內實作。
