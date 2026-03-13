# API 模組

[English README](README.md)

## 模組目的

此模組包含專案的 FastAPI 服務。它目前提供：
- 最小 landing route 與 health route
- JWT / Keycloak 驗證骨架
- `sub` / `groups` claims 解析
- Knowledge Area create/list/detail 最小切片
- area access management API
- area access-check 驗證切片
- documents upload / list / detail API
- ingest jobs detail API
- SQLAlchemy 與 Alembic migration 骨架

## 啟動方式

- 本機 Python 執行：
  - `python -m venv .venv && source .venv/bin/activate`
  - `pip install -e .[dev]`
  - `alembic upgrade head`
  - `uvicorn app.main:app --app-dir src --reload --host 0.0.0.0 --port 18000`
- 本機執行測試：
  - `pytest`
- Docker Compose：
  - `docker compose -f ../../infra/docker-compose.yml --env-file ../../.env up api`

## 環境變數

- `API_SERVICE_NAME`
- `API_VERSION`
- `API_HOST`
- `API_PORT`
- `API_CORS_ORIGINS`
- `DATABASE_URL`
- `DATABASE_ECHO`
- `REDIS_URL`
- `STORAGE_BACKEND`
- `MINIO_ENDPOINT`
- `MINIO_ACCESS_KEY`
- `MINIO_SECRET_KEY`
- `MINIO_SECURE`
- `MINIO_BUCKET`
- `LOCAL_STORAGE_PATH`
- `MAX_UPLOAD_SIZE_BYTES`
- `CHUNK_MIN_PARENT_SECTION_LENGTH`
- `CHUNK_TARGET_CHILD_SIZE`
- `CHUNK_CHILD_OVERLAP`
- `CHUNK_CONTENT_PREVIEW_LENGTH`
- `CHUNK_TXT_PARENT_GROUP_SIZE`
- `CELERY_BROKER_URL`
- `CELERY_RESULT_BACKEND`
- `INGEST_INLINE_MODE`
- `KEYCLOAK_URL`
- `KEYCLOAK_ISSUER`
- `KEYCLOAK_JWKS_URL`
- `KEYCLOAK_GROUPS_CLAIM`
- `AUTH_TEST_MODE`

## 主要目錄結構

- `src/app/main.py`：FastAPI 應用程式進入點
- `src/app/core`：設定與共用執行期輔助元件
- `src/app/auth`：JWT 驗證、principal 解析與 auth dependency
- `src/app/db`：SQLAlchemy models、session 與 metadata
- `src/app/routes`: HTTP routes
- `src/app/schemas`：回應模型
- `src/app/services`：授權與 runtime service
- `alembic`：migration 執行環境與版本腳本
- `tests`：授權與 API 測試

## 對外介面

- `GET /`
- `GET /health`
- `GET /auth/context`
- `POST /areas`
- `GET /areas`
- `GET /areas/{area_id}`
- `GET /areas/{area_id}/access`
- `PUT /areas/{area_id}/access`
- `GET /areas/{area_id}/access-check`
- `POST /areas/{area_id}/documents`
- `GET /areas/{area_id}/documents`
- `GET /documents/{document_id}`
- `POST /documents/{document_id}/reindex`
- `DELETE /documents/{document_id}`
- `GET /ingest-jobs/{job_id}`

## 疑難排解

- 若 import 失敗，請確認啟動命令包含 `--app-dir src`。
- 若 `alembic upgrade head` 無法連到資料庫，請先確認根目錄 `.env` 內的 `DATABASE_URL`。
- 若本機只想跑測試，可啟用 `AUTH_TEST_MODE=true`，以 `Bearer test::<sub>::<group1,group2>` 驗證 auth flow。
- `GET /areas/{area_id}`、`GET /areas/{area_id}/access` 對未授權與不存在資源都會回 `404`，此為 deny-by-default 的既定語意。
- `AUTH_TEST_MODE=true` 常搭配 `STORAGE_BACKEND=filesystem` 與 `INGEST_INLINE_MODE=true`，供 API 測試與 Playwright E2E 使用。
- `TXT/MD` 上傳目前會建立 SQL-first 的 parent-child `document_chunks`；會保留 custom parent sections，並以 `LangChain RecursiveCharacterTextSplitter` 切分 child chunks。
- 未支援格式仍維持受控 `failed`。
- 此模組目前尚未實作 retrieval 或 chat。
