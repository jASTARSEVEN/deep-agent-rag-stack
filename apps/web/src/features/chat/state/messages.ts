/** Chat feature 的 message state helpers。 */

import type { ChatMessageViewModel, ChatToolCallState } from "../../../lib/types";
import type { LangGraphChatStreamUpdate } from "../transport/langgraph";
import { containsCitationMarkerPrefix, resolveAnswerBlocks } from "./answerBlocks";

/** 可覆寫的助理訊息預設值。 */
interface AssistantMessageOverrides {
  /** 訊息 id。 */
  id?: string;
  /** 初始內容。 */
  content?: string;
  /** 是否正在串流。 */
  isStreaming?: boolean;
  /** 結構化回答區塊。 */
  answerBlocks?: ChatMessageViewModel["answerBlocks"];
  /** citations。 */
  citations?: ChatMessageViewModel["citations"];
  /** 是否使用知識庫。 */
  usedKnowledgeBase?: ChatMessageViewModel["usedKnowledgeBase"];
  /** 預設選取的 citation context。 */
  selectedCitationContextIndex?: number | null;
}

/** 建立新的使用者訊息。 */
export function createUserMessage(question: string, id?: string): ChatMessageViewModel {
  return {
    id: id ?? `user-${Date.now()}`,
    role: "user",
    rawContent: question,
    content: question,
    answerBlocks: [],
    citations: [],
    phaseState: null,
    toolCalls: [],
    isStreaming: false,
    isError: false,
    usedKnowledgeBase: null,
    selectedCitationContextIndex: null,
  };
}


/** 建立新的助理 placeholder 訊息。 */
export function createAssistantMessage(overrides: AssistantMessageOverrides = {}): ChatMessageViewModel {
  return {
    id: overrides.id ?? `assistant-${Date.now()}`,
    role: "assistant",
    rawContent: overrides.content ?? "",
    content: overrides.content ?? "",
    answerBlocks: overrides.answerBlocks ?? [],
    citations: overrides.citations ?? [],
    phaseState: null,
    toolCalls: [],
    isStreaming: overrides.isStreaming ?? true,
    isError: false,
    usedKnowledgeBase: overrides.usedKnowledgeBase ?? null,
    selectedCitationContextIndex: overrides.selectedCitationContextIndex ?? null,
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
    nextMessages = updateLastAssistantMessage(nextMessages, (current) => {
      const nextRawContent = `${current.rawContent}${streamUpdate.delta}`;
      const shouldResolveCitationBlocks =
        current.answerBlocks.length > 0 || containsCitationMarkerPrefix(nextRawContent);
      if (!shouldResolveCitationBlocks) {
        return {
          ...current,
          rawContent: nextRawContent,
          content: nextRawContent,
        };
      }
      const resolvedAnswer = resolveAnswerBlocks(nextRawContent, current.answerBlocks, current.citations);
      return {
        ...current,
        rawContent: nextRawContent,
        content: resolvedAnswer.cleanAnswer,
        answerBlocks: resolvedAnswer.answerBlocks,
      };
    });
  }
  if (Array.isArray(streamUpdate.references)) {
    nextMessages = updateLastAssistantMessage(nextMessages, (current) => {
      const nextCitations = streamUpdate.references ?? [];
      const shouldResolveCitationBlocks =
        current.answerBlocks.length > 0 || containsCitationMarkerPrefix(current.rawContent);
      if (!shouldResolveCitationBlocks) {
        return {
          ...current,
          citations: nextCitations,
        };
      }
      const resolvedAnswer = resolveAnswerBlocks(current.rawContent, current.answerBlocks, nextCitations);
      return {
        ...current,
        citations: nextCitations,
        content: resolvedAnswer.cleanAnswer,
        answerBlocks: resolvedAnswer.answerBlocks,
      };
    });
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
    nextMessages = updateLastAssistantMessage(nextMessages, (current) => {
      const nextCitations = Array.isArray(streamUpdate.references) ? streamUpdate.references : current.citations;
      const nextAnswer = streamUpdate.answer || current.content;
      const resolvedAnswer = resolveAnswerBlocks(
        nextAnswer,
        Array.isArray(streamUpdate.answerBlocks) ? streamUpdate.answerBlocks : current.answerBlocks,
        nextCitations,
      );

      return {
        ...current,
        rawContent: nextAnswer,
        content: resolvedAnswer.cleanAnswer,
        answerBlocks: resolvedAnswer.answerBlocks,
        citations: nextCitations,
        phaseState: null,
        isStreaming: false,
        usedKnowledgeBase: streamUpdate.usedKnowledgeBase ?? current.usedKnowledgeBase,
      };
    });
  }

  return nextMessages;
}
