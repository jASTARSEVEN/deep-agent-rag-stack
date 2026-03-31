/** Chat feature 的工具呼叫檢視元件。 */

import type { ChatToolCallState } from "../../../lib/types";
import { StructuredValueNode } from "./StructuredValueNode";


interface ToolCallViewerProps {
  /** 目前訊息上累積的工具呼叫列表。 */
  toolCalls: ChatToolCallState[];
}


/** 顯示目前助理訊息的工具呼叫摘要。 */
export function ToolCallViewer({ toolCalls }: ToolCallViewerProps): JSX.Element | null {
  if (toolCalls.length === 0) {
    return null;
  }

  return (
    <div className="mt-4 space-y-2" data-testid="chat-tool-calls">
      {toolCalls.map((toolCall) => (
        <details
          key={toolCall.name}
          className="rounded-2xl border border-stone-200 bg-white/85 px-4 py-3"
        >
          <summary className="flex cursor-pointer list-none items-center justify-between gap-3 text-sm font-medium text-stone-900">
            <span>{toolCall.name}</span>
            <span className={`rounded-full px-3 py-1 text-xs ${
              toolCall.status === "completed"
                ? "bg-emerald-100 text-emerald-700"
                : "bg-stone-900 text-stone-100"
            }`}>
              {toolCall.status === "completed" ? "完成" : "執行中"}
            </span>
          </summary>
          <div className="mt-3 grid gap-3 text-xs text-stone-600">
            <StructuredValueNode label="輸入參數" value={toolCall.input} defaultOpen />
            {toolCall.output ? <StructuredValueNode label="輸出參數" value={toolCall.output} /> : null}
          </div>
        </details>
      ))}
    </div>
  );
}
