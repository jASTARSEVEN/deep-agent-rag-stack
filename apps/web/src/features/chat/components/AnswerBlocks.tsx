/** assistant 回答區塊與 citation chips 顯示元件。 */

import { MarkdownContent } from "../../../components/MarkdownContent";
import type { ChatAnswerBlock, ChatPhaseState } from "../../../lib/types";


interface AnswerBlocksProps {
  /** 已 parse 完成的回答區塊。 */
  answerBlocks: ChatAnswerBlock[];
  /** 若尚未有結構化區塊時回退使用的內容。 */
  fallbackContent: string;
  /** 是否仍在串流中。 */
  isStreaming: boolean;
  /** 目前高層 chat 階段。 */
  phaseState: ChatPhaseState | null;
  /** 目前選取的 citation context index。 */
  selectedCitationContextIndex: number | null;
  /** 點擊 citation 時通知外層。 */
  onCitationClick: (contextIndex: number) => void;
}

/** 將細節 phase 收斂成穩定、可理解的使用者文案。 */
export function resolveStreamingStatusLabel(phaseState: ChatPhaseState | null): string {
  if (!phaseState) {
    return "正在準備回答...";
  }
  switch (phaseState.phase) {
    case "preparing":
      return "正在準備回答...";
    case "thinking":
      return "正在思考中...";
    case "searching":
    case "tool_calling":
      return "正在查找相關內容...";
    case "drafting":
      return "正在撰寫回答...";
    default:
      return "正在準備回答...";
  }
}

/** 根據目前 phase 與輪播索引產生 streaming 佔位文案。 */
function resolveStreamingPlaceholder(
  fallbackContent: string,
  isStreaming: boolean,
  phaseState: ChatPhaseState | null,
): string {
  if (fallbackContent) {
    return fallbackContent;
  }
  if (!isStreaming) {
    return "目前尚無內容";
  }
  return "";
}


/** 顯示 assistant 回答與句尾 citations。 */
export function AnswerBlocks({
  answerBlocks,
  fallbackContent,
  isStreaming,
  phaseState,
  selectedCitationContextIndex,
  onCitationClick,
}: AnswerBlocksProps): JSX.Element {
  if (answerBlocks.length === 0) {
    const placeholderContent = resolveStreamingPlaceholder(fallbackContent, isStreaming, phaseState);
    return (
      <div className="rounded-2xl bg-white/70 px-4 py-3">
        {placeholderContent ? (
          <MarkdownContent
            content={placeholderContent}
            className="text-sm leading-7 text-inherit"
          />
        ) : (
          <div className="h-6" aria-hidden="true" />
        )}
      </div>
    );
  }

  return (
    <div className="rounded-2xl bg-white/70 px-4 py-3">
      {answerBlocks.map((block, index) => (
        <div
          key={`${index}-${block.text.slice(0, 24)}`}
          className={index === 0 ? "" : "mt-4 border-t border-stone-200/70 pt-4"}
        >
          <MarkdownContent content={block.text} className="text-sm leading-7 text-stone-800" />
          {block.display_citations.length > 0 ? (
            <div className="mt-4 inline-flex flex-wrap items-center gap-2 align-middle">
              {block.display_citations.map((citation) => {
                const isSelected = selectedCitationContextIndex === citation.context_index;
                const label = citation.context_label || `C${citation.context_index + 1}`;
                return (
                  <button
                    key={`${index}-${citation.context_index}`}
                    type="button"
                    data-testid={`citation-chip-${citation.context_index}`}
                    title={`${citation.document_name}${citation.heading ? ` / ${citation.heading}` : ""}`}
                    className={`rounded-full border px-2.5 py-0.5 text-[11px] font-semibold transition ${
                      isSelected
                        ? "border-amber-500 bg-amber-100 text-amber-900"
                        : "border-stone-200 bg-white text-stone-600 hover:border-amber-300 hover:text-stone-900"
                    }`}
                    onClick={() => onCitationClick(citation.context_index)}
                  >
                    {label}
                  </button>
                );
              })}
            </div>
          ) : null}
        </div>
      ))}
    </div>
  );
}
