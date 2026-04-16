/** Chat feature 的工具呼叫檢視元件。 */

import { useState } from "react";

import type { ChatToolCallState } from "../../../lib/types";
import { StructuredValueNode } from "./StructuredValueNode";


interface ToolCallViewerProps {
  /** 目前訊息上累積的工具呼叫列表。 */
  toolCalls: ChatToolCallState[];
}

/**
 * 將 latency budget 狀態轉為摘要 badge 文案。
 *
 * @param status Tool output 內的 budget 狀態。
 * @returns 可直接顯示的 badge 文字；若無則回傳 `null`。
 */
function resolveLatencyBudgetLabel(status: unknown): string | null {
  if (status === "within_budget" || status === "normal") {
    return "20s 內";
  }
  if (status === "degraded") {
    return "延遲降級";
  }
  if (status === "failed" || status === "warning") {
    return "40s+ 警告";
  }
  if (typeof status === "string" && status.trim()) {
    return status;
  }
  return null;
}

interface ToolCallDetailsProps {
  /** 單一工具呼叫狀態。 */
  toolCall: ChatToolCallState;
  /** 目前工具在列表中的順序。 */
  index: number;
}

/**
 * 顯示單一工具呼叫卡片，並僅在展開時掛載大型 debug payload。
 *
 * @param props 元件輸入。
 * @returns 單一工具呼叫的摘要與可展開內容。
 */
function ToolCallDetails({ toolCall, index }: ToolCallDetailsProps): JSX.Element {
  const [isOpen, setIsOpen] = useState(false);
  const output = toolCall.output;
  const toolCallCount = typeof output?.tool_call_count === "number" ? output.tool_call_count : null;
  const followupCallCount = typeof output?.followup_call_count === "number" ? output.followup_call_count : null;
  const synopsisInspectionCount = typeof output?.synopsis_inspection_count === "number"
    ? output.synopsis_inspection_count
    : null;
  const stopReason = typeof output?.stop_reason === "string" ? output.stop_reason : null;
  const latencyBudgetLabel = resolveLatencyBudgetLabel(output?.latency_budget_status);
  const insufficientEvidence = output?.coverage_signals?.insufficient_evidence === true;

  return (
    <div
      data-testid={`chat-tool-call-${index}`}
      className="rounded-2xl border border-stone-200 bg-white/85 px-4 py-3"
    >
      <button
        className="flex w-full cursor-pointer items-center justify-between gap-3 text-left text-sm font-medium text-stone-900"
        type="button"
        onClick={() => setIsOpen((current) => !current)}
      >
        <span className="flex flex-wrap items-center gap-2">
          <span>{toolCall.name}</span>
          {toolCallCount !== null ? (
            <span className="rounded-full bg-stone-100 px-2 py-0.5 text-[10px] font-semibold text-stone-600">
              共 {toolCallCount} 次
            </span>
          ) : null}
          {followupCallCount !== null && followupCallCount > 0 ? (
            <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-semibold text-amber-700">
              follow-up {followupCallCount} 次
            </span>
          ) : null}
          {synopsisInspectionCount !== null && synopsisInspectionCount > 0 ? (
            <span className="rounded-full bg-sky-100 px-2 py-0.5 text-[10px] font-semibold text-sky-700">
              synopsis {synopsisInspectionCount} 次
            </span>
          ) : null}
          {latencyBudgetLabel ? (
            <span className="rounded-full bg-rose-100 px-2 py-0.5 text-[10px] font-semibold text-rose-700">
              {latencyBudgetLabel}
            </span>
          ) : null}
          {insufficientEvidence ? (
            <span className="rounded-full bg-orange-100 px-2 py-0.5 text-[10px] font-semibold text-orange-700">
              證據不足
            </span>
          ) : null}
        </span>
        <span className="flex items-center gap-2">
          {stopReason ? (
            <span className="rounded-full bg-stone-100 px-3 py-1 text-[10px] text-stone-600">
              停止：{stopReason}
            </span>
          ) : null}
          <span className={`rounded-full px-3 py-1 text-xs ${
            toolCall.status === "completed"
              ? "bg-emerald-100 text-emerald-700"
              : "bg-stone-900 text-stone-100"
          }`}>
            {toolCall.status === "completed" ? "完成" : "執行中"}
          </span>
        </span>
      </button>
      {isOpen ? (
        <div className="mt-3 grid gap-3 text-xs text-stone-600">
          <StructuredValueNode label="輸入參數" value={toolCall.input} defaultOpen />
          {toolCall.output ? <StructuredValueNode label="輸出參數" value={toolCall.output} /> : null}
        </div>
      ) : null}
    </div>
  );
}


/** 顯示目前助理訊息的工具呼叫摘要。 */
export function ToolCallViewer({ toolCalls }: ToolCallViewerProps): JSX.Element | null {
  if (toolCalls.length === 0) {
    return null;
  }

  return (
    <div className="mt-4 space-y-2" data-testid="chat-tool-calls">
      {toolCalls.map((toolCall, index) => (
        <ToolCallDetails key={`${toolCall.name}-${index}`} toolCall={toolCall} index={index} />
      ))}
    </div>
  );
}
