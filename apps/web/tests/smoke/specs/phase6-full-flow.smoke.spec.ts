import { test, expect } from '@playwright/test';

test.describe('Phase 6 Full Flow Smoke Test', () => {
  test('應可完成登入、創區、上傳與問答完整流程', async ({ page }) => {
    // 監聽控制台輸出
    page.on('console', msg => console.log(`BROWSER [${msg.type()}]: ${msg.text()}`));

    // 1. 訪問首頁
    console.log('Visiting Home Page...');
    await page.goto('http://localhost:13000', { waitUntil: 'networkidle' });
    
    // 2. 登入流程
    if (await page.getByText('前往 Areas').isVisible()) {
      console.log('Already authenticated, proceeding to Areas...');
      await page.click('text=前往 Areas');
    } else {
      console.log('Clicking login button...');
      await page.click('button[data-testid="login-button"]');
      
      console.log('Waiting for Keycloak login page...');
      await page.waitForURL(/.*18080.*/, { timeout: 20000 });
      await page.fill('#username', 'alice');
      await page.fill('#password', 'alice123');
      await page.click('#kc-login');
    }

    // 3. 驗證進入 Areas 頁
    console.log('Waiting for Areas Page...');
    await page.waitForURL(/.*areas/, { timeout: 20000 });
    await expect(page.getByText('Knowledge Areas')).toBeVisible();

    // 4. 建立新 Area
    console.log('Creating Area...');
    const areaName = `Test-Area-${Date.now()}`;
    await page.fill('input[data-testid="create-area-name"]', areaName);
    await page.fill('textarea[data-testid="create-area-description"]', 'Phase 6 Integration Test');
    await page.click('button[data-testid="create-area-submit"]');
    
    // 等待 Area 列表更新並點擊
    console.log(`Waiting for Area "${areaName}" to appear...`);
    await page.waitForSelector(`text=${areaName}`, { timeout: 15000 });
    await page.click(`text=${areaName}`);

    // 5. 打開文件管理抽屜並上傳
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

    // 6. 等待處理完成 (Status: ready)
    console.log('Waiting for document to be ready...');
    // 檢查是否有 ready 字樣
    await expect(page.getByText('ready')).toBeVisible({ timeout: 60000 });
    
    // 關閉抽屜 (按 Esc)
    await page.keyboard.press('Escape');

    // 7. 進行對話測試
    console.log('Starting Chat...');
    const chatInput = page.getByPlaceholder('Ask a question...');
    await chatInput.fill('這份測試文件是關於什麼的？');
    await page.keyboard.press('Enter');

    // 8. 驗證 AI 回答
    console.log('Waiting for AI response...');
    // 檢查是否出現包含關鍵字的回答
    await expect(page.getByText(/Phase 6|Supabase|整合/)).toBeVisible({ timeout: 40000 });
    
    console.log('✅ Phase 6 Full Flow Test Passed!');
  });
});
