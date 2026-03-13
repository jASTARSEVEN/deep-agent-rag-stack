/** React 前端骨架 UI 使用的共用型別。 */


/** landing page 上顯示的服務中繼資料。 */
export interface PlannedService {
  /** 服務名稱。 */
  name: string;
  /** 服務分類，例如 api、queue、storage。 */
  kind: string;
  /** 用於 UI 顯示的服務用途說明。 */
  description: string;
}


/** FastAPI 骨架服務回傳的 API health payload。 */
export interface ApiHealthPayload {
  /** 服務健康狀態。 */
  status: string;
  /** 服務名稱。 */
  service: string;
  /** 服務版本號。 */
  version: string;
}


/** 已驗證使用者的最小 auth context。 */
export interface AuthContextPayload {
  /** 使用者唯一識別 `sub`。 */
  sub: string;
  /** access token 內的群組列表。 */
  groups: string[];
  /** 是否已通過驗證。 */
  authenticated: boolean;
}


/** 前端 auth provider 對外暴露的 session 狀態。 */
export interface AuthSessionState {
  /** 是否仍在還原或驗證 session。 */
  isLoading: boolean;
  /** 目前是否已登入。 */
  isAuthenticated: boolean;
  /** 目前 session 持有的 access token。 */
  accessToken: string | null;
  /** 目前登入者的 principal。 */
  principal: AuthContextPayload | null;
}


/** Area 角色型別。 */
export type AreaRole = "reader" | "maintainer" | "admin";


/** Area list 與 detail 共用的 API 型別。 */
export interface AreaSummary {
  /** Area 唯一識別碼。 */
  id: string;
  /** Area 顯示名稱。 */
  name: string;
  /** Area 補充說明。 */
  description: string | null;
  /** 目前使用者在此 area 的 effective role。 */
  effective_role: AreaRole;
  /** Area 建立時間。 */
  created_at: string;
  /** Area 最後更新時間。 */
  updated_at: string;
}


/** Area list API payload。 */
export interface AreaListPayload {
  /** 目前使用者可存取的 area 清單。 */
  items: AreaSummary[];
}


/** 單一 user access entry。 */
export interface AccessUserEntry {
  /** 被授權使用者的 `sub`。 */
  user_sub: string;
  /** 指派給該使用者的角色。 */
  role: AreaRole;
}


/** 單一 group access entry。 */
export interface AccessGroupEntry {
  /** 被授權 Keycloak group path。 */
  group_path: string;
  /** 指派給該群組的角色。 */
  role: AreaRole;
}


/** Area access management payload。 */
export interface AreaAccessPayload {
  /** Access 規則所屬 area。 */
  area_id: string;
  /** 直接使用者角色映射列表。 */
  users: AccessUserEntry[];
  /** 群組角色映射列表。 */
  groups: AccessGroupEntry[];
}


/** 文件處理狀態。 */
export type DocumentStatus = "uploaded" | "processing" | "ready" | "failed";


/** 背景 ingest job 狀態。 */
export type IngestJobStatus = "queued" | "processing" | "succeeded" | "failed";


/** 文件或 ingest job 的 chunk 摘要。 */
export interface ChunkSummary {
  /** chunk 總數。 */
  total_chunks: number;
  /** parent chunk 數量。 */
  parent_chunks: number;
  /** child chunk 數量。 */
  child_chunks: number;
  /** 最近一次成功完成 indexing 的時間。 */
  last_indexed_at: string | null;
}


/** 單一文件摘要。 */
export interface DocumentSummary {
  /** 文件唯一識別碼。 */
  id: string;
  /** 文件所屬 area。 */
  area_id: string;
  /** 使用者上傳時的原始檔名。 */
  file_name: string;
  /** 上傳時記錄的 MIME 類型。 */
  content_type: string;
  /** 原始檔大小，單位為 bytes。 */
  file_size: number;
  /** 文件目前處理狀態。 */
  status: DocumentStatus;
  /** 文件 chunk 摘要。 */
  chunk_summary: ChunkSummary;
  /** 文件建立時間。 */
  created_at: string;
  /** 文件最後更新時間。 */
  updated_at: string;
}


/** 單一 ingest job 摘要。 */
export interface IngestJobSummary {
  /** 背景 job 唯一識別碼。 */
  id: string;
  /** 此 job 對應的文件識別碼。 */
  document_id: string;
  /** job 目前狀態。 */
  status: IngestJobStatus;
  /** job 目前執行階段。 */
  stage: string;
  /** job chunk 摘要。 */
  chunk_summary: ChunkSummary;
  /** job 失敗時的可讀錯誤訊息。 */
  error_message: string | null;
  /** job 建立時間。 */
  created_at: string;
  /** job 最後更新時間。 */
  updated_at: string;
}


/** area 文件列表 payload。 */
export interface DocumentListPayload {
  /** 指定 area 內目前可見的文件清單。 */
  items: DocumentSummary[];
}


/** 單一文件上傳回應。 */
export interface UploadDocumentPayload {
  /** 剛建立的文件摘要。 */
  document: DocumentSummary;
  /** 與本次上傳對應的 ingest job 摘要。 */
  job: IngestJobSummary;
}


/** 單一文件 reindex 回應。 */
export interface ReindexDocumentPayload {
  /** 重新派送後的文件摘要。 */
  document: DocumentSummary;
  /** 新建立的 ingest job 摘要。 */
  job: IngestJobSummary;
}


/** API health 請求生命週期使用的本機元件狀態。 */
export type ApiHealthState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "success"; payload: ApiHealthPayload };
