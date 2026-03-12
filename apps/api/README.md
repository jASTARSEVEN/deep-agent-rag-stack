# API 模組

## 模組目的

此模組包含專案的 FastAPI 骨架服務。它提供最小 landing route 與 health route，並預留未來 auth、database、route、service 的模組結構。

## 啟動方式

- 本機 Python 執行：
  - `python -m venv .venv && source .venv/bin/activate`
  - `pip install -e .`
  - `uvicorn app.main:app --app-dir src --reload --host 0.0.0.0 --port 18000`
- Docker Compose：
  - `docker compose -f ../../infra/docker-compose.yml --env-file ../../.env up api`

## 環境變數

- `API_SERVICE_NAME`
- `API_VERSION`
- `API_HOST`
- `API_PORT`
- `API_CORS_ORIGINS`
- `DATABASE_URL`
- `REDIS_URL`
- `MINIO_ENDPOINT`
- `MINIO_BUCKET`
- `KEYCLOAK_URL`
- `KEYCLOAK_ISSUER`
- `KEYCLOAK_JWKS_URL`
- `KEYCLOAK_GROUPS_CLAIM`

## 主要目錄結構

- `src/app/main.py`：FastAPI 應用程式進入點
- `src/app/core`：設定與共用執行期輔助元件
- `src/app/routes`: HTTP routes
- `src/app/schemas`：回應模型
- `src/app/services`：service 層預留模組
- `src/app/auth`：未來 auth 整合預留模組
- `src/app/db`：未來資料庫整合預留模組

## 對外介面

- `GET /`
- `GET /health`

## 疑難排解

- 若 import 失敗，請確認啟動命令包含 `--app-dir src`。
- 若 API 無法連到其他服務，請確認根目錄 `.env` 內的設定值。
- 此模組目前尚未實作 RBAC、SQL gate 或正式業務端點。
