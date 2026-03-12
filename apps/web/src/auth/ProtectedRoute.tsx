/** 受保護頁面入口；未登入時會觸發登入流程。 */

import { useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";

import { useAuth } from "./AuthProvider";


/** 保護需要登入才能操作的頁面。 */
export function ProtectedRoute(props: { children: JSX.Element }): JSX.Element {
  const { children } = props;
  const location = useLocation();
  const hasRequestedLogin = useRef(false);
  const { isAuthenticated, isLoading, login, error } = useAuth();

  useEffect(() => {
    if (isLoading || isAuthenticated || hasRequestedLogin.current) {
      return;
    }
    hasRequestedLogin.current = true;
    void login(`${location.pathname}${location.search}`);
  }, [isAuthenticated, isLoading, location.pathname, location.search, login]);

  if (isAuthenticated) {
    return children;
  }

  return (
    <main className="min-h-screen bg-stone-900 px-6 py-16 text-stone-100">
      <div className="mx-auto max-w-xl rounded-[2rem] border border-white/10 bg-white/10 p-8 backdrop-blur">
        <h1 className="text-3xl font-semibold tracking-tight">正在導向登入</h1>
        <p className="mt-4 text-sm leading-7 text-stone-300">
          此頁面需要已驗證身分。系統會將你導向 Keycloak，登入完成後再回到原本的頁面。
        </p>
        {error ? (
          <p className="mt-5 rounded-2xl border border-red-400/40 bg-red-500/10 px-4 py-3 text-sm text-red-200">
            {error}
          </p>
        ) : null}
      </div>
    </main>
  );
}
