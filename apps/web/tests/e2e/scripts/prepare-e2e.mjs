/** 準備 Playwright E2E 所需的 SQLite 測試資料與暫存目錄。 */

import { mkdirSync, rmSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";


/** 目前腳本所在目錄。 */
const currentDirectory = dirname(fileURLToPath(import.meta.url));

/** `apps/web` 模組根目錄。 */
const webRoot = resolve(currentDirectory, "../../..");

/** E2E 暫存目錄。 */
const tempDirectory = join(webRoot, ".tmp");

/** E2E SQLite 測試資料庫路徑。 */
const databasePath = join(tempDirectory, "playwright-e2e.sqlite");

/** E2E 本機物件儲存路徑。 */
const storagePath = join(tempDirectory, "playwright-storage");

mkdirSync(tempDirectory, { recursive: true });
rmSync(databasePath, { force: true });
rmSync(storagePath, { recursive: true, force: true });

const seedProcess = spawnSync("python", [join(currentDirectory, "seed_e2e_data.py"), databasePath], {
  cwd: webRoot,
  stdio: "inherit",
});

if (seedProcess.status !== 0) {
  process.exit(seedProcess.status ?? 1);
}
