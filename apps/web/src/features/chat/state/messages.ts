/** Chat feature 的 message state helpers。 */

import type { ChatMessageViewModel, ChatToolCallState } from "../../../lib/types";
import type { LangGraphChatStreamUpdate } from "../transport/langgraph";

/** 可覆寫的助理訊息預設值。 */
interface AssistantMessageOverrides {
  /** 訊息 id。 */
  id?: string;
  /** 初始內容。 */
  content?: string;
  /** 是否正在串流。 */
  isStreaming?: boolean;
}

/** 建立新的使用者訊息。 */
export function createUserMessage(question: string, id?: string): ChatMessageViewModel {
  return {
    id: id ?? `user-${Date.now()}`,
    role: "user",
    content: question,
    citations: [],
    phaseState: null,
    toolCalls: [],
    isStreaming: false,
    isError: false,
    usedKnowledgeBase: null,
  };
}


/** 建立新的助理 placeholder 訊息。 */
export function createAssistantMessage(overrides: AssistantMessageOverrides = {}): ChatMessageViewModel {
  return {
    id: overrides.id ?? `assistant-${Date.now()}`,
    role: "assistant",
    content: overrides.content ?? "",
    citations: [],
    phaseState: null,
    toolCalls: [],
    isStreaming: overrides.isStreaming ?? true,
    isError: false,
    usedKnowledgeBase: null,
  };
}


/** 更新最後一則助理訊息。 */
export function updateLastAssistantMessage(
  messages: ChatMessageViewModel[],
  updater: (current: ChatMessageViewModel) => ChatMessageViewModel,
): ChatMessageViewModel[] {
  const nextMessages = [...messages];
  const lastIndex = nextMessages.length - 1;
  if (lastIndex < 0) {
    return messages;
  }
  const lastMessage = nextMessages[lastIndex];
  if (lastMessage.role !== "assistant") {
    return messages;
  }
  nextMessages[lastIndex] = updater(lastMessage);
  return nextMessages;
}


/** 將單次 stream update 套用到目前訊息列表。 */
export function applyStreamUpdate(
  messages: ChatMessageViewModel[],
  streamUpdate: LangGraphChatStreamUpdate,
): ChatMessageViewModel[] {
  let nextMessages = messages;

  if (typeof streamUpdate.delta === "string" && streamUpdate.delta) {
    nextMessages = updateLastAssistantMessage(nextMessages, (current) => ({
      ...current,
      content: `${current.content}${streamUpdate.delta}`,
    }));
  }
  if (Array.isArray(streamUpdate.references)) {
    nextMessages = updateLastAssistantMessage(nextMessages, (current) => ({
      ...current,
      citations: streamUpdate.references ?? [],
    }));
  }
  if (streamUpdate.phaseState) {
    nextMessages = updateLastAssistantMessage(nextMessages, (current) => ({
      ...current,
      phaseState: streamUpdate.phaseState ?? null,
    }));
  }
  if (streamUpdate.toolCall) {
    const nextToolCall = streamUpdate.toolCall;
    nextMessages = updateLastAssistantMessage(nextMessages, (current) => ({
      ...current,
      toolCalls: [
        ...current.toolCalls.filter((item: ChatToolCallState) => item.name !== nextToolCall.name),
        nextToolCall,
      ],
    }));
  }
  if (streamUpdate.completed) {
    nextMessages = updateLastAssistantMessage(nextMessages, (current) => ({
      ...current,
      content: streamUpdate.answer || current.content,
      phaseState: null,
      isStreaming: false,
      usedKnowledgeBase: streamUpdate.usedKnowledgeBase ?? current.usedKnowledgeBase,
    }));
  }

  return nextMessages;
}
