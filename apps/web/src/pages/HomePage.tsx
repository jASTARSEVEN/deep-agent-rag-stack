/** 匿名首頁，提供產品說明與登入入口。 */

import { Link } from "react-router-dom";

import { useAuth } from "../auth/AuthProvider";
import { getTestRoleLabel, TEST_ROLE_TOKENS, type TestAuthRole } from "../auth/testTokens";
import { appConfig } from "../lib/config";


/** 匿名首頁。 */
export function HomePage(): JSX.Element {
  const { isAuthenticated, principal, login, loginAsTestRole, error, clearAuthError } = useAuth();

  const testRoles = Object.keys(TEST_ROLE_TOKENS) as TestAuthRole[];

  return (
    <main className="min-h-screen bg-[linear-gradient(180deg,_#f3ecdf_0%,_#e4dac4_48%,_#c8c0aa_100%)] text-stone-900">
      <div className="mx-auto flex max-w-6xl flex-col gap-8 px-6 py-10">
        <header className="rounded-[2rem] border border-stone-900/10 bg-[rgba(255,252,246,0.88)] p-8 shadow-[0_24px_80px_rgba(47,39,24,0.12)] backdrop-blur">
          <p className="text-sm font-semibold uppercase tracking-[0.32em] text-amber-700">Identity Gateway</p>
          <h1 className="mt-4 text-4xl font-semibold tracking-tight">{appConfig.appName}</h1>
          <p className="mt-4 max-w-3xl text-base leading-7 text-stone-700">
            使用 Keycloak 完成登入後，即可進入 Knowledge Area 管理與後續文件問答功能。匿名使用者可先查看產品說明，但進入受保護頁面時必須先完成登入。
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            {isAuthenticated ? (
              <Link
                className="rounded-full bg-stone-900 px-5 py-2 text-sm font-medium text-white transition hover:bg-stone-700"
                to="/areas"
              >
                前往 Areas
              </Link>
            ) : (
              <button
                className="rounded-full bg-stone-900 px-5 py-2 text-sm font-medium text-white transition hover:bg-stone-700"
                data-testid="login-button"
                type="button"
                onClick={() => void login("/areas")}
              >
                使用 Keycloak 登入
              </button>
            )}
            <a
              className="rounded-full border border-stone-900/10 bg-white/70 px-5 py-2 text-sm font-medium text-stone-900 transition hover:bg-white"
              href={appConfig.keycloakUrl}
              rel="noreferrer"
              target="_blank"
            >
              開啟 Keycloak
            </a>
          </div>
        </header>

        <section className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
          <article className="rounded-[1.75rem] border border-stone-900/10 bg-white/85 p-6 shadow-[0_18px_50px_rgba(47,39,24,0.08)]">
            <h2 className="text-xl font-semibold">登入後可做的事情</h2>
            <ul className="mt-5 space-y-3 text-sm leading-7 text-stone-700">
              <li>依 Keycloak groups 取得 Knowledge Area 存取權。</li>
              <li>在 Areas 頁列出目前可存取的區域並查看 effective role。</li>
              <li>`admin` 可管理 area access，`maintainer` 與 `reader` 僅可執行各自允許操作。</li>
            </ul>
          </article>

          <article className="rounded-[1.75rem] border border-stone-900/10 bg-[#201913] p-6 text-stone-100 shadow-[0_18px_50px_rgba(24,18,9,0.22)]">
            <h2 className="text-xl font-semibold">目前 Session</h2>
            <div className="mt-5 rounded-2xl bg-white/10 p-4 text-sm leading-7 text-stone-200">
              {isAuthenticated && principal ? (
                <>
                  <p className="font-medium text-white">sub: {principal.sub}</p>
                  <p>groups: {principal.groups.length > 0 ? principal.groups.join(", ") : "(無)"}</p>
                </>
              ) : (
                <p>目前尚未登入。</p>
              )}
            </div>

            {appConfig.authMode === "test" ? (
              <div className="mt-6">
                <p className="text-sm font-semibold uppercase tracking-[0.22em] text-stone-400">Playwright Test Auth</p>
                <div className="mt-4 flex flex-wrap gap-3">
                  {testRoles.map((role) => (
                    <button
                      key={role}
                      className="rounded-full border border-white/15 bg-white/10 px-4 py-2 text-sm font-medium transition hover:bg-white/20"
                      data-testid={`test-login-${role}`}
                      type="button"
                      onClick={() => void loginAsTestRole(role)}
                    >
                      以 {getTestRoleLabel(role)} 登入
                    </button>
                  ))}
                </div>
              </div>
            ) : null}

            {error ? (
              <div className="mt-6 rounded-2xl border border-red-400/40 bg-red-500/10 px-4 py-3 text-sm text-red-100">
                <p>{error}</p>
                <button
                  className="mt-3 rounded-full border border-red-200/30 px-4 py-1 text-xs font-medium"
                  type="button"
                  onClick={clearAuthError}
                >
                  關閉錯誤
                </button>
              </div>
            ) : null}
          </article>
        </section>
      </div>
    </main>
  );
}
