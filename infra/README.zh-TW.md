# Infra 模組

[English README](README.md)

## 模組目的

此模組包含本機 Docker Compose stack，以及啟動 Documents + Retrieval Foundation 所需的容器建置資產。

## 啟動方式

- 在專案根目錄執行：
  - `cp .env.example .env`
  - `docker compose -f infra/docker-compose.yml --env-file .env up --build`

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
- `CELERY_*`
- `INGEST_INLINE_MODE`
- `EMBEDDING_*`
- `OPENAI_API_KEY`
- `TEXT_SEARCH_CONFIG`
- `RETRIEVAL_*`
- `VITE_*`
- `PG_JIEBA_REPO_URL`
- `PG_JIEBA_REF`

## 主要目錄結構

- `docker-compose.yml`：本機服務編排設定
- `docker/postgres`：內建 `pg_jieba`、繁體中文詞庫與 init SQL 的 Postgres 映像
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
  - Postgres: `15432`
  - Redis: `16379`

## 疑難排解

- `postgres` 服務啟動時會以 `shared_preload_libraries=pg_jieba` 載入 extension，並使用 repo 內固定的繁體中文詞庫。
- Keycloak 目前會在第一次啟動時自動匯入 `deep-agent-dev` realm、`deep-agent-web` client、groups mapper 與預設 users/groups。
- 若要回到預設 Keycloak 身份資料，請刪除 `keycloak-db` volume 後重新啟動 stack。
- Compose health check 目前只驗證骨架 stack 是否就緒，不代表正式業務正確性。
- 正式 compose 預設使用 `STORAGE_BACKEND=minio`；若做本機測試模式驗證，可改成 `filesystem` 並搭配 `INGEST_INLINE_MODE=true`。
