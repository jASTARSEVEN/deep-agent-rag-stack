/** Chat feature 使用的 LangGraph SDK transport。 */

import { Client } from "@langchain/langgraph-sdk";

import type { AccessTokenGetter } from "../../../lib/api";
import { appConfig } from "../../../lib/config";
import type {
  ChatAnswerBlock,
  ChatContextReference,
  ChatPhaseState,
  ChatToolCallState,
} from "../../../lib/types";
import { resolveAnswerBlocks } from "../state/answerBlocks";


/** 前端 session storage 使用的 area-thread mapping key。 */
const AREA_THREAD_STORAGE_KEY = "deep-agent.langgraph.area-threads";
/** 前端 session storage 使用的 LangGraph assistant id key。 */
const ASSISTANT_ID_STORAGE_KEY = "deep-agent.langgraph.assistant-id";

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

/** 單次 chat 送出時可攜帶的選項。 */
export interface LangGraphChatRunOptions {
  /** 是否啟用 thinking mode。 */
  thinkingMode?: boolean;
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


/** 從 session storage 讀取 area-thread mapping。 */
function readAreaThreadMap(): Record<string, string> {
  const rawValue = window.sessionStorage.getItem(AREA_THREAD_STORAGE_KEY);
  if (!rawValue) {
    return {};
  }
  try {
    const parsed = JSON.parse(rawValue) as Record<string, string>;
    return typeof parsed === "object" && parsed !== null ? parsed : {};
  } catch {
    return {};
  }
}


/** 將 area-thread mapping 寫回 session storage。 */
function saveAreaThreadMap(threadMap: Record<string, string>): void {
  window.sessionStorage.setItem(AREA_THREAD_STORAGE_KEY, JSON.stringify(threadMap));
}


/** 清除指定 area 對應的 thread mapping。 */
function clearAreaThreadId(areaId: string): void {
  const nextThreadMap = readAreaThreadMap();
  delete nextThreadMap[areaId];
  saveAreaThreadMap(nextThreadMap);
}


/** 清除目前 session 內的 assistant id。 */
function clearAssistantId(): void {
  window.sessionStorage.removeItem(ASSISTANT_ID_STORAGE_KEY);
}


/** 讀取指定 area 目前 session 內的 thread id。 */
function getAreaThreadId(areaId: string): string | null {
  return readAreaThreadMap()[areaId] ?? null;
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


/** 確保指定 area 有對應的 thread id。 */
async function ensureAreaThreadId(areaId: string, accessTokenGetter: AccessTokenGetter): Promise<string> {
  const existingThreadId = getAreaThreadId(areaId);
  if (existingThreadId) {
    return existingThreadId;
  }

  const token = await accessTokenGetter();
  if (!token) {
    throw new Error("目前尚未登入，無法建立 LangGraph thread。");
  }

  const client = createLangGraphClient(token);
  const thread = await (client.threads.create({
    metadata: {
      area_id: areaId,
    },
  }) as Promise<{ thread_id?: string; threadId?: string }>);
  const nextThreadId = thread.thread_id ?? thread.threadId;
  if (!nextThreadId) {
    throw new Error("LangGraph thread 建立成功，但回應缺少 thread_id。");
  }

  const nextThreadMap = readAreaThreadMap();
  nextThreadMap[areaId] = nextThreadId;
  saveAreaThreadMap(nextThreadMap);
  return nextThreadId;
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
  const threadId = getAreaThreadId(areaId);
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
      clearAreaThreadId(areaId);
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
  options?: LangGraphChatRunOptions,
): Promise<void> {
  await streamAreaThreadChatInternal(areaId, question, accessTokenGetter, onUpdate, true, options);
}


/** 以 LangGraph SDK stream 指定 area 的多輪 chat，並在 in-memory 資源遺失時自動重建一次。 */
async function streamAreaThreadChatInternal(
  areaId: string,
  question: string,
  accessTokenGetter: AccessTokenGetter,
  onUpdate: (update: LangGraphChatStreamUpdate) => void,
  allowRetry: boolean,
  options?: LangGraphChatRunOptions,
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
    const threadId = await ensureAreaThreadId(areaId, accessTokenGetter);
    const stream = client.runs.stream(threadId, assistantId, {
      input: {
        area_id: areaId,
        question,
        thinking_mode: Boolean(options?.thinkingMode),
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
      clearAreaThreadId(areaId);
      clearAssistantId();
      await streamAreaThreadChatInternal(areaId, question, accessTokenGetter, onUpdate, false, options);
      return;
    }
    throw error;
  }
}
