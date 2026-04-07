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

/** `apps/worker` 模組根目錄。 */
const workerRoot = resolve(webRoot, "../worker");

/** Playwright E2E 共用的 SQLite 測試資料庫路徑。 */
const databasePath = join(webRoot, ".tmp", "playwright-e2e.sqlite");

/** Playwright E2E 共用的本機檔案儲存路徑。 */
const storagePath = join(webRoot, ".tmp", "playwright-storage");

/** Playwright E2E 共用的 Celery filesystem broker 路徑。 */
const celeryBrokerPath = join(webRoot, ".tmp", "celery-broker");

/** E2E API / worker 共用環境變數。 */
const sharedEnv = {
  ...process.env,
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
  PDF_PARSER_PROVIDER: "local",
  CELERY_BROKER_URL: "filesystem://",
  CELERY_RESULT_BACKEND: "cache+memory://",
  CELERY_BROKER_PATH: celeryBrokerPath,
  EMBEDDING_PROVIDER: "deterministic",
  EMBEDDING_MODEL: "text-embedding-3-small",
  EMBEDDING_DIMENSIONS: "1536",
  RERANK_PROVIDER: "deterministic",
  RERANK_MODEL: "rerank-v3.5",
  RERANK_TOP_N: "6",
  RERANK_MAX_CHARS_PER_DOC: "2000",
  ASSEMBLER_MAX_CONTEXTS: "6",
  ASSEMBLER_MAX_CHARS_PER_CONTEXT: "2500",
  ASSEMBLER_MAX_CHILDREN_PER_PARENT: "3",
  KEYCLOAK_URL: "http://localhost:18080",
  KEYCLOAK_ISSUER: "http://localhost:18080/realms/deep-agent-dev",
  KEYCLOAK_JWKS_URL: "http://localhost:18080/realms/deep-agent-dev/protocol/openid-connect/certs",
  KEYCLOAK_GROUPS_CLAIM: "groups",
  AUTH_TEST_MODE: "true",
};

/** E2E API server 環境變數。 */
const apiEnv = {
  ...sharedEnv,
  API_SERVICE_NAME: "deep-agent-api-e2e",
  API_VERSION: "0.1.0-e2e",
  API_HOST: "127.0.0.1",
  API_PORT: "18001",
  API_CORS_ORIGINS: "http://127.0.0.1:13001",
  CHAT_PROVIDER: "deterministic",
  CHAT_MODEL: "deterministic-chat",
  CHAT_MAX_OUTPUT_TOKENS: "700",
  CHAT_TIMEOUT_SECONDS: "30",
  CHAT_INCLUDE_TRACE: "true",
  CHAT_STREAM_CHUNK_SIZE: "24",
  LANGGRAPH_SERVICE_PORT: "18001",
};

/** E2E worker 環境變數。 */
const workerEnv = {
  ...sharedEnv,
  WORKER_SERVICE_NAME: "deep-agent-worker-e2e",
  PYTHONPATH: process.env.PYTHONPATH ? `${join(workerRoot, "src")}:${process.env.PYTHONPATH}` : join(workerRoot, "src"),
};

/** Worker 啟動用子行程。 */
const workerProcess = spawn(
  "python",
  ["-m", "celery", "-A", "worker.celery_app.celery_app", "worker", "--pool=solo", "--loglevel=INFO"],
  {
    cwd: workerRoot,
    stdio: "inherit",
    env: workerEnv,
  },
);

/** API server 啟動用子行程。 */
const apiProcess = spawn(
  "python",
  ["-m", "uvicorn", "app.chat.runtime.langgraph_http_postgres:postgres", "--app-dir", "src", "--host", "127.0.0.1", "--port", "18001"],
  {
    cwd: apiRoot,
    stdio: "inherit",
    env: apiEnv,
  },
);

const childProcesses = [workerProcess, apiProcess];

/** 將終止訊號轉發給 API / worker 子行程。 */
function forwardSignal(signal) {
  for (const childProcess of childProcesses) {
    if (!childProcess.killed) {
      childProcess.kill(signal);
    }
  }
}

process.on("SIGINT", () => forwardSignal("SIGINT"));
process.on("SIGTERM", () => forwardSignal("SIGTERM"));

let didExit = false;

function exitAll(code) {
  if (didExit) {
    return;
  }
  didExit = true;
  forwardSignal("SIGTERM");
  process.exit(code ?? 0);
}

workerProcess.on("exit", (code) => exitAll(code));
apiProcess.on("exit", (code) => exitAll(code));
