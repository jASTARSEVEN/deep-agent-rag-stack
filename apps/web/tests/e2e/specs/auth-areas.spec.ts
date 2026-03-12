/** Playwright E2E 測試正式登入流程下的匿名首頁與 Areas 操作頁。 */

import { expect, test } from "@playwright/test";


/** 以 test auth mode 指定角色登入。 */
async function loginAs(page, role: "admin" | "maintainer" | "reader" | "outsider"): Promise<void> {
  await page.goto("/");
  await page.getByTestId(`test-login-${role}`).click();
}


test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    window.sessionStorage.clear();
    window.localStorage.clear();
  });
});


test("匿名首頁可見登入入口與產品說明", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByText("Identity Gateway")).toBeVisible();
  await expect(page.getByTestId("login-button")).toBeVisible();
  await expect(page.getByText("登入後可做的事情")).toBeVisible();
});


test("未登入進 /areas 會要求登入", async ({ page }) => {
  await page.goto("/areas");

  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByTestId("login-button")).toBeVisible();
});


test("admin 可登入、建立 area 並更新 access 規則", async ({ page }) => {
  const newAreaName = `Playwright Area ${Date.now()}`;

  await loginAs(page, "admin");

  await expect(page).toHaveURL(/\/areas$/);
  await expect(page.getByTestId("auth-context-panel")).toContainText("sub: user-admin");

  await page.getByTestId("create-area-name").fill(newAreaName);
  await page.getByTestId("create-area-description").fill("由 Playwright 建立的 area。");
  await page.getByTestId("create-area-submit").click();

  await expect(page.getByTestId("areas-list")).toContainText(newAreaName);
  await expect(page.getByTestId("area-detail-panel")).toContainText(newAreaName);

  await page.getByTestId("access-users").fill("user-admin,admin\nuser-reader,reader");
  await page.getByTestId("access-groups").fill("/group/reader,reader");
  await page.getByTestId("save-access").click();

  await expect(page.getByTestId("access-summary")).toContainText("users: 2 筆");
  await expect(page.getByTestId("access-summary")).toContainText("groups: 1 筆");
});


test("reader 可看 detail 但不能管理 access", async ({ page }) => {
  await loginAs(page, "reader");

  await expect(page).toHaveURL(/\/areas$/);
  await expect(page.getByTestId("areas-list")).toContainText("Reader Handbook Area");
  await expect(page.getByTestId("area-detail-panel")).toContainText("Reader Handbook Area");
  await expect(page.getByText("目前角色只能檢視 area detail。若需要管理 access，必須使用 admin 身分。")).toBeVisible();
});


test("maintainer 可看 detail 但 access 管理區不可操作", async ({ page }) => {
  await loginAs(page, "maintainer");

  await expect(page).toHaveURL(/\/areas$/);
  await expect(page.getByTestId("areas-list")).toContainText("Maintainer Docs Area");
  await expect(page.getByTestId("area-detail-panel")).toContainText("Maintainer Docs Area");
  await expect(page.getByTestId("access-users")).toHaveCount(0);
});


test("outsider 會被 deny-by-default 擋下，area list 應為空", async ({ page }) => {
  await loginAs(page, "outsider");

  await expect(page).toHaveURL(/\/areas$/);
  await expect(page.getByTestId("areas-list")).toContainText("尚無可存取的 area。");
});


test("logout 後會回首頁並失去受保護頁能力", async ({ page }) => {
  await loginAs(page, "admin");

  await page.getByRole("button", { name: "登出" }).click();

  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByTestId("login-button")).toBeVisible();

  await page.goto("/areas");
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByTestId("login-button")).toBeVisible();
});
