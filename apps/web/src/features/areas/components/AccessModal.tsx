import React, { useState, useEffect, type FormEvent, useCallback } from "react";
import type { AreaAccessPayload, AreaRole, AccessUserEntry, AccessGroupEntry, UserSearchResult, GroupSearchResult } from "../../../lib/types";
import { fetchAreaAccess, replaceAreaAccess, searchUsers, searchGroups } from "../../../lib/api";

/** Area access 編輯支援的固定角色。 */
const AREA_ROLE_OPTIONS: AreaRole[] = ["reader", "maintainer", "admin"];

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
  const [users, setUsers] = useState<AccessUserEntry[]>([]);
  const [groups, setGroups] = useState<AccessGroupEntry[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  // Autocomplete states
  const [userQuery, setUserQuery] = useState("");
  const [userSuggestions, setUserSuggestions] = useState<UserSearchResult[]>([]);
  const [showUserDropdown, setShowUserDropdown] = useState(false);
  const [newUserRole, setNewUserRole] = useState<AreaRole>("reader");

  const [groupQuery, setGroupQuery] = useState("");
  const [groupSuggestions, setGroupSuggestions] = useState<GroupSearchResult[]>([]);
  const [showGroupDropdown, setShowGroupDropdown] = useState(false);
  const [newGroupRole, setNewGroupRole] = useState<AreaRole>("reader");

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
      setUsers(payload.users);
      setGroups(payload.groups);
    } catch (err) {
      setError(err instanceof Error ? err.message : "載入存取權限失敗");
    } finally {
      setIsLoading(false);
    }
  }

  // Debounced search for users
  useEffect(() => {
    if (!showUserDropdown || !userQuery.startsWith("@")) {
      setUserSuggestions([]);
      return;
    }

    const actualQuery = userQuery.slice(1).trim();
    
    const timer = setTimeout(() => {
      searchUsers(actualQuery).then(setUserSuggestions).catch(console.error);
    }, 300);
    return () => clearTimeout(timer);
  }, [userQuery, showUserDropdown]);

  // Debounced search for groups
  useEffect(() => {
    if (!showGroupDropdown || !groupQuery.startsWith("@")) {
      setGroupSuggestions([]);
      return;
    }

    const actualQuery = groupQuery.slice(1).trim();

    const timer = setTimeout(() => {
      searchGroups(actualQuery).then(setGroupSuggestions).catch(console.error);
    }, 300);
    return () => clearTimeout(timer);
  }, [groupQuery, showGroupDropdown]);

  async function handleSave(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setIsSubmitting(true);
    setError(null);
    setNotice(null);
    try {
      await replaceAreaAccess(areaId, { users, groups });
      setNotice("已成功更新存取權限規則。");
      onAccessUpdated?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "更新存取權限失敗");
    } finally {
      setIsSubmitting(false);
    }
  }

  function addUser() {
    const trimmed = userQuery.trim();
    if (!trimmed) return;
    const username = trimmed.startsWith("@") ? trimmed.slice(1) : trimmed;
    if (!username) return;

    setUsers((prev) => {
      const filtered = prev.filter((u) => u.username !== username);
      return [...filtered, { username, role: newUserRole }];
    });
    setUserQuery("");
    setShowUserDropdown(false);
  }

  function removeUser(username: string) {
    setUsers((prev) => prev.filter((u) => u.username !== username));
  }

  function addGroup() {
    const trimmed = groupQuery.trim();
    if (!trimmed) return;
    const group_path = trimmed.startsWith("@") ? trimmed.slice(1) : trimmed;
    if (!group_path) return;

    setGroups((prev) => {
      const filtered = prev.filter((g) => g.group_path !== group_path);
      return [...filtered, { group_path, role: newGroupRole }];
    });
    setGroupQuery("");
    setShowGroupDropdown(false);
  }

  function removeGroup(path: string) {
    setGroups((prev) => prev.filter((g) => g.group_path !== path));
  }

  if (!isOpen) return <></>;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6">
      <div 
        className="absolute inset-0 bg-stone-900/40 backdrop-blur-sm transition-opacity" 
        onClick={onClose}
      />

      <div className="relative w-full max-w-3xl transform rounded-[2rem] border border-stone-900/10 bg-white p-8 shadow-2xl transition-all max-h-[90vh] flex flex-col">
        <header className="flex-shrink-0 flex items-center justify-between pb-4 border-b border-stone-100">
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
          <div className="flex-shrink-0 mt-4 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {notice && (
          <div className="flex-shrink-0 mt-4 rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
            {notice}
          </div>
        )}

        <div className="flex-1 overflow-y-auto min-h-0 py-4 pb-48">
          {isLoading ? (
            <div className="py-20 text-center">
              <span className="text-sm text-stone-400">載入中...</span>
            </div>
          ) : (
            <form id="access-form" onSubmit={handleSave} className="space-y-8">
              {/* Users Section */}
              <div className="space-y-4">
                <h3 className="text-lg font-semibold text-stone-800">使用者 (Users)</h3>
                
                {/* Add User */}
                <div className="flex gap-2 items-start relative">
                  <div className="flex-1 relative">
                    <input
                      type="text"
                      className="w-full rounded-xl border border-stone-200 bg-stone-50 px-4 py-2 text-sm outline-none transition focus:border-amber-600 focus:bg-white"
                      placeholder="輸入 @ 搜尋使用者..."
                      value={userQuery}
                      onChange={(e) => {
                        const val = e.target.value;
                        setUserQuery(val);
                        setShowUserDropdown(val.startsWith("@"));
                      }}
                      onFocus={() => {
                        if (userQuery.startsWith("@")) setShowUserDropdown(true);
                      }}
                    />
                    {showUserDropdown && userSuggestions.length > 0 && (
                      <ul className="absolute z-20 w-full mt-1 max-h-48 overflow-auto rounded-xl border border-stone-200 bg-white shadow-lg">
                        {userSuggestions.map((u) => (
                          <li
                            key={u.username}
                            className="cursor-pointer px-4 py-2 text-sm hover:bg-stone-50"
                            onClick={() => {
                              setUserQuery(`@${u.username}`);
                              setShowUserDropdown(false);
                            }}
                          >
                            <div className="font-medium text-stone-900">{u.username}</div>
                            {u.email && <div className="text-xs text-stone-500">{u.email}</div>}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                  <select
                    className="rounded-xl border border-stone-200 bg-stone-50 px-3 py-2 text-sm outline-none transition focus:border-amber-600"
                    value={newUserRole}
                    onChange={(e) => setNewUserRole(e.target.value as AreaRole)}
                  >
                    {AREA_ROLE_OPTIONS.map((r) => (
                      <option key={r} value={r}>{r}</option>
                    ))}
                  </select>
                  <button
                    type="button"
                    onClick={addUser}
                    className="rounded-xl bg-stone-100 px-4 py-2 text-sm font-semibold text-stone-700 hover:bg-stone-200 transition"
                  >
                    新增
                  </button>
                </div>

                {/* User List */}
                {users.length > 0 && (
                  <div className="rounded-xl border border-stone-200 overflow-hidden">
                    <table className="w-full text-sm text-left">
                      <thead className="bg-stone-50 text-stone-500">
                        <tr>
                          <th className="px-4 py-2 font-medium">Username</th>
                          <th className="px-4 py-2 font-medium w-32">Role</th>
                          <th className="px-4 py-2 font-medium w-16 text-center">操作</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-stone-100">
                        {users.map((u) => (
                          <tr key={u.username} className="hover:bg-stone-50/50">
                            <td className="px-4 py-2 text-stone-900">{u.username}</td>
                            <td className="px-4 py-2 text-stone-600">{u.role}</td>
                            <td className="px-4 py-2 text-center">
                              <button
                                type="button"
                                onClick={() => removeUser(u.username)}
                                className="text-red-500 hover:text-red-700"
                              >
                                移除
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

              {/* Groups Section */}
              <div className="space-y-4">
                <h3 className="text-lg font-semibold text-stone-800">群組 (Groups)</h3>
                
                {/* Add Group */}
                <div className="flex gap-2 items-start relative">
                  <div className="flex-1 relative">
                    <input
                      type="text"
                      className="w-full rounded-xl border border-stone-200 bg-stone-50 px-4 py-2 text-sm outline-none transition focus:border-amber-600 focus:bg-white"
                      placeholder="輸入 @ 搜尋群組..."
                      value={groupQuery}
                      onChange={(e) => {
                        const val = e.target.value;
                        setGroupQuery(val);
                        setShowGroupDropdown(val.startsWith("@"));
                      }}
                      onFocus={() => {
                        if (groupQuery.startsWith("@")) setShowGroupDropdown(true);
                      }}
                    />
                    {showGroupDropdown && groupSuggestions.length > 0 && (
                      <ul className="absolute z-20 w-full bottom-full mb-1 max-h-48 overflow-auto rounded-xl border border-stone-200 bg-white shadow-lg">
                        {groupSuggestions.map((g) => (
                          <li
                            key={g.path}
                            className="cursor-pointer px-4 py-2 text-sm hover:bg-stone-50"
                            onClick={() => {
                              setGroupQuery(`@${g.path}`);
                              setShowGroupDropdown(false);
                            }}
                          >
                            <div className="font-medium text-stone-900">{g.name}</div>
                            <div className="text-xs text-stone-500">{g.path}</div>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                  <select
                    className="rounded-xl border border-stone-200 bg-stone-50 px-3 py-2 text-sm outline-none transition focus:border-amber-600"
                    value={newGroupRole}
                    onChange={(e) => setNewGroupRole(e.target.value as AreaRole)}
                  >
                    {AREA_ROLE_OPTIONS.map((r) => (
                      <option key={r} value={r}>{r}</option>
                    ))}
                  </select>
                  <button
                    type="button"
                    onClick={addGroup}
                    className="rounded-xl bg-stone-100 px-4 py-2 text-sm font-semibold text-stone-700 hover:bg-stone-200 transition"
                  >
                    新增
                  </button>
                </div>

                {/* Group List */}
                {groups.length > 0 && (
                  <div className="rounded-xl border border-stone-200 overflow-hidden">
                    <table className="w-full text-sm text-left">
                      <thead className="bg-stone-50 text-stone-500">
                        <tr>
                          <th className="px-4 py-2 font-medium">Group Path</th>
                          <th className="px-4 py-2 font-medium w-32">Role</th>
                          <th className="px-4 py-2 font-medium w-16 text-center">操作</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-stone-100">
                        {groups.map((g) => (
                          <tr key={g.group_path} className="hover:bg-stone-50/50">
                            <td className="px-4 py-2 text-stone-900 font-mono text-xs">{g.group_path}</td>
                            <td className="px-4 py-2 text-stone-600">{g.role}</td>
                            <td className="px-4 py-2 text-center">
                              <button
                                type="button"
                                onClick={() => removeGroup(g.group_path)}
                                className="text-red-500 hover:text-red-700"
                              >
                                移除
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </form>
          )}
        </div>

        <footer className="flex-shrink-0 pt-6 mt-2 border-t border-stone-100 flex items-center justify-between">
          <p className="text-xs text-stone-400">
            已加入: {users.length} 位使用者, {groups.length} 個群組
          </p>
          <div className="flex gap-3">
            <button
              type="button"
              onClick={onClose}
              className="rounded-full border border-stone-200 px-6 py-2 text-sm font-semibold text-stone-600 hover:bg-stone-50 transition"
            >
              取消
            </button>
            <button
              form="access-form"
              className="rounded-full bg-stone-900 px-8 py-2 text-sm font-semibold text-white transition hover:bg-stone-700 disabled:opacity-50"
              disabled={isSubmitting || isLoading}
              type="submit"
            >
              {isSubmitting ? "儲存中..." : "更新權限"}
            </button>
          </div>
        </footer>
      </div>
    </div>
  );
}
