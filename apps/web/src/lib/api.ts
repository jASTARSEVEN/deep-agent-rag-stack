/** React 前端使用的 API client 與受保護請求輔助函式。 */

import { appConfig } from "./config";
import type {
  ApiHealthPayload,
  AreaAccessPayload,
  AreaListPayload,
  AreaSummary,
  AuthContextPayload,
} from "./types";


/** 提供目前 access token 的非同步 getter。 */
export type AccessTokenGetter = () => Promise<string | null>;

/** 全域 access token getter；由 auth provider 在啟動時注入。 */
let accessTokenGetter: AccessTokenGetter = async () => null;


/** 讓 auth provider 註冊目前的 access token getter。 */
export function registerAccessTokenGetter(nextGetter: AccessTokenGetter): void {
  accessTokenGetter = nextGetter;
}


/** 解析 API 失敗回應，盡量提供可讀的錯誤訊息。 */
async function readErrorMessage(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: string };
    if (typeof payload.detail === "string" && payload.detail) {
      return payload.detail;
    }
  } catch {
    return `未預期的 API 回應狀態：${response.status}`;
  }
  return `未預期的 API 回應狀態：${response.status}`;
}


/** 建立受保護 API 請求 header。 */
async function buildProtectedHeaders(): Promise<HeadersInit> {
  const token = await accessTokenGetter();
  if (!token) {
    throw new Error("目前尚未登入，無法呼叫受保護 API。");
  }
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
  };
}


/** 發送受保護 API 請求並在失敗時拋出可讀訊息。 */
async function fetchProtected(path: string, init?: RequestInit): Promise<Response> {
  const response = await fetch(`${appConfig.apiBaseUrl}${path}`, {
    ...init,
    headers: {
      ...(await buildProtectedHeaders()),
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    throw new Error(await readErrorMessage(response));
  }
  return response;
}


/** 取得 landing page health panel 使用的 API health payload。 */
export async function fetchApiHealth(): Promise<ApiHealthPayload> {
  const response = await fetch(`${appConfig.apiBaseUrl}/health`);
  if (!response.ok) {
    throw new Error(`未預期的 API 回應狀態：${response.status}`);
  }
  return (await response.json()) as ApiHealthPayload;
}


/** 取得目前登入者對應的 auth context。 */
export async function fetchAuthContext(): Promise<AuthContextPayload> {
  const response = await fetchProtected("/auth/context");
  return (await response.json()) as AuthContextPayload;
}


/** 讀取目前使用者可存取的 areas。 */
export async function fetchAreas(): Promise<AreaListPayload> {
  const response = await fetchProtected("/areas");
  return (await response.json()) as AreaListPayload;
}


/** 建立新的 Knowledge Area。 */
export async function createArea(payload: { name: string; description: string }): Promise<AreaSummary> {
  const response = await fetchProtected("/areas", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return (await response.json()) as AreaSummary;
}


/** 讀取單一 area 詳細資料。 */
export async function fetchAreaDetail(areaId: string): Promise<AreaSummary> {
  const response = await fetchProtected(`/areas/${areaId}`);
  return (await response.json()) as AreaSummary;
}


/** 讀取單一 area 的 access 管理內容。 */
export async function fetchAreaAccess(areaId: string): Promise<AreaAccessPayload> {
  const response = await fetchProtected(`/areas/${areaId}/access`);
  return (await response.json()) as AreaAccessPayload;
}


/** 整體替換單一 area 的 access 規則。 */
export async function replaceAreaAccess(
  areaId: string,
  payload: Pick<AreaAccessPayload, "users" | "groups">,
): Promise<AreaAccessPayload> {
  const response = await fetchProtected(`/areas/${areaId}/access`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
  return (await response.json()) as AreaAccessPayload;
}
