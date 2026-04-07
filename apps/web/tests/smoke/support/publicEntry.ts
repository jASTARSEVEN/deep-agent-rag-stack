/** Compose smoke 測試共用的公開入口與 Keycloak 導覽輔助。 */

import { expect, type Page } from "@playwright/test";

// Compose smoke 預設使用的 demo 使用者帳號。
const SMOKE_USERNAME = process.env.SMOKE_KEYCLOAK_USERNAME ?? "alice";

// Compose smoke 預設使用的 demo 使用者密碼。
const SMOKE_PASSWORD = process.env.SMOKE_KEYCLOAK_PASSWORD ?? "alice123";

/**
 * 透過單一公開入口進入首頁。
 *
 * 參數：
 * - `page`：目前 Playwright page。
 *
 * 回傳：
 * - `Promise<void>`：首頁完成載入後結束。
 */
export async function openSmokeHomePage(page: Page): Promise<void> {
  await page.goto("/", { waitUntil: "networkidle" });
}

/**
 * 透過 Caddy `/auth/*` 路徑完成真實 Keycloak 登入，並確保回到 `/areas`。
 *
 * 參數：
 * - `page`：目前 Playwright page。
 *
 * 回傳：
 * - `Promise<void>`：登入成功並回到 Areas 頁後結束。
 */
export async function loginViaPublicKeycloak(page: Page): Promise<void> {
  await openSmokeHomePage(page);

  if (await page.getByText("前往 Areas").isVisible()) {
    await page.getByText("前往 Areas").click();
    await page.waitForURL(/\/areas$/);
    return;
  }

  await page.getByTestId("login-button").click();
  await page.waitForURL((url) => url.pathname.startsWith("/auth/"), { timeout: 20_000 });
  await page.locator('input[name="username"], #username').fill(SMOKE_USERNAME);
  await page.locator('input[name="password"], #password').fill(SMOKE_PASSWORD);
  await page.locator('input[type="submit"], button[type="submit"], #kc-login').click();
  await page.waitForURL(/\/areas$/, { timeout: 20_000 });
}

/**
 * 建立並打開新的 smoke area。
 *
 * 參數：
 * - `page`：目前 Playwright page。
 * - `areaName`：要建立的 area 名稱。
 * - `description`：要寫入的 area 說明。
 *
 * 回傳：
 * - `Promise<void>`：area 出現在列表且已被選取後結束。
 */
export async function createAndOpenSmokeArea(
  page: Page,
  options: {
    areaName: string;
    description: string;
  },
): Promise<void> {
  const { areaName, description } = options;
  await expect(page.getByText("Knowledge Areas")).toBeVisible();
  await page.getByTestId("create-area-name").fill(areaName);
  await page.getByTestId("create-area-description").fill(description);
  await page.getByTestId("create-area-submit").click();
  await expect(page.getByTestId("areas-list")).toContainText(areaName);
  await page.getByTestId("areas-list").getByRole("button", { name: new RegExp(areaName) }).first().click();
}
