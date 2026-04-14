/** 準備 Playwright E2E 所需的 SQLite 測試資料與暫存目錄。 */

import { mkdirSync, rmSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";


/** 目前腳本所在目錄。 */
const currentDirectory = dirname(fileURLToPath(import.meta.url));

/** `apps/web` 模組根目錄。 */
const webRoot = resolve(currentDirectory, "../../..");

/** `apps/worker` 模組根目錄。 */
const workerRoot = resolve(webRoot, "../worker");

/** E2E 暫存目錄。 */
const tempDirectory = join(webRoot, ".tmp");

/** E2E SQLite 測試資料庫路徑。 */
const databasePath = join(tempDirectory, "playwright-e2e.sqlite");

/** E2E 本機物件儲存路徑。 */
const storagePath = join(tempDirectory, "playwright-storage");

/** E2E Celery filesystem broker 路徑。 */
const celeryBrokerPath = join(tempDirectory, "celery-broker");

mkdirSync(tempDirectory, { recursive: true });
rmSync(databasePath, { force: true });
rmSync(storagePath, { recursive: true, force: true });
rmSync(celeryBrokerPath, { recursive: true, force: true });
rmSync(join(workerRoot, "control"), { recursive: true, force: true });
rmSync(join(workerRoot, "processed"), { recursive: true, force: true });
mkdirSync(celeryBrokerPath, { recursive: true });
mkdirSync(join(celeryBrokerPath, "in"), { recursive: true });
mkdirSync(join(celeryBrokerPath, "out"), { recursive: true });
mkdirSync(join(celeryBrokerPath, "processed"), { recursive: true });

const seedProcess = spawnSync("python", [join(currentDirectory, "seed_e2e_data.py"), databasePath, storagePath], {
  cwd: webRoot,
  stdio: "inherit",
});

if (seedProcess.status !== 0) {
  process.exit(seedProcess.status ?? 1);
}
