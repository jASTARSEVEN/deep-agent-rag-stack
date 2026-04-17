import React, { useState, useEffect, useMemo, useRef, type FormEvent } from "react";
import { DocumentPreviewPane } from "../../chat/components/DocumentPreviewPane";
import { 
  fetchDocuments, 
  fetchDocumentPreview,
  uploadDocument, 
  reindexDocument, 
  deleteDocument,
  fetchIngestJob
} from "../../../lib/api";
import type { DocumentPreviewPayload, DocumentSummary, IngestJobSummary } from "../../../generated/rest";

/**
 * DocumentsDrawer 元件。
 * 右側滑出的抽屜，用於管理指定 Area 的文件。
 * 
 * @param isOpen 是否開啟。
 * @param onClose 關閉回調。
 * @param areaId 目前選中的 Area 識別碼。
 * @param areaName 目前選中的 Area 名稱。
 * @param effectiveRole 使用者在該 Area 的角色。
 */
interface DocumentsDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  areaId: string;
  areaName: string;
  effectiveRole: string;
}

/** 格式化 chunk 摘要文字。 */
function formatChunkSummary(document: DocumentSummary): string {
  return `${document.chunk_summary.total_chunks} chunks (${document.chunk_summary.parent_chunks} parent / ${document.chunk_summary.child_chunks} child)`;
}

/** 建立 chunk 摘要預覽文字。 */
function buildChunkExcerpt(preview: DocumentPreviewPayload, startOffset: number, endOffset: number): string {
  const content = preview.display_text.slice(Math.max(0, startOffset), Math.max(startOffset, endOffset)).replace(/\s+/g, " ").trim();
  if (!content) {
    return "此 chunk 沒有可顯示的文字內容。";
  }
  return content.length > 140 ? `${content.slice(0, 140)}…` : content;
}

export function DocumentsDrawer({ 
  isOpen, 
  onClose, 
  areaId, 
  areaName,
  effectiveRole
}: DocumentsDrawerProps): JSX.Element {
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [documentJobs, setDocumentJobs] = useState<Record<string, IngestJobSummary>>({});
  const [previewDocumentCache, setPreviewDocumentCache] = useState<Record<string, DocumentPreviewPayload>>({});
  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(null);
  const [selectedChunkId, setSelectedChunkId] = useState<string | null>(null);
  const [hoverChunkId, setHoverChunkId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isPreviewLoading, setIsPreviewLoading] = useState(false);
  const [isSubmittingUpload, setIsSubmittingUpload] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [activeActionId, setActiveActionId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const chunkListContainerRef = useRef<HTMLDivElement | null>(null);
  const chunkItemRefs = useRef<Record<string, HTMLButtonElement | null>>({});
  const lastChunkSelectionSourceRef = useRef<"list-click" | "preview-scroll" | "system" | null>(null);

  // 載入文件清單
  const loadDocuments = async () => {
    setIsLoading(true);
    try {
      const payload = await fetchDocuments(areaId);
      setDocuments(payload.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "載入文件失敗");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen && areaId) {
      void loadDocuments();
    }
  }, [isOpen, areaId]);

  useEffect(() => {
    if (isOpen) {
      return;
    }
    setSelectedDocumentId(null);
    setSelectedChunkId(null);
    setHoverChunkId(null);
    setPreviewDocumentCache({});
  }, [isOpen]);

  useEffect(() => {
    setSelectedDocumentId(null);
    setSelectedChunkId(null);
    setHoverChunkId(null);
    setPreviewDocumentCache({});
    setDocumentJobs({});
  }, [areaId]);

  // 輪詢狀態
  useEffect(() => {
    if (!areaId || !isOpen) return;

    const hasPending = documents.some(d => d.status === "uploaded" || d.status === "processing");
    const pendingJobs = Object.entries(documentJobs).filter(([, job]) => job.status === "queued" || job.status === "processing");

    if (!hasPending && pendingJobs.length === 0) return;

    const timer = window.setTimeout(async () => {
      const payload = await fetchDocuments(areaId);
      setDocuments(payload.items);

      if (pendingJobs.length > 0) {
        const refreshed = await Promise.all(
          pendingJobs.map(async ([docId, job]) => [docId, await fetchIngestJob(job.id)] as const)
        );
        setDocumentJobs(prev => ({ ...prev, ...Object.fromEntries(refreshed) }));
      }
    }, 2000);

    return () => window.clearTimeout(timer);
  }, [areaId, isOpen, documents, documentJobs]);

  useEffect(() => {
    if (!selectedDocumentId) {
      return;
    }

    const selectedDocument = documents.find((doc) => doc.id === selectedDocumentId);
    if (!selectedDocument) {
      setSelectedDocumentId(null);
      setSelectedChunkId(null);
      setHoverChunkId(null);
      return;
    }

    if (selectedDocument.status !== "ready") {
      setSelectedChunkId(null);
      setHoverChunkId(null);
      return;
    }

    const selectedPreview = previewDocumentCache[selectedDocumentId];
    if (!selectedPreview || selectedPreview.chunks.length === 0) {
      setSelectedChunkId(null);
      return;
    }

    const hasSelectedChunk = selectedChunkId !== null && selectedPreview.chunks.some((chunk) => chunk.chunk_id === selectedChunkId);
    if (!hasSelectedChunk) {
      lastChunkSelectionSourceRef.current = "system";
      setSelectedChunkId(selectedPreview.chunks[0]?.chunk_id ?? null);
    }
  }, [documents, previewDocumentCache, selectedChunkId, selectedDocumentId]);

  useEffect(() => {
    if (lastChunkSelectionSourceRef.current !== "preview-scroll" || !selectedChunkId) {
      return;
    }

    const container = chunkListContainerRef.current;
    const item = chunkItemRefs.current[selectedChunkId];
    if (!container || !item) {
      return;
    }

    const containerRect = container.getBoundingClientRect();
    const itemRect = item.getBoundingClientRect();
    const isVisible = itemRect.top >= containerRect.top && itemRect.bottom <= containerRect.bottom;

    if (!isVisible) {
      item.scrollIntoView({
        behavior: "smooth",
        block: "nearest",
        inline: "nearest",
      });
    }

    lastChunkSelectionSourceRef.current = null;
  }, [selectedChunkId]);

  const selectedDocument = useMemo(
    () => documents.find((doc) => doc.id === selectedDocumentId) ?? null,
    [documents, selectedDocumentId],
  );
  const selectedPreview = selectedDocumentId ? (previewDocumentCache[selectedDocumentId] ?? null) : null;

  /**
   * 清除單一文件相關的 preview 與選取狀態。
   *
   * @param documentId 要清除的文件識別碼。
   * @returns 無；僅更新本地 state。
   */
  function clearDocumentPreviewState(documentId: string): void {
    setPreviewDocumentCache((prev) => {
      if (!(documentId in prev)) {
        return prev;
      }
      const next = { ...prev };
      delete next[documentId];
      return next;
    });
    if (selectedDocumentId === documentId) {
      setSelectedChunkId(null);
      setHoverChunkId(null);
    }
  }

  /**
   * 開啟指定 ready 文件的 chunk-aware 預覽。
   *
   * @param document 要開啟的文件。
   * @returns 預覽資料載入完成後結束。
   */
  async function handleReadyDocumentSelect(document: DocumentSummary): Promise<void> {
    if (document.status !== "ready") {
      return;
    }

    setSelectedDocumentId(document.id);
    lastChunkSelectionSourceRef.current = "system";
    setSelectedChunkId(null);
    setHoverChunkId(null);
    setError(null);

    if (previewDocumentCache[document.id]) {
      return;
    }

    setIsPreviewLoading(true);
    try {
      const previewPayload = await fetchDocumentPreview(document.id);
      setPreviewDocumentCache((current) => ({
        ...current,
        [document.id]: previewPayload,
      }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "載入文件預覽失敗");
    } finally {
      setIsPreviewLoading(false);
    }
  }

  const handleUpload = async (e: FormEvent) => {
    e.preventDefault();
    if (!uploadFile) return;

    setIsSubmittingUpload(true);
    setError(null);
    setNotice(null);
    try {
      const payload = await uploadDocument(areaId, uploadFile);
      const job = await fetchIngestJob(payload.job.id);
      setDocumentJobs(prev => ({ ...prev, [payload.document.id]: job }));
      setUploadFile(null);
      setNotice(`已上傳：${payload.document.file_name}`);
      await loadDocuments();
    } catch (err) {
      setError(err instanceof Error ? err.message : "上傳失敗");
    } finally {
      setIsSubmittingUpload(false);
    }
  };

  const handleReindex = async (doc: DocumentSummary, forceReparse = false) => {
    setActiveActionId(doc.id);
    setError(null);
    setNotice(null);
    try {
      const payload = await reindexDocument(doc.id, { forceReparse });
      const job = await fetchIngestJob(payload.job.id);
      setDocumentJobs(prev => ({ ...prev, [doc.id]: job }));
      setNotice(forceReparse ? `已啟動強制重新解析：${doc.file_name}` : `已啟動重新索引：${doc.file_name}`);
      clearDocumentPreviewState(doc.id);
      await loadDocuments();
    } catch (err) {
      setError(err instanceof Error ? err.message : (forceReparse ? "強制重新解析失敗" : "重新索引失敗"));
    } finally {
      setActiveActionId(null);
    }
  };

  const handleDelete = async (doc: DocumentSummary) => {
    if (!confirm(`確定要刪除 ${doc.file_name} 嗎？`)) return;
    setActiveActionId(doc.id);
    setError(null);
    setNotice(null);
    try {
      await deleteDocument(doc.id);
      clearDocumentPreviewState(doc.id);
      setDocumentJobs(prev => {
        const next = { ...prev };
        delete next[doc.id];
        return next;
      });
      if (selectedDocumentId === doc.id) {
        setSelectedDocumentId(null);
      }
      setNotice(`已刪除：${doc.file_name}`);
      await loadDocuments();
    } catch (err) {
      setError(err instanceof Error ? err.message : "刪除失敗");
    } finally {
      setActiveActionId(null);
    }
  };

  const canEdit = effectiveRole === "admin" || effectiveRole === "maintainer";
  const activeChunkIds = useMemo(() => (selectedChunkId ? [selectedChunkId] : []), [selectedChunkId]);

  return (
    <>
      {/* Backdrop */}
      {isOpen && (
        <div 
          className="fixed inset-0 z-40 bg-stone-900/40 backdrop-blur-sm transition-opacity" 
          onClick={onClose}
        />
      )}

      {/* Drawer */}
      <aside className={`fixed right-0 top-0 z-50 h-full w-full max-w-[min(92vw,1200px)] transform bg-white shadow-2xl transition-transform duration-300 ease-in-out ${isOpen ? "translate-x-0" : "translate-x-full"}`}>
        <div className="flex h-full flex-col">
          <header className="flex items-center justify-between border-b border-stone-200 px-6 py-4">
            <div>
              <h2 className="text-xl font-bold text-stone-900">文件管理</h2>
              <p className="text-xs text-stone-500">{areaName}</p>
            </div>
            <button 
              onClick={onClose} 
              aria-label="Close documents drawer"
              className="rounded-full p-2 hover:bg-stone-100"
            >
              <span className="text-2xl">&times;</span>
            </button>
          </header>

          <div className="flex min-h-0 flex-1 overflow-hidden">
            <div className="flex min-w-0 flex-[0_0_480px] flex-col overflow-y-auto border-r border-stone-200 p-6">
              {error && (
                <div className="mb-4 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                  {error}
                </div>
              )}
              {notice && (
                <div className="mb-4 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-700">
                  {notice}
                </div>
              )}

              {canEdit && (
                <section className="mb-8 rounded-2xl border border-stone-200 bg-stone-50 p-5">
                  <h3 className="text-sm font-bold text-stone-900">上傳新文件</h3>
                  <form onSubmit={handleUpload} className="mt-4 space-y-4">
                    <input
                      id="document-upload"
                      data-testid="document-upload"
                      type="file"
                      className="w-full text-xs"
                      accept=".txt,.md,.pdf,.docx,.pptx,.html,.xlsx"
                      onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                    />
                    <p className="text-[11px] leading-5 text-stone-500">
                      支援 TXT、Markdown、HTML、PDF、DOCX、PPTX。PDF 會依後端設定走 local 或 LlamaParse 解析。
                    </p>
                    <button
                      data-testid="upload-document-submit"
                      className="w-full rounded-full bg-emerald-700 py-2 text-xs font-bold text-white transition hover:bg-emerald-600 disabled:opacity-50"
                      disabled={isSubmittingUpload || !uploadFile}
                      type="submit"
                    >
                      {isSubmittingUpload ? "上傳中..." : "上傳文件"}
                    </button>
                  </form>
                </section>
              )}

              <section>
                <div className="mb-4 flex items-center justify-between">
                  <h3 className="text-sm font-bold text-stone-900">文件列表</h3>
                  <span className="text-xs text-stone-500">{documents.length} files</span>
                </div>

                <div className="space-y-4" data-testid="documents-list">
                  {documents.map((doc) => {
                    const job = documentJobs[doc.id];
                    const isSelected = selectedDocumentId === doc.id;
                    const isReady = doc.status === "ready";
                    return (
                      <article
                        key={doc.id}
                        data-testid={`document-card-${doc.id}`}
                        className={`rounded-xl border bg-white p-4 shadow-sm transition ${
                          isSelected ? "border-amber-300 ring-1 ring-amber-200" : "border-stone-200"
                        }`}
                        role={isReady ? "button" : undefined}
                        tabIndex={isReady ? 0 : undefined}
                        onClick={isReady ? () => void handleReadyDocumentSelect(doc) : undefined}
                        onKeyDown={
                          isReady
                            ? (event) => {
                                if (event.key === "Enter" || event.key === " ") {
                                  event.preventDefault();
                                  void handleReadyDocumentSelect(doc);
                                }
                              }
                            : undefined
                        }
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="max-w-[70%]">
                            <button
                              type="button"
                              className={`text-left text-sm font-bold break-words ${
                                isReady ? "text-stone-900 hover:text-amber-700" : "cursor-default text-stone-900"
                              }`}
                              data-testid={`select-document-${doc.id}`}
                              disabled={!isReady}
                              onClick={(event) => {
                                event.stopPropagation();
                                void handleReadyDocumentSelect(doc);
                              }}
                            >
                              {doc.file_name}
                            </button>
                            <p className="mt-1 text-[10px] text-stone-500">{doc.content_type} / {doc.file_size} bytes</p>
                          </div>
                          <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${
                            doc.status === "ready" ? "bg-emerald-100 text-emerald-700" :
                            doc.status === "failed" ? "bg-red-100 text-red-700" : "bg-amber-100 text-amber-700"
                          }`}>
                            {doc.status}
                          </span>
                        </div>

                        <div className="mt-3 rounded-lg bg-stone-50 p-2 text-[10px] text-stone-600">
                          <p className="font-bold uppercase tracking-wider text-stone-400">Chunks</p>
                          <p className="mt-1" data-testid={`document-chunk-summary-${doc.id}`}>{formatChunkSummary(doc)}</p>
                        </div>

                        {isReady ? (
                          <p className="mt-2 text-[10px] text-emerald-700" data-testid={`document-preview-ready-${doc.id}`}>
                            可開啟 chunk-aware 全文預覽。
                          </p>
                        ) : (
                          <p className="mt-2 text-[10px] text-stone-500" data-testid={`document-preview-unavailable-${doc.id}`}>
                            尚未可預覽，需等文件進入 ready 狀態。
                          </p>
                        )}

                        {job && (
                          <div className="mt-2 rounded-lg bg-amber-50 p-2 text-[10px] text-amber-800">
                            <p className="font-bold">JOB: {job.status} ({job.stage})</p>
                            {job.error_message && <p className="mt-1 text-red-600" data-testid={`document-job-error-${doc.id}`}>{job.error_message}</p>}
                          </div>
                        )}

                        {canEdit && (
                          <div className="mt-3 flex gap-2">
                            <button
                              data-testid={`reindex-document-${doc.id}`}
                              className="flex-1 rounded-lg bg-stone-900 py-1.5 text-[10px] font-bold text-white hover:bg-stone-700 disabled:opacity-50"
                              disabled={activeActionId === doc.id}
                              onClick={(event) => {
                                event.stopPropagation();
                                void handleReindex(doc);
                              }}
                            >
                              {activeActionId === doc.id ? "處理中..." : "重新索引"}
                            </button>
                            <button
                              data-testid={`force-reindex-document-${doc.id}`}
                              className="rounded-lg border border-amber-300 px-3 py-1.5 text-[10px] font-bold text-amber-700 hover:bg-amber-50 disabled:opacity-50"
                              disabled={activeActionId === doc.id}
                              onClick={(event) => {
                                event.stopPropagation();
                                void handleReindex(doc, true);
                              }}
                            >
                              強制重新解析
                            </button>
                            <button
                              data-testid={`delete-document-${doc.id}`}
                              className="rounded-lg border border-red-200 px-3 py-1.5 text-[10px] font-bold text-red-600 hover:bg-red-50 disabled:opacity-50"
                              disabled={activeActionId === doc.id}
                              onClick={(event) => {
                                event.stopPropagation();
                                void handleDelete(doc);
                              }}
                            >
                              刪除
                            </button>
                          </div>
                        )}
                      </article>
                    );
                  })}

                  {documents.length === 0 && !isLoading && (
                    <div className="py-12 text-center text-xs text-stone-400">尚無文件</div>
                  )}
                </div>
              </section>
            </div>

            <div className="hidden min-w-0 flex-1 xl:flex">
              <div className="flex min-w-0 flex-[0_0_320px] flex-col border-r border-stone-200 bg-stone-50/60">
                <div className="border-b border-stone-200 px-5 py-4">
                  <h3 className="text-sm font-bold text-stone-900">Chunk 檢視</h3>
                  <p className="mt-1 text-[11px] text-stone-500">
                    {selectedDocument ? `${selectedDocument.file_name} 的 child chunks` : "選擇 ready 文件以檢視 chunk 結構與全文高亮。"}
                  </p>
                </div>
                <div ref={chunkListContainerRef} className="min-h-0 flex-1 overflow-y-auto px-4 py-4" data-testid="document-chunk-list">
                  {!selectedDocument ? (
                    <p className="text-sm text-stone-500">尚未選擇文件。</p>
                  ) : selectedDocument.status !== "ready" ? (
                    <p className="text-sm text-stone-500">此文件尚未 ready，暫時不可預覽。</p>
                  ) : isPreviewLoading && !selectedPreview ? (
                    <p className="text-sm text-stone-500">Loading chunks...</p>
                  ) : selectedPreview ? (
                    <div className="space-y-3">
                      {selectedPreview.chunks.map((chunk, index) => {
                        const isActive = selectedChunkId === chunk.chunk_id;
                        const isHover = hoverChunkId === chunk.chunk_id;
                        return (
                          <button
                            key={chunk.chunk_id}
                            ref={(element) => {
                              chunkItemRefs.current[chunk.chunk_id] = element;
                            }}
                            type="button"
                            data-testid={`document-chunk-item-${chunk.chunk_id}`}
                            className={`block w-full rounded-2xl border px-4 py-3 text-left transition ${
                              isActive
                                ? "border-amber-300 bg-amber-50 ring-1 ring-amber-200"
                                : isHover
                                  ? "border-sky-200 bg-sky-50"
                                  : "border-stone-200 bg-white hover:border-stone-300"
                            }`}
                            onClick={() => {
                              lastChunkSelectionSourceRef.current = "list-click";
                              setSelectedChunkId(chunk.chunk_id);
                            }}
                            onMouseEnter={() => setHoverChunkId(chunk.chunk_id)}
                            onMouseLeave={() => setHoverChunkId((current) => (current === chunk.chunk_id ? null : current))}
                          >
                            <div className="flex items-center justify-between gap-3">
                              <span className="text-[10px] font-bold uppercase tracking-wider text-stone-400">
                                Chunk {index + 1}
                              </span>
                              <span className="rounded-full bg-stone-100 px-2 py-1 text-[10px] font-semibold text-stone-600">
                                {chunk.structure_kind}
                              </span>
                            </div>
                            <p className="mt-2 text-xs font-semibold text-stone-900">{chunk.heading ?? "(無標題)"}</p>
                            <p className="mt-2 text-xs leading-5 text-stone-600">
                              {buildChunkExcerpt(selectedPreview, chunk.start_offset, chunk.end_offset)}
                            </p>
                          </button>
                        );
                      })}
                    </div>
                  ) : (
                    <p className="text-sm text-stone-500">選取 ready 文件後即可載入 chunk 清單。</p>
                  )}
                </div>
              </div>

              <DocumentPreviewPane
                isOpen
                isLoading={Boolean(selectedDocument && selectedDocument.status === "ready" && isPreviewLoading && !selectedPreview)}
                preview={selectedPreview}
                activeChunkIds={activeChunkIds}
                hoverChunkId={hoverChunkId}
                onHoverChunkChange={setHoverChunkId}
                onChunkClick={(chunkId) => {
                  lastChunkSelectionSourceRef.current = "list-click";
                  setSelectedChunkId(chunkId);
                }}
                onFocusedChunkChange={(chunkId) => {
                  if (!chunkId) {
                    return;
                  }
                  lastChunkSelectionSourceRef.current = "preview-scroll";
                  setSelectedChunkId(chunkId);
                }}
                title={selectedDocument?.file_name ?? "Document Preview"}
                subtitle={selectedDocument?.status === "ready" ? "文件管理中的 chunk-aware 全文預覽" : "全文預覽"}
                emptyMessage={
                  selectedDocument
                    ? selectedDocument.status === "ready"
                      ? "此文件正在載入全文預覽。"
                      : "此文件尚未 ready，暫時不可預覽。"
                    : "Select a ready document from the list to preview chunks."
                }
                activeLegendLabel="Selected chunk"
                hoverLegendLabel="Hover syncs with the chunk list"
                onClose={() => {
                  setSelectedDocumentId(null);
                  setSelectedChunkId(null);
                  setHoverChunkId(null);
                }}
              />
            </div>
          </div>
        </div>
      </aside>
    </>
  );
}
