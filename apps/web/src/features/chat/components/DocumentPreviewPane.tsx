/** Chat 右側全文預覽與 chunk-aware highlighting 元件。 */

import { useEffect, useMemo, useRef, useState } from "react";

import { MarkdownContent } from "../../../components/MarkdownContent";
import type { ChatContextReference, DocumentPreviewPayload } from "../../../lib/types";


interface PreviewSegment {
  /** 區段穩定識別碼。 */
  key: string;
  /** 區段文字內容。 */
  text: string;
  /** 若此區段對應到 chunk，則帶上 chunk 識別碼。 */
  chunkId: string | null;
}


interface DocumentPreviewPaneProps {
  /** 預覽欄是否開啟。 */
  isOpen: boolean;
  /** 是否仍在載入全文。 */
  isLoading: boolean;
  /** 已載入的全文 preview payload。 */
  preview: DocumentPreviewPayload | null;
  /** 目前作用中的 citation；chat 模式可選。 */
  activeCitation?: ChatContextReference | null;
  /** 目前作用中的 chunk ids。 */
  activeChunkIds?: string[];
  /** 目前 hover 的 chunk id。 */
  hoverChunkId?: string | null;
  /** chunk hover 狀態變更通知。 */
  onHoverChunkChange?: (chunkId: string | null) => void;
  /** 點擊 chunk 時通知外層。 */
  onChunkClick?: (chunkId: string) => void;
  /** 使用者手動捲動 preview 時，通知目前聚焦的 chunk。 */
  onFocusedChunkChange?: (chunkId: string | null) => void;
  /** 面板標題。 */
  title?: string;
  /** 面板副標。 */
  subtitle?: string;
  /** 無資料時顯示的訊息。 */
  emptyMessage?: string;
  /** 作用中高亮說明。 */
  activeLegendLabel?: string;
  /** hover 高亮說明。 */
  hoverLegendLabel?: string;
  /** 關閉預覽欄。 */
  onClose: () => void;
}


/** 顯示全文、active citation 與 hover chunk 高亮。 */
export function DocumentPreviewPane({
  isOpen,
  isLoading,
  preview,
  activeCitation = null,
  activeChunkIds: activeChunkIdsProp,
  hoverChunkId: hoverChunkIdProp,
  onHoverChunkChange,
  onChunkClick,
  onFocusedChunkChange,
  title,
  subtitle,
  emptyMessage = "Select a citation to preview the document.",
  activeLegendLabel = "Active citation",
  hoverLegendLabel = "Hover highlights current chunk",
  onClose,
}: DocumentPreviewPaneProps): JSX.Element | null {
  const [internalHoverChunkId, setInternalHoverChunkId] = useState<string | null>(null);
  const scrollContainerRef = useRef<HTMLDivElement | null>(null);
  const chunkRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const autoScrollTargetChunkIdRef = useRef<string | null>(null);
  const programmaticScrollUntilRef = useRef(0);
  const scrollFrameRef = useRef<number | null>(null);

  const orderedActiveChunkIds = activeChunkIdsProp ?? activeCitation?.child_chunk_ids ?? [];
  const activeChunkIds = useMemo(() => new Set(orderedActiveChunkIds), [orderedActiveChunkIds]);
  const hoverChunkId = hoverChunkIdProp ?? internalHoverChunkId;

  const previewSegments = useMemo<PreviewSegment[]>(() => {
    if (!preview) {
      return [];
    }

    const segments: PreviewSegment[] = [];
    const sortedChunks = [...preview.chunks].sort((left, right) => left.start_offset - right.start_offset);
    let cursor = 0;

    sortedChunks.forEach((chunk, index) => {
      const start = Math.max(0, chunk.start_offset);
      const end = Math.max(start, chunk.end_offset);

      if (start > cursor) {
        segments.push({
          key: `gap-${cursor}-${start}`,
          text: preview.display_text.slice(cursor, start),
          chunkId: null,
        });
      }

      segments.push({
        key: `chunk-${chunk.chunk_id}-${index}`,
        text: preview.display_text.slice(start, end),
        chunkId: chunk.chunk_id,
      });
      cursor = Math.max(cursor, end);
    });

    if (cursor < preview.display_text.length) {
      segments.push({
        key: `gap-${cursor}-${preview.display_text.length}`,
        text: preview.display_text.slice(cursor),
        chunkId: null,
      });
    }

    return segments;
  }, [preview]);

  /**
   * 根據目前 viewport 計算最接近中央的可見 chunk，作為使用者捲動時的 focus chunk。
   *
   * @returns 目前最接近 viewport 中央的 chunk id；若無可見 chunk 則回傳 null。
   */
  function findFocusedChunkId(): string | null {
    const container = scrollContainerRef.current;
    if (!container || !preview) {
      return null;
    }

    const containerRect = container.getBoundingClientRect();
    const viewportCenter = containerRect.top + (containerRect.height / 2);
    let closestChunkId: string | null = null;
    let closestDistance = Number.POSITIVE_INFINITY;

    preview.chunks.forEach((chunk) => {
      const element = chunkRefs.current[chunk.chunk_id];
      if (!element) {
        return;
      }

      const rect = element.getBoundingClientRect();
      const visibleTop = Math.max(rect.top, containerRect.top);
      const visibleBottom = Math.min(rect.bottom, containerRect.bottom);
      if (visibleBottom <= visibleTop) {
        return;
      }

      const visibleCenter = visibleTop + ((visibleBottom - visibleTop) / 2);
      const distance = Math.abs(visibleCenter - viewportCenter);
      if (distance < closestDistance) {
        closestDistance = distance;
        closestChunkId = chunk.chunk_id;
      }
    });

    return closestChunkId;
  }

  useEffect(() => {
    if (!isOpen || orderedActiveChunkIds.length === 0) {
      return;
    }

    const nextChunkId = orderedActiveChunkIds.find((chunkId) => Boolean(chunkRefs.current[chunkId])) ?? null;
    if (!nextChunkId || autoScrollTargetChunkIdRef.current === nextChunkId) {
      return;
    }

    autoScrollTargetChunkIdRef.current = nextChunkId;
    programmaticScrollUntilRef.current = window.performance.now() + 500;
    chunkRefs.current[nextChunkId]?.scrollIntoView({
      behavior: "smooth",
      block: "center",
      inline: "nearest",
    });
  }, [isOpen, orderedActiveChunkIds, preview]);

  useEffect(() => {
    if (!preview) {
      autoScrollTargetChunkIdRef.current = null;
      return;
    }

    const previewChunkIds = new Set(preview.chunks.map((chunk) => chunk.chunk_id));
    if (autoScrollTargetChunkIdRef.current && !previewChunkIds.has(autoScrollTargetChunkIdRef.current)) {
      autoScrollTargetChunkIdRef.current = null;
    }
  }, [preview]);

  useEffect(() => {
    const container = scrollContainerRef.current;
    if (!container || !preview) {
      return;
    }

    /**
     * 在使用者手動捲動後，回報目前最接近 preview 中央的 chunk。
     *
     * @returns 無；僅通知外層目前聚焦的 chunk。
     */
    function syncFocusedChunkFromScroll(): void {
      if (window.performance.now() < programmaticScrollUntilRef.current) {
        return;
      }

      const focusedChunkId = findFocusedChunkId();
      if (!focusedChunkId || activeChunkIds.has(focusedChunkId)) {
        return;
      }
      onFocusedChunkChange?.(focusedChunkId);
    }

    /**
     * 將高頻 scroll 事件收斂到單一 animation frame，避免重複量測。
     *
     * @returns 無；僅排程 focused chunk 同步。
     */
    function handleScroll(): void {
      if (scrollFrameRef.current !== null) {
        window.cancelAnimationFrame(scrollFrameRef.current);
      }
      scrollFrameRef.current = window.requestAnimationFrame(() => {
        scrollFrameRef.current = null;
        syncFocusedChunkFromScroll();
      });
    }

    container.addEventListener("scroll", handleScroll, { passive: true });
    return () => {
      container.removeEventListener("scroll", handleScroll);
      if (scrollFrameRef.current !== null) {
        window.cancelAnimationFrame(scrollFrameRef.current);
        scrollFrameRef.current = null;
      }
    };
  }, [activeChunkIds, onFocusedChunkChange, preview]);

  /**
   * 同步更新 hover chunk 狀態，支援受控與非受控模式。
   *
   * @param nextChunkId 下一個 hover chunk id。
   * @returns 無；僅更新目前 hover 狀態。
   */
  function updateHoverChunk(nextChunkId: string | null): void {
    if (hoverChunkIdProp === undefined) {
      setInternalHoverChunkId(nextChunkId);
    }
    onHoverChunkChange?.(nextChunkId);
  }

  if (!isOpen) {
    return null;
  }

  return (
    <aside className="hidden h-full w-[28rem] flex-col border-l border-stone-900/5 bg-stone-50/80 xl:flex">
      <div className="flex items-start justify-between gap-4 border-b border-stone-900/5 px-5 py-4">
        <div className="min-w-0">
          <h4 className="truncate text-sm font-semibold text-stone-900">
            {title ?? preview?.file_name ?? activeCitation?.document_name ?? "Document Preview"}
          </h4>
          <p className="mt-1 truncate text-[11px] text-stone-500">
            {subtitle ?? activeCitation?.heading ?? "全文預覽"}
          </p>
        </div>
        <button
          type="button"
          className="rounded-full border border-stone-200 bg-white px-3 py-1 text-[11px] font-semibold text-stone-600 transition hover:border-stone-300 hover:text-stone-900"
          onClick={onClose}
        >
          Close
        </button>
      </div>

      <div ref={scrollContainerRef} className="flex-1 overflow-y-auto px-5 py-4" data-testid="document-preview-pane">
        {isLoading ? <p className="text-sm text-stone-500">Loading document preview...</p> : null}
        {!isLoading && !preview ? (
          <p className="text-sm text-stone-500">{emptyMessage}</p>
        ) : null}
        {!isLoading && preview ? (
          <div className="rounded-2xl border border-stone-200 bg-white p-4 shadow-sm">
            <div className="mb-3 flex flex-wrap items-center gap-2 text-[11px] text-stone-500">
              <span className="rounded-full bg-amber-100 px-2 py-1 text-amber-800">{activeLegendLabel}</span>
              <span className="rounded-full bg-stone-100 px-2 py-1 text-stone-600">{hoverLegendLabel}</span>
            </div>
            <div className="space-y-3 text-sm leading-7 text-stone-700">
              {previewSegments.map((segment) => {
                if (!segment.chunkId) {
                  return (
                    <div key={segment.key} className="rounded-xl px-1">
                      <MarkdownContent content={segment.text} className="text-sm leading-7 text-stone-700" />
                    </div>
                  );
                }

                const chunkId = segment.chunkId;
                const isActiveChunk = activeChunkIds.has(chunkId);
                const isHoverChunk = hoverChunkId === chunkId;
                const highlightClass = isActiveChunk
                  ? "border-amber-300 bg-amber-100/90 ring-1 ring-amber-300"
                  : isHoverChunk
                    ? "border-sky-200 bg-sky-50/90"
                    : "border-transparent";

                return (
                  <div
                    key={segment.key}
                    ref={(element) => {
                      chunkRefs.current[chunkId] = element;
                    }}
                    data-testid={`preview-chunk-${chunkId}`}
                    className={`cursor-pointer rounded-2xl border px-3 py-2 transition-colors ${highlightClass}`}
                    onClick={() => onChunkClick?.(chunkId)}
                    onMouseEnter={() => updateHoverChunk(chunkId)}
                    onMouseLeave={() => updateHoverChunk(null)}
                  >
                    <MarkdownContent content={segment.text} className="text-sm leading-7 text-stone-700" />
                  </div>
                );
              })}
            </div>
          </div>
        ) : null}
      </div>
    </aside>
  );
}
