/** React 前端骨架使用的 API 輔助函式。 */

import { appConfig } from "./config";
import type { ApiHealthPayload } from "./types";


/** 取得 landing page health panel 使用的 API health payload。 */
export async function fetchApiHealth(): Promise<ApiHealthPayload> {
  const response = await fetch(`${appConfig.apiBaseUrl}/health`);
  if (!response.ok) {
    throw new Error(`未預期的 API 回應狀態：${response.status}`);
  }
  return (await response.json()) as ApiHealthPayload;
}
