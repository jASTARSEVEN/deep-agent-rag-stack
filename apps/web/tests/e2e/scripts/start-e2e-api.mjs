/** 啟動 Playwright E2E 使用的 FastAPI test-mode 服務。 */

import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawn } from "node:child_process";


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

/** API server 啟動用子行程。 */
const childProcess = spawn(
  "python",
  ["-m", "uvicorn", "app.main:app", "--app-dir", "src", "--host", "127.0.0.1", "--port", "18001"],
  {
    cwd: apiRoot,
    stdio: "inherit",
    env: {
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
      KEYCLOAK_URL: "http://localhost:18080",
      KEYCLOAK_ISSUER: "http://localhost:18080/realms/deep-agent-dev",
      KEYCLOAK_JWKS_URL: "http://localhost:18080/realms/deep-agent-dev/protocol/openid-connect/certs",
      KEYCLOAK_GROUPS_CLAIM: "groups",
      AUTH_TEST_MODE: "true",
    },
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
