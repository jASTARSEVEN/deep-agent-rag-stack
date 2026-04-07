/** 共用 Markdown 顯示元件，負責統一 chat 與 preview 的排版風格。 */

import { createElement } from "react";
import type { ReactNode } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";


/** Markdown 內容的顯示模式。 */
type MarkdownDisplayMode = "block" | "inline";

/** 可承接 citation adornment 的 block 標籤集合。 */
const TRAILING_ADORNMENT_BLOCK_TAGS = new Set([
  "p",
  "ul",
  "ol",
  "blockquote",
  "pre",
  "table",
  "h1",
  "h2",
  "h3",
  "h4",
  "h5",
  "h6",
]);

/** citation 可直接接在同一個 block 末尾的標籤集合。 */
const INLINE_ADORNMENT_TAGS = ["p", "li", "blockquote", "h1", "h2", "h3", "h4", "h5", "h6", "pre"] as const;

/** ReactMarkdown 節點的最小需求型別。 */
interface MarkdownNodeLike {
  /** 子節點列表。 */
  children?: unknown[];
  /** 來源文字位置資訊。 */
  position?: {
    /** 結束位置資訊。 */
    end?: {
      /** 在原始字串中的結束 offset。 */
      offset?: number;
    };
  };
}

/** 我們在 markdown override 中實際會用到的最小 props。 */
interface MarkdownRendererProps {
  /** ReactMarkdown 傳入的 HAST node。 */
  node?: MarkdownNodeLike;
  /** 該節點既有 children。 */
  children?: ReactNode;
}

interface MarkdownContentProps {
  /** 要顯示的 Markdown 內容。 */
  content: string;
  /** 額外樣式。 */
  className?: string;
  /** 是否以 inline 方式渲染。 */
  displayMode?: MarkdownDisplayMode;
  /** 需要接在 Markdown 最後一個 block 後方的額外內容。 */
  trailingAdornment?: ReactNode;
}

/**
 * 組合 CSS class，避免在 JSX 中重複手動串接。
 *
 * @param className 呼叫端傳入的額外 class。
 * @param displayMode Markdown 顯示模式。
 * @returns 可直接套用到根節點的 class 字串。
 */
function buildMarkdownClassName(className?: string, displayMode: MarkdownDisplayMode = "block"): string {
  return ["markdown-content", displayMode === "inline" ? "inline" : "", className].filter(Boolean).join(" ");
}

/**
 * 將常見但不完全合法的 Markdown 清單前綴正規化，避免模型輸出少一個空白時失去列表樣式。
 *
 * @param content 原始 Markdown 文字。
 * @returns 補齊清單 marker 空白後的文字。
 */
function normalizeMarkdownListMarkers(content: string): string {
  return content
    .replace(/^(?<indent>\s*)-(?=\S)/gm, "$<indent>- ")
    .replace(/^(?<indent>\s*)(?<order>\d+)\.(?=\S)/gm, "$<indent>$<order>. ");
}

/**
 * 判斷節點是否已有 block-level 子節點，避免 parent/child 重複附加 citation adornment。
 *
 * @param node ReactMarkdown 傳入的節點資訊。
 * @returns 若已有 block-level 子節點則回傳 `true`。
 */
function hasNestedBlockChild(node: MarkdownNodeLike | undefined): boolean {
  if (!Array.isArray(node?.children)) {
    return false;
  }
  return node.children.some((child) => {
    if (typeof child !== "object" || child === null) {
      return false;
    }
    const tagName = "tagName" in child && typeof child.tagName === "string" ? child.tagName : "";
    return TRAILING_ADORNMENT_BLOCK_TAGS.has(tagName);
  });
}

/**
 * 判斷目前節點是否為應掛上尾端 adornment 的最後一個 block。
 *
 * @param node ReactMarkdown 傳入的節點資訊。
 * @param trailingOffset 正規化內容去尾端空白後的結束 offset。
 * @param allowNestedBlock 是否允許有 block-level 子節點仍視為可掛載。
 * @returns 若應掛上 adornment 則回傳 `true`。
 */
function shouldAttachTrailingAdornment(
  node: MarkdownNodeLike | undefined,
  trailingOffset: number | null,
  allowNestedBlock = false,
): boolean {
  if (trailingOffset === null) {
    return false;
  }
  if (!allowNestedBlock && hasNestedBlockChild(node)) {
    return false;
  }
  return node?.position?.end?.offset === trailingOffset;
}

/**
 * 將尾端 adornment 接到目前 block 後方。
 *
 * @param children 既有 Markdown block children。
 * @param trailingAdornment 要附加的內容。
 * @returns 組合後的 React 節點。
 */
function appendTrailingAdornment(children: ReactNode, trailingAdornment: ReactNode): ReactNode {
  return (
    <>
      {children}
      <span className="ml-2 inline-flex align-middle">{trailingAdornment}</span>
    </>
  );
}

/**
 * 將 markdown block 包成可附加尾端 adornment 的通用 renderer。
 *
 * @param tagName 要輸出的 HTML tag。
 * @param trailingAdornment 需要接在最後 block 後方的額外內容。
 * @param trailingOffset 正規化內容去尾端空白後的結束 offset。
 * @param allowNestedBlock 是否允許有 block-level 子節點仍視為可掛載。
 * @returns 對應的 ReactMarkdown component renderer。
 */
function createTrailingAdornmentRenderer(
  tagName: keyof JSX.IntrinsicElements,
  trailingAdornment: ReactNode | undefined,
  trailingOffset: number | null,
  allowNestedBlock = false,
): (props: MarkdownRendererProps) => JSX.Element {
  return ({ node, children }) =>
    createElement(
      tagName,
      null,
      shouldAttachTrailingAdornment(node, trailingOffset, allowNestedBlock) && trailingAdornment
        ? appendTrailingAdornment(children, trailingAdornment)
        : children,
    );
}

/**
 * 建立 table 的尾端 adornment renderer。
 *
 * @param trailingAdornment 需要接在最後 block 後方的額外內容。
 * @param trailingOffset 正規化內容去尾端空白後的結束 offset。
 * @returns table 專用 renderer。
 */
function createTableRenderer(
  trailingAdornment: ReactNode | undefined,
  trailingOffset: number | null,
): (props: MarkdownRendererProps) => JSX.Element {
  return ({ node, children }) => (
    <>
      <table>{children}</table>
      {shouldAttachTrailingAdornment(node, trailingOffset, true) && trailingAdornment ? (
        <div className="mt-2">{trailingAdornment}</div>
      ) : null}
    </>
  );
}

/**
 * 依顯示模式建立 ReactMarkdown components。
 *
 * @param displayMode Markdown 顯示模式。
 * @param trailingAdornment 需要接在最後 block 後方的額外內容。
 * @param trailingOffset 正規化內容去尾端空白後的結束 offset。
 * @returns ReactMarkdown components 設定。
 */
function resolveMarkdownComponents(
  displayMode: MarkdownDisplayMode,
  trailingAdornment?: ReactNode,
  trailingOffset: number | null = null,
): Components {
  if (displayMode === "inline") {
    return {
      p: ({ children }) => <span>{children}</span>,
    };
  }
  const components: Partial<Record<(typeof INLINE_ADORNMENT_TAGS)[number] | "table", (props: MarkdownRendererProps) => JSX.Element>> = {
    table: createTableRenderer(trailingAdornment, trailingOffset),
  };
  INLINE_ADORNMENT_TAGS.forEach((tagName) => {
    components[tagName] = createTrailingAdornmentRenderer(tagName, trailingAdornment, trailingOffset);
  });
  return components as Components;
}

/**
 * 顯示支援 GFM 的 Markdown 內容。
 *
 * @param props Markdown 顯示設定。
 * @param props.content 要顯示的 Markdown 文字。
 * @param props.className 額外 class 名稱。
 * @param props.displayMode Markdown 顯示模式。
 * @param props.trailingAdornment 需要接在最後 block 後方的額外內容。
 * @returns Markdown 呈現結果。
 */
export function MarkdownContent({
  content,
  className,
  displayMode = "block",
  trailingAdornment,
}: MarkdownContentProps): JSX.Element {
  const normalizedContent = normalizeMarkdownListMarkers(content);
  const trailingOffset = trailingAdornment ? normalizedContent.trimEnd().length : null;

  return (
    <div className={buildMarkdownClassName(className, displayMode)}>
      <ReactMarkdown
        components={resolveMarkdownComponents(displayMode, trailingAdornment, trailingOffset)}
        remarkPlugins={[remarkGfm]}
      >
        {normalizedContent}
      </ReactMarkdown>
    </div>
  );
}
