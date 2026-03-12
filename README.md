# Deep Agent RAG Stack

## 模組目的

此倉庫包含一個可自架、NotebookLM 風格文件問答平台的 MVP 開發骨架。本輪只建立 monorepo 結構、本機基礎設施接線，以及最小可執行應用程式。

## 本輪範圍

- 建立 API、worker、web、infra、shared package 的 monorepo 骨架。
- 使用 Docker Compose 串接本機服務。
- 提供最小可執行的 FastAPI、Celery、React 應用程式。
- 補上 health check、環境變數文件與啟動說明。

## 目前尚未實作

- Knowledge Area 業務邏輯
- 文件上傳完整流程
- Chat、retrieval、SQL gate、RAG、FTS、rerank
- Keycloak realm 初始化與授權強制邏輯

## 倉庫結構

- `apps/api`：FastAPI API 骨架服務
- `apps/worker`：Celery 背景工作骨架
- `apps/web`：React + Tailwind 前端骨架
- `infra`：Docker Compose 與容器建置資產
- `packages/shared`：未來共用型別與常數的預留目錄

## 啟動方式

1. Copy environment variables:
   - `cp .env.example .env`
2. Optional local Python dependencies install:
   - `python -m venv .venv && source .venv/bin/activate`
   - `pip install -e ./apps/api -e ./apps/worker`
3. Build and start the local stack:
   - `docker compose -f infra/docker-compose.yml --env-file .env up --build`
4. 開啟本機服務：
   - Web: `http://localhost:13000`
   - API: `http://localhost:18000`
   - API health: `http://localhost:18000/health`
   - Keycloak: `http://localhost:18080`
   - MinIO API: `http://localhost:19000`
   - MinIO Console: `http://localhost:19001`

## 環境變數

完整本機預設值請參考 `.env.example`。

## 驗證方式

- API health：
  - `curl http://localhost:18000/health`
- Worker ping task：
  - `docker compose -f infra/docker-compose.yml exec worker python -m worker.scripts.healthcheck`
- Web wiring：
  - Open `http://localhost:13000` and confirm that the API health panel reports `ok`
- Phase 1 auth 驗證手冊：
  - `docs/phase1-auth-verification.md`

## 疑難排解

- 若 Docker 映像建置失敗，請確認 Docker Desktop 正在執行，且能存取套件來源。
- 若 Keycloak 啟動較慢，請等到 `keycloak` health check 通過後再開啟 UI。
- 若 web 無法連到 API，請確認 `.env` 中的 `VITE_API_BASE_URL`。
