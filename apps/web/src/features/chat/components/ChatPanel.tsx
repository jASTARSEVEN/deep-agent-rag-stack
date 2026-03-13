/** Area-scoped chat panel，正式透過 LangGraph built-in thread/run 互動。 */

import { useEffect, useState, type FormEvent } from "react";

import type { AccessTokenGetter } from "../../../lib/api";
import type { ChatMessageViewModel } from "../../../lib/types";
import { applyStreamUpdate, createAssistantMessage, createUserMessage, updateLastAssistantMessage } from "../state/messages";
import { streamAreaThreadChat } from "../transport/langgraph";
import { ContextViewer } from "./ContextViewer";
import { ToolCallViewer } from "./ToolCallViewer";


interface ChatPanelProps {
  /** 目前選取的 area。 */
  areaId: string | null;
  /** 取得最新 access token 的函式。 */
  accessTokenGetter: AccessTokenGetter;
  /** 當 chat 發生錯誤時，回寫給頁面層。 */
  onError: (message: string | null) => void;
  /** 當 chat 成功送出時，清除頁面層錯誤。 */
  onNoticeClear?: () => void;
}


/** 空的 chat 輸入狀態。 */
const EMPTY_CHAT_INPUT = "";


/** 顯示 area-scoped 對話與工具 debug view。 */
export function ChatPanel({
  areaId,
  accessTokenGetter,
  onError,
  onNoticeClear,
}: ChatPanelProps): JSX.Element {
  const [chatQuestion, setChatQuestion] = useState(EMPTY_CHAT_INPUT);
  const [chatMessages, setChatMessages] = useState<ChatMessageViewModel[]>([]);
  const [isSubmittingChat, setIsSubmittingChat] = useState(false);

  useEffect(() => {
    setChatQuestion(EMPTY_CHAT_INPUT);
    setChatMessages([]);
  }, [areaId]);

  async function handleChatSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!areaId) {
      onError("請先選擇 area。");
      return;
    }

    const trimmedQuestion = chatQuestion.trim();
    if (!trimmedQuestion) {
      onError("請先輸入問題。");
      return;
    }

    onError(null);
    onNoticeClear?.();
    setIsSubmittingChat(true);
    setChatQuestion(EMPTY_CHAT_INPUT);
    setChatMessages((current) => [...current, createUserMessage(trimmedQuestion), createAssistantMessage()]);

    try {
      await streamAreaThreadChat(areaId, trimmedQuestion, accessTokenGetter, (streamUpdate) => {
        setChatMessages((current) => applyStreamUpdate(current, streamUpdate));
      });
    } catch (streamError) {
      const errorMessage = streamError instanceof Error ? streamError.message : "chat 失敗。";
      setChatMessages((current) =>
        updateLastAssistantMessage(current, (assistantMessage) => ({
          ...assistantMessage,
          content: errorMessage,
          citations: [],
          phaseState: null,
          toolCalls: [],
          isStreaming: false,
          isError: true,
          usedKnowledgeBase: null,
        })),
      );
      onError(errorMessage);
    } finally {
      setIsSubmittingChat(false);
    }
  }

  return (
    <div className="rounded-2xl border border-stone-200 bg-white p-5">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Chat</h3>
        <span className="text-sm text-stone-500">reader 以上可提問</span>
      </div>

      <form className="mt-4 space-y-4" onSubmit={handleChatSubmit}>
        <div>
          <label className="block text-sm font-medium text-stone-700" htmlFor="chat-question">
            Question
          </label>
          <textarea
            id="chat-question"
            data-testid="chat-question"
            className="mt-2 min-h-28 w-full rounded-2xl border border-stone-300 bg-stone-50 px-4 py-3 text-sm outline-none transition focus:border-amber-600 focus:bg-white"
            placeholder="輸入要在此 area 內提問的問題。"
            value={chatQuestion}
            onChange={(event) => setChatQuestion(event.target.value)}
          />
        </div>
        <button
          data-testid="chat-submit"
          className="rounded-full bg-stone-900 px-5 py-2 text-sm font-medium text-white transition hover:bg-stone-700 disabled:cursor-not-allowed disabled:opacity-60"
          disabled={isSubmittingChat}
          type="submit"
        >
          {isSubmittingChat ? "回答中..." : "送出問題"}
        </button>
      </form>

      <div className="mt-5 grid gap-3" data-testid="chat-messages">
        {chatMessages.length > 0 ? (
          chatMessages.map((message) => (
            <article
              key={message.id}
              data-testid={`chat-message-${message.role}`}
              className={`rounded-2xl border px-4 py-4 ${
                message.role === "user"
                  ? "border-stone-200 bg-stone-50"
                  : message.isError
                    ? "border-red-200 bg-red-50"
                    : "border-amber-200 bg-amber-50"
              }`}
            >
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm font-semibold text-stone-900">
                  {message.role === "user" ? "User" : "Assistant"}
                </p>
                {message.isStreaming ? (
                  <span className="text-xs font-medium text-amber-700">streaming...</span>
                ) : null}
              </div>
              <p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-stone-700">
                {message.content || (message.isStreaming ? "正在生成回答..." : "尚無內容")}
              </p>
              {message.role === "assistant" && message.phaseState ? (
                <div className="mt-3 inline-flex items-center gap-2 rounded-full bg-stone-900 px-3 py-1 text-xs font-medium text-stone-100">
                  <span className="h-2 w-2 rounded-full bg-amber-400" />
                  <span>{message.phaseState.message}</span>
                </div>
              ) : null}
              {message.role === "assistant" ? <ToolCallViewer toolCalls={message.toolCalls} /> : null}
              {message.role === "assistant" && message.usedKnowledgeBase === false && !message.isStreaming ? (
                <p className="mt-3 text-xs font-medium text-stone-500">本輪未使用知識庫 references。</p>
              ) : null}
              {message.role === "assistant" ? <ContextViewer citations={message.citations} /> : null}
            </article>
          ))
        ) : (
          <div className="rounded-2xl border border-dashed border-stone-300 bg-stone-50 px-4 py-8 text-center text-sm text-stone-500">
            尚未提問。送出第一個問題後，這裡會顯示回答與 assembled contexts。
          </div>
        )}
      </div>
    </div>
  );
}
