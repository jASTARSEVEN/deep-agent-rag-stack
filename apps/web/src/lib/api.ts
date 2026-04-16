/** React 前端使用的 API client 與受保護請求輔助函式。 */

import { appConfig } from "./config";
import type {
  ApiHealthPayload,
  AreaAccessPayload,
  AreaListPayload,
  AreaSummary,
  ChatSessionListPayload,
  ChatSessionSummary,
  UpdateAreaPayload,
  DocumentListPayload,
  DocumentPreviewPayload,
  DocumentSummary,
  AuthContextPayload,
  IngestJobSummary,
  ReindexDocumentPayload,
  UploadDocumentPayload,
  EvaluationCandidatePreviewPayload,
  EvaluationDatasetDetailPayload,
  EvaluationDatasetSummary,
  EvaluationItemSummary,
  EvaluationProfile,
  EvaluationPreviewDebugPayload,
  EvaluationQueryType,
  EvaluationRunReportPayload,
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


interface RawPreviewChunkPayload {
  /** chunk 關聯的 locator。 */
  regions?: Array<{
    page_number: number;
    region_order: number;
    bbox_left: number;
    bbox_bottom: number;
    bbox_right: number;
    bbox_top: number;
  }>;
  /** chunk 唯一識別碼。 */
  chunk_id: string;
  /** chunk 所屬 parent chunk 識別碼。 */
  parent_chunk_id: string | null;
  /** parent 下 child 順序。 */
  child_index: number | null;
  /** chunk 所屬標題。 */
  heading: string | null;
  /** chunk 內容結構型別。 */
  structure_kind: "text" | "table";
  /** chunk 在全文中的起始 offset。 */
  start_offset: number;
  /** chunk 在全文中的結束 offset。 */
  end_offset: number;
  /** 起始頁碼。 */
  page_start?: number | null;
  /** 結束頁碼。 */
  page_end?: number | null;
}


interface RawDocumentPreviewPayload {
  /** 文件識別碼。 */
  document_id: string;
  /** 文件名稱。 */
  file_name: string;
  /** 文件 MIME 類型。 */
  content_type: string;
  /** 目前後端可能仍回傳的舊欄位。 */
  normalized_text?: string;
  /** 文件全文顯示文字。 */
  display_text?: string;
  /** child chunk map。 */
  chunks: RawPreviewChunkPayload[];
}


/**
 * 將後端 preview 回應正規化為前端正式契約。
 *
 * @param payload 後端回傳的原始 JSON。
 * @returns 供前端預覽使用的標準化 payload。
 */
function normalizeDocumentPreviewPayload(payload: RawDocumentPreviewPayload): DocumentPreviewPayload {
  const displayText =
    typeof payload.display_text === "string" && payload.display_text
      ? payload.display_text
      : typeof payload.normalized_text === "string"
        ? payload.normalized_text
        : "";

  if (!displayText) {
    throw new Error("文件預覽回應缺少 display_text。");
  }

  return {
    document_id: payload.document_id,
    file_name: payload.file_name,
    content_type: payload.content_type,
    display_text: displayText,
    chunks: payload.chunks.map((chunk) => ({
      chunk_id: chunk.chunk_id,
      parent_chunk_id: chunk.parent_chunk_id,
      child_index: chunk.child_index,
      heading: chunk.heading,
      structure_kind: chunk.structure_kind,
      start_offset: chunk.start_offset,
      end_offset: chunk.end_offset,
      page_start: typeof chunk.page_start === "number" ? chunk.page_start : null,
      page_end: typeof chunk.page_end === "number" ? chunk.page_end : null,
      regions: Array.isArray(chunk.regions) ? chunk.regions : [],
    })),
  };
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
 * 讀取指定 area 目前使用者可見的 chat sessions。
 *
 * @param areaId 目標 area 識別碼。
 * @returns chat session 清單 payload。
 */
export async function fetchAreaChatSessions(areaId: string): Promise<ChatSessionListPayload> {
  const response = await fetchProtected(`/areas/${areaId}/chat-sessions`);
  const payload = (await response.json()) as {
    items: Array<{
      thread_id: string;
      title: string;
      created_at: string;
      updated_at: string;
    }>;
  };
  return {
    items: payload.items.map((item) => ({
      threadId: item.thread_id,
      title: item.title,
      createdAt: item.created_at,
      updatedAt: item.updated_at,
    })),
  };
}


/**
 * 註冊既有 LangGraph thread 為正式 chat session metadata。
 *
 * @param areaId 目標 area 識別碼。
 * @param payload 要註冊的 thread 與可選 title。
 * @returns 建立或既有的 chat session 摘要。
 */
export async function registerAreaChatSession(
  areaId: string,
  payload: { threadId?: string | null; title?: string | null } = {},
): Promise<ChatSessionSummary> {
  const response = await fetchProtected(`/areas/${areaId}/chat-sessions`, {
    method: "POST",
    body: JSON.stringify({
      thread_id: payload.threadId ?? null,
      title: payload.title ?? null,
    }),
  });
  const item = (await response.json()) as {
    thread_id: string;
    title: string;
    created_at: string;
    updated_at: string;
  };
  return {
    threadId: item.thread_id,
    title: item.title,
    createdAt: item.created_at,
    updatedAt: item.updated_at,
  };
}


/**
 * 更新既有 chat session metadata。
 *
 * @param areaId 目標 area 識別碼。
 * @param threadId 目標 thread 識別碼。
 * @param payload 可選的新 title；缺省時只 touch `updated_at`。
 * @returns 更新後的 chat session 摘要。
 */
export async function updateAreaChatSession(
  areaId: string,
  threadId: string,
  payload: { title?: string | null } = {},
): Promise<ChatSessionSummary> {
  const response = await fetchProtected(`/areas/${areaId}/chat-sessions/${threadId}`, {
    method: "PATCH",
    body: JSON.stringify({
      title: payload.title ?? null,
    }),
  });
  const item = (await response.json()) as {
    thread_id: string;
    title: string;
    created_at: string;
    updated_at: string;
  };
  return {
    threadId: item.thread_id,
    title: item.title,
    createdAt: item.created_at,
    updatedAt: item.updated_at,
  };
}


/**
 * 刪除既有 chat session metadata。
 *
 * @param areaId 目標 area 識別碼。
 * @param threadId 目標 thread 識別碼。
 * @returns Promise<void>：刪除成功後結束。
 */
export async function deleteAreaChatSession(areaId: string, threadId: string): Promise<void> {
  await fetchProtected(`/areas/${areaId}/chat-sessions/${threadId}`, {
    method: "DELETE",
  });
}


/**
 * 讀取指定 area 的 evaluation datasets。
 *
 * @param areaId 目標 area 識別碼。
 * @returns 指定 area 的 evaluation dataset 清單。
 */
export async function fetchEvaluationDatasets(areaId: string): Promise<{ items: EvaluationDatasetSummary[] }> {
  const response = await fetchProtected(`/areas/${areaId}/evaluation/datasets`);
  return (await response.json()) as { items: EvaluationDatasetSummary[] };
}


/**
 * 建立新的 evaluation dataset。
 *
 * @param areaId 目標 area 識別碼。
 * @param payload 建立 payload。
 * @returns 新建立的 dataset。
 */
export async function createEvaluationDataset(
  areaId: string,
  payload: { name: string; query_type: EvaluationQueryType },
): Promise<EvaluationDatasetSummary> {
  const response = await fetchProtected(`/areas/${areaId}/evaluation/datasets`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return (await response.json()) as EvaluationDatasetSummary;
}


/**
 * 讀取 evaluation dataset detail。
 *
 * @param datasetId 目標 dataset 識別碼。
 * @returns dataset detail。
 */
export async function fetchEvaluationDatasetDetail(datasetId: string): Promise<EvaluationDatasetDetailPayload> {
  const response = await fetchProtected(`/evaluation/datasets/${datasetId}`);
  return (await response.json()) as EvaluationDatasetDetailPayload;
}


/**
 * 刪除單一 evaluation dataset。
 *
 * @param datasetId 要刪除的 dataset 識別碼。
 * @returns 無；刪除成功時只回傳 204。
 */
export async function deleteEvaluationDataset(datasetId: string): Promise<void> {
  const response = await fetchProtected(`/evaluation/datasets/${datasetId}`, {
    method: "DELETE",
  });
  if (response.status !== 204) {
    throw new Error(`未預期的 API 回應狀態：${response.status}`);
  }
}


/**
 * 建立 evaluation item。
 *
 * @param datasetId 目標 dataset 識別碼。
 * @param payload 建立 payload。
 * @returns 新建立的題目摘要。
 */
export async function createEvaluationItem(
  datasetId: string,
  payload: {
    query_text: string;
    language: "zh-TW" | "en" | "mixed";
    query_type?: EvaluationQueryType;
    notes?: string | null;
  },
): Promise<EvaluationItemSummary> {
  const response = await fetchProtected(`/evaluation/datasets/${datasetId}/items`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return (await response.json()) as EvaluationItemSummary;
}


/**
 * 刪除單一 evaluation 題目。
 *
 * @param datasetId 題目所屬 dataset 識別碼。
 * @param itemId 要刪除的題目識別碼。
 * @returns 無；刪除成功時只回傳 204。
 */
export async function deleteEvaluationItem(datasetId: string, itemId: string): Promise<void> {
  const response = await fetchProtected(`/evaluation/datasets/${datasetId}/items/${itemId}`, {
    method: "DELETE",
  });
  if (response.status !== 204) {
    throw new Error(`未預期的 API 回應狀態：${response.status}`);
  }
}


/**
 * 讀取單題的 candidate preview。
 *
 * @param datasetId 目標 dataset 識別碼。
 * @param itemId 目標 item 識別碼。
 * @returns candidate preview。
 */
export async function fetchEvaluationCandidatePreview(
  datasetId: string,
  itemId: string,
  payload: EvaluationPreviewDebugPayload = {},
): Promise<EvaluationCandidatePreviewPayload> {
  const response = await fetchProtected(`/evaluation/datasets/${datasetId}/items/${itemId}/candidate-preview`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return (await response.json()) as EvaluationCandidatePreviewPayload;
}


/**
 * 為題目新增 gold span。
 *
 * @param datasetId 目標 dataset 識別碼。
 * @param itemId 目標 item 識別碼。
 * @param payload span payload。
 * @returns 更新後的題目摘要。
 */
export async function createEvaluationSpan(
  datasetId: string,
  itemId: string,
  payload: { document_id: string; start_offset: number; end_offset: number; relevance_grade: 2 | 3 },
): Promise<EvaluationItemSummary> {
  const response = await fetchProtected(`/evaluation/datasets/${datasetId}/items/${itemId}/spans`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return (await response.json()) as EvaluationItemSummary;
}


/**
 * 將題目標記為 retrieval miss。
 *
 * @param datasetId 目標 dataset 識別碼。
 * @param itemId 目標 item 識別碼。
 * @returns 更新後的題目摘要。
 */
export async function markEvaluationMiss(datasetId: string, itemId: string): Promise<EvaluationItemSummary> {
  const response = await fetchProtected(`/evaluation/datasets/${datasetId}/items/${itemId}/mark-miss`, {
    method: "POST",
  });
  return (await response.json()) as EvaluationItemSummary;
}


/**
 * 執行 benchmark run。
 *
 * @param datasetId 目標 dataset 識別碼。
 * @param payload run payload。
 * @returns 完整 benchmark report。
 */
export async function runEvaluationDataset(
  datasetId: string,
  payload: { top_k?: number; evaluation_profile?: EvaluationProfile } = {},
): Promise<EvaluationRunReportPayload> {
  const response = await fetchProtected(`/evaluation/datasets/${datasetId}/runs`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return (await response.json()) as EvaluationRunReportPayload;
}


/**
 * 讀取既有 benchmark run。
 *
 * @param runId 目標 run 識別碼。
 * @returns 完整 benchmark report。
 */
export async function fetchEvaluationRun(runId: string): Promise<EvaluationRunReportPayload> {
  const response = await fetchProtected(`/evaluation/runs/${runId}`);
  return (await response.json()) as EvaluationRunReportPayload;
}


/**
 * 更新單一 area 的名稱與說明。
 *
 * @param areaId 要更新的 area 識別碼。
 * @param payload 更新後的名稱與說明。
 * @returns 更新後的 area 摘要資料。
 */
export async function updateArea(areaId: string, payload: UpdateAreaPayload): Promise<AreaSummary> {
  const response = await fetchProtected(`/areas/${areaId}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
  return (await response.json()) as AreaSummary;
}


/**
 * 刪除單一 area 與其關聯資料。
 *
 * @param areaId 要刪除的 area 識別碼。
 * @returns 無；成功時僅代表刪除完成。
 */
export async function deleteArea(areaId: string): Promise<void> {
  await fetchProtected(`/areas/${areaId}`, {
    method: "DELETE",
  });
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
 * 讀取單一文件的全文預覽內容與 chunk map。
 *
 * @param documentId 要查詢的文件識別碼。
 * @returns 文件全文預覽 payload。
 */
export async function fetchDocumentPreview(documentId: string): Promise<DocumentPreviewPayload> {
  const response = await fetchProtected(`/documents/${documentId}/preview`);
  return normalizeDocumentPreviewPayload((await response.json()) as RawDocumentPreviewPayload);
}


/**
 * 重新建立單一文件的 ingest job 與 chunks。
 *
 * @param documentId 要重建索引的文件識別碼。
 * @returns 重建後的文件與新 ingest job payload。
 */
export async function reindexDocument(
  documentId: string,
  options?: { forceReparse?: boolean },
): Promise<ReindexDocumentPayload> {
  const searchParams = new URLSearchParams();
  if (options?.forceReparse) {
    searchParams.set("force_reparse", "true");
  }
  const query = searchParams.size > 0 ? `?${searchParams.toString()}` : "";
  const response = await fetchProtected(`/documents/${documentId}/reindex${query}`, {
    method: "POST",
  });
  return (await response.json()) as ReindexDocumentPayload;
}


/**
 * 刪除單一文件與相關索引資料。
 *
 * @param documentId 要刪除的文件識別碼。
 * @returns 無；成功時僅代表刪除完成。
 */
export async function deleteDocument(documentId: string): Promise<void> {
  await fetchProtected(`/documents/${documentId}`, {
    method: "DELETE",
  });
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

/**
 * 依據關鍵字搜尋系統使用者。
 *
 * @param query 要搜尋的關鍵字。
 * @returns 符合條件的使用者清單。
 */
export async function searchUsers(query: string) {
  const response = await fetchProtected(`/directory/users?q=${encodeURIComponent(query)}`);
  return await response.json();
}

/**
 * 依據關鍵字搜尋系統群組。
 *
 * @param query 要搜尋的關鍵字。
 * @returns 符合條件的群組清單。
 */
export async function searchGroups(query: string) {
  const response = await fetchProtected(`/directory/groups?q=${encodeURIComponent(query)}`);
  return await response.json();
}
