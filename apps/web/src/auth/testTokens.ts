/** Playwright 與本機 test auth mode 使用的固定測試 token 定義。 */


/** 前端 test auth mode 可選角色。 */
export type TestAuthRole = "admin" | "maintainer" | "reader" | "outsider";


/** 各角色對應的測試 token。 */
export const TEST_ROLE_TOKENS: Record<TestAuthRole, string> = {
  admin: "test::user-admin::/group/admin",
  maintainer: "test::user-maintainer::/group/maintainer",
  reader: "test::user-reader::/group/reader",
  outsider: "test::user-outsider::/group/outsider",
};


/** 將 test role 轉成使用者可讀標籤。 */
export function getTestRoleLabel(role: TestAuthRole): string {
  return {
    admin: "Admin",
    maintainer: "Maintainer",
    reader: "Reader",
    outsider: "Outsider",
  }[role];
}
