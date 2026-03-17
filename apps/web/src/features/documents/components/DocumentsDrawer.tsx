import React, { useState, useEffect, type FormEvent } from "react";
import type { AreaSummary, DocumentSummary, IngestJobSummary } from "../../../lib/types";
import { 
  fetchDocuments, 
  uploadDocument, 
  reindexDocument, 
  deleteDocument,
  fetchIngestJob
} from "../../../lib/api";

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

/** 格式化時間字串。 */
function formatTimestamp(value: string): string {
  return new Intl.DateTimeFormat("zh-TW", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

/** 格式化 chunk 摘要文字。 */
function formatChunkSummary(document: DocumentSummary): string {
  return `${document.chunk_summary.total_chunks} chunks (${document.chunk_summary.parent_chunks} parent / ${document.chunk_summary.child_chunks} child)`;
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
  const [isLoading, setIsLoading] = useState(false);
  const [isSubmittingUpload, setIsSubmittingUpload] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [activeActionId, setActiveActionId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

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

  const handleReindex = async (doc: DocumentSummary) => {
    setActiveActionId(doc.id);
    setError(null);
    setNotice(null);
    try {
      const payload = await reindexDocument(doc.id);
      const job = await fetchIngestJob(payload.job.id);
      setDocumentJobs(prev => ({ ...prev, [doc.id]: job }));
      setNotice(`已啟動重新索引：${doc.file_name}`);
      await loadDocuments();
    } catch (err) {
      setError(err instanceof Error ? err.message : "重新索引失敗");
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
      setDocumentJobs(prev => {
        const next = { ...prev };
        delete next[doc.id];
        return next;
      });
      setNotice(`已刪除：${doc.file_name}`);
      await loadDocuments();
    } catch (err) {
      setError(err instanceof Error ? err.message : "刪除失敗");
    } finally {
      setActiveActionId(null);
    }
  };

  const canEdit = effectiveRole === "admin" || effectiveRole === "maintainer";

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
      <aside className={`fixed right-0 top-0 z-50 h-full w-[500px] transform bg-white shadow-2xl transition-transform duration-300 ease-in-out ${isOpen ? "translate-x-0" : "translate-x-full"}`}>
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

          <div className="flex-1 overflow-y-auto p-6">
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
                    accept=".txt,.md,.pdf,.docx,.pptx,.html"
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
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-bold text-stone-900">文件列表</h3>
                <span className="text-xs text-stone-500">{documents.length} files</span>
              </div>

              <div className="space-y-4" data-testid="documents-list">
                {documents.map((doc) => {
                  const job = documentJobs[doc.id];
                  return (
                    <article key={doc.id} data-testid={`document-card-${doc.id}`} className="rounded-xl border border-stone-200 bg-white p-4 shadow-sm">
                      <div className="flex items-start justify-between">
                        <div className="max-w-[70%]">
                          <p className="font-bold text-stone-900 break-words text-sm">{doc.file_name}</p>
                          <p className="text-[10px] text-stone-500 mt-1">{doc.content_type} / {doc.file_size} bytes</p>
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
                            onClick={() => handleReindex(doc)}
                          >
                            {activeActionId === doc.id ? "處理中..." : "重新索引"}
                          </button>
                          <button
                            data-testid={`delete-document-${doc.id}`}
                            className="rounded-lg border border-red-200 px-3 py-1.5 text-[10px] font-bold text-red-600 hover:bg-red-50 disabled:opacity-50"
                            disabled={activeActionId === doc.id}
                            onClick={() => handleDelete(doc)}
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
        </div>
      </aside>
    </>
  );
}
