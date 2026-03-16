import type { Page } from "@playwright/test";
import { TEST_ROLE_TOKENS, type TestAuthRole } from "../../src/auth/testTokens";

/**
 * 快速執行 test auth mode 登入，直接寫入 sessionStorage 繞過 UI。
 * 
 * @param page Playwright Page 物件。
 * @param role 要登入的角色 ("admin" | "maintainer" | "reader")。
 * @param baseUrl 應用的根路徑 (預設為 http://localhost:5173)。
 */
export async function fastLogin(page: Page, role: TestAuthRole, baseUrl: string = "http://localhost:5173") {
  const token = TEST_ROLE_TOKENS[role];
  const [, sub, rawGroups] = token.split("::", 3);
  const groups = rawGroups ? rawGroups.split(",").filter(Boolean) : [];
  
  const principal = {
    sub,
    groups,
    authenticated: true,
  };

  // 1. 先前往頁面，確保 sessionStorage 是針對該 domain
  await page.goto(baseUrl);

  // 2. 注入 sessionStorage 內容
  await page.evaluate(({ token, principal }) => {
    sessionStorage.setItem("deep-agent-auth-access-token", token);
    sessionStorage.setItem("deep-agent-auth-test-principal", JSON.stringify(principal));
  }, { token, principal });

  // 3. 重新導向至首頁或功能頁，觸發 AuthProvider 初始化
  await page.goto(`${baseUrl}/areas`);
  
  // 4. 等待登入狀態載入完成 (可根據 UI 特徵判斷)
  await page.waitForSelector("nav");
}
