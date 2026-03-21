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
  /** 使用者姓名。 */
  name?: string | null;
  /** 使用者偏好帳號名稱。 */
  preferred_username?: string | null;
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


/** 使用者搜尋結果。 */
export interface UserSearchResult {
  username: string;
  email: string | null;
  firstName: string | null;
  lastName: string | null;
}

/** 群組搜尋結果。 */
export interface GroupSearchResult {
  path: string;
  name: string;
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


/** Area 更新請求 payload。 */
export interface UpdateAreaPayload {
  /** 更新後的 Area 顯示名稱。 */
  name: string;
  /** 更新後的 Area 補充說明。 */
  description: string | null;
}


/** Area list API payload。 */
export interface AreaListPayload {
  /** 目前使用者可存取的 area 清單。 */
  items: AreaSummary[];
}


/** 單一 user access entry。 */
export interface AccessUserEntry {
  /** 被授權使用者的 username。 */
  username: string;
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


/** chat citation 內容結構型別。 */
export type ChatStructureKind = "text" | "table";


/** 回答區塊句尾可點擊的 citation 顯示資料。 */
export interface ChatDisplayCitation {
  /** context 在回傳列表中的順序。 */
  context_index: number;
  /** 前端顯示用的穩定 citation label。 */
  context_label: string;
  /** context 所屬文件識別碼。 */
  document_id: string;
  /** context 所屬文件名稱。 */
  document_name: string;
  /** context 所屬段落標題。 */
  heading: string | null;
}


/** assistant 回答的單一顯示區塊。 */
export interface ChatAnswerBlock {
  /** 區塊文字內容。 */
  text: string;
  /** 此區塊引用的 context index 列表。 */
  citation_context_indices: number[];
  /** 句尾顯示用的 citations。 */
  display_citations: ChatDisplayCitation[];
}


/** 單一 assembled context reference。 */
export interface ChatContextReference {
  /** context 在回傳列表中的順序。 */
  context_index: number;
  /** 前端顯示用的穩定 citation label。 */
  context_label: string;
  /** context 所屬文件識別碼。 */
  document_id: string;
  /** context 所屬文件名稱。 */
  document_name: string;
  /** context 所屬 parent chunk 識別碼。 */
  parent_chunk_id: string | null;
  /** 合併進此 context 的 child chunk 識別碼。 */
  child_chunk_ids: string[];
  /** context 所屬段落標題。 */
  heading: string | null;
  /** context 內容結構型別。 */
  structure_kind: ChatStructureKind;
  /** context 在 normalized text 的起始 offset。 */
  start_offset: number;
  /** context 在 normalized text 的結束 offset。 */
  end_offset: number;
  /** context 組裝後文字摘要。 */
  excerpt: string;
  /** context 組裝後全文；若未提供則回退使用 excerpt。 */
  assembled_text?: string;
  /** context 來源，可能為 vector、fts 或 hybrid。 */
  source: string;
  /** 此 context 是否已被裁切。 */
  truncated: boolean;
}


/** LangGraph custom event 對應的高層 chat 階段。 */
export type ChatPhase = "thinking" | "searching" | "tool_calling";


/** 前端顯示用的 chat 階段狀態。 */
export interface ChatPhaseState {
  /** 目前階段。 */
  phase: ChatPhase;
  /** 階段狀態。 */
  status: "started" | "completed";
  /** 對應 UI 顯示訊息。 */
  message: string;
}


/** 前端顯示用的工具呼叫事件。 */
export interface ChatToolCallState {
  /** 工具名稱。 */
  name: string;
  /** 工具狀態。 */
  status: "started" | "completed";
  /** 工具輸入參數。 */
  input: Record<string, unknown>;
  /** 工具輸出摘要。 */
  output: Record<string, unknown> | null;
}

/** 全文預覽使用的 child chunk 範圍。 */
export interface PreviewChunk {
  /** child chunk 識別碼。 */
  chunk_id: string;
  /** 所屬 parent chunk 識別碼。 */
  parent_chunk_id: string | null;
  /** 同 parent 下的 child 順序。 */
  child_index: number | null;
  /** chunk 所屬標題。 */
  heading: string | null;
  /** chunk 內容結構型別。 */
  structure_kind: ChatStructureKind;
  /** chunk 在全文中的起始 offset。 */
  start_offset: number;
  /** chunk 在全文中的結束 offset。 */
  end_offset: number;
}


/** 文件全文預覽 payload。 */
export interface DocumentPreviewPayload {
  /** 文件識別碼。 */
  document_id: string;
  /** 文件名稱。 */
  file_name: string;
  /** 文件 MIME 類型。 */
  content_type: string;
  /** 供 preview 與 chunk 定位使用的顯示全文。 */
  display_text: string;
  /** child chunk map。 */
  chunks: PreviewChunk[];
}

/** 前端 chat 訊息 view model。 */
export interface ChatMessageViewModel {
  /** 訊息唯一識別碼。 */
  id: string;
  /** 訊息角色。 */
  role: "user" | "assistant";
  /** 訊息內容。 */
  content: string;
  /** assistant 回答區塊。 */
  answerBlocks: ChatAnswerBlock[];
  /** 助理訊息對應的 assembled context references。 */
  citations: ChatContextReference[];
  /** 助理目前所處的高層階段。 */
  phaseState: ChatPhaseState | null;
  /** 助理本輪工具呼叫摘要。 */
  toolCalls: ChatToolCallState[];
  /** 是否仍在串流中。 */
  isStreaming: boolean;
  /** 是否為錯誤訊息。 */
  isError: boolean;
  /** 本輪是否使用知識庫 references。 */
  usedKnowledgeBase: boolean | null;
  /** 目前被選取的 citation context。 */
  selectedCitationContextIndex: number | null;
}


/** API health 請求生命週期使用的本機元件狀態。 */
export type ApiHealthState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "success"; payload: ApiHealthPayload };
