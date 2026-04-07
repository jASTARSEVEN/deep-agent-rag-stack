/** Compose full-flow smoke，驗證公開入口 login、upload、ready 與 chat 主路徑。 */

import { test, expect } from '@playwright/test';

import { createAndOpenSmokeArea, loginViaPublicKeycloak } from "../support/publicEntry";

test.describe('Phase 6 Full Flow Smoke Test', () => {
  test('應可完成登入、創區、上傳與問答完整流程', async ({ page }) => {
    // 監聽控制台輸出
    page.on('console', msg => console.log(`BROWSER [${msg.type()}]: ${msg.text()}`));

    // 1. 登入流程
    console.log('Waiting for Areas Page...');
    await loginViaPublicKeycloak(page);

    // 2. 建立新 Area
    console.log('Creating Area...');
    const areaName = `Test-Area-${Date.now()}`;
    await createAndOpenSmokeArea(page, {
      areaName,
      description: 'Phase 6 Integration Test',
    });

    // 3. 打開文件管理抽屜並上傳
    console.log('Opening Documents Drawer...');
    await page.click('button:has-text("管理文件")');
    
    console.log('Uploading Document...');
    const fileContent = "Deep Agent RAG Stack Phase 6 測試文件。這是一份關於 Supabase 整合的說明。";
    const fileName = `test-doc-${Date.now()}.txt`;
    
    // 使用 input 選擇檔案
    await page.setInputFiles('input[data-testid="document-upload"]', {
      name: fileName,
      mimeType: 'text/plain',
      buffer: Buffer.from(fileContent),
    });
    
    await page.click('button[data-testid="upload-document-submit"]');

    // 4. 等待處理完成 (Status: ready)
    console.log('Waiting for document to be ready...');
    const documentCard = page.getByTestId("documents-list").locator("article").filter({ hasText: fileName });
    await expect(documentCard).toContainText("ready", { timeout: 60000 });
    
    // 關閉抽屜 (按 Esc)
    await page.keyboard.press('Escape');

    // 5. 進行對話測試
    console.log('Starting Chat...');
    const chatInput = page.getByPlaceholder('Type your question here...');
    await chatInput.fill('Supabase 整合的說明是關於什麼？');
    await page.keyboard.press('Enter');

    // 6. 驗證 AI 回答
    console.log('Waiting for AI response...');
    const assistantMessage = page.getByTestId('chat-message-assistant').last();
    await expect(assistantMessage).toContainText(/Phase 6|Supabase|整合/, { timeout: 40000 });
    
    console.log('✅ Phase 6 Full Flow Test Passed!');
  });
});
