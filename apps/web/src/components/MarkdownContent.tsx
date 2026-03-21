/** 共用 Markdown 顯示元件，負責統一 chat 與 preview 的排版風格。 */

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";


interface MarkdownContentProps {
  /** 要顯示的 Markdown 內容。 */
  content: string;
  /** 額外樣式。 */
  className?: string;
}


/**
 * 組合 CSS class，避免在 JSX 中重複手動串接。
 *
 * @param className 呼叫端傳入的額外 class。
 * @returns 可直接套用到根節點的 class 字串。
 */
function buildMarkdownClassName(className?: string): string {
  return ["markdown-content", className].filter(Boolean).join(" ");
}


/** 顯示支援 GFM 的 Markdown 內容。 */
export function MarkdownContent({ content, className }: MarkdownContentProps): JSX.Element {
  return (
    <div className={buildMarkdownClassName(className)}>
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
    </div>
  );
}
