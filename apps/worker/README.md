# Worker 模組

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

## 主要目錄結構

- `src/worker/celery_app.py`：Celery 應用程式進入點
- `src/worker/tasks`：health 與 ingest task 模組
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
- `TXT/MD` 以外的檔案型別目前會進入受控 `failed`，此為 Phase 3 MVP 的既定行為。
- 此模組目前尚未實作 chunking、embedding、FTS preparation 或 retrieval indexing。
