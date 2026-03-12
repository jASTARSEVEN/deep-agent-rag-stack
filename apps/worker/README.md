# Worker 模組

## 模組目的

此模組包含專案的 Celery 骨架 worker。它提供啟動 worker 程序所需的最小執行期接線，並以簡單的 ping task 驗證任務執行能力。

## 啟動方式

- 本機 Python 執行：
  - `python -m venv .venv && source .venv/bin/activate`
  - `pip install -r requirements.txt`
  - `pip install -e .`
  - `celery -A worker.celery_app.celery_app worker --loglevel=INFO`
- 本機健康檢查命令：
  - `python -m worker.scripts.healthcheck`
- Docker Compose：
  - `docker compose -f ../../infra/docker-compose.yml --env-file ../../.env up worker`

## 環境變數

- `WORKER_SERVICE_NAME`
- `CELERY_BROKER_URL`
- `CELERY_RESULT_BACKEND`

## 主要目錄結構

- `src/worker/celery_app.py`：Celery 應用程式進入點
- `src/worker/tasks`：最小 task 模組與預留位置
- `src/worker/core`：worker 設定與共用輔助元件
- `src/worker/scripts`：給操作人員使用的輔助腳本

## 對外介面

- Celery task：`worker.tasks.health.ping`
- 健康檢查腳本：`python -m worker.scripts.healthcheck`

## 疑難排解

- 若 worker 無法連到 Redis，請確認 `CELERY_BROKER_URL`。
- 若沒有 task 被註冊，請確認 `worker.tasks` 套件有被 Celery 載入。
- 此模組目前尚未實作 ingestion、indexing 或狀態轉換。
