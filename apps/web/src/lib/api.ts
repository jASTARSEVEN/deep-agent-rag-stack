/** React 前端使用的 API client 與受保護請求輔助函式。 */

import { appConfig } from "./config";
import type {
  ApiHealthPayload,
  AreaAccessPayload,
  AreaListPayload,
  AreaSummary,
  DocumentListPayload,
  DocumentSummary,
  AuthContextPayload,
  IngestJobSummary,
  UploadDocumentPayload,
} from "./types";


/** 提供目前 access token 的非同步 getter。 */
export type AccessTokenGetter = () => Promise<string | null>;

/** 全域 access token getter；由 auth provider 在啟動時注入。 */
let accessTokenGetter: AccessTokenGetter = async () => null;


/**
 * 讓 auth provider 註冊目前的 access token getter。
 *
 * @param nextGetter 之後所有受保護請求共用的 token getter。
 * @returns 無；僅更新模組內的 getter 參考。
 */
export function registerAccessTokenGetter(nextGetter: AccessTokenGetter): void {
  accessTokenGetter = nextGetter;
}


/**
 * 將瀏覽器層 fetch 失敗轉成較可判讀的訊息。
 *
 * @param error 原始 fetch 例外。
 * @returns 可直接顯示在 UI 的錯誤物件。
 */
function normalizeFetchError(error: unknown): Error {
  if (error instanceof Error && error.name === "TypeError") {
    return new Error(
      `無法連線到 API。請確認 API 是否啟動，且 API CORS 已允許目前前端來源：${window.location.origin}。`,
    );
  }
  return error instanceof Error ? error : new Error("發生未知的網路錯誤。");
}


/**
 * 解析 API 失敗回應，盡量提供可讀的錯誤訊息。
 *
 * @param response 非成功狀態的 fetch 回應。
 * @returns 可直接顯示在 UI 的錯誤訊息字串。
 */
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


/**
 * 建立受保護 API 請求 header。
 *
 * @returns 包含 Bearer token 與 JSON content type 的 request headers。
 */
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


/**
 * 建立受保護 API 請求 header，但不強制指定 content type。
 *
 * @returns 僅包含 Bearer token 的 request headers。
 */
async function buildBearerHeaders(): Promise<HeadersInit> {
  const token = await accessTokenGetter();
  if (!token) {
    throw new Error("目前尚未登入，無法呼叫受保護 API。");
  }
  return {
    Authorization: `Bearer ${token}`,
  };
}


/**
 * 發送受保護 API 請求並在失敗時拋出可讀訊息。
 *
 * @param path API 路徑。
 * @param init 額外的 fetch 初始化參數。
 * @returns 成功狀態下的原始 `Response`。
 */
async function fetchProtected(path: string, init?: RequestInit): Promise<Response> {
  let response: Response;
  try {
    response = await fetch(`${appConfig.apiBaseUrl}${path}`, {
      ...init,
      headers: {
        ...(await buildProtectedHeaders()),
        ...(init?.headers ?? {}),
      },
    });
  } catch (error) {
    throw normalizeFetchError(error);
  }
  if (!response.ok) {
    throw new Error(await readErrorMessage(response));
  }
  return response;
}


/**
 * 取得 landing page health panel 使用的 API health payload。
 *
 * @returns API health payload。
 */
export async function fetchApiHealth(): Promise<ApiHealthPayload> {
  let response: Response;
  try {
    response = await fetch(`${appConfig.apiBaseUrl}/health`);
  } catch (error) {
    throw normalizeFetchError(error);
  }
  if (!response.ok) {
    throw new Error(`未預期的 API 回應狀態：${response.status}`);
  }
  return (await response.json()) as ApiHealthPayload;
}


/**
 * 取得目前登入者對應的 auth context。
 *
 * @returns 已驗證使用者的最小 auth context。
 */
export async function fetchAuthContext(): Promise<AuthContextPayload> {
  const response = await fetchProtected("/auth/context");
  return (await response.json()) as AuthContextPayload;
}


/**
 * 讀取目前使用者可存取的 areas。
 *
 * @returns area list API payload。
 */
export async function fetchAreas(): Promise<AreaListPayload> {
  const response = await fetchProtected("/areas");
  return (await response.json()) as AreaListPayload;
}


/**
 * 建立新的 Knowledge Area。
 *
 * @param payload 要建立的 area 名稱與說明。
 * @returns 新建立 area 的摘要資料。
 */
export async function createArea(payload: { name: string; description: string }): Promise<AreaSummary> {
  const response = await fetchProtected("/areas", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return (await response.json()) as AreaSummary;
}


/**
 * 讀取單一 area 詳細資料。
 *
 * @param areaId 要查詢的 area 識別碼。
 * @returns 指定 area 的摘要資料。
 */
export async function fetchAreaDetail(areaId: string): Promise<AreaSummary> {
  const response = await fetchProtected(`/areas/${areaId}`);
  return (await response.json()) as AreaSummary;
}


/**
 * 讀取單一 area 的 access 管理內容。
 *
 * @param areaId 要查詢 access 規則的 area 識別碼。
 * @returns 指定 area 的 access 管理 payload。
 */
export async function fetchAreaAccess(areaId: string): Promise<AreaAccessPayload> {
  const response = await fetchProtected(`/areas/${areaId}/access`);
  return (await response.json()) as AreaAccessPayload;
}


/**
 * 整體替換單一 area 的 access 規則。
 *
 * @param areaId 要更新 access 規則的 area 識別碼。
 * @param payload 新的 users/groups 規則內容。
 * @returns 更新後的 area access payload。
 */
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


/**
 * 讀取指定 area 內文件。
 *
 * @param areaId 要查詢文件的 area 識別碼。
 * @returns 指定 area 的文件列表 payload。
 */
export async function fetchDocuments(areaId: string): Promise<DocumentListPayload> {
  const response = await fetchProtected(`/areas/${areaId}/documents`);
  return (await response.json()) as DocumentListPayload;
}


/**
 * 上傳單一文件並建立 ingest job。
 *
 * @param areaId 文件所屬 area 識別碼。
 * @param file 要上傳的單一檔案。
 * @returns 本次上傳建立的 document 與 ingest job payload。
 */
export async function uploadDocument(areaId: string, file: File): Promise<UploadDocumentPayload> {
  const formData = new FormData();
  formData.append("file", file);
  let response: Response;
  try {
    response = await fetch(`${appConfig.apiBaseUrl}/areas/${areaId}/documents`, {
      method: "POST",
      headers: await buildBearerHeaders(),
      body: formData,
    });
  } catch (error) {
    throw normalizeFetchError(error);
  }
  if (!response.ok) {
    throw new Error(await readErrorMessage(response));
  }
  return (await response.json()) as UploadDocumentPayload;
}


/**
 * 讀取單一文件詳情。
 *
 * @param documentId 要查詢的文件識別碼。
 * @returns 指定文件的摘要資料。
 */
export async function fetchDocumentDetail(documentId: string): Promise<DocumentSummary> {
  const response = await fetchProtected(`/documents/${documentId}`);
  return (await response.json()) as DocumentSummary;
}


/**
 * 讀取單一 ingest job 詳情。
 *
 * @param jobId 要查詢的 ingest job 識別碼。
 * @returns 指定 ingest job 的摘要資料。
 */
export async function fetchIngestJob(jobId: string): Promise<IngestJobSummary> {
  const response = await fetchProtected(`/ingest-jobs/${jobId}`);
  return (await response.json()) as IngestJobSummary;
}
