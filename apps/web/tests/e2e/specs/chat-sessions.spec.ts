/** Playwright E2E 測試正式存後端的 chat session 主流程。 */

import { expect, test, type Page } from "@playwright/test";

test.describe.configure({ mode: "serial" });


/**
 * 以 test auth mode 指定角色登入。
 *
 * @param page Playwright page 物件。
 * @param role 要使用的測試角色。
 * @returns 無；僅推進登入流程。
 */
async function loginAs(page: Page, role: "admin" | "maintainer" | "reader" | "outsider"): Promise<void> {
  await page.goto("/");
  await page.getByTestId(`test-login-${role}`).click();
  await expect(page).toHaveURL(/\/areas$/);
}


/**
 * 建立供 chat session 測試使用的 area，並授權 reader / maintainer。
 *
 * @param page Playwright page 物件。
 * @param areaName 新 area 名稱。
 * @returns 無；僅完成 area 與 access 初始化。
 */
async function createSharedSessionArea(page: Page, areaName: string): Promise<void> {
  await loginAs(page, "admin");
  await page.getByTestId("create-area-name").fill(areaName);
  await page.getByTestId("create-area-description").fill("Chat session E2E area");
  await page.getByTestId("create-area-submit").click();
  await expect(page.getByTestId("areas-list")).toContainText(areaName);
  await expect(page.getByTestId("area-detail-panel")).toContainText(areaName);

  await page.getByRole("button", { name: "權限設定" }).click();
  await page.getByTestId("access-groups-input").fill("/group/reader");
  await page.getByTestId("access-group-role").selectOption("reader");
  await page.getByTestId("access-groups-add").click();
  await page.getByTestId("access-groups-input").fill("/group/maintainer");
  await page.getByTestId("access-group-role").selectOption("maintainer");
  await page.getByTestId("access-groups-add").click();
  await page.getByTestId("save-access").click();
  await expect(page.getByText("已成功更新存取權限規則。")).toBeVisible();
  await page.getByLabel("Close access modal").click();
}


/**
 * 切換到指定 area。
 *
 * @param page Playwright page 物件。
 * @param areaName 目標 area 名稱。
 * @returns 無；僅切換目前選取的 area。
 */
async function selectArea(page: Page, areaName: string): Promise<void> {
  await page.getByTestId("areas-list").getByRole("button", { name: new RegExp(areaName) }).first().click();
  await expect(page.getByTestId("area-detail-panel")).toContainText(areaName);
}


/**
 * 送出 chat 問題並等待 assistant 回應完成。
 *
 * @param page Playwright page 物件。
 * @param question 要送出的問題。
 * @returns 無；僅推進 chat 流程。
 */
async function submitChatQuestion(page: Page, question: string): Promise<void> {
  await page.getByTestId("chat-question").fill(question);
  await page.getByTestId("chat-submit").click();
  await expect(page.getByTestId("chat-message-user").last()).toContainText(question);
  await expect(page.getByTestId("chat-message-assistant").last()).not.toContainText("回應中...");
}


/**
 * 將指定 thread 標記為 stale，模擬 LangGraph thread state 404。
 *
 * @param page Playwright page 物件。
 * @param threadId 目標 thread 識別碼。
 * @returns 無；僅通知 E2E API 後續回 404。
 */
async function markThreadStale(page: Page, threadId: string): Promise<void> {
  const response = await page.request.post(`http://127.0.0.1:18001/__e2e/threads/${threadId}/mark-stale`);
  expect(response.ok()).toBeTruthy();
}


test("reader 建立新 session 後 reload 仍可看到 session list", async ({ page }) => {
  const areaName = `Session List ${Date.now()}`;
  await createSharedSessionArea(page, areaName);

  await page.getByRole("button", { name: "登出" }).click();
  await loginAs(page, "reader");
  await selectArea(page, areaName);

  await submitChatQuestion(page, "reader policy");
  await expect(page.getByTestId("chat-session-select")).toContainText("reader policy");

  await page.getByTestId("chat-new-session").click();
  await expect(page.getByTestId("chat-session-select")).toContainText("新對話");

  await page.reload();
  await expect(page.getByTestId("areas-list")).toContainText(areaName);
  await selectArea(page, areaName);
  await expect(page.getByTestId("chat-session-select")).toContainText("reader policy");
  await expect(page.getByTestId("chat-session-select")).toContainText("新對話");
});


test("沒有既有 session 時直接送出第一題會自動建立 session 並顯示在 selector", async ({ page }) => {
  const areaName = `Session Auto Create ${Date.now()}`;
  await createSharedSessionArea(page, areaName);

  await page.getByRole("button", { name: "登出" }).click();
  await loginAs(page, "reader");
  await selectArea(page, areaName);

  await expect(page.getByTestId("chat-session-select")).toContainText("尚未建立 session");
  await submitChatQuestion(page, "reader policy");

  await expect(page.getByTestId("chat-message-assistant").last()).toContainText("Reader Handbook");
  await expect(page.getByTestId("chat-session-select")).toContainText("reader policy");
  await expect.poll(async () => page.getByTestId("chat-session-select").inputValue()).not.toBe("");
  await expect(page.getByTestId("chat-session-select").locator("option:checked")).toContainText("reader policy");
  await expect(page.getByTestId("chat-session-select").locator("option:checked")).not.toContainText("新對話");
});


test("手動建立新對話後，第一題會把 session title 改成問題", async ({ page }) => {
  const areaName = `Session Rename ${Date.now()}`;
  await createSharedSessionArea(page, areaName);

  await page.getByRole("button", { name: "登出" }).click();
  await loginAs(page, "reader");
  await selectArea(page, areaName);

  await page.getByTestId("chat-new-session").click();
  await expect(page.getByTestId("chat-session-select").locator("option:checked")).toContainText("新對話");

  await submitChatQuestion(page, "reader policy");

  await expect(page.getByTestId("chat-message-assistant").last()).toContainText("Reader Handbook");
  await expect(page.getByTestId("chat-session-select").locator("option:checked")).toContainText("reader policy");
  await expect(page.getByTestId("chat-session-select").locator("option:checked")).not.toContainText("新對話");
});


test("切回既有 session 會回填 LangGraph 歷史訊息", async ({ page }) => {
  const areaName = `Session Switch ${Date.now()}`;
  await createSharedSessionArea(page, areaName);

  await page.getByRole("button", { name: "登出" }).click();
  await loginAs(page, "reader");
  await selectArea(page, areaName);

  await submitChatQuestion(page, "reader policy");
  const firstSessionId = await page.getByTestId("chat-session-select").inputValue();

  await page.getByTestId("chat-new-session").click();
  await expect.poll(async () => page.getByTestId("chat-session-select").inputValue()).not.toBe(firstSessionId);
  const secondSessionId = await page.getByTestId("chat-session-select").inputValue();
  await expect(page.getByTestId("chat-message-user")).toHaveCount(0);
  await expect(page.getByTestId("chat-message-assistant")).toHaveCount(0);

  await page.getByTestId("chat-session-select").selectOption(firstSessionId);
  await expect(page.getByTestId("chat-message-user").last()).toContainText("reader policy");
  await expect(page.getByTestId("chat-message-assistant").last()).toContainText("Reader Handbook");
});


test("同一使用者跨新 page context 可恢復後端保存的 sessions", async ({ browser, page }) => {
  const areaName = `Session MultiPage ${Date.now()}`;
  await createSharedSessionArea(page, areaName);

  await page.getByRole("button", { name: "登出" }).click();
  await loginAs(page, "reader");
  await selectArea(page, areaName);
  await submitChatQuestion(page, "reader policy");

  const secondPage = await browser.newPage();
  await secondPage.addInitScript(() => {
    window.sessionStorage.clear();
    window.localStorage.clear();
  });
  await loginAs(secondPage, "reader");
  await selectArea(secondPage, areaName);

  await expect(secondPage.getByTestId("chat-session-select")).toContainText("reader policy");
  await expect(secondPage.getByTestId("chat-message-user").last()).toContainText("reader policy");
  await expect(secondPage.getByTestId("chat-message-assistant").last()).toContainText("Reader Handbook");
  await secondPage.close();
});


test("thread state 404 時會自動刪除 stale session metadata", async ({ page }) => {
  const areaName = `Session Stale ${Date.now()}`;
  await createSharedSessionArea(page, areaName);

  await page.getByRole("button", { name: "登出" }).click();
  await loginAs(page, "reader");
  await selectArea(page, areaName);
  await submitChatQuestion(page, "reader policy");

  const staleThreadId = await page.getByTestId("chat-session-select").inputValue();
  await markThreadStale(page, staleThreadId);
  await page.reload();
  await selectArea(page, areaName);

  await expect(page.getByTestId("chat-session-select")).toContainText("尚未建立 session");
  await expect(page.getByTestId("chat-session-select")).not.toContainText("reader policy");
  await expect(page.getByTestId("chat-message-user")).toHaveCount(0);
});


test("session 僅對建立者可見", async ({ page }) => {
  const areaName = `Session Privacy ${Date.now()}`;
  await createSharedSessionArea(page, areaName);

  await page.getByRole("button", { name: "登出" }).click();
  await loginAs(page, "reader");
  await selectArea(page, areaName);
  await submitChatQuestion(page, "reader policy");

  await page.getByRole("button", { name: "登出" }).click();
  await loginAs(page, "maintainer");
  await selectArea(page, areaName);

  await expect(page.getByTestId("chat-session-select")).not.toContainText("reader policy");
  await expect(page.getByTestId("chat-message-user")).toHaveCount(0);
  await expect(page.getByTestId("chat-message-assistant")).toHaveCount(0);
});


test("area 刪除後 session metadata 不再可見", async ({ page }) => {
  const areaName = `Session Delete ${Date.now()}`;
  await createSharedSessionArea(page, areaName);
  await submitChatQuestion(page, "reader policy");
  await expect(page.getByTestId("chat-session-select")).toContainText("reader policy");

  page.on("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "刪除區域" }).click();

  await expect(page.getByTestId("areas-list")).not.toContainText(areaName);
  await expect(page.getByTestId("workspace-notice")).toContainText(`已刪除區域：${areaName}`);
  await expect(page.getByTestId("chat-session-select")).toHaveCount(0);
});
