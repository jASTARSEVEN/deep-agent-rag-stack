# Infra 模組

[English README](README.md)

## 模組目的

此模組包含本機 Docker Compose stack，以及啟動整個自架平台所需的容器建置資產。
目前正式對外部署模型採用 `Caddy` 提供單一公開 HTTPS origin，而 `web`、`api`、`keycloak` 則留在內部 Docker network。

## 啟動方式

- 在專案根目錄執行：
  - `cp .env.example .env`
  - 本機開發請保留預設 `PUBLIC_HOST=localhost`
  - 對外部署時再設定 `PUBLIC_HOST`、`PUBLIC_BASE_URL`、`TLS_ACME_EMAIL`
  - 若要啟用本機 Hugging Face provider，請先設定 `API_INSTALL_OPTIONAL_GROUPS=local-huggingface`；若 worker embeddings 也改用 Hugging Face，則再加上 `WORKER_INSTALL_OPTIONAL_GROUPS=local-huggingface`
  - 對外部署時再將 `PUBLIC_HOST` 的 DNS 指向部署主機
  - 對外部署時再將外部 `80` 與 `443` 轉發到 Docker 主機
  - `docker compose --env-file .env -f infra/docker-compose.yml up --build`
- Compose 檔已固定 project name 為 `deep-agent-rag-stack`
- `worker` 現在預設以 CPU-safe 模式啟動，不會自動要求 Docker GPU 裝置

## 環境變數

- `PUBLIC_HOST`
- `PUBLIC_BASE_URL`
- `TLS_ACME_*`
- `KEYCLOAK_EXPOSE_ADMIN`
- `POSTGRES_*`
- `REDIS_PORT`
- `MINIO_*`
- `KEYCLOAK_REALM`
- `KEYCLOAK_CLIENT_ID`
- `KEYCLOAK_GROUPS_CLAIM`
- `STORAGE_BACKEND`
- `LOCAL_STORAGE_PATH`
- `PDF_PARSER_PROVIDER`
- `OPENDATALOADER_*`
- `LLAMAPARSE_*`
- `NVIDIA_*`
- `API_INSTALL_OPTIONAL_GROUPS`
- `WORKER_INSTALL_OPTIONAL_GROUPS`
- `EMBEDDING_*`
- `OPENAI_API_KEY`
- `RERANK_*`
- `COHERE_API_KEY`
- `SELF_HOSTED_EMBEDDING_*`
- `SELF_HOSTED_RERANK_*`
- `CHAT_MODEL`
- `LANGSMITH_*`
- `VITE_APP_NAME`
- `VITE_CHAT_STREAM_DEBUG`

Compose 範本刻意省略了許多低頻的 runtime tuning 參數。
只有真的需要微調時，再手動把額外 env var 加進 `.env` 即可。

## 主要目錄結構

- `docker-compose.yml`：本機服務編排設定
- `docker/caddy`：reverse proxy 映像、Caddyfile 模板與啟動腳本
- `docker/api`：API container 映像
- `docker/worker`：worker container 映像
- `docker/web`：web container 映像
- `keycloak`：本機開發用 realm bootstrap 匯入資產

## 對外介面

- 瀏覽器正式入口：
  - 本機開發：`http://localhost/`、`http://localhost/api/*`、`http://localhost/auth/*`
  - 對外部署：`https://<PUBLIC_HOST>/`、`https://<PUBLIC_HOST>/api/*`、`https://<PUBLIC_HOST>/auth/*`
- 正式公開埠號：
  - 本機開發：`80`
  - 對外部署：`443` 為主要 HTTPS 入口，`80` 僅供 ACME 驗證與 HTTP 轉 HTTPS
- 仍可能保留的本機管理用 host ports：
  - MinIO API：`19000`
  - MinIO Console：`19001`
  - Postgres (Supabase)：`15432`
  - Redis：`16379`

## 疑難排解

- 當 `PUBLIC_HOST=localhost` 或 `127.0.0.1` 時，Caddy 會刻意改走純 HTTP，避免本機開發依賴 ACME 憑證。
- 若憑證無法簽發，先確認 `PUBLIC_HOST` 可由公網解析，且 `80/443` 已正確轉發到 Docker 主機。
- 若 reverse proxy 切換後登入失敗，請確認 `PUBLIC_BASE_URL` 正確，且 realm client 的 redirect URI 仍指向 `<PUBLIC_BASE_URL>/auth/callback` 與 `<PUBLIC_BASE_URL>/silent-check-sso.html`。
- `Caddy` 會把 `/auth/callback` 轉給 web，並把其餘 `/auth*` 轉給 Keycloak，因為前端 callback 與 Keycloak 共用 `/auth` prefix。
- `KEYCLOAK_EXPOSE_ADMIN=false` 會在 proxy 層封鎖 `/auth/admin*`；只有在你確定需要遠端管理主控台時，才應改成 `true`。
- compose stack 已不再公開舊的 `13000/18000/18080`，因此直接從 host 連 web / API / Keycloak 失敗是預期行為。
- 若你需要 GPU 加速，請先依實際執行環境明確加入 Docker GPU runtime 設定；預設 Compose 路徑刻意不再主動要求 GPU 裝置。
- 預設 API / worker image 不會安裝本機 Hugging Face optional 依賴。若切成 `EMBEDDING_PROVIDER=huggingface` 或 `RERANK_PROVIDER=huggingface`，請在重建前設定 `API_INSTALL_OPTIONAL_GROUPS=local-huggingface`；若 worker embeddings 也走 Hugging Face，請再加上 `WORKER_INSTALL_OPTIONAL_GROUPS=local-huggingface`。
- `supabase-db` 使用 `supabase/postgres` 映像，內建 PGroonga 支援繁體中文檢索。
- Compose health check 目前只驗證服務就緒，不代表完整業務正確性。
