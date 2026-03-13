/** Chat feature 使用的 LangGraph SDK transport。 */

import { Client } from "@langchain/langgraph-sdk";

import type { AccessTokenGetter } from "../../../lib/api";
import { appConfig } from "../../../lib/config";
import type { ChatContextReference, ChatPhaseState, ChatToolCallState } from "../../../lib/types";


/** 前端 session storage 使用的 area-thread mapping key。 */
const AREA_THREAD_STORAGE_KEY = "deep-agent.langgraph.area-threads";
/** 前端 session storage 使用的 LangGraph assistant id key。 */
const ASSISTANT_ID_STORAGE_KEY = "deep-agent.langgraph.assistant-id";

/** LangGraph graph id；對應 `apps/api/langgraph.json` 的公開 graph 名稱。 */
const GRAPH_ID = "agent";


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
  /** 最終 trace。 */
  trace?: Record<string, unknown>;
  /** 本輪是否有使用知識庫 references。 */
  usedKnowledgeBase: boolean;
}


/** 判斷未知資料是否為一般 record。 */
function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
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
  const existingThreadId = readAreaThreadMap()[areaId];
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
  try {
    const assistantId = await ensureAssistant(client);
    const threadId = await ensureAreaThreadId(areaId, accessTokenGetter);
    const stream = client.runs.stream(threadId, assistantId, {
      input: {
        area_id: areaId,
        question,
      },
      streamMode: ["messages-tuple", "custom", "values"],
    } as never) as AsyncIterable<{ event?: string; data?: unknown }>;

    for await (const part of stream) {
      if ((part.event === "messages" || part.event === "messages-tuple")) {
        const delta = extractMessageDelta(part.data);
        if (delta) {
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
          (phase === "thinking" || phase === "searching" || phase === "tool_calling")
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
          logChatStreamDebug(streamStartedAt, "custom_token", {
            deltaLength: delta.length,
            deltaPreview: delta.slice(0, 80),
          });
          onUpdate({ delta });
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
      if (part.event === "values" && isRecord(part.data) && isCurrentQuestionState(part.data, areaId, question)) {
        const citations = Array.isArray(part.data.citations) ? (part.data.citations as ChatContextReference[]) : [];
        const assembledContexts = Array.isArray(part.data.assembled_contexts)
          ? (part.data.assembled_contexts as Array<Record<string, unknown>>)
          : [];
        const references = assembledContexts.length > 0
          ? assembledContexts.map(
              (context): ChatContextReference => ({
                context_index: typeof context.context_index === "number" ? context.context_index : 0,
                document_id: typeof context.document_id === "string" ? context.document_id : "",
                parent_chunk_id: typeof context.parent_chunk_id === "string" ? context.parent_chunk_id : null,
                child_chunk_ids: Array.isArray(context.child_chunk_ids)
                  ? context.child_chunk_ids.filter((item): item is string => typeof item === "string")
                  : [],
                heading: typeof context.heading === "string" ? context.heading : null,
                structure_kind: context.structure_kind === "table" ? "table" : "text",
                start_offset: typeof context.start_offset === "number" ? context.start_offset : 0,
                end_offset: typeof context.end_offset === "number" ? context.end_offset : 0,
                excerpt: typeof context.assembled_text === "string"
                  ? context.assembled_text
                  : (typeof context.excerpt === "string" ? context.excerpt : ""),
                assembled_text: typeof context.assembled_text === "string" ? context.assembled_text : undefined,
                source: typeof context.source === "string" ? context.source : "",
                truncated: Boolean(context.truncated),
              }),
            )
          : citations;
        const answer = typeof part.data.answer === "string" ? part.data.answer : "";
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
          answer,
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
      await streamAreaThreadChatInternal(areaId, question, accessTokenGetter, onUpdate, false);
      return;
    }
    throw error;
  }
}
