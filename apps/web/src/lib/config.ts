/** React 前端骨架使用的執行期設定。 */

import type { PlannedService } from "./types";


/** 前端支援的 auth 模式。 */
export type AuthMode = "keycloak" | "test";


// 顯示在 landing page 上、可由前端讀取的應用程式名稱。
export const appConfig = {
  appName: import.meta.env.VITE_APP_NAME ?? "Deep Agent RAG Stack",
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL ?? "http://localhost:18000",
  authMode: (import.meta.env.VITE_AUTH_MODE ?? "keycloak") as AuthMode,
  keycloakUrl: import.meta.env.VITE_KEYCLOAK_URL ?? "http://localhost:18080",
  keycloakRealm: import.meta.env.VITE_KEYCLOAK_REALM ?? "deep-agent-dev",
  keycloakClientId: import.meta.env.VITE_KEYCLOAK_CLIENT_ID ?? "deep-agent-web",
};


// 顯示在 landing page 上、用來說明 stack 接線的本機服務清單。
export const plannedServices: PlannedService[] = [
  { name: "postgres", kind: "database", description: "未來應用資料使用的主要關聯式資料庫預留服務。" },
  { name: "redis", kind: "queue", description: "提供未來背景工作使用的 Celery broker 與 result backend。" },
  { name: "minio", kind: "storage", description: "提供未來文件原始檔使用的 S3 相容物件儲存。" },
  { name: "keycloak", kind: "identity", description: "提供未來登入與群組授權使用的 OIDC 身分服務。" },
  { name: "api", kind: "backend", description: "提供 landing 與 health 端點的 FastAPI 骨架服務。" },
  { name: "worker", kind: "background", description: "具備最小 ping task 的 Celery 骨架 worker。" },
  { name: "web", kind: "frontend", description: "負責驗證 API 連線狀態的 React 前端骨架。" },
];
