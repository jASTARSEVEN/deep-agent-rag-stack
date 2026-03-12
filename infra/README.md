# Infra 模組

## 模組目的

此模組包含本機 Docker Compose stack，以及啟動 MVP 骨架環境所需的容器建置資產。

## 啟動方式

- From the repository root:
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
- `CELERY_*`
- `VITE_*`
- `PG_JIEBA_REPO_URL`
- `PG_JIEBA_REF`

## 主要目錄結構

- `docker-compose.yml`：本機服務編排設定
- `docker/postgres`：預留未來 `pg_jieba` 建置掛勾的 Postgres 映像
- `docker/api`：API container 映像
- `docker/worker`：Worker container 映像
- `docker/web`：Web container 映像
- `keycloak`：未來 realm bootstrap 資產的預留目錄

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

- `PG_JIEBA_REF` 在本輪仍只是預留值；開始做 FTS 之前請改成固定 commit SHA。
- Keycloak realm import 目前尚未自動化，請在下一階段手動建立 realm 與 client。
- Compose health check 目前只驗證骨架 stack 是否就緒，不代表正式業務正確性。
