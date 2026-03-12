/** 登入後的 Areas 管理頁。 */

import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { useAuth } from "../auth/AuthProvider";
import {
  createArea,
  fetchDocuments,
  fetchApiHealth,
  fetchAreaAccess,
  fetchAreaDetail,
  fetchAreas,
  fetchAuthContext,
  fetchIngestJob,
  replaceAreaAccess,
  uploadDocument,
} from "../lib/api";
import { appConfig } from "../lib/config";
import type {
  AccessGroupEntry,
  AccessUserEntry,
  ApiHealthState,
  AreaAccessPayload,
  AreaRole,
  AreaSummary,
  DocumentSummary,
  IngestJobSummary,
} from "../lib/types";


/** Area access 編輯支援的固定角色。 */
const AREA_ROLE_OPTIONS: AreaRole[] = ["reader", "maintainer", "admin"];

/** 空的 access 編輯狀態。 */
const EMPTY_ACCESS_STATE = {
  usersText: "",
  groupsText: "",
};

/** 空的文件上傳狀態。 */
const EMPTY_UPLOAD_STATE = {
  file: null as File | null,
};


/**
 * 將 API 時間字串格式化為較易讀的本地時間。
 *
 * @param value API 回傳的 ISO 時間字串。
 * @returns 適合 UI 顯示的本地化時間字串。
 */
function formatTimestamp(value: string): string {
  return new Intl.DateTimeFormat("zh-TW", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}


/**
 * 將 user access entries 序列化為可編輯文字。
 *
 * @param entries users access 條目列表。
 * @returns 可直接放入 textarea 的文字內容。
 */
function serializeUsers(entries: AccessUserEntry[]): string {
  return entries.map((entry) => `${entry.user_sub},${entry.role}`).join("\n");
}


/**
 * 將 group access entries 序列化為可編輯文字。
 *
 * @param entries groups access 條目列表。
 * @returns 可直接放入 textarea 的文字內容。
 */
function serializeGroups(entries: AccessGroupEntry[]): string {
  return entries.map((entry) => `${entry.group_path},${entry.role}`).join("\n");
}


/**
 * 驗證並解析 user access 編輯文字。
 *
 * @param rawValue textarea 內的原始 users access 文字。
 * @returns 驗證後的 users access 條目列表。
 */
function parseUsersText(rawValue: string): AccessUserEntry[] {
  return rawValue
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [userSub, role] = line.split(",").map((item) => item.trim());
      if (!userSub || !role || !AREA_ROLE_OPTIONS.includes(role as AreaRole)) {
        throw new Error("使用者 access 格式必須為 user_sub,role。");
      }
      return { user_sub: userSub, role: role as AreaRole };
    });
}


/**
 * 驗證並解析 group access 編輯文字。
 *
 * @param rawValue textarea 內的原始 groups access 文字。
 * @returns 驗證後的 groups access 條目列表。
 */
function parseGroupsText(rawValue: string): AccessGroupEntry[] {
  return rawValue
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [groupPath, role] = line.split(",").map((item) => item.trim());
      if (!groupPath || !role || !AREA_ROLE_OPTIONS.includes(role as AreaRole)) {
        throw new Error("群組 access 格式必須為 group_path,role。");
      }
      return { group_path: groupPath, role: role as AreaRole };
    });
}


/**
 * 將 access payload 轉成 textarea 可編輯狀態。
 *
 * @param accessPayload API 回傳的 area access payload。
 * @returns 可直接綁定到 textarea 的編輯狀態。
 */
function buildEditableAccessState(accessPayload: AreaAccessPayload): { usersText: string; groupsText: string } {
  return {
    usersText: serializeUsers(accessPayload.users),
    groupsText: serializeGroups(accessPayload.groups),
  };
}


/** 登入後的 Areas 管理頁。 */
export function AreasPage(): JSX.Element {
  const { principal, logout } = useAuth();
  const [healthState, setHealthState] = useState<ApiHealthState>({ status: "loading" });
  const [areas, setAreas] = useState<AreaSummary[]>([]);
  const [selectedAreaId, setSelectedAreaId] = useState<string | null>(null);
  const [selectedArea, setSelectedArea] = useState<AreaSummary | null>(null);
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [accessPayload, setAccessPayload] = useState<AreaAccessPayload | null>(null);
  const [documentJobs, setDocumentJobs] = useState<Record<string, IngestJobSummary>>({});
  const [accessEditor, setAccessEditor] = useState(EMPTY_ACCESS_STATE);
  const [uploadState, setUploadState] = useState(EMPTY_UPLOAD_STATE);
  const [createName, setCreateName] = useState("");
  const [createDescription, setCreateDescription] = useState("");
  const [workspaceError, setWorkspaceError] = useState<string | null>(null);
  const [workspaceNotice, setWorkspaceNotice] = useState<string | null>(null);
  const [isLoadingWorkspace, setIsLoadingWorkspace] = useState(false);
  const [isSubmittingCreate, setIsSubmittingCreate] = useState(false);
  const [isSubmittingAccess, setIsSubmittingAccess] = useState(false);
  const [isSubmittingUpload, setIsSubmittingUpload] = useState(false);

  useEffect(() => {
    let isMounted = true;

    async function loadHealth(): Promise<void> {
      try {
        const response = await fetchApiHealth();
        if (!isMounted) {
          return;
        }
        setHealthState({ status: "success", payload: response });
      } catch (error) {
        if (!isMounted) {
          return;
        }
        setHealthState({
          status: "error",
          message: error instanceof Error ? error.message : "未知的 API health 錯誤",
        });
      }
    }

    void loadHealth();

    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    void loadWorkspace();
  }, []);

  useEffect(() => {
    if (!selectedAreaId) {
      return;
    }

    const hasPendingDocuments = documents.some(
      (document) => document.status === "uploaded" || document.status === "processing",
    );
    const pendingJobEntries = Object.entries(documentJobs).filter(([, job]) =>
      job.status === "queued" || job.status === "processing",
    );
    if (!hasPendingDocuments && pendingJobEntries.length === 0) {
      return;
    }

    const timerId = window.setTimeout(() => {
      void (async () => {
        await loadArea(selectedAreaId);
        if (pendingJobEntries.length > 0) {
          const refreshedJobs = await Promise.all(
            pendingJobEntries.map(async ([documentId, job]) => [documentId, await fetchIngestJob(job.id)] as const),
          );
          setDocumentJobs((current) => ({
            ...current,
            ...Object.fromEntries(refreshedJobs),
          }));
        }
      })();
    }, 2_000);

    return () => window.clearTimeout(timerId);
  }, [selectedAreaId, documents, documentJobs]);

  /**
   * 依目前 session 重新載入 auth context 與 area 清單。
   *
   * @param preferredAreaId 載入完成後優先選取的 area 識別碼。
   * @returns 無；僅更新頁面狀態。
   */
  async function loadWorkspace(preferredAreaId?: string | null): Promise<void> {
    setIsLoadingWorkspace(true);
    setWorkspaceError(null);
    setWorkspaceNotice(null);
    try {
      const [, areasPayload] = await Promise.all([fetchAuthContext(), fetchAreas()]);
      const nextSelectedAreaId = preferredAreaId ?? selectedAreaId ?? areasPayload.items[0]?.id ?? null;

      setAreas(areasPayload.items);
      setSelectedAreaId(nextSelectedAreaId);

      if (nextSelectedAreaId) {
        await loadArea(nextSelectedAreaId);
      } else {
        setSelectedArea(null);
        setDocuments([]);
        setAccessPayload(null);
        setDocumentJobs({});
        setAccessEditor(EMPTY_ACCESS_STATE);
        setUploadState(EMPTY_UPLOAD_STATE);
      }
    } catch (error) {
      setWorkspaceError(error instanceof Error ? error.message : "載入工作區失敗。");
      setAreas([]);
      setSelectedAreaId(null);
      setSelectedArea(null);
      setDocuments([]);
      setAccessPayload(null);
      setDocumentJobs({});
      setAccessEditor(EMPTY_ACCESS_STATE);
      setUploadState(EMPTY_UPLOAD_STATE);
    } finally {
      setIsLoadingWorkspace(false);
    }
  }

  /**
   * 載入單一 area 詳細資料與必要的 access 資訊。
   *
   * @param areaId 要載入的 area 識別碼。
   * @returns 無；僅更新頁面狀態。
   */
  async function loadArea(areaId: string): Promise<void> {
    const [detail, documentsPayload] = await Promise.all([fetchAreaDetail(areaId), fetchDocuments(areaId)]);
    setSelectedArea(detail);
    setDocuments(documentsPayload.items);
    if (detail.effective_role === "admin") {
      const nextAccessPayload = await fetchAreaAccess(areaId);
      setAccessPayload(nextAccessPayload);
      setAccessEditor(buildEditableAccessState(nextAccessPayload));
      return;
    }
    setAccessPayload(null);
    setAccessEditor(EMPTY_ACCESS_STATE);
  }

  /**
   * 建立新的 area，成功後自動選取。
   *
   * @param event 建立 area 表單的 submit event。
   * @returns 無；僅更新頁面狀態。
   */
  async function handleCreateArea(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setIsSubmittingCreate(true);
    setWorkspaceError(null);
    setWorkspaceNotice(null);
    try {
      const createdArea = await createArea({
        name: createName,
        description: createDescription,
      });
      setCreateName("");
      setCreateDescription("");
      setWorkspaceNotice(`已建立 area：${createdArea.name}`);
      await loadWorkspace(createdArea.id);
    } catch (error) {
      setWorkspaceError(error instanceof Error ? error.message : "建立 area 失敗。");
    } finally {
      setIsSubmittingCreate(false);
    }
  }

  /**
   * 切換目前選取的 area。
   *
   * @param areaId 要切換到的 area 識別碼。
   * @returns 無；僅更新頁面狀態。
   */
  async function handleSelectArea(areaId: string): Promise<void> {
    setSelectedAreaId(areaId);
    setWorkspaceError(null);
    setWorkspaceNotice(null);
    try {
      await loadArea(areaId);
    } catch (error) {
      setWorkspaceError(error instanceof Error ? error.message : "讀取 area 失敗。");
    }
  }

  /**
   * 提交 access 整體替換。
   *
   * @param event access 表單的 submit event。
   * @returns 無；僅更新頁面狀態。
   */
  async function handleSaveAccess(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!selectedAreaId) {
      return;
    }

    setIsSubmittingAccess(true);
    setWorkspaceError(null);
    setWorkspaceNotice(null);
    try {
      const nextPayload = await replaceAreaAccess(selectedAreaId, {
        users: parseUsersText(accessEditor.usersText),
        groups: parseGroupsText(accessEditor.groupsText),
      });
      setAccessPayload(nextPayload);
      setAccessEditor(buildEditableAccessState(nextPayload));
      setWorkspaceNotice("已更新 area access 規則。");
      await loadWorkspace(selectedAreaId);
    } catch (error) {
      setWorkspaceError(error instanceof Error ? error.message : "更新 access 失敗。");
    } finally {
      setIsSubmittingAccess(false);
    }
  }

  /**
   * 上傳單一文件並更新文件列表。
   *
   * @param event upload 表單的 submit event。
   * @returns 無；僅更新頁面狀態。
   */
  async function handleUploadDocument(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!selectedAreaId || !uploadState.file) {
      setWorkspaceError("請先選擇要上傳的檔案。");
      return;
    }

    setIsSubmittingUpload(true);
    setWorkspaceError(null);
    setWorkspaceNotice(null);
    try {
      const payload = await uploadDocument(selectedAreaId, uploadState.file);
      const refreshedJob = await fetchIngestJob(payload.job.id);
      setDocumentJobs((current) => ({ ...current, [payload.document.id]: refreshedJob }));
      setUploadState(EMPTY_UPLOAD_STATE);
      setWorkspaceNotice(`已建立文件：${payload.document.file_name}`);
      await loadArea(selectedAreaId);
    } catch (error) {
      setWorkspaceError(error instanceof Error ? error.message : "上傳文件失敗。");
    } finally {
      setIsSubmittingUpload(false);
    }
  }

  return (
    <main className="min-h-screen bg-[linear-gradient(180deg,_#f4efe4_0%,_#e6dfcf_46%,_#d4d0be_100%)] text-stone-900">
      <div className="mx-auto flex max-w-7xl flex-col gap-6 px-6 py-8">
        <header className="rounded-[2rem] border border-stone-900/10 bg-[rgba(255,252,246,0.88)] p-8 shadow-[0_24px_80px_rgba(47,39,24,0.12)] backdrop-blur">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.32em] text-amber-700">Protected Workspace</p>
              <h1 className="mt-3 text-4xl font-semibold tracking-tight">{appConfig.appName}</h1>
              <p className="mt-4 max-w-3xl text-sm leading-7 text-stone-700">
                目前已接上正式登入流程。此頁僅對已驗證使用者開放，並透過既有 API 與 SQL gate 顯示目前可存取的 Knowledge Areas。
              </p>
            </div>
            <div className="flex flex-col gap-3 rounded-2xl border border-stone-900/10 bg-stone-900 px-5 py-4 text-sm text-stone-100">
              <p className="font-medium">{principal?.sub ?? "unknown-user"}</p>
              <p className="text-xs text-stone-300">
                groups: {principal?.groups.length ? principal.groups.join(", ") : "(無)"}
              </p>
              <div className="flex gap-3">
                <Link className="rounded-full border border-white/15 px-4 py-1 text-xs" to="/">
                  回首頁
                </Link>
                <button className="rounded-full bg-white/10 px-4 py-1 text-xs" onClick={() => void logout()} type="button">
                  登出
                </button>
              </div>
            </div>
          </div>

          <div className="mt-6 rounded-2xl border border-stone-900/10 bg-stone-900 px-5 py-4 text-sm text-stone-100">
            <p>API Base URL</p>
            <p className="mt-1 font-mono text-xs text-stone-300">{appConfig.apiBaseUrl}</p>
            <p className="mt-3 text-stone-300">
              Health:{" "}
              {healthState.status === "success"
                ? `${healthState.payload.status} / ${healthState.payload.version}`
                : healthState.status === "error"
                  ? "error"
                  : "loading"}
            </p>
          </div>
        </header>

        <section className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
          <div className="space-y-6">
            <section className="rounded-[1.75rem] border border-stone-900/10 bg-white/85 p-6 shadow-[0_18px_50px_rgba(47,39,24,0.08)]">
              <div className="flex items-center justify-between">
                <h2 className="text-xl font-semibold">Auth Context</h2>
                {isLoadingWorkspace ? <span className="text-sm text-amber-700">同步中...</span> : null}
              </div>
              <div className="mt-5 rounded-2xl bg-stone-100 p-4 text-sm text-stone-700" data-testid="auth-context-panel">
                <p className="font-medium text-stone-900">sub: {principal?.sub ?? "(無)"}</p>
                <p className="mt-2">groups: {principal?.groups.length ? principal.groups.join(", ") : "(無)"}</p>
              </div>
            </section>

            <section className="rounded-[1.75rem] border border-stone-900/10 bg-[#1f1a14] p-6 text-stone-100 shadow-[0_18px_50px_rgba(24,18,9,0.2)]">
              <h2 className="text-xl font-semibold">Create Area</h2>
              <p className="mt-2 text-sm leading-6 text-stone-300">建立後會立即把目前使用者加入 `admin` direct role。</p>
              <form className="mt-5 space-y-4" onSubmit={handleCreateArea}>
                <div>
                  <label className="block text-sm font-medium text-stone-200" htmlFor="create-area-name">
                    名稱
                  </label>
                  <input
                    id="create-area-name"
                    data-testid="create-area-name"
                    className="mt-2 w-full rounded-2xl border border-white/10 bg-white/10 px-4 py-3 text-sm outline-none transition focus:border-amber-400 focus:bg-white/15"
                    value={createName}
                    onChange={(event) => setCreateName(event.target.value)}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-stone-200" htmlFor="create-area-description">
                    說明
                  </label>
                  <textarea
                    id="create-area-description"
                    data-testid="create-area-description"
                    className="mt-2 min-h-24 w-full rounded-2xl border border-white/10 bg-white/10 px-4 py-3 text-sm outline-none transition focus:border-amber-400 focus:bg-white/15"
                    value={createDescription}
                    onChange={(event) => setCreateDescription(event.target.value)}
                  />
                </div>
                <button
                  data-testid="create-area-submit"
                  className="rounded-full bg-amber-500 px-5 py-2 text-sm font-semibold text-stone-950 transition hover:bg-amber-400 disabled:cursor-not-allowed disabled:opacity-60"
                  disabled={isSubmittingCreate}
                  type="submit"
                >
                  {isSubmittingCreate ? "建立中..." : "建立 area"}
                </button>
              </form>
            </section>
          </div>

          <div className="space-y-6">
            <section className="rounded-[1.75rem] border border-stone-900/10 bg-white/85 p-6 shadow-[0_18px_50px_rgba(47,39,24,0.08)]">
              <div className="flex items-center justify-between">
                <h2 className="text-xl font-semibold">Areas</h2>
                <span className="text-sm text-stone-500">{areas.length} items</span>
              </div>

              {workspaceError ? (
                <div
                  data-testid="workspace-error"
                  className="mt-4 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
                >
                  {workspaceError}
                </div>
              ) : null}
              {workspaceNotice ? (
                <div
                  data-testid="workspace-notice"
                  className="mt-4 rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700"
                >
                  {workspaceNotice}
                </div>
              ) : null}

              <div className="mt-5 grid gap-3" data-testid="areas-list">
                {areas.length > 0 ? (
                  areas.map((area) => (
                    <button
                      key={area.id}
                      data-testid={`area-card-${area.id}`}
                      className={`rounded-2xl border px-4 py-4 text-left transition ${
                        area.id === selectedAreaId
                          ? "border-amber-600 bg-amber-50"
                          : "border-stone-200 bg-stone-50 hover:border-stone-300 hover:bg-white"
                      }`}
                      type="button"
                      onClick={() => void handleSelectArea(area.id)}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="font-semibold text-stone-900">{area.name}</p>
                          <p className="mt-1 text-sm text-stone-600">{area.description ?? "無說明"}</p>
                        </div>
                        <span className="rounded-full bg-stone-900 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-stone-100">
                          {area.effective_role}
                        </span>
                      </div>
                      <p className="mt-3 text-xs text-stone-500">更新時間：{formatTimestamp(area.updated_at)}</p>
                    </button>
                  ))
                ) : (
                  <div className="rounded-2xl border border-dashed border-stone-300 bg-stone-50 px-4 py-8 text-center text-sm text-stone-500">
                    尚無可存取的 area。
                  </div>
                )}
              </div>
            </section>

            <section className="rounded-[1.75rem] border border-stone-900/10 bg-[#f8f6f0] p-6 shadow-[0_18px_50px_rgba(47,39,24,0.08)]">
              <h2 className="text-xl font-semibold">Area Detail</h2>
              {selectedArea ? (
                <div className="mt-5 space-y-6" data-testid="area-detail-panel">
                  <div className="rounded-2xl border border-stone-200 bg-white p-5" data-testid="area-summary-card">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <p className="text-lg font-semibold">{selectedArea.name}</p>
                        <p className="mt-2 text-sm text-stone-600">{selectedArea.description ?? "無說明"}</p>
                      </div>
                      <span className="rounded-full bg-amber-600 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-white">
                        {selectedArea.effective_role}
                      </span>
                    </div>
                    <dl className="mt-4 grid gap-3 text-sm text-stone-600 sm:grid-cols-2">
                      <div>
                        <dt className="font-medium text-stone-900">建立時間</dt>
                        <dd className="mt-1">{formatTimestamp(selectedArea.created_at)}</dd>
                      </div>
                      <div>
                        <dt className="font-medium text-stone-900">更新時間</dt>
                        <dd className="mt-1">{formatTimestamp(selectedArea.updated_at)}</dd>
                      </div>
                    </dl>
                  </div>

                  <div className="rounded-2xl border border-stone-200 bg-white p-5">
                    <div className="flex items-center justify-between">
                      <h3 className="text-lg font-semibold">Access Tab</h3>
                      <span className="text-sm text-stone-500">
                        {selectedArea.effective_role === "admin" ? "可管理" : "僅 admin 可管理"}
                      </span>
                    </div>

                    {selectedArea.effective_role === "admin" ? (
                      <form className="mt-4 space-y-4" onSubmit={handleSaveAccess}>
                        <div className="grid gap-4 lg:grid-cols-2">
                          <div>
                            <label className="block text-sm font-medium text-stone-700" htmlFor="access-users">
                              Users
                            </label>
                            <textarea
                              id="access-users"
                              data-testid="access-users"
                              className="mt-2 min-h-48 w-full rounded-2xl border border-stone-300 bg-stone-50 px-4 py-3 font-mono text-sm outline-none transition focus:border-amber-600 focus:bg-white"
                              placeholder={"一行一筆：user_sub,role\n例如：user-admin,admin"}
                              value={accessEditor.usersText}
                              onChange={(event) =>
                                setAccessEditor((current) => ({ ...current, usersText: event.target.value }))
                              }
                            />
                          </div>
                          <div>
                            <label className="block text-sm font-medium text-stone-700" htmlFor="access-groups">
                              Groups
                            </label>
                            <textarea
                              id="access-groups"
                              data-testid="access-groups"
                              className="mt-2 min-h-48 w-full rounded-2xl border border-stone-300 bg-stone-50 px-4 py-3 font-mono text-sm outline-none transition focus:border-amber-600 focus:bg-white"
                              placeholder={"一行一筆：group_path,role\n例如：/group/reader,reader"}
                              value={accessEditor.groupsText}
                              onChange={(event) =>
                                setAccessEditor((current) => ({ ...current, groupsText: event.target.value }))
                              }
                            />
                          </div>
                        </div>
                        <p className="text-sm text-stone-500">支援角色：{AREA_ROLE_OPTIONS.join(", ")}</p>
                        <button
                          data-testid="save-access"
                          className="rounded-full bg-stone-900 px-5 py-2 text-sm font-medium text-white transition hover:bg-stone-700 disabled:cursor-not-allowed disabled:opacity-60"
                          disabled={isSubmittingAccess}
                          type="submit"
                        >
                          {isSubmittingAccess ? "儲存中..." : "更新 access"}
                        </button>

                        {accessPayload ? (
                          <div data-testid="access-summary" className="rounded-2xl bg-stone-100 p-4 text-sm text-stone-700">
                            <p className="font-medium text-stone-900">目前 access 規則已載入。</p>
                            <p className="mt-2">users: {accessPayload.users.length} 筆</p>
                            <p>groups: {accessPayload.groups.length} 筆</p>
                          </div>
                        ) : null}
                      </form>
                    ) : (
                      <div className="mt-4 rounded-2xl border border-dashed border-stone-300 bg-stone-50 px-4 py-6 text-sm text-stone-500">
                        目前角色只能檢視 area detail。若需要管理 access，必須使用 admin 身分。
                      </div>
                    )}
                  </div>

                  <div className="rounded-2xl border border-stone-200 bg-white p-5">
                    <div className="flex items-center justify-between">
                      <h3 className="text-lg font-semibold">Files Tab</h3>
                      <span className="text-sm text-stone-500">{documents.length} files</span>
                    </div>

                    {selectedArea.effective_role === "admin" || selectedArea.effective_role === "maintainer" ? (
                      <form className="mt-4 space-y-4" onSubmit={handleUploadDocument}>
                        <div>
                          <label className="block text-sm font-medium text-stone-700" htmlFor="document-upload">
                            Upload File
                          </label>
                          <input
                            id="document-upload"
                            data-testid="document-upload"
                            className="mt-2 block w-full rounded-2xl border border-stone-300 bg-stone-50 px-4 py-3 text-sm"
                            type="file"
                            accept=".txt,.md,.pdf,.docx,.pptx,.html"
                            onChange={(event) =>
                              setUploadState({ file: event.target.files?.[0] ?? null })
                            }
                          />
                          <p className="mt-2 text-sm text-stone-500">
                            MVP 目前真正支援解析 `TXT/MD`；其餘型別會建立 job，但可能進入 failed。
                          </p>
                        </div>
                        <button
                          data-testid="upload-document-submit"
                          className="rounded-full bg-emerald-700 px-5 py-2 text-sm font-medium text-white transition hover:bg-emerald-600 disabled:cursor-not-allowed disabled:opacity-60"
                          disabled={isSubmittingUpload}
                          type="submit"
                        >
                          {isSubmittingUpload ? "上傳中..." : "上傳文件"}
                        </button>
                      </form>
                    ) : (
                      <div className="mt-4 rounded-2xl border border-dashed border-stone-300 bg-stone-50 px-4 py-6 text-sm text-stone-500">
                        目前角色可檢視文件與狀態，但不可上傳新文件。
                      </div>
                    )}

                    <div className="mt-5 grid gap-3" data-testid="documents-list">
                      {documents.length > 0 ? (
                        documents.map((document) => {
                          const latestJob = documentJobs[document.id] ?? null;
                          return (
                            <article
                              key={document.id}
                              data-testid={`document-card-${document.id}`}
                              className="rounded-2xl border border-stone-200 bg-stone-50 px-4 py-4"
                            >
                              <div className="flex flex-wrap items-start justify-between gap-3">
                                <div>
                                  <p className="font-semibold text-stone-900">{document.file_name}</p>
                                  <p className="mt-1 text-sm text-stone-600">
                                    {document.content_type} / {document.file_size} bytes
                                  </p>
                                </div>
                                <span
                                  className={`rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] ${
                                    document.status === "ready"
                                      ? "bg-emerald-100 text-emerald-700"
                                      : document.status === "failed"
                                        ? "bg-red-100 text-red-700"
                                        : "bg-amber-100 text-amber-700"
                                  }`}
                                >
                                  {document.status}
                                </span>
                              </div>
                              <p className="mt-3 text-xs text-stone-500">
                                更新時間：{formatTimestamp(document.updated_at)}
                              </p>
                              {latestJob ? (
                                <div className="mt-3 rounded-2xl bg-white px-4 py-3 text-sm text-stone-700">
                                  <p className="font-medium text-stone-900">job: {latestJob.status}</p>
                                  {latestJob.error_message ? (
                                    <p className="mt-2 text-red-700" data-testid={`document-job-error-${document.id}`}>
                                      {latestJob.error_message}
                                    </p>
                                  ) : null}
                                </div>
                              ) : null}
                            </article>
                          );
                        })
                      ) : (
                        <div className="rounded-2xl border border-dashed border-stone-300 bg-stone-50 px-4 py-8 text-center text-sm text-stone-500">
                          此 area 尚無文件。
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="mt-5 rounded-2xl border border-dashed border-stone-300 bg-white px-4 py-12 text-center text-sm text-stone-500">
                  先從左側清單選一個 area。
                </div>
              )}
            </section>
          </div>
        </section>
      </div>
    </main>
  );
}
