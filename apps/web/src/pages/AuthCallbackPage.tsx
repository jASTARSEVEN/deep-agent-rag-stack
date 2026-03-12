/** Keycloak callback 頁面。 */

import { Link } from "react-router-dom";

import { useAuth } from "../auth/AuthProvider";


/** 顯示 callback 處理中的頁面。 */
export function AuthCallbackPage(): JSX.Element {
  const { isLoading, error } = useAuth();

  return (
    <main className="min-h-screen bg-stone-900 px-6 py-16 text-stone-100">
      <div className="mx-auto max-w-xl rounded-[2rem] border border-white/10 bg-white/10 p-8 backdrop-blur">
        <h1 className="text-3xl font-semibold tracking-tight">正在完成登入</h1>
        <p className="mt-4 text-sm leading-7 text-stone-300">
          系統正在處理 Keycloak callback，完成後會自動導回你要前往的頁面。
        </p>
        {isLoading ? <p className="mt-6 text-sm text-amber-300">處理中...</p> : null}
        {error ? (
          <div className="mt-6 rounded-2xl border border-red-400/40 bg-red-500/10 px-4 py-3 text-sm text-red-100">
            <p>{error}</p>
            <Link className="mt-3 inline-block text-sm underline" to="/">
              回到首頁重新登入
            </Link>
          </div>
        ) : null}
      </div>
    </main>
  );
}
