# Web 模組

[English README](README.md)

## 模組目的

此模組包含專案的 React + Tailwind 前端。它目前提供匿名首頁、Keycloak 正式登入 / callback 流程，以及登入後的 Areas / Files 管理頁。

## 啟動方式

- 本機 Node 執行：
  - `npm install`
  - `npm run dev`
- 本機驗證正式登入：
  - 確保 Keycloak 與 API 已可用
  - 開啟 `http://localhost:3000` 或 compose 對外網址
  - 由首頁進入 Keycloak，完成登入後回到 `/areas`
- 本機執行 Playwright E2E：
  - `npm install`
  - `npx playwright install chromium`
  - `npm run test:e2e`
- 本機執行真實 Keycloak smoke：
  - 先確認 compose stack 的 `web`、`api`、`keycloak` 已啟動
  - `npm install`
  - `npx playwright install chromium`
  - `npm run test:smoke:keycloak`
- Docker Compose：
  - `docker compose -f ../../infra/docker-compose.yml --env-file ../../.env up web`

## 環境變數

- `VITE_APP_NAME`
- `VITE_API_BASE_URL`
- `VITE_AUTH_MODE`
- `VITE_KEYCLOAK_URL`
- `VITE_KEYCLOAK_REALM`
- `VITE_KEYCLOAK_CLIENT_ID`

## 主要目錄結構

- `src/main.tsx`：應用程式啟動入口
- `src/app/App.tsx`：router 與 auth provider 入口
- `src/auth`: Keycloak / test auth mode、session persistence 與 protected route
- `src/pages`: 匿名首頁、callback 與 Areas 頁
- `src/features/chat`：LangGraph SDK transport、chat state 與 chat/debug UI
- `src/components`: Reusable UI blocks
- `src/lib`: Environment and API helpers
- `tests/e2e`: Playwright E2E 測試、bootstrap 與本機 test-mode API 啟動腳本
- `playwright.config.ts`：Playwright 執行設定

## 對外介面

- 瀏覽器路由：`/`
- 瀏覽器路由：`/auth/callback`
- 瀏覽器路由：`/areas`
- 使用 `VITE_API_BASE_URL + /health` 顯示 API health 狀態
- 使用 `VITE_API_BASE_URL + /auth/context` 建立登入後 principal
- 使用 `VITE_API_BASE_URL + /areas*` 執行 Area create/list/detail、access management 與 files upload/list
- 使用 `VITE_API_BASE_URL + /documents/*`、`/ingest-jobs/*` 顯示文件狀態、chunk 摘要、reindex、delete 與 job stage
- `npm run test:e2e`：啟動 Playwright、web dev server 與 test-mode API 自動化驗證
- `npm run test:smoke:keycloak`：直接對 compose 的真實 Keycloak / callback / logout 流程做 smoke 驗證

## 疑難排解

- 若頁面顯示 API 錯誤，請確認 API container 健康且 `VITE_API_BASE_URL` 設定正確。
- 若 Areas 頁出現 `Failed to fetch` 或無法連線到 API，請確認 `API_CORS_ORIGINS` 已包含目前前端來源；本機預設應至少包含 `http://localhost:3000` 與 `http://localhost:13000`。
- 若登入後 callback 無法回到前端，請確認 Keycloak client `deep-agent-web` 的 redirect URI 與 `VITE_KEYCLOAK_URL`、`VITE_KEYCLOAK_CLIENT_ID` 一致。
- 若 area API 一直出現 `401`，請確認 Keycloak token 內仍含 `groups` claim，且 API issuer / JWKS 設定正確。
- `VITE_AUTH_MODE=test` 僅供 Playwright 與本機測試，不可當成正式登入驗證結論。
- `npm run test:e2e` 使用 test auth mode，不會覆蓋真實 Keycloak issuer、callback、logout 與 SSO 行為；這些問題需由 `npm run test:smoke:keycloak` 補驗。
- files 仍整合在 `/areas` 頁；chat 則透過 `src/features/chat` 掛載，並使用 LangGraph SDK 預設 thread/run 端點串接。UI 會顯示 Deep Agents 任務進度，並顯示 assembler 後的 contexts，而不是 child-level citations。
- 若 `npm run test:e2e` 失敗於瀏覽器缺失，請先執行 `npx playwright install chromium`。
- 若 `npm run test:smoke:keycloak` 失敗，請先確認 compose stack 已完成啟動，且 `deep-agent-dev` realm 仍可用 `alice / alice123` 登入。
- 若 E2E 啟動失敗，請先確認 `python`、`uvicorn` 與 `apps/api` 依賴已可在本機 shell 執行。
