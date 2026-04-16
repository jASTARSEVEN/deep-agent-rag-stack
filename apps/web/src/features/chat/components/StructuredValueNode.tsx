/** Chat debug viewer 使用的結構化資料樹狀節點。 */

import { useState } from "react";


interface StructuredValueNodeProps {
  /** 目前節點標籤。 */
  label: string;
  /** 目前節點值。 */
  value: unknown;
  /** 是否預設展開。 */
  defaultOpen?: boolean;
  /** 目前遞迴深度。 */
  depth?: number;
}


/**
 * 判斷值是否為一般物件。
 *
 * @param value 待判斷的未知值。
 * @returns 若為非陣列物件則回傳 `true`。
 */
function isStructuredRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/**
 * 將純量值格式化為可直接顯示的完整文字。
 *
 * @param value 待格式化的純量值。
 * @returns 可直接顯示的字串。
 */
function formatStructuredScalarValue(value: unknown): string {
  if (typeof value === "string") {
    return value;
  }
  if (value === null) {
    return "null";
  }
  if (typeof value === "undefined") {
    return "undefined";
  }
  return String(value);
}


/**
 * 產生結構化資料節點摘要文字。
 *
 * @param value 目前節點值。
 * @returns 適合放在 summary 的精簡預覽文字。
 */
function formatStructuredPreview(value: unknown): string {
  if (Array.isArray(value)) {
    return `array(${value.length})`;
  }
  if (isStructuredRecord(value)) {
    return `object(${Object.keys(value).length})`;
  }
  if (typeof value === "string" && value.length > 40) {
    return `${value.slice(0, 40)}...`;
  }
  return formatStructuredScalarValue(value);
}


/**
 * 以遞迴 `<details>` 顯示可縮放的結構化資料。
 *
 * @param props 元件輸入。
 * @returns 可直接嵌入頁面的節點 UI。
 */
export function StructuredValueNode({
  label,
  value,
  defaultOpen = false,
  depth = 0,
}: StructuredValueNodeProps): JSX.Element {
  const [isOpen, setIsOpen] = useState(defaultOpen || depth < 1);
  const isArrayValue = Array.isArray(value);
  const isRecordValue = isStructuredRecord(value);
  const isExpandable = (isArrayValue && value.length > 0) || (isRecordValue && Object.keys(value).length > 0);

  if (!isExpandable) {
    return (
      <div className="rounded-xl bg-stone-100 px-3 py-2 text-xs text-stone-700">
        <span className="font-semibold text-stone-900">{label}</span>
        <span className="ml-2 whitespace-pre-wrap break-all">{formatStructuredScalarValue(value)}</span>
      </div>
    );
  }

  const entries = isArrayValue
    ? value.map((item, index) => [`[${index}]`, item] as const)
    : Object.entries(value);

  return (
    <div className="rounded-xl border border-stone-200 bg-stone-50">
      <button
        className="flex w-full cursor-pointer items-center px-3 py-2 text-left text-xs font-semibold text-stone-900"
        type="button"
        onClick={() => setIsOpen((current) => !current)}
      >
        {label}
        <span className="ml-2 font-normal text-stone-500">{formatStructuredPreview(value)}</span>
      </button>
      {isOpen ? (
        <div className="grid gap-2 px-3 pb-3">
          {entries.map(([entryLabel, entryValue]) => (
            <StructuredValueNode
              key={`${label}-${entryLabel}`}
              label={entryLabel}
              value={entryValue}
              depth={depth + 1}
            />
          ))}
        </div>
      ) : null}
    </div>
  );
}
