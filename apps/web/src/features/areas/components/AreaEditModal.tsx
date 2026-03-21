/** Area 基本資料編輯 modal。 */

import React, { useEffect, useState, type FormEvent } from "react";

import { updateArea } from "../../../lib/api";


interface AreaEditModalProps {
  isOpen: boolean;
  onClose: () => void;
  areaId: string;
  areaName: string;
  initialName: string;
  initialDescription: string | null;
  onUpdated?: () => void;
}


/** Area 基本資料編輯 modal。 */
export function AreaEditModal({
  isOpen,
  onClose,
  areaId,
  areaName,
  initialName,
  initialDescription,
  onUpdated,
}: AreaEditModalProps): JSX.Element {
  const [name, setName] = useState(initialName);
  const [description, setDescription] = useState(initialDescription ?? "");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) {
      return;
    }
    setName(initialName);
    setDescription(initialDescription ?? "");
    setError(null);
  }, [initialDescription, initialName, isOpen]);

  /** 儲存 area 基本資料。 */
  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!name.trim()) {
      return;
    }

    setIsSubmitting(true);
    setError(null);
    try {
      await updateArea(areaId, {
        name,
        description: description.trim() ? description : null,
      });
      onUpdated?.();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "更新區域失敗");
    } finally {
      setIsSubmitting(false);
    }
  }

  if (!isOpen) {
    return <></>;
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6">
      <div className="absolute inset-0 bg-stone-900/40 backdrop-blur-sm transition-opacity" onClick={onClose} />

      <div className="relative w-full max-w-2xl rounded-[2rem] border border-stone-900/10 bg-white p-8 shadow-2xl">
        <header className="flex items-center justify-between border-b border-stone-100 pb-4">
          <div>
            <h2 className="text-2xl font-bold text-stone-900">編輯區域</h2>
            <p className="mt-1 text-sm text-stone-500">更新 {areaName} 的名稱與說明</p>
          </div>
          <button
            onClick={onClose}
            aria-label="Close area edit modal"
            className="rounded-full p-2 text-stone-400 transition hover:bg-stone-100 hover:text-stone-900"
          >
            <span className="text-2xl leading-none">&times;</span>
          </button>
        </header>

        {error ? (
          <div className="mt-4 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        ) : null}

        <form className="mt-6 space-y-4" onSubmit={handleSubmit}>
          <div>
            <label className="mb-2 block text-sm font-semibold text-stone-700" htmlFor="edit-area-name">
              區域名稱
            </label>
            <input
              id="edit-area-name"
              data-testid="edit-area-name"
              className="w-full rounded-xl border border-stone-200 bg-stone-50 px-4 py-3 text-sm outline-none transition focus:border-amber-600 focus:bg-white"
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
          </div>

          <div>
            <label className="mb-2 block text-sm font-semibold text-stone-700" htmlFor="edit-area-description">
              區域說明
            </label>
            <textarea
              id="edit-area-description"
              data-testid="edit-area-description"
              className="min-h-[140px] w-full rounded-xl border border-stone-200 bg-stone-50 px-4 py-3 text-sm outline-none transition focus:border-amber-600 focus:bg-white"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
            />
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-full border border-stone-200 bg-white px-5 py-2 text-sm font-semibold text-stone-700 transition hover:bg-stone-50"
            >
              取消
            </button>
            <button
              type="submit"
              data-testid="save-area-settings"
              className="rounded-full bg-stone-900 px-5 py-2 text-sm font-semibold text-white transition hover:bg-stone-700 disabled:opacity-50"
              disabled={isSubmitting || !name.trim()}
            >
              {isSubmitting ? "儲存中..." : "儲存設定"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
