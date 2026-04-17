/** EvaluationDrawer 負責 retrieval evaluation 的 reviewer workflow 與報表檢視。 */

import React, { useEffect, useMemo, useRef, useState, type FormEvent } from "react";

import { MarkdownContent } from "../../../components/MarkdownContent";
import type {
  AreaRole,
  DocumentPreviewPayload,
  EvaluationCandidatePreviewPayload,
  EvaluationDatasetDetailPayload,
  EvaluationDatasetSummary,
  EvaluationLanguage,
  EvaluationProfile,
  EvaluationPreviewDebugPayload,
  EvaluationQueryType,
  EvaluationRunReportPayload,
} from "../../../generated/rest";
import {
  createEvaluationDataset,
  createEvaluationItem,
  createEvaluationSpan,
  deleteEvaluationDataset,
  deleteEvaluationItem,
  fetchEvaluationRun,
  fetchDocumentPreview,
  fetchEvaluationCandidatePreview,
  fetchEvaluationDatasetDetail,
  fetchEvaluationDatasets,
  markEvaluationMiss,
  runEvaluationDataset,
} from "../../../lib/api";


interface EvaluationDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  areaId: string;
  areaName: string;
  effectiveRole: AreaRole;
}


const LANGUAGE_OPTIONS: EvaluationLanguage[] = ["zh-TW", "en", "mixed"];
const QUERY_TYPE_OPTIONS: Array<{ value: EvaluationQueryType; label: string }> = [
  { value: "fact_lookup", label: "Fact Lookup" },
  { value: "document_summary", label: "Document Summary" },
  { value: "cross_document_compare", label: "Cross-Document Compare" },
];
const EVALUATION_PROFILE_OPTIONS: Array<{ value: EvaluationProfile; label: string }> = [
  { value: "production_like_v1", label: "production_like_v1" },
  { value: "deterministic_gate_v1", label: "deterministic_gate_v1" },
];

type PreviewMode = "markdown" | "raw";
type EvaluationStageKey = "recall" | "rerank" | "assembled";

interface PreviewSegment {
  /** 區段穩定識別碼。 */
  key: string;
  /** 區段原文內容。 */
  text: string;
  /** 區段在全文內的起始 offset。 */
  startOffset: number;
  /** 區段在全文內的結束 offset。 */
  endOffset: number;
  /** 若此區段對應 child chunk，則帶上 chunk id。 */
  chunkId: string | null;
}

function ParameterHint({ description }: { description: string }): JSX.Element {
  return (
    <span className="group relative ml-1 inline-flex">
      <span
        className="inline-flex h-4 w-4 cursor-help items-center justify-center rounded-full border border-stone-300 text-[10px] font-bold text-stone-400"
        aria-label={description}
      >
        !
      </span>
      <span className="pointer-events-none absolute bottom-full left-1/2 z-10 mb-2 hidden w-52 -translate-x-1/2 rounded-lg bg-stone-900 px-2 py-1.5 text-[11px] font-medium leading-4 text-white shadow-lg group-hover:block">
        {description}
      </span>
    </span>
  );
}

/** 將 query type 轉成 UI 顯示文字。 */
function formatQueryTypeLabel(queryType: EvaluationQueryType): string {
  const matchedOption = QUERY_TYPE_OPTIONS.find((option) => option.value === queryType);
  return matchedOption?.label ?? queryType;
}


export function EvaluationDrawer({
  isOpen,
  onClose,
  areaId,
  areaName,
  effectiveRole,
}: EvaluationDrawerProps): JSX.Element {
  const [datasets, setDatasets] = useState<EvaluationDatasetSummary[]>([]);
  const [selectedDatasetId, setSelectedDatasetId] = useState<string | null>(null);
  const [selectedItemId, setSelectedItemId] = useState<string | null>(null);
  const [datasetDetail, setDatasetDetail] = useState<EvaluationDatasetDetailPayload | null>(null);
  const [candidatePreview, setCandidatePreview] = useState<EvaluationCandidatePreviewPayload | null>(null);
  const [runReport, setRunReport] = useState<EvaluationRunReportPayload | null>(null);
  const [previewDocument, setPreviewDocument] = useState<DocumentPreviewPayload | null>(null);
  const [previewDocumentId, setPreviewDocumentId] = useState<string | null>(null);
  const [datasetName, setDatasetName] = useState("");
  const [datasetQueryType, setDatasetQueryType] = useState<EvaluationQueryType>("fact_lookup");
  const [queryText, setQueryText] = useState("");
  const [language, setLanguage] = useState<EvaluationLanguage>("zh-TW");
  const [evaluationProfile, setEvaluationProfile] = useState<EvaluationProfile>("production_like_v1");
  const [previewVectorTopK, setPreviewVectorTopK] = useState(30);
  const [previewFtsTopK, setPreviewFtsTopK] = useState(30);
  const [previewMaxCandidates, setPreviewMaxCandidates] = useState(30);
  const [previewTopK, setPreviewTopK] = useState(20);
  const [startOffset, setStartOffset] = useState(0);
  const [endOffset, setEndOffset] = useState(0);
  const [relevanceGrade, setRelevanceGrade] = useState<2 | 3>(3);
  const [selectedText, setSelectedText] = useState("");
  const [previewMode, setPreviewMode] = useState<PreviewMode>("raw");
  const [isDocumentPreviewExpanded, setIsDocumentPreviewExpanded] = useState(true);
  const [previewSearchQuery, setPreviewSearchQuery] = useState("");
  const [activeSearchMatchIndex, setActiveSearchMatchIndex] = useState(0);
  const [pendingScrollOffset, setPendingScrollOffset] = useState<number | null>(null);
  const [expandedStages, setExpandedStages] = useState<Record<EvaluationStageKey, boolean>>({
    recall: false,
    rerank: true,
    assembled: false,
  });
  const [isLoading, setIsLoading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const previewScrollContainerRef = useRef<HTMLDivElement | null>(null);
  const previewRawSelectionRef = useRef<HTMLDivElement | null>(null);
  const previewSegmentRefs = useRef<Record<string, HTMLDivElement | null>>({});

  const canEdit = effectiveRole === "admin" || effectiveRole === "maintainer";

  useEffect(() => {
    if (!isOpen || !areaId || !canEdit) {
      return;
    }
    void loadDatasets();
  }, [isOpen, areaId, canEdit]);

  useEffect(() => {
    if (!isOpen) {
      setSelectedDatasetId(null);
      setSelectedItemId(null);
      setDatasetDetail(null);
      setCandidatePreview(null);
      setRunReport(null);
      setPreviewDocument(null);
      setPreviewDocumentId(null);
      setStartOffset(0);
      setEndOffset(0);
      setSelectedText("");
      setPreviewMode("raw");
      setDatasetQueryType("fact_lookup");
      setEvaluationProfile("production_like_v1");
      setPreviewVectorTopK(30);
      setPreviewFtsTopK(30);
      setPreviewMaxCandidates(30);
      setPreviewTopK(20);
      setIsDocumentPreviewExpanded(true);
      setPreviewSearchQuery("");
      setActiveSearchMatchIndex(0);
      setPendingScrollOffset(null);
      setExpandedStages({ recall: false, rerank: true, assembled: false });
    }
  }, [isOpen]);

  useEffect(() => {
    if (!previewDocument || !previewDocumentId) {
      return;
    }
    setSelectedText(previewDocument.display_text.slice(startOffset, endOffset));
  }, [previewDocument, previewDocumentId, startOffset, endOffset]);

  useEffect(() => {
    if (pendingScrollOffset === null || !previewDocument) {
      return;
    }
    const targetSegment = _findSegmentByOffset(buildPreviewSegments(previewDocument), pendingScrollOffset);
    if (targetSegment) {
      previewSegmentRefs.current[targetSegment.key]?.scrollIntoView({
        behavior: "smooth",
        block: "center",
        inline: "nearest",
      });
    } else {
      previewScrollContainerRef.current?.scrollTo({ top: 0, behavior: "smooth" });
    }
    setPendingScrollOffset(null);
  }, [pendingScrollOffset, previewDocument]);

  const previewSearchMatches = useMemo(() => {
    const content = previewDocument?.display_text ?? "";
    const query = previewSearchQuery.trim();
    if (!content || !query) {
      return [];
    }
    const loweredContent = content.toLocaleLowerCase();
    const loweredQuery = query.toLocaleLowerCase();
    const matches: Array<{ start: number; end: number }> = [];
    let searchFrom = 0;
    while (searchFrom < loweredContent.length) {
      const start = loweredContent.indexOf(loweredQuery, searchFrom);
      if (start < 0) {
        break;
      }
      matches.push({ start, end: start + query.length });
      searchFrom = start + Math.max(query.length, 1);
    }
    return matches;
  }, [previewDocument, previewSearchQuery]);

  const previewSegments = useMemo<PreviewSegment[]>(() => {
    if (!previewDocument) {
      return [];
    }
    return buildPreviewSegments(previewDocument);
  }, [previewDocument]);

  function buildPreviewDebugPayload(applyRerank: boolean): EvaluationPreviewDebugPayload {
    return {
      top_k: previewTopK,
      retrieval_vector_top_k: previewVectorTopK,
      retrieval_fts_top_k: previewFtsTopK,
      retrieval_max_candidates: previewMaxCandidates,
      apply_rerank: applyRerank,
    };
  }

  const activePreviewSegmentKeys = useMemo(() => {
    if (!previewDocument || endOffset <= startOffset) {
      return new Set<string>();
    }
    return new Set(
      previewSegments
        .filter((segment) =>
          _rangesOverlap({
            leftStart: startOffset,
            leftEnd: endOffset,
            rightStart: segment.startOffset,
            rightEnd: segment.endOffset,
          }),
        )
        .map((segment) => segment.key),
    );
  }, [endOffset, previewDocument, previewSegments, startOffset]);

  useEffect(() => {
    if (previewSearchMatches.length === 0) {
      setActiveSearchMatchIndex(0);
      return;
    }
    setActiveSearchMatchIndex((current) => Math.min(current, previewSearchMatches.length - 1));
  }, [previewSearchMatches]);

  async function loadDatasets(preferredDatasetId?: string | null): Promise<void> {
    setIsLoading(true);
    setError(null);
    try {
      const payload = await fetchEvaluationDatasets(areaId);
      setDatasets(payload.items);
      const nextDatasetId = preferredDatasetId ?? selectedDatasetId ?? payload.items[0]?.id ?? null;
      setSelectedDatasetId(nextDatasetId);
      if (nextDatasetId) {
        await loadDatasetDetail(nextDatasetId);
      } else {
        setDatasetDetail(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "載入 evaluation datasets 失敗。");
    } finally {
      setIsLoading(false);
    }
  }

  async function loadDatasetDetail(datasetId: string, preferredItemId?: string | null): Promise<void> {
    setIsLoading(true);
    setError(null);
    try {
      const payload = await fetchEvaluationDatasetDetail(datasetId);
      setDatasetDetail(payload);
      setSelectedDatasetId(datasetId);
      const nextItemId = preferredItemId ?? selectedItemId ?? payload.items[0]?.id ?? null;
      setSelectedItemId(nextItemId);
      if (nextItemId) {
      const preview = await fetchEvaluationCandidatePreview(datasetId, nextItemId);
      setCandidatePreview(preview);
      setExpandedStages({ recall: true, rerank: true, assembled: false });
    } else {
      setCandidatePreview(null);
    }
      await loadLatestRunReport(payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : "載入 dataset detail 失敗。");
    } finally {
      setIsLoading(false);
    }
  }

  async function loadLatestRunReport(payload: EvaluationDatasetDetailPayload): Promise<void> {
    const latestCompletedRun =
      payload.runs.find((run) => run.status === "completed") ??
      payload.runs[0] ??
      null;
    if (!latestCompletedRun) {
      setRunReport(null);
      return;
    }
    try {
      const report = await fetchEvaluationRun(latestCompletedRun.id);
      setRunReport(report);
    } catch {
      setRunReport(null);
    }
  }

  async function handleCreateDataset(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!datasetName.trim()) {
      return;
    }
    setIsSubmitting(true);
    setError(null);
    setNotice(null);
    try {
      const created = await createEvaluationDataset(areaId, { name: datasetName, query_type: datasetQueryType });
      setDatasetName("");
      setDatasetQueryType("fact_lookup");
      setNotice(`已建立評測 dataset：${created.name}`);
      await loadDatasets(created.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "建立 dataset 失敗。");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleCreateItem(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!selectedDatasetId || !queryText.trim()) {
      return;
    }
    setIsSubmitting(true);
    setError(null);
    setNotice(null);
    try {
      const created = await createEvaluationItem(selectedDatasetId, {
        query_text: queryText,
        language,
        query_type: selectedDataset?.query_type,
      });
      setQueryText("");
      setNotice(`已建立 ${formatQueryTypeLabel(created.query_type)} 題目。`);
      await loadDatasetDetail(selectedDatasetId, created.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "建立題目失敗。");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleSelectItem(itemId: string): Promise<void> {
    if (!selectedDatasetId) {
      return;
    }
    setSelectedItemId(itemId);
    setIsLoading(true);
    setError(null);
    try {
      const preview = await fetchEvaluationCandidatePreview(selectedDatasetId, itemId);
      setCandidatePreview(preview);
      setPreviewDocument(null);
      setPreviewDocumentId(null);
      setExpandedStages({ recall: true, rerank: true, assembled: false });
    } catch (err) {
      setError(err instanceof Error ? err.message : "載入 candidate preview 失敗。");
    } finally {
      setIsLoading(false);
    }
  }

  async function handleDeleteItem(itemId: string): Promise<void> {
    if (!selectedDatasetId) {
      return;
    }
    if (!window.confirm("確定要刪除此題目嗎？")) {
      return;
    }
    setIsSubmitting(true);
    setError(null);
    setNotice(null);
    try {
      await deleteEvaluationItem(selectedDatasetId, itemId);
      setNotice("已刪除題目。");
      if (selectedItemId === itemId) {
        setSelectedItemId(null);
        setCandidatePreview(null);
        setPreviewDocument(null);
        setPreviewDocumentId(null);
        setSelectedText("");
        setStartOffset(0);
        setEndOffset(0);
      }
      await loadDatasetDetail(selectedDatasetId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "刪除題目失敗。");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleDeleteDataset(datasetId: string): Promise<void> {
    if (!window.confirm("確定要刪除此 dataset 嗎？所有題目與 run 也會一併刪除。")) {
      return;
    }
    setIsSubmitting(true);
    setError(null);
    setNotice(null);
    try {
      await deleteEvaluationDataset(datasetId);
      setNotice("已刪除 dataset。");
      if (selectedDatasetId === datasetId) {
        setSelectedDatasetId(null);
        setSelectedItemId(null);
        setDatasetDetail(null);
        setCandidatePreview(null);
        setRunReport(null);
        setPreviewDocument(null);
        setPreviewDocumentId(null);
        setSelectedText("");
        setStartOffset(0);
        setEndOffset(0);
      }
      await loadDatasets();
    } catch (err) {
      setError(err instanceof Error ? err.message : "刪除 dataset 失敗。");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function openDocumentPreview(documentId: string, nextStart: number, nextEnd: number): Promise<void> {
    setIsLoading(true);
    setError(null);
    try {
      const preview = await fetchDocumentPreview(documentId);
      setPreviewDocument(preview);
      setPreviewDocumentId(documentId);
      setStartOffset(nextStart);
      setEndOffset(nextEnd);
      setSelectedText(preview.display_text.slice(nextStart, nextEnd));
      setIsDocumentPreviewExpanded(true);
      setPreviewSearchQuery("");
      setActiveSearchMatchIndex(0);
      setPendingScrollOffset(nextStart);
    } catch (err) {
      setError(err instanceof Error ? err.message : "載入文件預覽失敗。");
    } finally {
      setIsLoading(false);
    }
  }

  function applySearchMatch(nextIndex: number): void {
    const match = previewSearchMatches[nextIndex];
    if (!match) {
      return;
    }
    setActiveSearchMatchIndex(nextIndex);
    setStartOffset(match.start);
    setEndOffset(match.end);
    setSelectedText(previewDocument?.display_text.slice(match.start, match.end) ?? "");
    setIsDocumentPreviewExpanded(true);
    setPendingScrollOffset(match.start);
  }

  function handleRawPreviewSelection(): void {
    const container = previewRawSelectionRef.current;
    const selection = window.getSelection();
    if (!container || !selection || selection.rangeCount === 0 || selection.isCollapsed) {
      return;
    }
    const range = selection.getRangeAt(0);
    if (!container.contains(range.startContainer) || !container.contains(range.endContainer)) {
      return;
    }
    const nextStartOffset = _calculateContainerOffset(container, range.startContainer, range.startOffset);
    const nextEndOffset = _calculateContainerOffset(container, range.endContainer, range.endOffset);
    const normalizedStart = Math.min(nextStartOffset, nextEndOffset);
    const normalizedEnd = Math.max(nextStartOffset, nextEndOffset);
    setStartOffset(normalizedStart);
    setEndOffset(normalizedEnd);
    setSelectedText(previewDocument?.display_text.slice(normalizedStart, normalizedEnd) ?? "");
    setPendingScrollOffset(normalizedStart);
  }

  async function handleCreateSpan(): Promise<void> {
    if (!selectedDatasetId || !selectedItemId || !previewDocumentId) {
      return;
    }
    setIsSubmitting(true);
    setError(null);
    setNotice(null);
    try {
      await createEvaluationSpan(selectedDatasetId, selectedItemId, {
        document_id: previewDocumentId,
        start_offset: startOffset,
        end_offset: endOffset,
        relevance_grade: relevanceGrade,
      });
      setNotice("已新增 gold source span。");
      await loadDatasetDetail(selectedDatasetId, selectedItemId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "新增 span 失敗。");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleMarkMiss(): Promise<void> {
    if (!selectedDatasetId || !selectedItemId) {
      return;
    }
    setIsSubmitting(true);
    setError(null);
    setNotice(null);
    try {
      await markEvaluationMiss(selectedDatasetId, selectedItemId);
      setNotice("已將題目標記為 retrieval miss。");
      await loadDatasetDetail(selectedDatasetId, selectedItemId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "標記 retrieval miss 失敗。");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleRun(): Promise<void> {
    if (!selectedDatasetId) {
      return;
    }
    setIsSubmitting(true);
    setError(null);
    setNotice(null);
    try {
      const report = await runEvaluationDataset(selectedDatasetId, { top_k: 10, evaluation_profile: evaluationProfile });
      setRunReport(report);
      setNotice(`已完成 benchmark run，run id：${report.run.id}`);
      await loadDatasetDetail(selectedDatasetId, selectedItemId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "執行 benchmark run 失敗。");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handlePreviewDebug(applyRerank: boolean): Promise<void> {
    if (!selectedDatasetId || !selectedItemId) {
      return;
    }
    setIsSubmitting(true);
    setError(null);
    setNotice(null);
    try {
      const preview = await fetchEvaluationCandidatePreview(
        selectedDatasetId,
        selectedItemId,
        buildPreviewDebugPayload(applyRerank),
      );
      setCandidatePreview(preview);
      setExpandedStages({ recall: false, rerank: false, assembled: false });
    } catch (err) {
      setError(err instanceof Error ? err.message : "載入 candidate preview 失敗。");
    } finally {
      setIsSubmitting(false);
    }
  }

  const selectedDataset = useMemo(
    () => datasets.find((dataset) => dataset.id === selectedDatasetId) ?? null,
    [datasets, selectedDatasetId],
  );

  if (!isOpen) {
    return <></>;
  }

  return (
    <>
      <div className="fixed inset-0 z-40 bg-stone-900/40 backdrop-blur-sm" onClick={onClose} />
      <aside className={`fixed right-0 top-0 z-50 h-full w-full max-w-[min(96vw,1440px)] bg-white shadow-2xl transition-transform ${isOpen ? "translate-x-0" : "translate-x-full"}`}>
        <div className="flex h-full flex-col">
          <header className="flex items-center justify-between border-b border-stone-200 px-6 py-4">
            <div>
              <h2 className="text-xl font-bold text-stone-900">評測 / 標註</h2>
              <p className="text-xs text-stone-500">{areaName}</p>
            </div>
            <button onClick={onClose} aria-label="Close evaluation drawer" className="rounded-full p-2 hover:bg-stone-100">
              <span className="text-2xl leading-none">&times;</span>
            </button>
          </header>

          {error ? (
            <div className="mx-6 mt-4 flex items-start justify-between gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              <span>{error}</span>
              <button
                type="button"
                className="rounded-md px-2 py-1 text-xs font-semibold text-red-700 hover:bg-red-100"
                onClick={() => setError(null)}
              >
                關閉
              </button>
            </div>
          ) : null}
          {notice ? (
            <div className="mx-6 mt-4 flex items-start justify-between gap-3 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
              <span>{notice}</span>
              <button
                type="button"
                className="rounded-md px-2 py-1 text-xs font-semibold text-emerald-700 hover:bg-emerald-100"
                onClick={() => setNotice(null)}
              >
                關閉
              </button>
            </div>
          ) : null}

          {!canEdit ? (
            <div className="m-6 rounded-xl border border-stone-200 bg-stone-50 px-4 py-3 text-sm text-stone-600">
              目前角色無法操作 retrieval evaluation。
            </div>
          ) : (
            <div className="grid h-full min-h-0 grid-cols-[320px_minmax(360px,1fr)_minmax(360px,1fr)] gap-0">
              <section className="border-r border-stone-200 p-5 overflow-y-auto" data-testid="evaluation-dataset-section">
                <h3 className="text-sm font-bold text-stone-900">Dataset</h3>
                <form onSubmit={handleCreateDataset} className="mt-4 space-y-3">
                  <input
                    data-testid="evaluation-dataset-name"
                    className="w-full rounded-xl border border-stone-200 px-3 py-2 text-sm"
                    placeholder="Phase 7 dataset name"
                    value={datasetName}
                    onChange={(event) => setDatasetName(event.target.value)}
                  />
                  <select
                    data-testid="evaluation-dataset-query-type"
                    className="w-full rounded-xl border border-stone-200 px-3 py-2 text-sm"
                    value={datasetQueryType}
                    onChange={(event) => setDatasetQueryType(event.target.value as EvaluationQueryType)}
                  >
                    {QUERY_TYPE_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                  <button
                    data-testid="evaluation-create-dataset"
                    type="submit"
                    className="w-full rounded-xl bg-stone-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
                    disabled={isSubmitting}
                  >
                    建立 Dataset
                  </button>
                </form>

                <div className="mt-6 space-y-2" data-testid="evaluation-datasets-list">
                  {datasets.map((dataset) => (
                    <div
                      key={dataset.id}
                      className={`rounded-xl border px-3 py-3 ${selectedDatasetId === dataset.id ? "border-amber-400 bg-amber-50" : "border-stone-200 bg-white"}`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <button
                          type="button"
                          className="min-w-0 flex-1 text-left"
                          onClick={() => void loadDatasetDetail(dataset.id)}
                        >
                          <div className="text-sm font-semibold text-stone-900">{dataset.name}</div>
                          <div className="mt-1 text-xs text-stone-500">
                            {formatQueryTypeLabel(dataset.query_type)} / {dataset.item_count} items
                          </div>
                        </button>
                        <button
                          type="button"
                          className="rounded-lg border border-red-200 bg-red-50 px-2 py-1 text-xs font-semibold text-red-700 disabled:opacity-50"
                          data-testid={`evaluation-delete-dataset-${dataset.id}`}
                          disabled={isSubmitting}
                          onClick={() => void handleDeleteDataset(dataset.id)}
                        >
                          刪除
                        </button>
                      </div>
                    </div>
                  ))}
                </div>

                {selectedDataset ? (
                  <form onSubmit={handleCreateItem} className="mt-6 space-y-3 border-t border-stone-200 pt-6">
                    <h4 className="text-sm font-bold text-stone-900">
                      新增 {formatQueryTypeLabel(selectedDataset.query_type)} 題目
                    </h4>
                    <div className="rounded-xl border border-stone-200 bg-stone-50 px-3 py-2 text-xs text-stone-600">
                      Dataset Query Type: {formatQueryTypeLabel(selectedDataset.query_type)}
                    </div>
                    <textarea
                      data-testid="evaluation-item-query"
                      className="h-24 w-full rounded-xl border border-stone-200 px-3 py-2 text-sm"
                      placeholder={`請輸入 ${formatQueryTypeLabel(selectedDataset.query_type)} query`}
                      value={queryText}
                      onChange={(event) => setQueryText(event.target.value)}
                    />
                    <select
                      data-testid="evaluation-item-language"
                      className="w-full rounded-xl border border-stone-200 px-3 py-2 text-sm"
                      value={language}
                      onChange={(event) => setLanguage(event.target.value as EvaluationLanguage)}
                    >
                      {LANGUAGE_OPTIONS.map((option) => (
                        <option key={option} value={option}>{option}</option>
                      ))}
                    </select>
                    <button
                      data-testid="evaluation-create-item"
                      type="submit"
                      className="w-full rounded-xl bg-amber-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
                      disabled={isSubmitting}
                    >
                      建立題目
                    </button>
                  </form>
                ) : null}

                {datasetDetail ? (
                  <div className="mt-6 space-y-2 border-t border-stone-200 pt-6" data-testid="evaluation-items-list">
                    <h4 className="text-sm font-bold text-stone-900">Review Items</h4>
                    {datasetDetail.items.map((item) => (
                      <div
                        key={item.id}
                        className={`rounded-xl border px-3 py-3 ${selectedItemId === item.id ? "border-stone-900 bg-stone-100" : "border-stone-200 bg-white"}`}
                      >
                        <div className="flex items-start justify-between gap-3">
                          <button
                            type="button"
                            className="min-w-0 flex-1 text-left"
                            onClick={() => void handleSelectItem(item.id)}
                          >
                            <div className="text-sm font-semibold text-stone-900">{item.query_text}</div>
                            <div className="mt-1 text-xs text-stone-500">
                              {formatQueryTypeLabel(item.query_type)} / {item.language} / spans {item.spans.length}
                            </div>
                          </button>
                          <button
                            type="button"
                            className="rounded-lg border border-red-200 bg-red-50 px-2 py-1 text-xs font-semibold text-red-700 disabled:opacity-50"
                            data-testid={`evaluation-delete-item-${item.id}`}
                            disabled={isSubmitting}
                            onClick={() => void handleDeleteItem(item.id)}
                          >
                            刪除
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : null}
              </section>

              <section className="border-r border-stone-200 p-5 overflow-y-auto" data-testid="evaluation-review-section">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-bold text-stone-900">Review</h3>
                  <div className="flex items-center gap-3">
                    <select
                      className="rounded-xl border border-stone-200 px-3 py-2 text-xs"
                      value={evaluationProfile}
                      onChange={(event) => setEvaluationProfile(event.target.value as EvaluationProfile)}
                    >
                      {EVALUATION_PROFILE_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                    <button
                      data-testid="evaluation-run-benchmark"
                      type="button"
                      onClick={() => void handleRun()}
                      className="rounded-xl bg-stone-900 px-4 py-2 text-xs font-semibold text-white disabled:opacity-50"
                      disabled={!selectedDatasetId || isSubmitting}
                    >
                      執行 Benchmark
                    </button>
                  </div>
                </div>

                {candidatePreview ? (
                  <div className="space-y-6">
                    <div className="mt-4 rounded-xl border border-stone-200 bg-stone-50 p-4" data-testid="evaluation-item-detail">
                      <div className="text-sm font-semibold text-stone-900">{candidatePreview.item.query_text}</div>
                      <div className="mt-1 text-xs text-stone-500">
                        {formatQueryTypeLabel(candidatePreview.item.query_type)} / {candidatePreview.item.language}
                      </div>
                      <div className="mt-3 rounded-xl border border-stone-200 bg-white px-3 py-3 text-xs text-stone-600" data-testid="evaluation-query-routing">
                        <div>Query Type: {formatQueryTypeLabel(candidatePreview.query_routing.query_type)}</div>
                        <div>Routing Source: {candidatePreview.query_routing.source}</div>
                        <div>Routing Confidence: {candidatePreview.query_routing.confidence.toFixed(2)}</div>
                        <div>Summary Strategy: {candidatePreview.query_routing.summary_strategy ?? "-"}</div>
                        <div>Summary Strategy Source: {candidatePreview.query_routing.summary_strategy_source ?? "-"}</div>
                        <div>Selected Profile: {candidatePreview.query_routing.selected_profile}</div>
                      </div>
                      {candidatePreview.selection ? (
                        <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-3 text-xs text-amber-900" data-testid="evaluation-selection">
                          <div className="font-semibold text-amber-950">Selection</div>
                          <div className="mt-2">Applied: {candidatePreview.selection.applied ? "yes" : "no"}</div>
                          <div>Strategy: {candidatePreview.selection.strategy}</div>
                          <div>Selected Documents: {candidatePreview.selection.selected_document_count}</div>
                          <div>Selected Parents: {candidatePreview.selection.selected_parent_count}</div>
                        </div>
                      ) : null}
                      <div className="mt-3 flex flex-wrap gap-2">
                        {candidatePreview.item.spans.map((span) => (
                          <span key={span.id} className="rounded-full bg-amber-100 px-3 py-1 text-xs text-amber-900">
                            {span.is_retrieval_miss ? "retrieval_miss" : `${span.relevance_grade} @ ${span.start_offset}-${span.end_offset}`}
                          </span>
                        ))}
                      </div>
                    </div>

                    {(["rerank", "assembled", "recall"] as const).map((stageKey) => {
                      const stage = candidatePreview[stageKey];
                      return (
                        <div key={stageKey} className="rounded-xl border border-stone-200 bg-white p-4" data-testid={`evaluation-stage-${stageKey}`}>
                          <button
                            type="button"
                            className="flex w-full items-center justify-between text-left"
                            onClick={() =>
                              setExpandedStages((current) => ({
                                ...current,
                                [stageKey]: !current[stageKey],
                              }))
                            }
                          >
                            <h4 className="text-sm font-bold text-stone-900">{stage.stage}</h4>
                            <div className="flex items-center gap-3">
                              <span className="text-xs text-stone-500">first hit: {stage.first_hit_rank ?? "miss"}</span>
                              <span className="text-xs text-stone-500">full rank: {stage.full_hit_rank ?? "miss"}</span>
                              <span className="text-xs text-stone-500">{expandedStages[stageKey] ? "收合" : "展開"}</span>
                            </div>
                          </button>
                          {stage.stage === "rerank" && stage.fallback_reason ? (
                            <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                              {buildRerankFallbackLabel(stage.fallback_reason)}
                            </div>
                          ) : null}
                          {expandedStages[stageKey] ? (
                            <div className="mt-3 space-y-2">
                              {stage.items.map((candidate) => (
                                <button
                                  key={`${stageKey}-${candidate.rank}-${candidate.document_id}-${candidate.start_offset}`}
                                  type="button"
                                  className="w-full rounded-xl border border-stone-200 px-3 py-3 text-left hover:bg-stone-50"
                                  onClick={() => void openDocumentPreview(candidate.document_id, candidate.start_offset, candidate.end_offset)}
                                >
                                  <div className="flex items-center justify-between gap-2">
                                    <span className="text-xs font-bold uppercase tracking-wide text-stone-500">#{candidate.rank}</span>
                                    <span className="text-xs text-amber-700">rel {candidate.matched_relevance ?? 0}</span>
                                  </div>
                                  <div className="mt-2 flex flex-wrap gap-2 text-[11px] text-stone-500">
                                    {candidate.vector_rank !== null ? <span>Vector {candidate.vector_rank}</span> : null}
                                    {candidate.fts_rank !== null ? <span>FTS {candidate.fts_rank}</span> : null}
                                    {candidate.rrf_rank !== null ? <span>RRF {candidate.rrf_rank}</span> : null}
                                    {candidate.rerank_rank !== null ? <span>Rerank {candidate.rerank_rank}</span> : null}
                                  </div>
                                  <div className="mt-1 text-sm font-semibold text-stone-900">{candidate.document_name}</div>
                                  <div className="text-xs text-stone-500">{candidate.heading ?? "No heading"}</div>
                                  <div className="mt-2 text-xs text-stone-600">{candidate.excerpt}</div>
                                </button>
                              ))}
                            </div>
                          ) : null}
                        </div>
                      );
                    })}

                    <div className="rounded-xl border border-stone-200 bg-white p-4" data-testid="evaluation-document-search-hits">
                      <h4 className="text-sm font-bold text-stone-900">文件內搜尋命中</h4>
                      <div className="mt-1 text-xs text-stone-500">依目前題目文字搜尋 area 內 ready 文件，方便快速定位 span。</div>
                      <div className="mt-3 space-y-2">
                        {candidatePreview.document_search_hits.length > 0 ? (
                          candidatePreview.document_search_hits.map((hit, index) => (
                            <button
                              key={`${hit.document_id}-${hit.chunk_id}-${index}`}
                              type="button"
                              className="w-full rounded-xl border border-stone-200 px-3 py-3 text-left hover:bg-stone-50"
                              onClick={() => void openDocumentPreview(hit.document_id, hit.start_offset, hit.end_offset)}
                            >
                              <div className="text-sm font-semibold text-stone-900">{hit.document_name}</div>
                              <div className="mt-1 text-xs text-stone-500">{hit.heading ?? "No heading"}</div>
                              <div className="mt-2 text-xs text-stone-600">{hit.excerpt}</div>
                            </button>
                          ))
                        ) : (
                          <div className="rounded-xl border border-dashed border-stone-300 px-3 py-4 text-xs text-stone-500">
                            目前沒有文件內搜尋命中。
                          </div>
                        )}
                      </div>
                    </div>

                    <div className="rounded-xl border border-stone-200 bg-white p-4" data-testid="evaluation-preview-debug">
                      <h4 className="text-sm font-bold text-stone-900">調參 / Debug</h4>
                      <div className="mt-1 text-xs text-stone-500">使用下列參數覆跑 preview，觀察 Recall、RRF 與 Rerank 名次變化。</div>
                      <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4">
                        <label className="text-[11px] text-stone-500">
                          <div className="mb-1 flex items-center">
                            preview_top_k
                            <ParameterHint description="控制畫面上每個 stage 最多顯示多少筆結果，以及 first hit 的判定範圍。" />
                          </div>
                          <input
                            className="w-full rounded-xl border border-stone-200 px-3 py-2 text-xs text-stone-900"
                            type="number"
                            value={previewTopK}
                            onChange={(event) => setPreviewTopK(Number(event.target.value))}
                          />
                        </label>
                        <label className="text-[11px] text-stone-500">
                          <div className="mb-1 flex items-center">
                            vector_top_k
                            <ParameterHint description="向向量檢索先取回多少筆候選，再進入後續融合排序。" />
                          </div>
                          <input
                            className="w-full rounded-xl border border-stone-200 px-3 py-2 text-xs text-stone-900"
                            type="number"
                            value={previewVectorTopK}
                            onChange={(event) => setPreviewVectorTopK(Number(event.target.value))}
                          />
                        </label>
                        <label className="text-[11px] text-stone-500">
                          <div className="mb-1 flex items-center">
                            fts_top_k
                            <ParameterHint description="向全文檢索先取回多少筆候選，再進入後續融合排序。" />
                          </div>
                          <input
                            className="w-full rounded-xl border border-stone-200 px-3 py-2 text-xs text-stone-900"
                            type="number"
                            value={previewFtsTopK}
                            onChange={(event) => setPreviewFtsTopK(Number(event.target.value))}
                          />
                        </label>
                        <label className="text-[11px] text-stone-500">
                          <div className="mb-1 flex items-center">
                            max_candidates
                            <ParameterHint description="RRF 融合後最多保留多少筆候選。超過這個數量的結果不會進入後續 rerank。" />
                          </div>
                          <input
                            className="w-full rounded-xl border border-stone-200 px-3 py-2 text-xs text-stone-900"
                            type="number"
                            value={previewMaxCandidates}
                            onChange={(event) => setPreviewMaxCandidates(Number(event.target.value))}
                          />
                        </label>
                      </div>
                      <div className="mt-4 flex items-center gap-3">
                        <button
                          type="button"
                          className="rounded-xl border border-stone-200 bg-white px-3 py-2 text-xs font-semibold text-stone-700 disabled:opacity-50"
                          disabled={isSubmitting}
                          onClick={() => void handlePreviewDebug(false)}
                        >
                          查看 Recall / RRF
                        </button>
                        <button
                          type="button"
                          className="rounded-xl bg-amber-600 px-3 py-2 text-xs font-semibold text-white disabled:opacity-50"
                          disabled={isSubmitting}
                          onClick={() => void handlePreviewDebug(true)}
                        >
                          執行 Rerank
                        </button>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="mt-6 rounded-xl border border-dashed border-stone-300 px-4 py-6 text-sm text-stone-500">
                    選擇一個 dataset item 後即可檢視 recall / rerank / assembled candidates。
                  </div>
                )}
              </section>

              <section className="p-5 overflow-y-auto" data-testid="evaluation-runs-section">
                <h3 className="text-sm font-bold text-stone-900">Runs / Preview</h3>

                <div className="mt-4 rounded-xl border border-stone-200 bg-stone-50 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-xs font-semibold uppercase tracking-wide text-stone-500">Span Annotation</div>
                    <div className="inline-flex rounded-xl border border-stone-200 bg-white p-1 text-xs">
                      <button
                        type="button"
                        className={`rounded-lg px-3 py-1 font-semibold ${previewMode === "markdown" ? "bg-stone-900 text-white" : "text-stone-600"}`}
                        onClick={() => setPreviewMode("markdown")}
                      >
                        Markdown
                      </button>
                      <button
                        type="button"
                        className={`rounded-lg px-3 py-1 font-semibold ${previewMode === "raw" ? "bg-stone-900 text-white" : "text-stone-600"}`}
                        onClick={() => setPreviewMode("raw")}
                      >
                        Raw
                      </button>
                    </div>
                  </div>
                  <div className="mt-3 rounded-xl border border-stone-200 bg-white">
                    <button
                      type="button"
                      className="flex w-full items-center justify-between px-4 py-3 text-left"
                      data-testid="evaluation-toggle-document-preview"
                      onClick={() => setIsDocumentPreviewExpanded((current) => !current)}
                    >
                      <span className="text-sm font-semibold text-stone-900">全文預覽</span>
                      <span className="text-xs text-stone-500">{isDocumentPreviewExpanded ? "收合" : "展開"}</span>
                    </button>
                    <div className="border-t border-stone-200 px-4 py-3">
                      <div className="flex items-center gap-2">
                        <input
                          type="text"
                          value={previewSearchQuery}
                          onChange={(event) => setPreviewSearchQuery(event.target.value)}
                          placeholder="搜尋全文預覽"
                          data-testid="evaluation-preview-search"
                          className="min-w-0 flex-1 rounded-xl border border-stone-200 px-3 py-2 text-sm"
                          disabled={!previewDocument}
                        />
                        <span className="min-w-12 text-center text-xs text-stone-500" data-testid="evaluation-preview-search-count">
                          {previewSearchMatches.length === 0 ? "0/0" : `${activeSearchMatchIndex + 1}/${previewSearchMatches.length}`}
                        </span>
                        <button
                          type="button"
                          className="rounded-lg border border-stone-200 px-3 py-2 text-xs font-semibold text-stone-700 disabled:opacity-50"
                          disabled={!previewDocument || previewSearchMatches.length === 0}
                          onClick={() =>
                            applySearchMatch(
                              activeSearchMatchIndex === 0 ? previewSearchMatches.length - 1 : activeSearchMatchIndex - 1,
                            )
                          }
                        >
                          上一個
                        </button>
                        <button
                          type="button"
                          className="rounded-lg border border-stone-200 px-3 py-2 text-xs font-semibold text-stone-700 disabled:opacity-50"
                          disabled={!previewDocument || previewSearchMatches.length === 0}
                          onClick={() =>
                            applySearchMatch(
                              activeSearchMatchIndex === previewSearchMatches.length - 1 ? 0 : activeSearchMatchIndex + 1,
                            )
                          }
                        >
                          下一個
                        </button>
                      </div>
                    </div>
                    {isDocumentPreviewExpanded ? (
                      <div className="border-t border-stone-200 p-4">
                        {!previewDocument ? (
                          <div className="rounded-xl border border-dashed border-stone-300 px-4 py-6 text-sm text-stone-500">
                            請先從 recall / rerank / assembled 或文件內搜尋選擇一段內容，再查看全文預覽。
                          </div>
                        ) : previewMode === "markdown" ? (
                          <>
                            <div
                              ref={previewScrollContainerRef}
                              data-testid="evaluation-document-preview-markdown"
                              className="max-h-64 overflow-y-auto rounded-xl border border-stone-200 bg-white p-3"
                            >
                              <div className="space-y-2">
                                {previewSegments.map((segment) => {
                                  const isActive = activePreviewSegmentKeys.has(segment.key);
                                  return (
                                    <div
                                      key={segment.key}
                                      ref={(element) => {
                                        previewSegmentRefs.current[segment.key] = element;
                                      }}
                                      className={`rounded-xl px-3 py-2 transition-colors ${
                                        isActive
                                          ? "border border-amber-300 bg-amber-100/90 ring-1 ring-amber-300"
                                          : "border border-transparent"
                                      }`}
                                    >
                                      <MarkdownContent
                                        content={segment.text}
                                        className="text-sm leading-7 text-stone-700"
                                      />
                                    </div>
                                  );
                                })}
                              </div>
                            </div>
                            <p className="mt-3 text-xs text-stone-500">
                              Markdown 檢視供閱讀複核使用；要建立精確 offsets，請切換到 Raw 後直接框選文字。
                            </p>
                          </>
                        ) : (
                          <div
                            ref={previewScrollContainerRef}
                            data-testid="evaluation-document-preview"
                            className="max-h-64 overflow-y-auto rounded-xl border border-stone-200 bg-white p-3"
                          >
                            <div
                              ref={previewRawSelectionRef}
                              className="space-y-2 text-sm leading-6 text-stone-700"
                              onMouseUp={handleRawPreviewSelection}
                              onKeyUp={handleRawPreviewSelection}
                            >
                              {previewSegments.map((segment) => {
                                const isActive = activePreviewSegmentKeys.has(segment.key);
                                return (
                                  <div
                                    key={segment.key}
                                    ref={(element) => {
                                      previewSegmentRefs.current[segment.key] = element;
                                    }}
                                    className={`whitespace-pre-wrap rounded-xl px-3 py-2 font-mono transition-colors ${
                                      isActive
                                        ? "border border-amber-300 bg-amber-100/90 ring-1 ring-amber-300"
                                        : "border border-transparent"
                                    }`}
                                  >
                                    {segment.text}
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        )}
                      </div>
                    ) : null}
                  </div>
                  <div className="mt-3 grid grid-cols-2 gap-3">
                    <input
                      data-testid="evaluation-span-start"
                      type="number"
                      className="rounded-xl border border-stone-200 px-3 py-2 text-sm"
                      value={startOffset}
                      onChange={(event) => setStartOffset(Number(event.target.value))}
                    />
                    <input
                      data-testid="evaluation-span-end"
                      type="number"
                      className="rounded-xl border border-stone-200 px-3 py-2 text-sm"
                      value={endOffset}
                      onChange={(event) => setEndOffset(Number(event.target.value))}
                    />
                  </div>
                  <div className="mt-3 space-y-3">
                    <div className="text-xs font-semibold uppercase tracking-wide text-stone-500">
                      目前選取文字
                    </div>
                    {previewMode === "markdown" ? (
                      selectedText ? (
                        <div
                          data-testid="evaluation-selected-text-markdown"
                          className="rounded-xl border border-stone-200 bg-white p-4"
                        >
                          <MarkdownContent
                            content={selectedText}
                            className="text-sm leading-7 text-stone-700"
                          />
                        </div>
                      ) : (
                        <div className="rounded-xl border border-stone-200 bg-white px-3 py-2 text-xs text-stone-500" data-testid="evaluation-selected-text-markdown">
                          尚未選取文字
                        </div>
                      )
                    ) : (
                      <div
                        className="rounded-xl border border-stone-200 bg-white px-3 py-2 text-xs text-stone-500"
                        data-testid="evaluation-selected-text"
                      >
                        {selectedText || "尚未選取文字"}
                      </div>
                    )}
                  </div>
                  <div className="mt-3 flex items-center gap-3">
                    <select
                      data-testid="evaluation-span-relevance"
                      className="rounded-xl border border-stone-200 px-3 py-2 text-sm"
                      value={relevanceGrade}
                      onChange={(event) => setRelevanceGrade(Number(event.target.value) as 2 | 3)}
                    >
                      <option value={3}>3 核心證據</option>
                      <option value={2}>2 可接受證據</option>
                    </select>
                    <button
                      data-testid="evaluation-add-span"
                      type="button"
                      className="rounded-xl bg-amber-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
                      disabled={!previewDocumentId || endOffset <= startOffset || isSubmitting}
                      onClick={() => void handleCreateSpan()}
                    >
                      新增 Span
                    </button>
                    <button
                      data-testid="evaluation-mark-miss"
                      type="button"
                      className="rounded-xl border border-red-200 bg-red-50 px-4 py-2 text-sm font-semibold text-red-700 disabled:opacity-50"
                      disabled={!selectedItemId || isSubmitting}
                      onClick={() => void handleMarkMiss()}
                    >
                      標記 retrieval_miss
                    </button>
                  </div>
                </div>

                {runReport ? (
                  <div className="mt-6 space-y-4" data-testid="evaluation-run-report">
                    <div className="rounded-xl border border-stone-200 bg-white p-4">
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <div className="text-sm font-bold text-stone-900">Summary Metrics</div>
                          <div className="mt-2 space-y-1 text-[11px] text-stone-500">
                            <div data-testid="evaluation-run-id">Run ID: {runReport.run.id}</div>
                            <div>Run Status: {runReport.run.status}</div>
                            <div>Profile: {runReport.run.evaluation_profile}</div>
                            <div>
                              Query Type: {formatQueryTypeLabel(runReport.dataset.query_type)}
                            </div>
                            <div>
                              Routed Profile: {String((runReport.run.config_snapshot.query_routing as Record<string, unknown> | undefined)?.selected_profile ?? "-")}
                            </div>
                          </div>
                        </div>
                        <div className="text-right text-[11px] text-stone-500">
                          <div>建立時間</div>
                          <div>{new Date(runReport.run.created_at).toLocaleString("zh-TW")}</div>
                          <div className="mt-2">完成時間</div>
                          <div>
                            {runReport.run.completed_at
                              ? new Date(runReport.run.completed_at).toLocaleString("zh-TW")
                              : "尚未完成"}
                          </div>
                        </div>
                      </div>
                      <div className="mt-3 grid gap-3 md:grid-cols-3">
                        {Object.entries(runReport.summary_metrics).map(([stageName, metrics]) => (
                          <div key={stageName} className="rounded-xl border border-stone-100 bg-stone-50 p-3">
                            <div className="text-xs font-bold uppercase tracking-wide text-stone-500">{stageName}</div>
                            <div className="mt-2 space-y-1 text-xs text-stone-700">
                              <div>nDCG@k: {metrics.nDCG_at_k.toFixed(3)}</div>
                              <div>Recall@k: {metrics.recall_at_k.toFixed(3)}</div>
                              <div>MRR@k: {metrics.mrr_at_k.toFixed(3)}</div>
                              <div>Precision@k: {metrics.precision_at_k.toFixed(3)}</div>
                              <div>Doc Coverage@k: {metrics.document_coverage_at_k.toFixed(3)}</div>
                            </div>
                          </div>
                        ))}
                      </div>
                      <details className="mt-4 rounded-xl border border-stone-100 bg-stone-50 p-3">
                        <summary className="cursor-pointer text-xs font-bold uppercase tracking-wide text-stone-500">
                          Config Snapshot
                        </summary>
                        <pre className="mt-2 overflow-x-auto whitespace-pre-wrap break-all text-[11px] text-stone-700">
                          {JSON.stringify(runReport.run.config_snapshot, null, 2)}
                        </pre>
                      </details>
                    </div>

                    <div className="rounded-xl border border-stone-200 bg-white p-4">
                      <div className="text-sm font-bold text-stone-900">Per Query</div>
                      <div className="mt-3 space-y-3" data-testid="evaluation-per-query-list">
                        {runReport.per_query.map((item) => (
                          <div key={item.item_id} className="rounded-xl border border-stone-100 bg-stone-50 p-3">
                            <div className="text-sm font-semibold text-stone-900">{item.query_text}</div>
                            <div className="mt-1 text-xs text-stone-500">
                              {formatQueryTypeLabel(item.query_routing.query_type)} / {item.language}
                            </div>
                            <div className="mt-2 rounded-lg border border-stone-200 bg-white px-3 py-2 text-xs text-stone-600">
                              <div>Routing Source: {item.query_routing.source}</div>
                              <div>Routing Confidence: {item.query_routing.confidence.toFixed(2)}</div>
                              <div>Summary Strategy: {item.query_routing.summary_strategy ?? "-"}</div>
                              <div>Selected Profile: {item.query_routing.selected_profile}</div>
                            </div>
                            {item.selection ? (
                              <div className="mt-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
                                <div>Selection Strategy: {item.selection.strategy}</div>
                                <div>Selected Documents: {item.selection.selected_document_count}</div>
                                <div>Selected Parents: {item.selection.selected_parent_count}</div>
                              </div>
                            ) : null}
                            <div className="mt-2 grid gap-2 md:grid-cols-3 text-xs text-stone-700">
                              <div>Recall first hit: {item.recall.first_hit_rank ?? "miss"}</div>
                              <div>Rerank first hit: {item.rerank.first_hit_rank ?? "miss"}</div>
                              <div>Assembled first hit: {item.assembled.first_hit_rank ?? "miss"}</div>
                            </div>
                            {item.rerank.fallback_reason ? (
                              <div className="mt-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                                {buildRerankFallbackLabel(item.rerank.fallback_reason)}
                              </div>
                            ) : null}
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                ) : null}
              </section>
            </div>
          )}
        </div>
      </aside>
    </>
  );
}


function buildPreviewSegments(previewDocument: DocumentPreviewPayload): PreviewSegment[] {
  /** 依 child chunk 邊界建立穩定的全文預覽區段。 */
  const segments: PreviewSegment[] = [];
  const sortedChunks = [...previewDocument.chunks].sort((left, right) => left.start_offset - right.start_offset);
  let cursor = 0;

  sortedChunks.forEach((chunk, index) => {
    const start = Math.max(0, chunk.start_offset);
    const end = Math.max(start, chunk.end_offset);

    if (start > cursor) {
      segments.push({
        key: `gap-${cursor}-${start}`,
        text: previewDocument.display_text.slice(cursor, start),
        startOffset: cursor,
        endOffset: start,
        chunkId: null,
      });
    }

    segments.push({
      key: `chunk-${chunk.chunk_id}-${index}`,
      text: previewDocument.display_text.slice(start, end),
      startOffset: start,
      endOffset: end,
      chunkId: chunk.chunk_id,
    });
    cursor = Math.max(cursor, end);
  });

  if (cursor < previewDocument.display_text.length) {
    segments.push({
      key: `gap-${cursor}-${previewDocument.display_text.length}`,
      text: previewDocument.display_text.slice(cursor),
      startOffset: cursor,
      endOffset: previewDocument.display_text.length,
      chunkId: null,
    });
  }

  return segments;
}


function formatDocumentRecallDocuments(
  documentRecall: {
    candidates: Array<{ document_id: string; file_name: string }>;
  },
  documentIds: string[],
): string {
  /** 將 document recall 的文件 id 列表轉成可閱讀標籤。 */

  if (documentIds.length === 0) {
    return "-";
  }

  const fileNamesById = new Map(documentRecall.candidates.map((candidate) => [candidate.document_id, candidate.file_name]));
  return documentIds.map((documentId) => fileNamesById.get(documentId) ?? documentId).join(", ");
}


function formatDocumentRecallCandidates(documentRecall: {
  candidates: Array<{ file_name: string; rrf_rank: number }>;
}): string {
  /** 將 document recall candidates 轉成單行摘要，便於 preview 與 run report 顯示。 */

  if (documentRecall.candidates.length === 0) {
    return "-";
  }

  return documentRecall.candidates
    .map((candidate) => `${candidate.file_name} (#${candidate.rrf_rank})`)
    .join(", ");
}

function _findSegmentByOffset(segments: PreviewSegment[], targetOffset: number): PreviewSegment | null {
  /** 依 offset 找出最接近的預覽區段，供事件式 scroll 使用。 */
  return (
    segments.find((segment) =>
      targetOffset >= segment.startOffset && targetOffset < segment.endOffset,
    ) ??
    segments[segments.length - 1] ??
    null
  );
}

function _rangesOverlap({
  leftStart,
  leftEnd,
  rightStart,
  rightEnd,
}: {
  leftStart: number;
  leftEnd: number;
  rightStart: number;
  rightEnd: number;
}): boolean {
  /** 判斷兩段 offset 區間是否實際重疊。 */
  return leftStart < rightEnd && rightStart < leftEnd;
}

function buildRerankFallbackLabel(
  fallbackReason: string | null | undefined,
): string {
  /** 將 rerank fallback 原因轉為可讀文案。 */
  if (fallbackReason === "provider_error") {
    return "rerank provider 失敗，已回退到 recall 順序";
  }
  if (fallbackReason === "missing_score") {
    return "rerank provider 未回傳完整分數，已局部回退";
  }
  return "rerank 已回退到 recall 順序";
}

function _calculateContainerOffset(container: HTMLElement, targetNode: Node, targetOffset: number): number {
  /** 將 DOM selection 端點換算回全文 offset。 */
  const range = document.createRange();
  range.selectNodeContents(container);
  range.setEnd(targetNode, targetOffset);
  return range.toString().length;
}
