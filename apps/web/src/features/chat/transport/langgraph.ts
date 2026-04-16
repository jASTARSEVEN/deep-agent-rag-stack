/** Chat feature 使用的 LangGraph SDK transport。 */

import { Client } from "@langchain/langgraph-sdk";

import {
  deleteAreaChatSession,
  fetchAreaChatSessions,
  registerAreaChatSession,
  type AccessTokenGetter,
  updateAreaChatSession,
} from "../../../lib/api";
import { appConfig } from "../../../lib/config";
import type {
  ChatAnswerBlock,
  ChatContextReference,
  ChatPhaseState,
  ChatSessionSummary,
  ChatToolCallState,
} from "../../../lib/types";
import { resolveAnswerBlocks } from "../state/answerBlocks";


/** 舊版前端 session storage 使用的 area-thread mapping key。 */
const LEGACY_AREA_THREAD_STORAGE_KEY = "deep-agent.langgraph.area-threads";
/** 舊版前端 session storage 使用的 area-sessions metadata key。 */
const LEGACY_AREA_SESSION_STORAGE_KEY = "deep-agent.langgraph.area-sessions";
/** 目前前端 session storage 使用的 area-active-thread mapping key。 */
const ACTIVE_AREA_THREAD_STORAGE_KEY = "deep-agent.langgraph.active-area-threads";
/** 前端 session storage 使用的 LangGraph assistant id key。 */
const ASSISTANT_ID_STORAGE_KEY = "deep-agent.langgraph.assistant-id";
/** 新建 session 的預設標題。 */
const DEFAULT_SESSION_TITLE = "新對話";
/** 由問題自動產生 session 標題時的最大長度。 */
const SESSION_TITLE_MAX_LENGTH = 48;

/** LangGraph graph id；對應 `apps/api/langgraph.json` 的公開 graph 名稱。 */
const GRAPH_ID = "agent";

/** LangGraph thread state 內會出現的最小 message payload。 */
interface LangGraphStateMessage {
  /** LangChain / LangGraph message type。 */
  type?: string;
  /** OpenAI 風格 message role。 */
  role?: string;
  /** 訊息內容。 */
  content?: unknown;
}

/** LangGraph thread state 上的 assistant turn artifact。 */
interface LangGraphMessageArtifact {
  /** assistant turn 在 thread messages 內的順序。 */
  assistant_turn_index?: unknown;
  /** 回答區塊。 */
  answer_blocks?: unknown;
  /** assembled-context 引用資料。 */
  citations?: unknown;
  /** 是否使用知識庫。 */
  used_knowledge_base?: unknown;
}

/** LangGraph chat stream 的單次更新。 */
export interface LangGraphChatStreamUpdate {
  /** 本次 delta 文字；若無則為空值。 */
  delta?: string;
  /** 本次更新帶回的 assembled context references。 */
  references?: ChatContextReference[];
  /** 是否已完成整輪 run。 */
  completed?: boolean;
  /** 完成後的最終回答文字。 */
  answer?: string;
  /** 完成後的結構化回答區塊。 */
  answerBlocks?: ChatAnswerBlock[];
  /** 是否回傳 trace。 */
  trace?: Record<string, unknown>;
  /** 目前高層 chat 階段。 */
  phaseState?: ChatPhaseState | null;
  /** 目前工具呼叫狀態。 */
  toolCall?: ChatToolCallState;
  /** 本輪是否有使用知識庫 references。 */
  usedKnowledgeBase?: boolean;
}

/** 等待 run 結束後再提交到 UI 的最終 state 摘要。 */
interface PendingCompletionUpdate {
  /** 最終 references。 */
  references: ChatContextReference[];
  /** 最終回答文字。 */
  answer: string;
  /** 最終回答區塊。 */
  answerBlocks: ChatAnswerBlock[];
  /** 最終 trace。 */
  trace?: Record<string, unknown>;
  /** 本輪是否有使用知識庫 references。 */
  usedKnowledgeBase: boolean;
}

/** session storage 內單一 area session 的持久化格式。 */
interface StoredAreaSession {
  /** LangGraph thread 識別碼。 */
  threadId: string;
  /** 前端顯示用 session 標題。 */
  title: string;
  /** session 建立時間。 */
  createdAt: string;
  /** 最近一次互動時間。 */
  updatedAt: string;
}

/** session storage 內 area -> active thread 的持久化格式。 */
type StoredAreaThreadMap = Record<string, string>;

/** 正式 token 串流來源；`custom` 僅承載 phase 與 tool_call 等產品事件。 */
const PRIMARY_TOKEN_STREAM_EVENT = "messages-tuple";


/** 判斷未知資料是否為一般 record。 */
function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}


/** 正規化 context label。 */
function normalizeContextLabel(contextIndex: number, rawValue: unknown): string {
  return typeof rawValue === "string" && rawValue.trim() ? rawValue.trim() : `C${contextIndex + 1}`;
}


/** 將未知資料正規化為前端 citation payload。 */
function normalizeChatContextReference(value: unknown): ChatContextReference | null {
  if (!isRecord(value)) {
    return null;
  }
  const contextIndex = typeof value.context_index === "number" ? value.context_index : 0;
  return {
    context_index: contextIndex,
    context_label: normalizeContextLabel(contextIndex, value.context_label),
    document_id: typeof value.document_id === "string" ? value.document_id : "",
    document_name: typeof value.document_name === "string" ? value.document_name : "Unknown document",
    parent_chunk_id: typeof value.parent_chunk_id === "string" ? value.parent_chunk_id : null,
    child_chunk_ids: Array.isArray(value.child_chunk_ids)
      ? value.child_chunk_ids.filter((item): item is string => typeof item === "string")
      : [],
    heading: typeof value.heading === "string" ? value.heading : null,
    structure_kind: value.structure_kind === "table" ? "table" : "text",
    start_offset: typeof value.start_offset === "number" ? value.start_offset : 0,
    end_offset: typeof value.end_offset === "number" ? value.end_offset : 0,
    page_start: typeof value.page_start === "number" ? value.page_start : null,
    page_end: typeof value.page_end === "number" ? value.page_end : null,
    regions: Array.isArray(value.regions)
      ? value.regions.flatMap((item) => {
          if (!isRecord(item)) {
            return [];
          }
          return [{
            page_number: typeof item.page_number === "number" ? item.page_number : 0,
            region_order: typeof item.region_order === "number" ? item.region_order : 0,
            bbox_left: typeof item.bbox_left === "number" ? item.bbox_left : 0,
            bbox_bottom: typeof item.bbox_bottom === "number" ? item.bbox_bottom : 0,
            bbox_right: typeof item.bbox_right === "number" ? item.bbox_right : 0,
            bbox_top: typeof item.bbox_top === "number" ? item.bbox_top : 0,
          }];
        })
      : [],
    excerpt: typeof value.assembled_text === "string"
      ? value.assembled_text
      : (typeof value.excerpt === "string" ? value.excerpt : ""),
    assembled_text: typeof value.assembled_text === "string" ? value.assembled_text : undefined,
    source: typeof value.source === "string" ? value.source : "",
    truncated: Boolean(value.truncated),
  };
}


/** 將未知資料正規化為回答區塊。 */
function normalizeAnswerBlock(value: unknown): ChatAnswerBlock | null {
  if (!isRecord(value) || typeof value.text !== "string") {
    return null;
  }
  const citationContextIndices = Array.isArray(value.citation_context_indices)
    ? value.citation_context_indices.filter((item): item is number => typeof item === "number")
    : [];
  const displayCitations = Array.isArray(value.display_citations)
    ? value.display_citations.flatMap((item) => {
        if (!isRecord(item)) {
          return [];
        }
        const contextIndex = typeof item.context_index === "number" ? item.context_index : 0;
        return [
          {
            context_index: contextIndex,
            context_label: normalizeContextLabel(contextIndex, item.context_label),
            document_id: typeof item.document_id === "string" ? item.document_id : "",
            document_name: typeof item.document_name === "string" ? item.document_name : "Unknown document",
            heading: typeof item.heading === "string" ? item.heading : null,
            page_start: typeof item.page_start === "number" ? item.page_start : null,
            page_end: typeof item.page_end === "number" ? item.page_end : null,
          },
        ];
      })
    : [];
  return {
    text: value.text,
    citation_context_indices: citationContextIndices,
    display_citations: displayCitations,
  };
}


/** 正規化 answer blocks 列表。 */
function normalizeAnswerBlocks(value: unknown): ChatAnswerBlock[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.flatMap((item) => {
    const block = normalizeAnswerBlock(item);
    return block ? [block] : [];
  });
}


/**
 * 將文字、引用與原始 answer blocks 合併為最終可顯示結果。
 *
 * @param answer 原始回答文字。
 * @param rawAnswerBlocks 未正規化前的 answer blocks payload。
 * @param citations 當前回答可用的 citation metadata。
 * @returns 清理後文字與最終 answer blocks。
 */
function resolveNormalizedAnswer(
  answer: string,
  rawAnswerBlocks: unknown,
  citations: ChatContextReference[],
): { cleanAnswer: string; answerBlocks: ChatAnswerBlock[] } {
  return resolveAnswerBlocks(answer, normalizeAnswerBlocks(rawAnswerBlocks), citations);
}


/** 依 assistant turn 順序取得對應 artifact。 */
function getAssistantArtifact(
  artifacts: LangGraphMessageArtifact[],
  assistantTurnIndex: number,
): LangGraphMessageArtifact | undefined {
  return artifacts.find((artifact, artifactIndex) => {
    const artifactTurnIndex = typeof artifact.assistant_turn_index === "number"
      ? artifact.assistant_turn_index
      : artifactIndex;
    return artifactTurnIndex === assistantTurnIndex;
  });
}


/** 從 `messages-tuple` / `messages` event payload 擷取文字增量。 */
function extractMessageDelta(data: unknown): string {
  if (!Array.isArray(data) || data.length === 0) {
    return "";
  }
  const messageLike = data[0];
  if (typeof messageLike === "string") {
    return messageLike;
  }
  if (!isRecord(messageLike)) {
    return "";
  }
  const content = messageLike.content;
  if (typeof content === "string") {
    return content;
  }
  if (!Array.isArray(content)) {
    return "";
  }
  return content
    .flatMap((item) => {
      if (typeof item === "string") {
        return [item];
      }
      if (!isRecord(item)) {
        return [];
      }
      if (typeof item.text === "string") {
        return [item.text];
      }
      if (item.type === "text" && typeof item.content === "string") {
        return [item.content];
      }
      return [];
    })
    .join("");
}


/** 判斷 values event 是否屬於目前送出的問題。 */
function isCurrentQuestionState(data: Record<string, unknown>, areaId: string, question: string): boolean {
  return data.area_id === areaId && data.question === question;
}


/** 於啟用 debug 時輸出前端 chat stream 時間點。 */
function logChatStreamDebug(startedAt: number, event: string, fields: Record<string, unknown> = {}): void {
  if (!appConfig.chatStreamDebug) {
    return;
  }
  const elapsedMs = Math.round((performance.now() - startedAt) * 10) / 10;
  console.debug("[chat-stream-debug]", { event, elapsedMs, ...fields });
}


/** 建立附帶 Bearer token 的 LangGraph SDK client。 */
function createLangGraphClient(token: string) {
  return new Client({
    apiUrl: appConfig.apiBaseUrl,
    defaultHeaders: {
      Authorization: `Bearer ${token}`,
    },
  } as never);
}


/**
 * 判斷未知資料是否為已持久化的單一 session。
 *
 * @param value 待檢查的未知資料。
 * @returns 若格式正確則回傳正規化後的 session，否則回傳 `null`。
 */
function normalizeStoredAreaSession(value: unknown): StoredAreaSession | null {
  if (!isRecord(value) || typeof value.threadId !== "string" || !value.threadId.trim()) {
    return null;
  }
  const createdAt = typeof value.createdAt === "string" && value.createdAt.trim()
    ? value.createdAt
    : new Date().toISOString();
  const updatedAt = typeof value.updatedAt === "string" && value.updatedAt.trim()
    ? value.updatedAt
    : createdAt;
  return {
    threadId: value.threadId,
    title: normalizeSessionTitle(typeof value.title === "string" ? value.title : DEFAULT_SESSION_TITLE),
    createdAt,
    updatedAt,
  };
}


/**
 * 從 session storage 讀取 area-active-thread mapping。
 *
 * @returns area -> active thread 的對應表。
 */
function readActiveAreaThreadMap(): StoredAreaThreadMap {
  const rawValue = window.sessionStorage.getItem(ACTIVE_AREA_THREAD_STORAGE_KEY);
  if (!rawValue) {
    return {};
  }
  try {
    const parsed = JSON.parse(rawValue) as Record<string, string>;
    if (!parsed || typeof parsed !== "object") {
      return {};
    }
    return Object.fromEntries(
      Object.entries(parsed).filter(
        (entry): entry is [string, string] => typeof entry[0] === "string" && typeof entry[1] === "string" && entry[1].trim().length > 0,
      ),
    );
  } catch {
    return {};
  }
}


/**
 * 將 area-active-thread mapping 寫回 session storage。
 *
 * @param threadMap 要持久化的 area -> active thread 對應表。
 * @returns 無；僅更新 session storage。
 */
function saveActiveAreaThreadMap(threadMap: StoredAreaThreadMap): void {
  window.sessionStorage.setItem(ACTIVE_AREA_THREAD_STORAGE_KEY, JSON.stringify(threadMap));
}


/**
 * 讀取指定 area 目前啟用中的 session 識別碼。
 *
 * @param areaId 目標 area 識別碼。
 * @returns 啟用中的 LangGraph thread id；若尚未建立則回傳 `null`。
 */
export function getActiveAreaSessionId(areaId: string): string | null {
  return readActiveAreaThreadMap()[areaId] ?? null;
}


/**
 * 清除指定 area 的本機 active thread 選取。
 *
 * @param areaId 目標 area 識別碼。
 * @returns 無；僅更新 session storage。
 */
export function clearActiveAreaSessionId(areaId: string): void {
  const nextThreadMap = readActiveAreaThreadMap();
  delete nextThreadMap[areaId];
  saveActiveAreaThreadMap(nextThreadMap);
}


/**
 * 正規化 session 標題，避免空白與過長值污染 UI。
 *
 * @param value 原始標題。
 * @returns 清理後標題。
 */
function normalizeSessionTitle(value: string): string {
  const trimmedValue = value.trim();
  if (!trimmedValue) {
    return DEFAULT_SESSION_TITLE;
  }
  if (trimmedValue.length <= SESSION_TITLE_MAX_LENGTH) {
    return trimmedValue;
  }
  return `${trimmedValue.slice(0, SESSION_TITLE_MAX_LENGTH - 1).trimEnd()}…`;
}


/**
 * 由使用者問題自動產生 session 標題。
 *
 * @param question 本輪送出的問題。
 * @returns 可安全顯示於 session selector 的標題。
 */
function deriveSessionTitleFromQuestion(question: string): string {
  return normalizeSessionTitle(question.replace(/\s+/g, " "));
}


/**
 * 回傳指定 area 目前可切換的 session 摘要，依最近互動時間排序。
 *
 * @param areaId 目標 area 識別碼。
 * @returns 目前 area 內所有 session 摘要。
 */
export async function listAreaSessions(areaId: string): Promise<ChatSessionSummary[]> {
  await migrateLegacyAreaSessions(areaId);
  const payload = await fetchAreaChatSessions(areaId);
  return payload.items.sort((left, right) => right.updatedAt.localeCompare(left.updatedAt));
}


/**
 * 將指定 session 設為目前 area 的啟用 session。
 *
 * @param areaId 目標 area 識別碼。
 * @param threadId 要切換的 LangGraph thread id。
 * @returns 永遠回傳 `true`；後端存在性由 caller 自行驗證。
 */
export function setActiveAreaSessionId(areaId: string, threadId: string): boolean {
  const nextThreadMap = readActiveAreaThreadMap();
  nextThreadMap[areaId] = threadId;
  saveActiveAreaThreadMap(nextThreadMap);
  return true;
}


/**
 * 讀取舊版 local area-sessions metadata，供一次性後端遷移使用。
 *
 * @returns 舊版 local metadata；無法解析時回傳空物件。
 */
function readLegacyAreaSessionMap(): Record<string, { activeThreadId: string | null; sessions: StoredAreaSession[] }> {
  const rawValue = window.sessionStorage.getItem(LEGACY_AREA_SESSION_STORAGE_KEY);
  if (!rawValue) {
    return {};
  }
  try {
    const parsed = JSON.parse(rawValue) as Record<string, unknown>;
    if (!parsed || typeof parsed !== "object") {
      return {};
    }
    return Object.fromEntries(
      Object.entries(parsed).map(([areaId, value]) => {
        if (!isRecord(value)) {
          return [areaId, { activeThreadId: null, sessions: [] }];
        }
        const sessions = Array.isArray(value.sessions)
          ? value.sessions
              .map((session) => normalizeStoredAreaSession(session))
              .filter((session): session is StoredAreaSession => session !== null)
          : [];
        const activeThreadId = typeof value.activeThreadId === "string" ? value.activeThreadId : null;
        return [areaId, { activeThreadId, sessions }];
      }),
    );
  } catch {
    return {};
  }
}


/**
 * 將舊版 local metadata best-effort 註冊到後端，成功後移除舊 key。
 *
 * @param areaId 目標 area 識別碼。
 * @returns Promise<void>：遷移嘗試完成後結束。
 */
async function migrateLegacyAreaSessions(areaId: string): Promise<void> {
  const legacyAreaSessions = readLegacyAreaSessionMap();
  const legacyThreadMap = (() => {
    const rawValue = window.sessionStorage.getItem(LEGACY_AREA_THREAD_STORAGE_KEY);
    if (!rawValue) {
      return {} as Record<string, string>;
    }
    try {
      const parsed = JSON.parse(rawValue) as Record<string, string>;
      return parsed && typeof parsed === "object" ? parsed : {};
    } catch {
      return {};
    }
  })();

  const sessions = legacyAreaSessions[areaId]?.sessions ?? [];
  const legacyThreadId = legacyThreadMap[areaId];
  const migrationTargets = [
    ...sessions,
    ...(legacyThreadId && !sessions.some((session) => session.threadId === legacyThreadId)
      ? [{
          threadId: legacyThreadId,
          title: DEFAULT_SESSION_TITLE,
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
        } satisfies StoredAreaSession]
      : []),
  ];

  if (migrationTargets.length === 0) {
    return;
  }

  let didAllSucceed = true;
  for (const item of migrationTargets) {
    try {
      await registerAreaChatSession(areaId, {
        threadId: item.threadId,
        title: item.title,
      });
      if (legacyAreaSessions[areaId]?.activeThreadId === item.threadId || legacyThreadId === item.threadId) {
        setActiveAreaSessionId(areaId, item.threadId);
      }
    } catch {
      didAllSucceed = false;
    }
  }

  if (didAllSucceed) {
    window.sessionStorage.removeItem(LEGACY_AREA_SESSION_STORAGE_KEY);
    window.sessionStorage.removeItem(LEGACY_AREA_THREAD_STORAGE_KEY);
  }
}


/** 清除目前 session 內的 assistant id。 */
function clearAssistantId(): void {
  window.sessionStorage.removeItem(ASSISTANT_ID_STORAGE_KEY);
}


/** 確保目前 session 內有合法的 assistant UUID。 */
function ensureAssistantId(): string {
  const existingValue = window.sessionStorage.getItem(ASSISTANT_ID_STORAGE_KEY);
  if (existingValue) {
    return existingValue;
  }
  const nextValue = crypto.randomUUID();
  window.sessionStorage.setItem(ASSISTANT_ID_STORAGE_KEY, nextValue);
  return nextValue;
}


/**
 * 建立新的 area session 並設為目前啟用中的 session。
 *
 * @param areaId 目標 area 識別碼。
 * @param accessTokenGetter 取得最新 access token 的函式。
 * @returns 新建立的 session 摘要。
 */
export async function createAreaSession(
  areaId: string,
  title: string = DEFAULT_SESSION_TITLE,
): Promise<ChatSessionSummary> {
  const registeredSession = await registerAreaChatSession(areaId, {
    title,
  });
  setActiveAreaSessionId(areaId, registeredSession.threadId);
  return registeredSession;
}


/**
 * 確保指定 area 至少存在一個可用 session，若無則自動建立。
 *
 * @param areaId 目標 area 識別碼。
 * @param accessTokenGetter 取得最新 access token 的函式。
 * @returns 目前啟用中的 session 摘要。
 */
export async function ensureAreaSession(
  areaId: string,
  options: {
    titleOnCreate?: string;
  } = {},
): Promise<ChatSessionSummary> {
  const activeThreadId = getActiveAreaSessionId(areaId);
  const currentSessions = await listAreaSessions(areaId);
  const existingSession = currentSessions.find((session) => session.threadId === activeThreadId);
  if (existingSession) {
    return existingSession;
  }
  if (activeThreadId) {
    clearActiveAreaSessionId(areaId);
  }
  if (currentSessions[0]) {
    setActiveAreaSessionId(areaId, currentSessions[0].threadId);
    return currentSessions[0];
  }
  return createAreaSession(areaId, options.titleOnCreate ?? DEFAULT_SESSION_TITLE);
}


/**
 * 以第一個使用者問題初始化 session 標題。
 *
 * @param areaId 目標 area 識別碼。
 * @param threadId 目標 LangGraph thread id。
 * @param question 本輪送出的第一個問題。
 * @returns 無；僅在標題仍為預設值時更新 session metadata。
 */
export async function seedAreaSessionTitleFromQuestion(areaId: string, threadId: string, question: string): Promise<void> {
  const nextTitle = deriveSessionTitleFromQuestion(question);
  await updateAreaChatSession(areaId, threadId, {
    title: nextTitle,
  });
}


/** 確保預設 graph 已註冊成可供 thread/run 使用的 assistant。 */
async function ensureAssistant(client: Client): Promise<string> {
  const assistantId = ensureAssistantId();
  await client.assistants.create({
    graphId: GRAPH_ID,
    assistantId,
    ifExists: "do_nothing",
  });
  return assistantId;
}


/** 將 LangGraph thread state message 轉成純文字。 */
function flattenStateMessageContent(content: unknown): string {
  if (typeof content === "string") {
    return content;
  }
  if (!Array.isArray(content)) {
    return "";
  }
  return content
    .flatMap((item) => {
      if (typeof item === "string") {
        return [item];
      }
      if (!isRecord(item)) {
        return [];
      }
      if (typeof item.text === "string") {
        return [item.text];
      }
      if (item.type === "text" && typeof item.content === "string") {
        return [item.content];
      }
      return [];
    })
    .join("");
}


/** 將 LangGraph thread state messages 轉成前端 chat message view models。 */
export function mapThreadStateMessagesToChatMessages(
  messages: LangGraphStateMessage[],
  messageArtifacts: LangGraphMessageArtifact[],
): Array<{
  id: string;
  role: "user" | "assistant";
  content: string;
  answerBlocks: ChatAnswerBlock[];
  citations: ChatContextReference[];
  usedKnowledgeBase: boolean | null;
}> {
  let assistantTurnIndex = 0;

  return messages.flatMap((message, index) => {
    const role =
      message.type === "human" || message.role === "user"
        ? "user"
        : (message.type === "ai" || message.role === "assistant" ? "assistant" : null);
    const content = flattenStateMessageContent(message.content).trim();
    if (!role || !content) {
      return [];
    }
    const artifact = role === "assistant" ? getAssistantArtifact(messageArtifacts, assistantTurnIndex) : undefined;
    const normalizedCitations = role === "assistant" && Array.isArray(artifact?.citations)
      ? artifact.citations.flatMap((citation) => {
          const normalized = normalizeChatContextReference(citation);
          return normalized ? [normalized] : [];
        })
      : [];
    const resolvedAnswer = role === "assistant"
      ? resolveNormalizedAnswer(content, artifact?.answer_blocks, normalizedCitations)
      : { cleanAnswer: content, answerBlocks: [] };
    const hydratedMessage = {
      id: `thread-${index}-${role}`,
      role,
      content: resolvedAnswer.cleanAnswer,
      answerBlocks: resolvedAnswer.answerBlocks,
      citations: normalizedCitations,
      usedKnowledgeBase: role === "assistant" && typeof artifact?.used_knowledge_base === "boolean"
        ? artifact.used_knowledge_base
        : null,
    } as const;
    if (role === "assistant") {
      assistantTurnIndex += 1;
    }
    return [
      hydratedMessage,
    ];
  });
}


/** 讀取指定 area 目前 thread 的對話歷史。 */
export async function loadAreaThreadHistory(
  areaId: string,
  accessTokenGetter: AccessTokenGetter,
): Promise<Array<{
  id: string;
  role: "user" | "assistant";
  content: string;
  answerBlocks: ChatAnswerBlock[];
  citations: ChatContextReference[];
  usedKnowledgeBase: boolean | null;
}>> {
  const threadId = getActiveAreaSessionId(areaId);
  if (!threadId) {
    return [];
  }

  const token = await accessTokenGetter();
  if (!token) {
    return [];
  }

  const client = createLangGraphClient(token);
  try {
    const threadState = await client.threads.getState<{
      messages?: LangGraphStateMessage[];
      message_artifacts?: LangGraphMessageArtifact[];
    }>(threadId);
    const stateMessages = Array.isArray(threadState.values?.messages) ? threadState.values.messages : [];
    const messageArtifacts = Array.isArray(threadState.values?.message_artifacts)
      ? threadState.values.message_artifacts
      : [];
    return mapThreadStateMessagesToChatMessages(stateMessages, messageArtifacts);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    if (message.includes("Thread") && message.includes("not found")) {
      try {
        await deleteAreaChatSession(areaId, threadId);
      } catch {
        // stale session metadata 清理失敗時，不阻擋前端先回空狀態。
      }
      clearActiveAreaSessionId(areaId);
      return [];
    }
    throw error;
  }
}


/** 以 LangGraph SDK stream 指定 area 的多輪 chat。 */
export async function streamAreaThreadChat(
  areaId: string,
  question: string,
  accessTokenGetter: AccessTokenGetter,
  onUpdate: (update: LangGraphChatStreamUpdate) => void,
): Promise<void> {
  await streamAreaThreadChatInternal(areaId, question, accessTokenGetter, onUpdate, true);
}

/** 以 LangGraph SDK stream 指定 area 的多輪 chat，並在 in-memory 資源遺失時自動重建一次。 */
async function streamAreaThreadChatInternal(
  areaId: string,
  question: string,
  accessTokenGetter: AccessTokenGetter,
  onUpdate: (update: LangGraphChatStreamUpdate) => void,
  allowRetry: boolean,
): Promise<void> {
  const token = await accessTokenGetter();
  if (!token) {
    throw new Error("目前尚未登入，無法呼叫 LangGraph chat。");
  }

  const streamStartedAt = performance.now();
  const client = createLangGraphClient(token);
  let pendingCompletion: PendingCompletionUpdate | null = null;
  let hasPrimaryTokenStream = false;
  try {
    const assistantId = await ensureAssistant(client);
    const threadId = (await ensureAreaSession(areaId)).threadId;
    const stream = client.runs.stream(threadId, assistantId, {
      input: {
        area_id: areaId,
        question,
        messages: [
          {
            role: "user",
            content: question,
          },
        ],
      },
      streamMode: ["messages-tuple", "custom", "values"],
    } as never) as AsyncIterable<{ event?: string; data?: unknown }>;

    for await (const part of stream) {
      if ((part.event === "messages" || part.event === PRIMARY_TOKEN_STREAM_EVENT)) {
        const delta = extractMessageDelta(part.data);
        if (delta) {
          hasPrimaryTokenStream = true;
          logChatStreamDebug(streamStartedAt, "messages_tuple", {
            deltaLength: delta.length,
            deltaPreview: delta.slice(0, 80),
          });
          onUpdate({ delta });
        }
        continue;
      }
      if (part.event === "custom" && isRecord(part.data) && part.data.type === "phase") {
        const phase = part.data.phase;
        const status = part.data.status;
        const message = part.data.message;
        if (
          (phase === "preparing"
            || phase === "thinking"
            || phase === "searching"
            || phase === "tool_calling"
            || phase === "drafting")
          && (status === "started" || status === "completed")
          && typeof message === "string"
        ) {
          logChatStreamDebug(streamStartedAt, "phase", { phase, status, message });
          onUpdate({
            phaseState: {
              phase,
              status,
              message,
            },
          });
        }
        continue;
      }
      if (part.event === "custom" && isRecord(part.data) && part.data.type === "token") {
        const delta = part.data.delta;
        if (typeof delta === "string" && delta) {
          logChatStreamDebug(streamStartedAt, hasPrimaryTokenStream ? "custom_token_ignored" : "custom_token_fallback", {
            deltaLength: delta.length,
            deltaPreview: delta.slice(0, 80),
          });
          if (!hasPrimaryTokenStream) {
            onUpdate({ delta });
          }
        }
        continue;
      }
      if (part.event === "custom" && isRecord(part.data) && part.data.type === "tool_call") {
        const name = part.data.name;
        const status = part.data.status;
        const input = part.data.input;
        const output = part.data.output;
        if (
          typeof name === "string"
          && (status === "started" || status === "completed")
          && isRecord(input)
          && (output === null || output === undefined || isRecord(output))
        ) {
          logChatStreamDebug(streamStartedAt, "tool_call", { name, status });
          onUpdate({
            toolCall: {
              name,
              status,
              input,
              output: output === undefined ? null : (output as Record<string, unknown> | null),
            },
          });
        }
        continue;
      }
      if (part.event === "custom" && isRecord(part.data) && part.data.type === "references") {
        const references = Array.isArray(part.data.references)
          ? part.data.references
              .map((reference) => normalizeChatContextReference(reference))
              .filter((reference): reference is ChatContextReference => reference !== null)
          : [];
        logChatStreamDebug(streamStartedAt, "references", { referencesCount: references.length });
        if (references.length > 0) {
          onUpdate({ references });
        }
        continue;
      }
      if (part.event === "values" && isRecord(part.data) && isCurrentQuestionState(part.data, areaId, question)) {
        const citations = Array.isArray(part.data.citations) ? (part.data.citations as ChatContextReference[]) : [];
        const normalizedCitations = citations
          .map((citation) => normalizeChatContextReference(citation))
          .filter((citation): citation is ChatContextReference => citation !== null);
        const assembledContexts = Array.isArray(part.data.assembled_contexts)
          ? (part.data.assembled_contexts as Array<Record<string, unknown>>)
          : [];
        const references = assembledContexts.length > 0
          ? assembledContexts
              .map((context) => normalizeChatContextReference(context))
              .filter((context): context is ChatContextReference => context !== null)
          : normalizedCitations;
        const answer = typeof part.data.answer === "string" ? part.data.answer : "";
        const resolvedAnswer = resolveNormalizedAnswer(answer, part.data.answer_blocks, references);
        const trace =
          part.data.trace && typeof part.data.trace === "object"
            ? (part.data.trace as Record<string, unknown>)
            : undefined;
        logChatStreamDebug(streamStartedAt, "values_current_question", {
          answerLength: answer.length,
          referencesCount: references.length,
        });
        pendingCompletion = {
          references,
          answer: resolvedAnswer.cleanAnswer,
          answerBlocks: resolvedAnswer.answerBlocks,
          trace,
          usedKnowledgeBase: references.length > 0 || Boolean((trace?.agent as { retrieval_invoked?: boolean } | undefined)?.retrieval_invoked),
        };
      }
    }
    if (pendingCompletion) {
      try {
        await updateAreaChatSession(areaId, threadId);
      } catch {
        // chat 主流程已完成時，不讓 metadata 同步失敗中斷回答。
      }
      logChatStreamDebug(streamStartedAt, "completion_commit", {
        answerLength: pendingCompletion.answer.length,
        referencesCount: pendingCompletion.references.length,
      });
      onUpdate({
        ...pendingCompletion,
        completed: true,
        phaseState: null,
      });
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    if (allowRetry && message.includes("Thread or assistant not found")) {
      const activeThreadId = getActiveAreaSessionId(areaId);
      if (activeThreadId) {
        clearActiveAreaSessionId(areaId);
      }
      clearAssistantId();
      await streamAreaThreadChatInternal(areaId, question, accessTokenGetter, onUpdate, false);
      return;
    }
    throw error;
  }
}
