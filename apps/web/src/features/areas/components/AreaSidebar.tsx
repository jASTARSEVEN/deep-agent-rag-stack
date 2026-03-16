import React, { useState, type FormEvent } from "react";
import type { AreaSummary } from "../../../lib/types";
import { createArea } from "../../../lib/api";

/**
 * AreaSidebar 元件。
 * 顯示 Knowledge Areas 列表，並提供建立新區域的表單。
 * 
 * @param areas 可選取的 Area 列表。
 * @param selectedAreaId 目前選中的 Area 識別碼。
 * @param onSelectArea 當使用者切換 Area 時觸發的點擊事件。
 * @param onAreaCreated 當成功建立新 Area 時，通知父元件重新整理。
 * @param isLoading 是否正在載入中。
 * @param error 顯示錯誤訊息。
 */
interface AreaSidebarProps {
  areas: AreaSummary[];
  selectedAreaId: string | null;
  onSelectArea: (areaId: string) => void;
  onAreaCreated: (newAreaId: string) => void;
  isLoading?: boolean;
  error?: string | null;
}

/** 格式化時間字串。 */
function formatTimestamp(value: string): string {
  return new Intl.DateTimeFormat("zh-TW", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function AreaSidebar({ 
  areas, 
  selectedAreaId, 
  onSelectArea, 
  onAreaCreated,
  isLoading,
  error
}: AreaSidebarProps): JSX.Element {
  const [createName, setCreateName] = useState("");
  const [createDescription, setCreateDescription] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  /** 提交建立 Area 的請求。 */
  async function handleCreate(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!createName.trim()) return;

    setIsSubmitting(true);
    setLocalError(null);
    try {
      const createdArea = await createArea({
        name: createName,
        description: createDescription,
      });
      setCreateName("");
      setCreateDescription("");
      onAreaCreated(createdArea.id);
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : "建立 Area 失敗");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="flex flex-col h-full gap-6 p-6">
      <section>
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold uppercase tracking-widest text-stone-500">Knowledge Areas</h2>
          {isLoading && <span className="text-xs text-amber-700">同步中...</span>}
        </div>

        {error || localError ? (
          <div className="mt-4 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
            {error || localError}
          </div>
        ) : null}

        <div className="mt-4 grid gap-2" data-testid="areas-list">
          {areas.length > 0 ? (
            areas.map((area) => (
              <button
                key={area.id}
                data-testid={`area-card-${area.id}`}
                className={`group rounded-xl border p-4 text-left transition-all ${
                  area.id === selectedAreaId
                    ? "border-amber-600 bg-amber-50 shadow-sm"
                    : "border-transparent bg-transparent hover:bg-stone-100"
                }`}
                type="button"
                onClick={() => onSelectArea(area.id)}
              >
                <div className="flex items-start justify-between gap-2">
                  <p className={`font-semibold text-sm ${area.id === selectedAreaId ? "text-amber-900" : "text-stone-900"}`}>
                    {area.name}
                  </p>
                  <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${
                    area.id === selectedAreaId ? "bg-amber-600 text-white" : "bg-stone-200 text-stone-600"
                  }`}>
                    {area.effective_role}
                  </span>
                </div>
                <p className="mt-1 line-clamp-1 text-xs text-stone-500">{area.description || "無說明"}</p>
                <p className="mt-2 text-[10px] text-stone-400">{formatTimestamp(area.updated_at)}</p>
              </button>
            ))
          ) : (
            <div className="rounded-xl border border-dashed border-stone-300 px-4 py-8 text-center text-xs text-stone-400">
              尚無可存取的 area。
            </div>
          )}
        </div>
      </section>

      <section className="mt-auto pt-6 border-t border-stone-900/5">
        <h2 className="text-sm font-semibold text-stone-900">建立新區域</h2>
        <form className="mt-4 space-y-3" onSubmit={handleCreate}>
          <input
            id="create-area-name"
            data-testid="create-area-name"
            placeholder="區域名稱"
            className="w-full rounded-xl border border-stone-200 bg-stone-50 px-3 py-2 text-xs outline-none focus:border-amber-400 focus:bg-white"
            value={createName}
            onChange={(e) => setCreateName(e.target.value)}
          />
          <textarea
            id="create-area-description"
            data-testid="create-area-description"
            placeholder="區域說明..."
            className="min-h-[80px] w-full rounded-xl border border-stone-200 bg-stone-50 px-3 py-2 text-xs outline-none focus:border-amber-400 focus:bg-white"
            value={createDescription}
            onChange={(e) => setCreateDescription(e.target.value)}
          />
          <button
            data-testid="create-area-submit"
            className="w-full rounded-full bg-stone-900 py-2 text-xs font-semibold text-white transition hover:bg-stone-700 disabled:opacity-50"
            disabled={isSubmitting || !createName.trim()}
            type="submit"
          >
            {isSubmitting ? "建立中..." : "建立 Area"}
          </button>
        </form>
      </section>
    </div>
  );
}
