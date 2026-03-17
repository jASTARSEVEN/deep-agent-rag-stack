# Worker 模組

[English README](README.md)

## 模組目的

此模組包含專案的 Celery worker。它目前提供最小 ingest 任務、文件狀態轉換與 parser routing 骨架，並保留後續 indexing 擴充空間。

## 啟動方式

- 本機 Python 執行：
  - `python -m venv .venv && source .venv/bin/activate`
  - `pip install -e .[dev]`
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
- `STORAGE_BACKEND`
- `MINIO_ENDPOINT`
- `MINIO_ACCESS_KEY`
- `MINIO_SECRET_KEY`
- `MINIO_SECURE`
- `MINIO_BUCKET`
- `LOCAL_STORAGE_PATH`
- `PDF_PARSER_PROVIDER`
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
- 若 ingest task 無法更新資料庫，請確認 `DATABASE_URL` 指向與 API 相同的資料庫。
- 若正式環境無法讀取文件內容，請確認 `MINIO_*` 與 `MINIO_BUCKET` 一致。
- 若沒有 task 被註冊，請確認 `worker.tasks` 套件有被 Celery 載入。
- `TXT`、`Markdown`、`HTML` 與 `PDF` 目前都會建立 SQL-first 的 parent-child chunks。
- `PDF_PARSER_PROVIDER=local` 會使用 LangChain PDF loader 作為自架 fallback；`PDF_PARSER_PROVIDER=llamaparse` 則會先把 PDF 轉成 Markdown，再交給既有 Markdown parser 與 chunk tree。
- `LLAMAPARSE_DO_NOT_CACHE=true` 是企業文件建議的安全預設；`LLAMAPARSE_MERGE_CONTINUED_TABLES=false` 則讓跨頁表格合併維持 opt-in。
- `document_chunks` 已包含 `structure_kind=text|table`，可明確區分一般文字與表格內容。
- 文字 child 會由 `LangChain RecursiveCharacterTextSplitter` 切分；大型表格則依 row groups 切分並重複表頭。
- `ready` 現在代表 chunking 與 embedding 都已完成。
- worker 目前已負責 child chunk 的 embedding。
- 本模組目前只啟用 LlamaParse 的標準 Markdown 轉換路徑，未來才會再評估 agentic mode。
- 尚未實作的檔案型別仍維持受控 `failed`。
- retrieval API、rerank 與 chat orchestration 不在此模組內實作。
