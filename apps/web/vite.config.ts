/** React 前端 Vite 開發伺服器設定。 */

import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

/**
 * 建立 Vite 設定，並以環境變數控制開發伺服器允許的 Host 清單。
 *
 * @param configEnv Vite 啟動時提供的模式資訊。
 * @returns 套用 React plugin 與 dev server 白名單的 Vite 設定。
 */
export default defineConfig((configEnv) => {
  const env = loadEnv(configEnv.mode, process.cwd(), "");
  const allowedHosts = (env.WEB_ALLOWED_HOSTS ?? "localhost,127.0.0.1")
    .split(",")
    .map((host) => host.trim())
    .filter(Boolean);

  return {
    plugins: [react()],
    server: {
      host: true,
      allowedHosts,
    },
  };
});
