/** Playwright E2E 設定，負責啟動本機 web 與 test-mode API。 */

import { defineConfig, devices } from "@playwright/test";


/** Playwright 在本機 E2E 使用的前端 base URL。 */
const E2E_WEB_URL = "http://127.0.0.1:13001";

/** Playwright 在本機 E2E 使用的 API base URL。 */
const E2E_API_URL = "http://127.0.0.1:18001";


export default defineConfig({
  testDir: "./tests/e2e/specs",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [["list"], ["html", { outputFolder: "playwright-report", open: "never" }]],
  timeout: 60_000,
  expect: {
    timeout: 10_000,
  },
  use: {
    baseURL: E2E_WEB_URL,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  webServer: [
    {
      command: "npm run api:e2e",
      url: `${E2E_API_URL}/health`,
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: "npm run dev:e2e",
      url: E2E_WEB_URL,
      reuseExistingServer: false,
      timeout: 120_000,
      env: {
        ...process.env,
        VITE_API_BASE_URL: E2E_API_URL,
        VITE_AUTH_MODE: "test",
      },
    },
  ],
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
      },
    },
  ],
});
