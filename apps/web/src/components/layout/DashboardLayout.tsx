import React, { type ReactNode } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../../auth/AuthProvider";
import { appConfig } from "../../lib/config";

/**
 * DashboardLayout 元件。
 * 提供側邊欄、頂部 Header 以及主內容區域的佈局骨架。
 * 
 * @param children 主要內容區顯示的元素。
 * @param sidebar 側邊欄區域顯示的元素。
 * @param headerActions 頂部 Header 右側顯示的額外操作。
 */
interface DashboardLayoutProps {
  children: ReactNode;
  sidebar?: ReactNode;
  headerActions?: ReactNode;
}

export function DashboardLayout({ children, sidebar, headerActions }: DashboardLayoutProps): JSX.Element {
  const { principal, logout } = useAuth();

  return (
    <div className="flex h-screen w-full overflow-hidden bg-[linear-gradient(180deg,_#f4efe4_0%,_#e6dfcf_46%,_#d4d0be_100%)] text-stone-900">
      {/* Sidebar - 左側固定邊欄 */}
      {sidebar && (
        <aside className="flex w-80 flex-col border-r border-stone-900/10 bg-white/40 shadow-xl backdrop-blur-sm">
          <div className="flex h-20 items-center border-b border-stone-900/5 px-6">
            <Link to="/" className="flex items-center gap-3">
              <div className="h-8 w-8 rounded-lg bg-amber-600 shadow-lg shadow-amber-600/20" />
              <h1 className="text-lg font-bold tracking-tight text-stone-900">{appConfig.appName}</h1>
            </Link>
          </div>
          <div className="flex-1 overflow-y-auto">
            {sidebar}
          </div>
        </aside>
      )}

      {/* Main Content Area - 右側主內容區 */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Header - 頂部標題與工具列 */}
        <header className="flex h-20 shrink-0 items-center justify-between border-b border-stone-900/10 bg-white/60 px-8 backdrop-blur-md">
          <div className="flex items-center gap-4">
            <p className="text-sm font-semibold uppercase tracking-[0.32em] text-amber-700">Protected Workspace</p>
          </div>
          
          <div className="flex items-center gap-6">
            {/* Header 擴充操作 (例如 Documents 管理按鈕) */}
            {headerActions}
            
            <div className="flex items-center gap-4 border-l border-stone-900/10 pl-6">
              <div className="text-right" data-testid="auth-context-panel">
                <p className="text-sm font-semibold text-stone-900">
                  {principal?.name && principal?.preferred_username
                    ? `${principal.name} (${principal.preferred_username})`
                    : `sub: ${principal?.sub ?? "unknown-user"}`}
                </p>
                <p className="text-[10px] font-mono text-stone-500 uppercase">
                  groups: {principal?.groups?.join(", ") || "no-group"}
                </p>
              </div>
              <button 
                onClick={() => void logout()}
                className="rounded-full bg-stone-900 px-5 py-1.5 text-xs font-semibold text-white transition hover:bg-stone-700"
                type="button"
              >
                登出
              </button>
            </div>
          </div>
        </header>

        {/* Main View Area */}
        <main className="flex flex-1 flex-col overflow-hidden p-8 relative">
          {children}
        </main>
      </div>
    </div>
  );
}
