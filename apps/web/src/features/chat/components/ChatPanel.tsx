/** Area-scoped chat panel，正式透過 LangGraph built-in thread/run 互動。 */

import { useEffect, useRef, useState, type FormEvent } from "react";

import { fetchDocumentPreview, type AccessTokenGetter } from "../../../lib/api";
import type { ChatContextReference, ChatMessageViewModel, DocumentPreviewPayload } from "../../../lib/types";
import { applyStreamUpdate, createAssistantMessage, createUserMessage, updateLastAssistantMessage } from "../state/messages";
import { loadAreaThreadHistory, streamAreaThreadChat } from "../transport/langgraph";
import { AnswerBlocks } from "./AnswerBlocks";
import { ContextViewer } from "./ContextViewer";
import { DocumentPreviewPane } from "./DocumentPreviewPane";
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
  const [isPreviewOpen, setIsPreviewOpen] = useState(false);
  const [isPreviewLoading, setIsPreviewLoading] = useState(false);
  const [previewDocumentCache, setPreviewDocumentCache] = useState<Record<string, DocumentPreviewPayload>>({});
  const [activePreviewCitation, setActivePreviewCitation] = useState<ChatContextReference | null>(null);
  const isChatSubmitLockedRef = useRef(false);

  useEffect(() => {
    setChatQuestion(EMPTY_CHAT_INPUT);
    setIsSubmittingChat(false);
    isChatSubmitLockedRef.current = false;

    if (!areaId) {
      setChatMessages([]);
      setIsPreviewOpen(false);
      setIsPreviewLoading(false);
      setActivePreviewCitation(null);
      return;
    }

    let isActive = true;
    void loadAreaThreadHistory(areaId, accessTokenGetter)
      .then((historyMessages) => {
        if (!isActive) {
          return;
        }
        setChatMessages(
          historyMessages.map((message) =>
            message.role === "user"
              ? createUserMessage(message.content, message.id)
              : createAssistantMessage({
                  id: message.id,
                  content: message.content,
                  answerBlocks: message.answerBlocks,
                  citations: message.citations,
                  usedKnowledgeBase: message.usedKnowledgeBase,
                  isStreaming: false,
                }),
          ),
        );
      })
      .catch((historyError) => {
        if (!isActive) {
          return;
        }
        const errorMessage = historyError instanceof Error ? historyError.message : "無法載入對話歷史。";
        setChatMessages([]);
        onError(errorMessage);
      });

    return () => {
      isActive = false;
    };
  }, [accessTokenGetter, areaId, onError]);

  /**
   * 開啟指定 citation 對應的全文預覽，並於首次點擊時抓取文件全文。
   *
   * Args:
   *   messageId: 被點擊引用所屬的 assistant 訊息識別碼。
   *   citation: 被點擊的 citation metadata。
   *
   * Returns:
   *   Promise<void>: 預覽狀態更新完成後結束。
   */
  async function handleCitationClick(messageId: string, citation: ChatContextReference): Promise<void> {
    setChatMessages((current) =>
      current.map((message) => ({
        ...message,
        selectedCitationContextIndex: message.id === messageId ? citation.context_index : null,
      })),
    );
    setIsPreviewOpen(true);
    setActivePreviewCitation(citation);

    if (previewDocumentCache[citation.document_id]) {
      return;
    }

    setIsPreviewLoading(true);
    try {
      const previewPayload = await fetchDocumentPreview(citation.document_id);
      setPreviewDocumentCache((current) => ({
        ...current,
        [citation.document_id]: previewPayload,
      }));
    } catch (error) {
      onError(error instanceof Error ? error.message : "無法載入文件預覽。");
    } finally {
      setIsPreviewLoading(false);
    }
  }

  /**
   * 送出目前的 area chat 問題，並以同步鎖避免連續 Enter 造成重複請求。
   *
   * Args:
   *   event: 觸發送出的表單事件。
   *
   * Returns:
   *   Promise<void>: 非同步送出流程完成後結束。
   */
  async function handleChatSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();

    if (isChatSubmitLockedRef.current) {
      return;
    }

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
    isChatSubmitLockedRef.current = true;
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
      isChatSubmitLockedRef.current = false;
      setIsSubmittingChat(false);
    }
  }

  return (
    <div className="flex h-full overflow-hidden rounded-[2rem] border border-stone-900/10 bg-white shadow-[0_18px_50px_rgba(47,39,24,0.04)]">
      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <div className="flex items-center justify-between border-b border-stone-900/5 px-8 py-4">
          <h3 className="text-lg font-semibold text-stone-900">Area Chat</h3>
          <span className="text-xs font-medium text-stone-400 uppercase tracking-wider">
            {areaId ? "Active Session" : "No Area Selected"}
          </span>
        </div>

        <div className="flex flex-1 flex-col overflow-hidden">
          <div className="flex-1 overflow-y-auto px-8 py-6 space-y-6" data-testid="chat-messages">
            {chatMessages.length > 0 ? (
              chatMessages.map((message) => (
                <article
                  key={message.id}
                  data-testid={`chat-message-${message.role}`}
                  className={`max-w-[85%] rounded-2xl px-5 py-4 ${
                    message.role === "user"
                      ? "ml-auto bg-stone-900 text-white"
                      : message.isError
                        ? "mr-auto border border-red-200 bg-red-50 text-red-900"
                        : "mr-auto border border-amber-100 bg-amber-50/50 text-stone-800"
                  }`}
                >
                  <div className="mb-2 flex items-center justify-between gap-3">
                    <p className={`text-[10px] font-bold uppercase tracking-widest ${
                      message.role === "user" ? "text-stone-400" : "text-amber-700"
                    }`}>
                      {message.role === "user" ? "You" : "Assistant"}
                    </p>
                    {message.isStreaming ? (
                      <span className="text-[10px] font-medium text-amber-600 animate-pulse">Streaming...</span>
                    ) : null}
                  </div>

                  {message.role === "assistant" ? (
                    <AnswerBlocks
                      answerBlocks={message.answerBlocks}
                      fallbackContent={message.content}
                      isStreaming={message.isStreaming}
                      selectedCitationContextIndex={message.selectedCitationContextIndex}
                      onCitationClick={(contextIndex) => {
                        const citation = message.citations.find((item) => item.context_index === contextIndex);
                        if (citation) {
                          void handleCitationClick(message.id, citation);
                        }
                      }}
                    />
                  ) : (
                    <p className="whitespace-pre-wrap text-sm leading-7">{message.content}</p>
                  )}

                  {message.role === "assistant" && message.phaseState ? (
                    <div className="mt-4 inline-flex items-center gap-2 rounded-full bg-stone-900/5 px-3 py-1 text-[10px] font-medium text-stone-600">
                      <span className="h-1.5 w-1.5 rounded-full bg-amber-500 animate-pulse" />
                      <span>{message.phaseState.message}</span>
                    </div>
                  ) : null}

                  {message.role === "assistant" && (
                    <div className="mt-4 space-y-3">
                      <ToolCallViewer toolCalls={message.toolCalls} />
                      {message.usedKnowledgeBase === false && !message.isStreaming && (
                        <p className="text-[10px] font-medium text-stone-400 italic">
                          No knowledge base references used in this turn.
                        </p>
                      )}
                      <ContextViewer citations={message.citations} />
                    </div>
                  )}
                </article>
              ))
            ) : (
              <div className="flex h-full flex-col items-center justify-center text-center opacity-40">
                <div className="mb-4 h-12 w-12 rounded-2xl bg-stone-100" />
                <p className="text-sm font-medium text-stone-500">
                  Ask a question to start the conversation.<br />
                  The assistant will search the knowledge base for answers.
                </p>
              </div>
            )}
          </div>

          <div className="border-t border-stone-900/5 bg-stone-50/50 p-6">
            <form className="relative" onSubmit={handleChatSubmit}>
              <textarea
                id="chat-question"
                data-testid="chat-question"
                rows={1}
                className="w-full resize-none rounded-2xl border border-stone-200 bg-white px-5 py-4 pr-32 text-sm shadow-sm outline-none transition focus:border-amber-600 focus:ring-1 focus:ring-amber-600/20"
                placeholder="Type your question here..."
                value={chatQuestion}
                onChange={(event) => setChatQuestion(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    void handleChatSubmit(event as unknown as FormEvent<HTMLFormElement>);
                  }
                }}
              />
              <div className="absolute right-3 top-3">
                <button
                  data-testid="chat-submit"
                  className="flex items-center gap-2 rounded-xl bg-stone-900 px-5 py-2 text-xs font-bold text-white transition hover:bg-stone-700 disabled:opacity-40"
                  disabled={isSubmittingChat || !chatQuestion.trim()}
                  type="submit"
                >
                  {isSubmittingChat ? "Thinking..." : "Send"}
                  <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 12h14M12 5l7 7-7 7" />
                  </svg>
                </button>
              </div>
            </form>
            <p className="mt-3 text-center text-[10px] text-stone-400">
              Press Enter to send, Shift + Enter for new line.
            </p>
          </div>
        </div>
      </div>

      <DocumentPreviewPane
        isOpen={isPreviewOpen}
        isLoading={isPreviewLoading}
        preview={activePreviewCitation ? (previewDocumentCache[activePreviewCitation.document_id] ?? null) : null}
        activeCitation={activePreviewCitation}
        onClose={() => {
          setIsPreviewOpen(false);
          setActivePreviewCitation(null);
          setChatMessages((current) =>
            current.map((message) => ({
              ...message,
              selectedCitationContextIndex: null,
            })),
          );
        }}
      />
    </div>
  );
}
