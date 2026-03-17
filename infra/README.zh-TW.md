# Infra 模組

[English README](README.md)

## 模組目的

此模組包含本機 Docker Compose stack，以及啟動 Documents + Retrieval Foundation 所需的容器建置資產。

## 啟動方式

- 在專案根目錄執行：
  - `cp .env.example .env`
  - `./scripts/compose.sh up --build`
  - wrapper 會固定注入 repo 根目錄 `.env` 與 `infra/docker-compose.yml`，避免從不同工作目錄執行 Compose 時把 `OPENAI_API_KEY` / `COHERE_API_KEY` 等值帶成空字串。
  - Compose 檔已固定 project name 為 `deep-agent-rag-stack`，且 fallback host ports 也改為 repo 標準值（`13000/18000/18080/19000/19001/15432/16379`），降低漏帶 `--env-file` 時的漂移風險。

## 環境變數

- `POSTGRES_*`
- `REDIS_PORT`
- `MINIO_*`
- `KEYCLOAK_*`
- `API_*`
- `DATABASE_URL`
- `REDIS_URL`
- `STORAGE_BACKEND`
- `LOCAL_STORAGE_PATH`
- `MAX_UPLOAD_SIZE_BYTES`
- `PDF_PARSER_PROVIDER`
- `LLAMAPARSE_*`
- `CELERY_*`
- `INGEST_INLINE_MODE`
- `EMBEDDING_*`
- `OPENAI_API_KEY`
- `RERANK_*`
- `COHERE_API_KEY`
- `LANGSMITH_*`
- `RETRIEVAL_*`
- `VITE_*`

## 主要目錄結構

- `docker-compose.yml`：本機服務編排設定
- `docker/api`：API container 映像
- `docker/worker`：Worker container 映像
- `docker/web`：Web container 映像
- `keycloak`：本機開發用的 realm bootstrap 匯入資產

## 對外介面

- 本機服務埠號：
  - Web: `13000`
  - API: `18000`
  - Keycloak: `18080`
  - MinIO API: `19000`
  - MinIO Console: `19001`
  - Postgres (Supabase): `15432`
  - Redis: `16379`

## 疑難排解

- 若你曾在固定 project name 前啟動過 stack，可能仍殘留 `infra-*` 之類的舊 container；在判斷目前是哪一組服務佔用 port 前，應先清理這些舊 container。
- `supabase-db` 服務使用 `supabase/postgres` 映像，內建 PGroonga 支援繁體中文檢索。
- Keycloak 目前會在第一次啟動時自動匯入 `deep-agent-dev` realm、`deep-agent-web` client、groups mapper 與預設 users/groups。
- `supabase/migrations/` 掛載到 `/docker-entrypoint-initdb.d` 只適用全新資料庫 volume；既有資料庫在專用 migration runner 落地前仍需走 Alembic 升級。
- Compose health check 目前只驗證骨架 stack 是否就緒，不代表正式業務正確性。
- 正式 compose 預設使用 `STORAGE_BACKEND=minio`；若做本機測試模式驗證，可改成 `filesystem` 並搭配 `INGEST_INLINE_MODE=true`。
- 若要讓 compose 內的 API 與 worker 都切換到 LlamaParse，除了在 `.env` 設定 `PDF_PARSER_PROVIDER=llamaparse` 外，也必須提供 `LLAMAPARSE_API_KEY`；修改後需重新啟動 `api` 與 `worker` 容器。
- 若要啟用 Cohere rerank，請確認 `.env` 內已提供 `COHERE_API_KEY`，並將 `RERANK_PROVIDER` 維持為 `cohere`。
