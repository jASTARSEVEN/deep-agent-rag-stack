/** 啟動 Playwright E2E 使用的 FastAPI test-mode 服務。 */

import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawn, spawnSync } from "node:child_process";


/** 目前腳本所在目錄。 */
const currentDirectory = dirname(fileURLToPath(import.meta.url));

/** `apps/web` 模組根目錄。 */
const webRoot = resolve(currentDirectory, "../../..");

/** `apps/api` 模組根目錄。 */
const apiRoot = resolve(webRoot, "../api");

/** Playwright E2E 共用的 SQLite 測試資料庫路徑。 */
const databasePath = join(webRoot, ".tmp", "playwright-e2e.sqlite");

/** Playwright E2E 共用的本機檔案儲存路徑。 */
const storagePath = join(webRoot, ".tmp", "playwright-storage");

/** E2E API server 共用環境變數。 */
const apiEnv = {
  ...process.env,
  API_SERVICE_NAME: "deep-agent-api-e2e",
  API_VERSION: "0.1.0-e2e",
  API_HOST: "127.0.0.1",
  API_PORT: "18001",
  API_CORS_ORIGINS: "http://127.0.0.1:13001",
  DATABASE_URL: `sqlite+pysqlite:///${databasePath}`,
  DATABASE_ECHO: "false",
  REDIS_URL: "redis://localhost:16379/0",
  STORAGE_BACKEND: "filesystem",
  MINIO_ENDPOINT: "http://localhost:19000",
  MINIO_ACCESS_KEY: "minio",
  MINIO_SECRET_KEY: "minio123",
  MINIO_BUCKET: "documents",
  LOCAL_STORAGE_PATH: storagePath,
  MAX_UPLOAD_SIZE_BYTES: "1048576",
  CELERY_BROKER_URL: "redis://localhost:16379/0",
  CELERY_RESULT_BACKEND: "redis://localhost:16379/1",
  INGEST_INLINE_MODE: "true",
  EMBEDDING_PROVIDER: "deterministic",
  EMBEDDING_MODEL: "text-embedding-3-small",
  EMBEDDING_DIMENSIONS: "1536",
  RERANK_PROVIDER: "deterministic",
  RERANK_MODEL: "rerank-v3.5",
  KEYCLOAK_URL: "http://localhost:18080",
  KEYCLOAK_ISSUER: "http://localhost:18080/realms/deep-agent-dev",
  KEYCLOAK_JWKS_URL: "http://localhost:18080/realms/deep-agent-dev/protocol/openid-connect/certs",
  KEYCLOAK_GROUPS_CLAIM: "groups",
  AUTH_TEST_MODE: "true",
  CHAT_PROVIDER: "deterministic",
  CHAT_MODEL: "deterministic-chat",
  CHAT_MAX_OUTPUT_TOKENS: "700",
  CHAT_TIMEOUT_SECONDS: "30",
  CHAT_INCLUDE_TRACE: "true",
  CHAT_STREAM_CHUNK_SIZE: "24",
  LANGGRAPH_SERVICE_PORT: "18001",
};

/** `langgraph` CLI 是否可直接執行。 */
const hasLangGraphCli = spawnSync("sh", ["-lc", "command -v langgraph >/dev/null 2>&1"], {
  cwd: apiRoot,
}).status === 0;

/** Python 環境是否可透過 module 啟動 LangGraph CLI。 */
const hasLangGraphCliModule = spawnSync("python", ["-c", "import langgraph_cli"], {
  cwd: apiRoot,
}).status === 0;

/** API server 啟動用子行程。 */
const childProcess = hasLangGraphCli
  ? spawn(
      "langgraph",
      ["dev", "--config", "langgraph.json", "--host", "127.0.0.1", "--port", "18001", "--no-browser", "--no-reload"],
      {
        cwd: apiRoot,
        stdio: "inherit",
        env: apiEnv,
      },
    )
  : hasLangGraphCliModule
    ? spawn(
        "python",
        ["-m", "langgraph_cli", "dev", "--config", "langgraph.json", "--host", "127.0.0.1", "--port", "18001", "--no-browser", "--no-reload"],
        {
          cwd: apiRoot,
          stdio: "inherit",
          env: apiEnv,
        },
      )
  : spawn(
      "python",
      ["-m", "uvicorn", "app.chat.runtime.langgraph_http_app:app", "--app-dir", "src", "--host", "127.0.0.1", "--port", "18001"],
      {
        cwd: apiRoot,
        stdio: "inherit",
        env: apiEnv,
      },
    );

/** 將終止訊號轉發給 API 子行程。 */
function forwardSignal(signal) {
  if (!childProcess.killed) {
    childProcess.kill(signal);
  }
}

process.on("SIGINT", () => forwardSignal("SIGINT"));
process.on("SIGTERM", () => forwardSignal("SIGTERM"));
childProcess.on("exit", (code) => process.exit(code ?? 0));
