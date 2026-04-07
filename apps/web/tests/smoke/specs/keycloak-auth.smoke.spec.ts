/** 真實 Keycloak 認證 smoke 測試，驗證公開入口 `/auth/*` 路徑。 */

import { expect, test } from "@playwright/test";

import { loginViaPublicKeycloak, openSmokeHomePage } from "../support/publicEntry";


test.describe("真實 Keycloak smoke", () => {
  test("login -> logout -> relogin 流程應可正常完成", async ({ page }) => {
    await loginViaPublicKeycloak(page);

    await expect(page.getByTestId("auth-context-panel")).toContainText("groups: /dept/hr");

    await page.getByRole("button", { name: "登出" }).click();

    await page.waitForURL(/\/$/);
    await expect(page.getByTestId("login-button")).toBeVisible();
    await expect(page.getByText("目前尚未登入。")).toBeVisible();

    await openSmokeHomePage(page);
    await loginViaPublicKeycloak(page);

    await expect(page.getByTestId("auth-context-panel")).toContainText("groups: /dept/hr");
  });
});
