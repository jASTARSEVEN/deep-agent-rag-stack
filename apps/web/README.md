# Web 模組

## 模組目的

此模組包含專案的 React + Tailwind 前端骨架。它會渲染一個 landing page，說明目前 MVP 骨架狀態，並透過 `/health` 端點驗證 API 接線。

## 啟動方式

- 本機 Node 執行：
  - `npm install`
  - `npm run dev`
- Docker Compose：
  - `docker compose -f ../../infra/docker-compose.yml --env-file ../../.env up web`

## 環境變數

- `VITE_APP_NAME`
- `VITE_API_BASE_URL`

## 主要目錄結構

- `src/main.tsx`：應用程式啟動入口
- `src/app/App.tsx`：主 landing page
- `src/components`: Reusable UI blocks
- `src/lib`: Environment and API helpers

## 對外介面

- 瀏覽器路由：`/`
- 使用 `VITE_API_BASE_URL + /health` 顯示 API health 狀態

## 疑難排解

- 若頁面顯示 API 錯誤，請確認 API container 健康且 `VITE_API_BASE_URL` 設定正確。
- 本輪的 Tailwind 只配置到骨架 UI 所需的最小範圍。
- login、areas、files、access、chat 頁面目前刻意尚未實作。
