/** 真實 Keycloak 認證 smoke 測試。 */

import { expect, test } from "@playwright/test";


// Smoke 測試使用的固定 demo 使用者帳號。
const SMOKE_USERNAME = process.env.SMOKE_KEYCLOAK_USERNAME ?? "alice";

// Smoke 測試使用的固定 demo 使用者密碼。
const SMOKE_PASSWORD = process.env.SMOKE_KEYCLOAK_PASSWORD ?? "alice123";


/** 透過真實 Keycloak 登入頁完成登入。 */
async function loginViaKeycloak(page: Parameters<typeof test>[0]["page"]): Promise<void> {
  await page.goto("/");
  await page.getByTestId("login-button").click();

  await page.waitForURL(/localhost:18080/);
  await page.locator('input[name="username"]').fill(SMOKE_USERNAME);
  await page.locator('input[name="password"]').fill(SMOKE_PASSWORD);
  await page.locator('input[type="submit"], button[type="submit"]').click();

  await page.waitForURL(/\/areas$/);
}


test.describe("真實 Keycloak smoke", () => {
  test("login -> logout -> relogin 流程應可正常完成", async ({ page }) => {
    await loginViaKeycloak(page);

    await expect(page.getByTestId("auth-context-panel")).toContainText("groups: /dept/hr");

    await page.getByRole("button", { name: "登出" }).click();

    await page.waitForURL(/\/$/);
    await expect(page.getByTestId("login-button")).toBeVisible();
    await expect(page.getByText("目前尚未登入。")).toBeVisible();

    await loginViaKeycloak(page);

    await expect(page.getByTestId("auth-context-panel")).toContainText("groups: /dept/hr");
  });
});
