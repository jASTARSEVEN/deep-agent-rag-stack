/** 真實 Keycloak smoke 測試設定。 */

import { defineConfig, devices } from "@playwright/test";


// Compose web 對外網址。
const SMOKE_WEB_URL = process.env.SMOKE_WEB_URL ?? "http://localhost:13000";


export default defineConfig({
  testDir: "./tests/smoke/specs",
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  workers: 1,
  reporter: [["list"], ["html", { outputFolder: "playwright-report-smoke", open: "never" }]],
  timeout: 90_000,
  expect: {
    timeout: 15_000,
  },
  use: {
    baseURL: SMOKE_WEB_URL,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
      },
    },
  ],
});
