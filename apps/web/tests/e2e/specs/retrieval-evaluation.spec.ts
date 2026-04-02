/** Playwright E2E 測試 Phase 7 retrieval evaluation drawer。 */

import { expect, test } from "@playwright/test";


test.describe.configure({ mode: "serial" });

let sharedEvaluationAreaName = "";


async function loginAs(page, role: "admin" | "maintainer" | "reader"): Promise<void> {
  await page.goto("/");
  await page.getByTestId(`test-login-${role}`).click();
  await expect(page).toHaveURL(/\/areas$/);
}


test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    window.sessionStorage.clear();
    window.localStorage.clear();
  });
});


test("admin 可建立 evaluation dataset、標註 span 並執行 benchmark", async ({ page }) => {
  sharedEvaluationAreaName = `Eval Area ${Date.now()}`;

  await loginAs(page, "admin");

  await page.getByTestId("create-area-name").fill(sharedEvaluationAreaName);
  await page.getByTestId("create-area-description").fill("Phase 7 evaluation E2E area");
  await page.getByTestId("create-area-submit").click();
  await expect(page.getByTestId("areas-list")).toContainText(sharedEvaluationAreaName);

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

  await page.getByRole("button", { name: "管理文件" }).click();
  const uploadButton = page.getByTestId("upload-document-submit");
  const documentsList = page.getByTestId("documents-list");
  for (const file of [
    {
      name: "alpha-zh.md",
      mimeType: "text/markdown",
      buffer: Buffer.from("# Alpha\nAlpha policy keeps zh-TW facts.\n", "utf-8"),
    },
    {
      name: "beta-en.md",
      mimeType: "text/markdown",
      buffer: Buffer.from("# Beta\nBeta policy keeps English facts.\n", "utf-8"),
    },
    {
      name: "gamma-mixed.md",
      mimeType: "text/markdown",
      buffer: Buffer.from("# Gamma\nGamma policy mixes zh-TW and English facts.\n", "utf-8"),
    },
  ]) {
    await page.getByTestId("document-upload").setInputFiles(file);
    await expect(uploadButton).toBeEnabled();
    await uploadButton.click();
    await expect(page.getByText(`已上傳：${file.name}`)).toBeVisible();
    await expect(documentsList).toContainText(file.name);
  }
  for (const fileName of ["alpha-zh.md", "beta-en.md", "gamma-mixed.md"]) {
    const documentCard = documentsList.locator("article").filter({ hasText: fileName });
    await expect(documentCard).toContainText("ready");
    await expect(documentCard).toContainText("JOB: succeeded");
  }
  await page.getByLabel("Close documents drawer").click();

  await page.getByRole("button", { name: "評測 / 標註" }).click();
  await page.getByTestId("evaluation-dataset-name").fill("Phase 7 Dataset");
  await page.getByTestId("evaluation-create-dataset").click();
  await expect(page.getByTestId("evaluation-datasets-list")).toContainText("Phase 7 Dataset");

  await page.getByTestId("evaluation-item-query").fill("zh-TW facts");
  await page.getByTestId("evaluation-item-language").selectOption("zh-TW");
  await page.getByTestId("evaluation-create-item").click();
  await expect(page.getByTestId("evaluation-items-list")).toContainText("zh-TW facts");
  await expect(page.getByTestId("evaluation-stage-recall")).toBeVisible();

  await page.getByTestId("evaluation-document-search-hits").getByRole("button", { name: /alpha-zh\.md/i }).click();
  await expect(page.getByTestId("evaluation-document-preview")).toContainText("Alpha policy keeps zh-TW facts.");
  await page.getByTestId("evaluation-document-preview").evaluate((element: HTMLTextAreaElement) => {
    const target = "Alpha policy keeps zh-TW facts.";
    const start = element.value.indexOf(target);
    const end = start + target.length;
    element.focus();
    element.setSelectionRange(start, end);
    element.dispatchEvent(new Event("select", { bubbles: true }));
  });
  await page.getByTestId("evaluation-span-relevance").selectOption("3");
  await page.getByTestId("evaluation-add-span").click();
  await expect(page.getByText("已新增 gold source span。")).toBeVisible();

  await page.getByTestId("evaluation-run-benchmark").click();
  await expect(page.getByTestId("evaluation-run-report")).toContainText("Summary Metrics");
  await expect(page.getByTestId("evaluation-per-query-list")).toContainText("zh-TW facts");

  await page.getByTestId("evaluation-dataset-name").fill("Disposable Dataset");
  await page.getByTestId("evaluation-create-dataset").click();
  await expect(page.getByTestId("evaluation-datasets-list")).toContainText("Disposable Dataset");
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByTestId(/^evaluation-delete-dataset-/).filter({ hasText: "刪除" }).last().click();
  await expect(page.getByText("已刪除 dataset。")).toBeVisible();
  await expect(page.getByTestId("evaluation-datasets-list")).not.toContainText("Disposable Dataset");
});


test("maintainer 可看到 evaluation 入口", async ({ page }) => {
  await loginAs(page, "maintainer");
  await expect(page.getByTestId("areas-list")).toContainText(sharedEvaluationAreaName);
  await page.getByTestId("areas-list").getByRole("button", { name: new RegExp(sharedEvaluationAreaName) }).first().click();
  await expect(page.getByRole("button", { name: "評測 / 標註" })).toBeVisible();
});


test("reader 不可看到 evaluation 入口", async ({ page }) => {
  await loginAs(page, "reader");
  await expect(page.getByTestId("areas-list")).toContainText(sharedEvaluationAreaName);
  await page.getByTestId("areas-list").getByRole("button", { name: new RegExp(sharedEvaluationAreaName) }).first().click();
  await expect(page.getByRole("button", { name: "評測 / 標註" })).toHaveCount(0);
});
