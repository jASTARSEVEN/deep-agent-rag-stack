/** Chat feature 的 assembled context 檢視元件。 */

import type { ChatContextReference } from "../../../lib/types";
import { StructuredValueNode } from "./StructuredValueNode";


interface ContextViewerProps {
  /** 本輪助理訊息附帶的 contexts。 */
  citations: ChatContextReference[];
}


/** 顯示 assembled contexts，而不是 child-level citations。 */
export function ContextViewer({ citations }: ContextViewerProps): JSX.Element | null {
  if (citations.length === 0) {
    return null;
  }

  return (
    <div className="mt-4 rounded-2xl bg-white/80 px-4 py-3" data-testid="chat-citations">
      <details>
        <summary className="cursor-pointer list-none text-xs font-semibold uppercase tracking-[0.18em] text-stone-500">
          Assembled Contexts
          <span className="ml-2 normal-case tracking-normal text-stone-400">
            {citations.length} contexts
          </span>
        </summary>
        <div className="mt-3 grid gap-2">
          {citations.map((citation) => (
            <details
              key={`${citation.context_index}-${citation.parent_chunk_id ?? "root"}`}
              data-testid={`chat-citation-${citation.context_index}`}
              className="rounded-xl border border-stone-200 bg-white px-3 py-3 text-sm text-stone-700"
            >
              <summary className="cursor-pointer list-none font-medium text-stone-900">
                #{citation.context_index + 1} {citation.heading ?? "(無標題)"} / {citation.structure_kind}
              </summary>
              <div className="mt-3">
                <StructuredValueNode
                  label={`Context ${citation.context_index + 1}`}
                  value={{
                    ...citation,
                    parent: citation.parent_chunk_id,
                    children: citation.child_chunk_ids.join(", "),
                  }}
                  defaultOpen
                />
              </div>
            </details>
          ))}
        </div>
      </details>
    </div>
  );
}
