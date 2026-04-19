/** 前端 UI state 與 chat view-model 使用的本機型別。 */

import type {
  ChatAnswerBlock,
  ChatAssembledContext,
  ChatCitation,
  ChatDisplayCitation,
} from "../generated/chat";
import type { ApiHealthPayload, AuthContextPayload } from "../generated/rest";

export type { ChatAnswerBlock, ChatDisplayCitation };


/** landing page 上顯示的服務中繼資料。 */
export interface PlannedService {
  /** 服務名稱。 */
  name: string;
  /** 服務分類，例如 api、queue、storage。 */
  kind: string;
  /** 用於 UI 顯示的服務用途說明。 */
  description: string;
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


/** 前端 area chat session 摘要 view-model。 */
export interface ChatSessionViewModel {
  /** LangGraph thread 識別碼。 */
  threadId: string;
  /** 前端顯示用 session 標題。 */
  title: string;
  /** session 建立時間。 */
  createdAt: string;
  /** 最近一次互動時間。 */
  updatedAt: string;
}


/** Chat 的可選思考模式。 */
export type ChatSynthesisMode = "disabled" | "summary_compare";


/** 單一 assembled context reference。 */
export type ChatContextReference = (ChatCitation | ChatAssembledContext) & {
  /** context 組裝後全文；若未提供則回退使用 excerpt。 */
  assembled_text?: string;
};


/** LangGraph custom event 對應的高層 chat 階段。 */
export type ChatPhase = "preparing" | "thinking" | "searching" | "tool_calling" | "drafting";


/** Phase 8C tool debug summary 的 latency budget 狀態。 */
export type ChatToolCallLatencyBudgetStatus = "within_budget" | "normal" | "degraded" | "warning" | "failed";


/** Tool output 內單一 planning document 的最小顯示型別。 */
export interface ChatToolCallPlanningDocument {
  /** 後端核發的短期文件 handle。 */
  handle?: string;
  /** 文件名稱。 */
  document_name?: string;
  /** 是否由 query 直接提及。 */
  mentioned_by_query?: boolean;
  /** 本輪是否命中。 */
  hit_in_current_round?: boolean;
  /** 是否可檢視 synopsis hint。 */
  synopsis_available?: boolean;
}


/** Tool output 的可選 coverage signals。 */
export interface ChatToolCallCoverageSignals {
  /** 目前仍缺少直接證據的文件名稱。 */
  missing_document_names?: string[];
  /** 目前是否已具備可比較的基礎。 */
  supports_compare?: boolean;
  /** 是否仍屬證據不足。 */
  insufficient_evidence?: boolean;
  /** 目前仍缺少的比較面向。 */
  missing_compare_axes?: string[];
  /** follow-up 是否找到新證據。 */
  new_evidence_found?: boolean;
}


/** Tool output 的最小 debug summary 型別。 */
export interface ChatToolCallOutputSummary extends Record<string, unknown> {
  /** 本輪 tool call 次數。 */
  tool_call_count?: number;
  /** follow-up 次數。 */
  followup_call_count?: number;
  /** synopsis 檢視次數。 */
  synopsis_inspection_count?: number;
  /** latency budget 狀態。 */
  latency_budget_status?: ChatToolCallLatencyBudgetStatus | string;
  /** loop 停止原因。 */
  stop_reason?: string;
  /** coverage planning 訊號。 */
  coverage_signals?: ChatToolCallCoverageSignals;
  /** planning document 清單。 */
  planning_documents?: ChatToolCallPlanningDocument[];
  /** 建議的下一步 follow-up。 */
  next_best_followups?: string[];
}


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
  output: ChatToolCallOutputSummary | null;
}


/** 前端 chat 訊息 view model。 */
export interface ChatMessageViewModel {
  /** 訊息唯一識別碼。 */
  id: string;
  /** 訊息角色。 */
  role: "user" | "assistant";
  /** 保留原始串流文字，供增量解析 citation marker 使用。 */
  rawContent: string;
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
  /** 本輪使用的 synthesis mode。 */
  synthesisMode?: ChatSynthesisMode | null;
  /** 目前被選取的 citation context。 */
  selectedCitationContextIndex: number | null;
}


/** API health 請求生命週期使用的本機元件狀態。 */
export type ApiHealthState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "success"; payload: ApiHealthPayload };
