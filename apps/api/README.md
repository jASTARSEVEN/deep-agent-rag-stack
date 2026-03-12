# API 模組

## 模組目的

此模組包含專案的 FastAPI 服務。它目前提供：
- 最小 landing route 與 health route
- JWT / Keycloak 驗證骨架
- `sub` / `groups` claims 解析
- area access-check 驗證切片
- SQLAlchemy 與 Alembic migration 骨架

## 啟動方式

- 本機 Python 執行：
  - `python -m venv .venv && source .venv/bin/activate`
  - `pip install -r requirements.txt`
  - `pip install -e .`
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
- `MINIO_ENDPOINT`
- `MINIO_BUCKET`
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
- `GET /areas/{area_id}/access-check`

## 疑難排解

- 若 import 失敗，請確認啟動命令包含 `--app-dir src`。
- 若 `alembic upgrade head` 無法連到資料庫，請先確認根目錄 `.env` 內的 `DATABASE_URL`。
- 若本機只想跑測試，可啟用 `AUTH_TEST_MODE=true`，以 `Bearer test::<sub>::<group1,group2>` 驗證 auth flow。
- 此模組目前尚未實作 area CRUD、upload、retrieval 或 chat。
