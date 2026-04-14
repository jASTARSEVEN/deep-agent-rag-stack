/** Playwright E2E 測試正式登入流程下的匿名首頁與 Areas 操作頁。 */

import { expect, test } from "@playwright/test";

test.describe.configure({ mode: "serial" });


/** 可被 local PDF parser 擷取文字的最小 PDF 測試樣本。 */
const MINIMAL_TEXT_PDF = Buffer.from(`%PDF-1.1
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 144] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>
endobj
4 0 obj
<< /Length 73 >>
stream
BT
/F1 18 Tf
50 100 Td
(Deep Agent PDF local parser sample) Tj
ET
endstream
endobj
5 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
xref
0 6
0000000000 65535 f 
0000000010 00000 n 
0000000063 00000 n 
0000000122 00000 n 
0000000248 00000 n 
0000000371 00000 n 
trailer
<< /Root 1 0 R /Size 6 >>
startxref
441
%%EOF
`, "utf-8");

/** 故意提供給 local PDF parser 的損毀 PDF 測試樣本。 */
const BROKEN_PDF = Buffer.from("%PDF-1.4 broken", "utf-8");

const DOCUMENT_READER_READY_ID = "00000000-0000-0000-0000-000000000101";
const DOCUMENT_MAINTAINER_READY_ID = "00000000-0000-0000-0000-000000000102";
const CHUNK_READER_CHILD_ID = "00000000-0000-0000-0000-000000000202";
const CHUNK_MAINTAINER_CHILD_ID = "00000000-0000-0000-0000-000000000204";
const SHARED_DOCUMENT_NAME = "playwright-notes.md";
const COMPARE_AREA_NAME = "Compare Travel Area";

let sharedAreaName = "";


/**
 * 以 test auth mode 指定角色登入。
 *
 * @param page Playwright page 物件。
 * @param role 要使用的測試角色。
 * @returns 無；僅推進登入流程。
 */
async function loginAs(page, role: "admin" | "maintainer" | "reader" | "outsider"): Promise<void> {
  await page.goto("/");
  await page.getByTestId(`test-login-${role}`).click();
}


/**
 * 切換到指定 area。
 *
 * @param page Playwright page 物件。
 * @param areaName 目標 area 名稱。
 * @returns 無；僅切換目前選取的 area。
 */
async function selectArea(page, areaName: string): Promise<void> {
  await page
    .getByTestId("areas-list")
    .locator("button")
    .filter({ hasText: areaName })
    .first()
    .click();
  await expect(page.getByTestId("area-detail-panel")).toContainText(areaName);
}


/**
 * 送出 chat 問題並等待 assistant 回應結束。
 *
 * @param page Playwright page 物件。
 * @param question 要送出的問題。
 * @returns 無；僅推進 chat 流程。
 */
async function submitChatQuestion(page, question: string): Promise<void> {
  await page.getByTestId("chat-question").fill(question);
  await page.getByTestId("chat-submit").click();
  await expect(page.getByTestId("chat-message-user").last()).toContainText(question);
  await expect(page.getByTestId("chat-message-assistant").last()).not.toContainText("回應中...");
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
  const renamedAreaName = `${newAreaName} Updated`;
  sharedAreaName = newAreaName;

  await loginAs(page, "admin");

  await expect(page).toHaveURL(/\/areas$/);
  await expect(page.getByTestId("auth-context-panel")).toContainText("sub: user-admin");

  await page.getByTestId("create-area-name").fill(newAreaName);
  await page.getByTestId("create-area-description").fill("由 Playwright 建立的 area。");
  await page.getByTestId("create-area-submit").click();

  await expect(page.getByTestId("areas-list")).toContainText(newAreaName);
  await expect(page.getByTestId("area-detail-panel")).toContainText(newAreaName);

  await page.getByRole("button", { name: "編輯區域" }).click();
  await page.getByTestId("edit-area-name").fill(renamedAreaName);
  await page.getByTestId("edit-area-description").fill("由 Playwright 更新的 area。");
  await page.getByTestId("save-area-settings").click();
  await expect(page.getByLabel("Close area edit modal")).toHaveCount(0);
  await expect(page.getByTestId("areas-list")).toContainText(renamedAreaName);
  await expect(page.getByTestId("area-detail-panel")).toContainText(renamedAreaName);
  sharedAreaName = renamedAreaName;

  // 打開權限設定
  await page.getByRole("button", { name: "權限設定" }).click();
  await page.getByTestId("access-groups-input").fill("/group/reader");
  await page.getByTestId("access-group-role").selectOption("reader");
  await page.getByTestId("access-groups-add").click();
  await page.getByTestId("access-groups-input").fill("/group/maintainer");
  await page.getByTestId("access-group-role").selectOption("maintainer");
  await page.getByTestId("access-groups-add").click();
  await page.getByTestId("save-access").click();

  await expect(page.getByText("已成功更新存取權限規則。")).toBeVisible();
  await expect(page.getByTestId("access-summary")).toContainText("1 位使用者");
  await expect(page.getByTestId("access-summary")).toContainText("2 個群組");
  await page.getByLabel("Close access modal").click(); // 關閉 Modal

  // 打開管理文件
  await page.getByRole("button", { name: "管理文件" }).click();
  await page.getByTestId("document-upload").setInputFiles({
    name: "playwright-notes.md",
    mimeType: "text/markdown",
    buffer: Buffer.from("# Playwright\nready\n"),
  });
  await page.getByTestId("upload-document-submit").click();

  await expect(page.getByTestId("documents-list")).toContainText("playwright-notes.md");
  await expect(page.getByTestId("documents-list")).toContainText("ready");
  await expect(page.getByTestId("documents-list")).toContainText("chunks");
});


test("reader 可看 detail 但不能管理 access", async ({ page }) => {
  await loginAs(page, "reader");

  await expect(page).toHaveURL(/\/areas$/);
  await expect(page.getByTestId("areas-list")).toContainText(sharedAreaName);
  await expect(page.getByTestId("area-detail-panel")).toContainText(sharedAreaName);
  await expect(page.getByText("目前角色只能檢視 area detail。若需要管理 access，必須使用 admin 身分。")).toBeVisible();
  await expect(page.getByRole("button", { name: "編輯區域" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "刪除區域" })).toHaveCount(0);
  
  // 打開管理文件
  await page.getByRole("button", { name: "管理文件" }).click();
  await expect(page.getByTestId("documents-list")).toContainText(SHARED_DOCUMENT_NAME);
  await expect(page.getByTestId("documents-list")).toContainText("2 chunks (1 parent / 1 child)");
  await page.getByRole("button", { name: SHARED_DOCUMENT_NAME }).click();
  await expect(page.getByTestId("document-chunk-list")).toContainText("Playwright");
  await expect(page.getByTestId("document-chunk-list")).toContainText("Chunk 1");
  await expect(page.getByTestId("document-chunk-list")).toContainText("ready");
  await expect(page.getByTestId("document-preview-pane")).toContainText("ready");
  await page.getByLabel("Close documents drawer").click(); // 關閉 Drawer

  await submitChatQuestion(page, "reader policy");
  await expect(page.getByTestId("chat-message-assistant").last()).toContainText("Reader Handbook");
  await expect(page.getByTestId("chat-tool-calls")).toContainText("retrieve_area_contexts");
  await expect(page.getByTestId("chat-tool-call-0")).toContainText("20s 內");
  
  // 再次打開確認權限限制
  await page.getByRole("button", { name: "管理文件" }).click();
  await expect(page.getByTestId("document-upload")).toHaveCount(0);
  await expect(page.getByText("重新索引")).toHaveCount(0);
});


test("reader compare 題會顯示 follow-up tool debug 與證據不足回覆", async ({ page }) => {
  await loginAs(page, "reader");
  await selectArea(page, COMPARE_AREA_NAME);

  await submitChatQuestion(page, "Compare Travel Policy and Expense Guidelines approval rules.");

  await expect(page.getByTestId("chat-message-assistant").last()).toContainText("證據不足以完成完整比較");
  await expect(page.getByTestId("chat-message-assistant").last()).toContainText("Travel Policy");
  await expect(page.getByTestId("chat-tool-call-0")).toContainText("共 1 次");
  await expect(page.getByTestId("chat-tool-call-0")).toContainText("20s 內");
  await expect(page.getByTestId("chat-tool-call-0")).toContainText("停止：followup_requested");
  await expect(page.getByTestId("chat-tool-call-1")).toContainText("共 2 次");
  await expect(page.getByTestId("chat-tool-call-1")).toContainText("follow-up 1 次");
  await expect(page.getByTestId("chat-tool-call-1")).toContainText("延遲降級");
  await expect(page.getByTestId("chat-tool-call-1")).toContainText("停止：latency_budget_soft_limit");
  await expect(page.getByTestId("chat-tool-call-1")).toContainText("證據不足");
});


test("reader 對未授權文件提問時不會從回答與 tool debug 洩漏文件名稱", async ({ page }) => {
  await loginAs(page, "reader");
  await selectArea(page, "Reader Handbook Area");

  await submitChatQuestion(page, "Compare reader handbook with maintainer guide.");

  await expect(page.getByTestId("chat-message-assistant").last()).toContainText("證據不足");
  await expect(page.getByTestId("chat-message-assistant").last()).not.toContainText("maintainer-guide.md");
  await expect(page.getByTestId("chat-message-assistant").last()).not.toContainText("processing-draft.md");

  const toolCall = page.getByTestId("chat-tool-call-0");
  await toolCall.locator("summary").first().click();
  await expect(toolCall).toContainText("reader-handbook.md");
  await expect(toolCall).not.toContainText("maintainer-guide.md");
  await expect(toolCall).not.toContainText("processing-draft.md");
});


test("maintainer 可看 detail 但 access 管理區不可操作", async ({ page }) => {
  await loginAs(page, "maintainer");

  await expect(page).toHaveURL(/\/areas$/);
  await expect(page.getByTestId("areas-list")).toContainText(sharedAreaName);
  await expect(page.getByTestId("area-detail-panel")).toContainText(sharedAreaName);
  await expect(page.getByTestId("access-users")).toHaveCount(0); // Access Modal 沒開的話本來就是 0，但原測試可能預期它在頁面中
  await expect(page.getByRole("button", { name: "編輯區域" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "刪除區域" })).toHaveCount(0);
  
  // 打開管理文件
  await page.getByRole("button", { name: "管理文件" }).click();
  await expect(page.getByTestId("documents-list")).toContainText(SHARED_DOCUMENT_NAME);
  await page.getByRole("button", { name: SHARED_DOCUMENT_NAME }).click();
  await expect(page.getByTestId("document-chunk-list")).toContainText("Playwright");
  await expect(page.getByTestId("document-preview-pane")).toContainText("ready");

  await page.getByTestId("document-upload").setInputFiles({
    name: "maintainer-upload.md",
    mimeType: "text/markdown",
    buffer: Buffer.from("# Maintainer\nupload\n"),
  });
  await page.getByTestId("upload-document-submit").click();

  await expect(page.getByTestId("documents-list")).toContainText("maintainer-upload.md");
  await expect(page.getByTestId("documents-list")).toContainText("ready");
  await page.getByTestId("documents-list").getByRole("button", { name: "重新索引" }).first().click();
  await expect(page.getByTestId("documents-list")).toContainText("JOB: succeeded");
});


test("admin 上傳 PDF 後會看到 ready 狀態", async ({ page }) => {
  const areaName = `PDF Area ${Date.now()}`;

  await loginAs(page, "admin");

  await expect(page).toHaveURL(/\/areas$/);
  await page.getByTestId("create-area-name").fill(areaName);
  await page.getByTestId("create-area-description").fill("PDF upload verification area");
  await page.getByTestId("create-area-submit").click();
  await expect(page.getByTestId("areas-list")).toContainText(areaName);
  await expect(page.getByTestId("area-detail-panel")).toContainText(areaName);
  await page.getByRole("button", { name: "管理文件" }).click();
  await page.getByTestId("document-upload").setInputFiles({
    name: "admin-guide.pdf",
    mimeType: "application/pdf",
    buffer: MINIMAL_TEXT_PDF,
  });
  await page.getByTestId("upload-document-submit").click();

  await expect(page.getByTestId("documents-list")).toContainText("admin-guide.pdf");
  await expect(page.getByTestId("documents-list")).toContainText("ready");
  await expect(page.getByTestId("documents-list")).toContainText("2 chunks (1 parent / 1 child)");
});


test("admin 上傳損毀 PDF 後會看到 failed 與錯誤訊息", async ({ page }) => {
  await loginAs(page, "admin");

  // 打開管理文件
  await page.getByRole("button", { name: "管理文件" }).click();
  await page.getByTestId("document-upload").setInputFiles({
    name: "broken.pdf",
    mimeType: "application/pdf",
    buffer: BROKEN_PDF,
  });
  await page.getByTestId("upload-document-submit").click();

  await expect(page.getByTestId("documents-list")).toContainText("broken.pdf");
  await expect(page.getByTestId("documents-list")).toContainText("failed");
  await expect(page.getByTestId("documents-list")).toContainText("local PDF parser");
  await expect(page.getByTestId("documents-list")).toContainText("0 chunks (0 parent / 0 child)");
  await expect(page.getByTestId(/document-preview-unavailable-/).last()).toContainText("尚未可預覽");
});


test("maintainer 可刪除文件，刪除後列表應移除", async ({ page }) => {
  await loginAs(page, "maintainer");

  // 打開管理文件
  await page.getByRole("button", { name: "管理文件" }).click();
  await expect(page.getByTestId("documents-list")).toContainText(SHARED_DOCUMENT_NAME);

  // 攔截並自動接受確認對話框
  page.on("dialog", (dialog) => dialog.accept());

  const sharedDocumentCard = page.getByTestId("documents-list").locator("article").filter({ hasText: SHARED_DOCUMENT_NAME });
  await sharedDocumentCard.getByRole("button", { name: "刪除" }).click();
  await expect(page.getByTestId("documents-list")).not.toContainText(SHARED_DOCUMENT_NAME);
});


test("admin 可刪除 area，刪除後 sidebar 應移除該區域", async ({ page }) => {
  const areaName = `Delete Area ${Date.now()}`;

  await loginAs(page, "admin");

  await page.getByTestId("create-area-name").fill(areaName);
  await page.getByTestId("create-area-description").fill("Delete verification area");
  await page.getByTestId("create-area-submit").click();
  await expect(page.getByTestId("areas-list")).toContainText(areaName);
  await expect(page.getByTestId("area-detail-panel")).toContainText(areaName);

  await page.getByRole("button", { name: "管理文件" }).click();
  await page.getByTestId("document-upload").setInputFiles({
    name: "delete-area-doc.md",
    mimeType: "text/markdown",
    buffer: Buffer.from("# Delete Area\ncontent\n"),
  });
  await page.getByTestId("upload-document-submit").click();
  await expect(page.getByTestId("documents-list")).toContainText("delete-area-doc.md");
  await page.getByLabel("Close documents drawer").click();

  page.on("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "刪除區域" }).click();

  await expect(page.getByTestId("areas-list")).not.toContainText(areaName);
  await expect(page.getByTestId("workspace-notice")).toContainText(`已刪除區域：${areaName}`);
});


test("outsider 會被 deny-by-default 擋下，area list 應為空", async ({ page }) => {
  await loginAs(page, "outsider");

  await expect(page).toHaveURL(/\/areas$/);
  await expect(page.getByTestId("areas-list")).toContainText("尚無可存取的 area。");
});


test("當 areas API 在瀏覽器層失敗時，頁面應顯示可診斷的連線錯誤", async ({ page }) => {
  await page.route("http://127.0.0.1:18001/areas", async (route) => {
    await route.abort("failed");
  });

  await loginAs(page, "admin");

  await expect(page).toHaveURL(/\/areas$/);
  await expect(page.getByTestId("workspace-error")).toContainText("無法連線到 API");
  await expect(page.getByTestId("workspace-error")).toContainText("API CORS");
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
