/** 登入後的 Areas 管理頁。重構為一頁式戰情室佈局。 */

import { useEffect, useState } from "react";

import { useAuth } from "../auth/AuthProvider";
import { DashboardLayout } from "../components/layout/DashboardLayout";
import { AreaSidebar } from "../features/areas/components/AreaSidebar";
import { AccessModal } from "../features/areas/components/AccessModal";
import { AreaEditModal } from "../features/areas/components/AreaEditModal";
import { DocumentsDrawer } from "../features/documents/components/DocumentsDrawer";
import { ChatPanel } from "../features/chat/components/ChatPanel";
import {
  deleteArea,
  fetchAreas,
  fetchAuthContext,
  fetchAreaDetail,
} from "../lib/api";
import type {
  AreaSummary,
} from "../lib/types";


/** 登入後的 Areas 管理頁。 */
export function AreasPage(): JSX.Element {
  const { ensureFreshToken } = useAuth();
  const [areas, setAreas] = useState<AreaSummary[]>([]);
  const [selectedAreaId, setSelectedAreaId] = useState<string | null>(null);
  const [selectedArea, setSelectedArea] = useState<AreaSummary | null>(null);
  const [workspaceError, setWorkspaceError] = useState<string | null>(null);
  const [workspaceNotice, setWorkspaceNotice] = useState<string | null>(null);
  const [isLoadingWorkspace, setIsLoadingWorkspace] = useState(false);
  const [isDocumentsOpen, setIsDocumentsOpen] = useState(false);
  const [isAccessOpen, setIsAccessOpen] = useState(false);
  const [isAreaEditOpen, setIsAreaEditOpen] = useState(false);
  const [isDeletingArea, setIsDeletingArea] = useState(false);

  useEffect(() => {
    void loadWorkspace();
  }, []);

  /**
   * 依目前 session 重新載入 auth context 與 area 清單。
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
      }
    } catch (error) {
      setWorkspaceError(error instanceof Error ? error.message : "載入工作區失敗。");
      setAreas([]);
      setSelectedAreaId(null);
      setSelectedArea(null);
    } finally {
      setIsLoadingWorkspace(false);
    }
  }

  /**
   * 載入單一 area 詳細資料。
   */
  async function loadArea(areaId: string): Promise<void> {
    const detail = await fetchAreaDetail(areaId);
    setSelectedArea(detail);
  }

  /**
   * 切換目前選取的 area。
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
   * 刪除目前 area，成功後自動切換到下一個可用 area。
   */
  async function handleDeleteArea(): Promise<void> {
    if (!selectedArea) {
      return;
    }
    if (!confirm(`確定要刪除 ${selectedArea.name} 嗎？這會一併刪除底下文件與索引資料。`)) {
      return;
    }

    setIsDeletingArea(true);
    setWorkspaceError(null);
    setWorkspaceNotice(null);
    try {
      const deletedAreaName = selectedArea.name;
      await deleteArea(selectedArea.id);
      setIsAreaEditOpen(false);
      setIsAccessOpen(false);
      setIsDocumentsOpen(false);
      await loadWorkspace(null);
      setWorkspaceNotice(`已刪除區域：${deletedAreaName}`);
    } catch (error) {
      setWorkspaceError(error instanceof Error ? error.message : "刪除 area 失敗。");
    } finally {
      setIsDeletingArea(false);
    }
  }

  return (
    <DashboardLayout
      sidebar={
        <AreaSidebar
          areas={areas}
          selectedAreaId={selectedAreaId}
          onSelectArea={handleSelectArea}
          onAreaCreated={(id) => void loadWorkspace(id)}
          isLoading={isLoadingWorkspace}
          error={workspaceError}
        />
      }
      headerActions={
        selectedArea && (
          <div className="flex items-center gap-3" data-testid="area-detail-panel">
            <span className="mr-4 text-sm font-bold text-stone-900">{selectedArea.name}</span>
            <button
              onClick={() => setIsDocumentsOpen(true)}
              className="rounded-full border border-stone-900/10 bg-white px-5 py-2 text-xs font-bold text-stone-900 shadow-sm hover:bg-stone-50 transition"
              type="button"
            >
              管理文件
            </button>
            {selectedArea.effective_role === "admin" && (
              <>
                <button
                  onClick={() => setIsAreaEditOpen(true)}
                  className="rounded-full border border-stone-900/10 bg-white px-5 py-2 text-xs font-bold text-stone-900 shadow-sm hover:bg-stone-50 transition"
                  type="button"
                >
                  編輯區域
                </button>
                <button
                  onClick={() => setIsAccessOpen(true)}
                  className="rounded-full border border-stone-900/10 bg-white px-5 py-2 text-xs font-bold text-stone-900 shadow-sm hover:bg-stone-50 transition"
                  type="button"
                >
                  權限設定
                </button>
                <button
                  onClick={() => void handleDeleteArea()}
                  className="rounded-full border border-red-200 bg-red-50 px-5 py-2 text-xs font-bold text-red-700 shadow-sm transition hover:bg-red-100 disabled:opacity-50"
                  disabled={isDeletingArea}
                  type="button"
                >
                  {isDeletingArea ? "刪除中..." : "刪除區域"}
                </button>
              </>
            )}
          </div>
        )
      }
    >
      <div className="flex flex-1 flex-col overflow-hidden">
        {workspaceError ? (
          <div
            data-testid="workspace-error"
            className="mb-6 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
          >
            {workspaceError}
          </div>
        ) : null}

        {workspaceNotice ? (
          <div
            data-testid="workspace-notice"
            className="mb-6 rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700"
          >
            {workspaceNotice}
          </div>
        ) : null}

        {selectedArea ? (
          <div className="flex flex-1 flex-col overflow-hidden">
            {selectedArea.effective_role === "reader" && (
              <div className="mb-4 rounded-xl border border-stone-200 bg-stone-50 px-4 py-2 text-[10px] text-stone-500">
                目前角色只能檢視 area detail。若需要管理 access，必須使用 admin 身分。
              </div>
            )}
            <ChatPanel
              areaId={selectedAreaId}
              accessTokenGetter={ensureFreshToken}
              onError={setWorkspaceError}
              onNoticeClear={() => setWorkspaceNotice(null)}
            />


            <DocumentsDrawer
              isOpen={isDocumentsOpen}
              onClose={() => setIsDocumentsOpen(false)}
              areaId={selectedArea.id}
              areaName={selectedArea.name}
              effectiveRole={selectedArea.effective_role}
            />

            <AccessModal
              isOpen={isAccessOpen}
              onClose={() => setIsAccessOpen(false)}
              areaId={selectedArea.id}
              areaName={selectedArea.name}
              onAccessUpdated={() => void loadWorkspace(selectedArea.id)}
            />

            <AreaEditModal
              isOpen={isAreaEditOpen}
              onClose={() => setIsAreaEditOpen(false)}
              areaId={selectedArea.id}
              areaName={selectedArea.name}
              initialName={selectedArea.name}
              initialDescription={selectedArea.description}
              onUpdated={() => void loadWorkspace(selectedArea.id)}
            />
          </div>
        ) : (
          <div className="flex flex-1 flex-col items-center justify-center rounded-[2rem] border border-dashed border-stone-300 bg-white/50 px-4 py-12 text-center text-sm text-stone-400">
            <div className="mb-4 h-16 w-16 rounded-3xl bg-stone-100" />
            <p>請先從左側清單選擇或建立一個 Knowledge Area 以開始對話。</p>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
