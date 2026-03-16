import React, { useState, useEffect, type FormEvent } from "react";
import type { AreaAccessPayload, AreaRole, AccessUserEntry, AccessGroupEntry } from "../../../lib/types";
import { fetchAreaAccess, replaceAreaAccess } from "../../../lib/api";

/** Area access 編輯支援的固定角色。 */
const AREA_ROLE_OPTIONS: AreaRole[] = ["reader", "maintainer", "admin"];

/**
 * 將 user access entries 序列化為可編輯文字。
 */
function serializeUsers(entries: AccessUserEntry[]): string {
  return entries.map((entry) => `${entry.user_sub},${entry.role}`).join("\n");
}

/**
 * 將 group access entries 序列化為可編輯文字。
 */
function serializeGroups(entries: AccessGroupEntry[]): string {
  return entries.map((entry) => `${entry.group_path},${entry.role}`).join("\n");
}

/**
 * 驗證並解析 user access 編輯文字。
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

interface AccessModalProps {
  isOpen: boolean;
  onClose: () => void;
  areaId: string;
  areaName: string;
  onAccessUpdated?: () => void;
}

export function AccessModal({
  isOpen,
  onClose,
  areaId,
  areaName,
  onAccessUpdated,
}: AccessModalProps): JSX.Element {
  const [usersText, setUsersText] = useState("");
  const [groupsText, setGroupsText] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen && areaId) {
      void loadAccess();
    }
  }, [isOpen, areaId]);

  async function loadAccess(): Promise<void> {
    setIsLoading(true);
    setError(null);
    try {
      const payload = await fetchAreaAccess(areaId);
      setUsersText(serializeUsers(payload.users));
      setGroupsText(serializeGroups(payload.groups));
    } catch (err) {
      setError(err instanceof Error ? err.message : "載入存取權限失敗");
    } finally {
      setIsLoading(false);
    }
  }

  async function handleSave(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setIsSubmitting(true);
    setError(null);
    setNotice(null);
    try {
      await replaceAreaAccess(areaId, {
        users: parseUsersText(usersText),
        groups: parseGroupsText(groupsText),
      });
      setNotice("已成功更新存取權限規則。");
      onAccessUpdated?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "更新存取權限失敗");
    } finally {
      setIsSubmitting(false);
    }
  }

  if (!isOpen) return <></>;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6">
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-stone-900/40 backdrop-blur-sm transition-opacity" 
        onClick={onClose}
      />

      {/* Modal Content */}
      <div className="relative w-full max-w-2xl transform rounded-[2rem] border border-stone-900/10 bg-white p-8 shadow-2xl transition-all">
        <header className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold text-stone-900">權限設定</h2>
            <p className="mt-1 text-sm text-stone-500">管理 {areaName} 的使用者與群組存取權</p>
          </div>
          <button 
            onClick={onClose}
            aria-label="Close access modal"
            className="rounded-full p-2 text-stone-400 hover:bg-stone-100 hover:text-stone-900 transition"
          >
            <span className="text-2xl leading-none">&times;</span>
          </button>
        </header>

        {error && (
          <div className="mt-6 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {notice && (
          <div className="mt-6 rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
            {notice}
          </div>
        )}

        {isLoading ? (
          <div className="py-20 text-center">
            <span className="text-sm text-stone-400">載入中...</span>
          </div>
        ) : (
          <form className="mt-8 space-y-6" onSubmit={handleSave}>
            <div className="grid gap-6 md:grid-cols-2">
              <div className="space-y-2">
                <label className="text-sm font-semibold text-stone-700" htmlFor="access-users">
                  使用者 (Users)
                </label>
                <textarea
                  id="access-users"
                  data-testid="access-users"
                  className="min-h-48 w-full rounded-2xl border border-stone-200 bg-stone-50 px-4 py-3 font-mono text-xs outline-none transition focus:border-amber-600 focus:bg-white"
                  placeholder={"一行一筆：user_sub,role\n例如：user-admin,admin"}
                  value={usersText}
                  onChange={(e) => setUsersText(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-semibold text-stone-700" htmlFor="access-groups">
                  群組 (Groups)
                </label>
                <textarea
                  id="access-groups"
                  data-testid="access-groups"
                  className="min-h-48 w-full rounded-2xl border border-stone-200 bg-stone-50 px-4 py-3 font-mono text-xs outline-none transition focus:border-amber-600 focus:bg-white"
                  placeholder={"一行一筆：group_path,role\n例如：/group/reader,reader"}
                  value={groupsText}
                  onChange={(e) => setGroupsText(e.target.value)}
                />
              </div>
            </div>

            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex flex-col gap-1">
                <p className="text-xs text-stone-500">
                  支援角色：<span className="font-mono text-amber-700">{AREA_ROLE_OPTIONS.join(", ")}</span>
                </p>
                <p className="text-xs text-stone-400" data-testid="access-summary">
                  目前設定：users: {usersText.split("\n").filter(l => l.trim()).length} 筆, groups: {groupsText.split("\n").filter(l => l.trim()).length} 筆
                </p>
              </div>
              <div className="flex gap-3">
                <button
                  type="button"
                  onClick={onClose}
                  className="rounded-full border border-stone-200 px-6 py-2 text-sm font-semibold text-stone-600 hover:bg-stone-50 transition"
                >
                  取消
                </button>
                <button
                  data-testid="save-access"
                  className="rounded-full bg-stone-900 px-8 py-2 text-sm font-semibold text-white transition hover:bg-stone-700 disabled:opacity-50"
                  disabled={isSubmitting}
                  type="submit"
                >
                  {isSubmitting ? "儲存中..." : "更新權限"}
                </button>
              </div>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
