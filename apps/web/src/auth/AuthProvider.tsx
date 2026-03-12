/** 前端 auth provider，封裝 Keycloak 與 test auth mode。 */

import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";

import { fetchAuthContext, registerAccessTokenGetter } from "../lib/api";
import { appConfig } from "../lib/config";
import type { AuthContextPayload, AuthSessionState } from "../lib/types";
import { getKeycloakClient, initializeKeycloak, resetKeycloakClient } from "./keycloak";
import { TEST_ROLE_TOKENS, type TestAuthRole } from "./testTokens";
import {
  clearTestPrincipal,
  clearTokenBundle,
  consumeReturnTo,
  readTestPrincipal,
  readTokenBundle,
  saveReturnTo,
  saveTestPrincipal,
  saveTokenBundle,
} from "./storage";


/** Auth context 對外提供的操作介面。 */
interface AuthContextValue extends AuthSessionState {
  error: string | null;
  login: (returnTo?: string) => Promise<void>;
  loginAsTestRole: (role: TestAuthRole) => Promise<void>;
  logout: () => Promise<void>;
  ensureFreshToken: () => Promise<string | null>;
  clearAuthError: () => void;
}


/** 全域 auth context。 */
const AuthContext = createContext<AuthContextValue | null>(null);


/** 在 test auth mode 解析測試 token 對應 principal。 */
function buildPrincipalFromTestToken(token: string): AuthContextPayload {
  const [, sub, rawGroups] = token.split("::", 3);
  const groups = rawGroups ? rawGroups.split(",").filter(Boolean) : [];
  return {
    sub,
    groups,
    authenticated: true,
  };
}


/** 提供整個 React app 使用的 auth provider。 */
export function AuthProvider(props: { children: ReactNode }): JSX.Element {
  const { children } = props;
  const navigate = useNavigate();
  const [state, setState] = useState<AuthSessionState>({
    isLoading: true,
    isAuthenticated: false,
    accessToken: null,
    principal: null,
  });
  const [error, setError] = useState<string | null>(null);
  const hasInitialized = useRef(false);

  useEffect(() => {
    registerAccessTokenGetter(async () => ensureFreshToken());
  });

  useEffect(() => {
    if (hasInitialized.current) {
      return;
    }
    hasInitialized.current = true;

    async function bootstrapAuth(): Promise<void> {
      try {
        if (appConfig.authMode === "test") {
          const storedTokens = readTokenBundle();
          const storedPrincipal = readTestPrincipal();
          if (storedTokens.accessToken && storedPrincipal) {
            setState({
              isLoading: false,
              isAuthenticated: true,
              accessToken: storedTokens.accessToken,
              principal: storedPrincipal,
            });
            return;
          }
          setState({
            isLoading: false,
            isAuthenticated: false,
            accessToken: null,
            principal: null,
          });
          return;
        }

        const storedTokens = readTokenBundle();
        const isCallbackRoute = window.location.pathname.startsWith("/auth/callback");
        if (!isCallbackRoute && !storedTokens.accessToken) {
          setState({
            isLoading: false,
            isAuthenticated: false,
            accessToken: null,
            principal: null,
          });
          return;
        }

        const keycloak = await initializeKeycloak();
        if (!keycloak.authenticated || !keycloak.token) {
          setState({
            isLoading: false,
            isAuthenticated: false,
            accessToken: null,
            principal: null,
          });
          return;
        }
        const principal = await fetchAuthContext();
        setState({
          isLoading: false,
          isAuthenticated: true,
          accessToken: keycloak.token,
          principal,
        });
      } catch (authError) {
        setError(authError instanceof Error ? authError.message : "登入初始化失敗。");
        setState({
          isLoading: false,
          isAuthenticated: false,
          accessToken: null,
          principal: null,
        });
      }
    }

    void bootstrapAuth();
  }, []);

  /** 嘗試刷新 access token，並回傳目前可用 token。 */
  async function ensureFreshToken(): Promise<string | null> {
    if (appConfig.authMode === "test") {
      return readTokenBundle().accessToken;
    }

    const keycloak = getKeycloakClient();
    if (!keycloak.authenticated || !keycloak.token) {
      return null;
    }
    try {
      await keycloak.updateToken(30);
      if (!keycloak.token) {
        return null;
      }
      saveTokenBundle({
        accessToken: keycloak.token,
        refreshToken: keycloak.refreshToken,
        idToken: keycloak.idToken,
      });
      return keycloak.token;
    } catch (refreshError) {
      clearTokenBundle();
      setState({
        isLoading: false,
        isAuthenticated: false,
        accessToken: null,
        principal: null,
      });
      setError(refreshError instanceof Error ? refreshError.message : "登入 session 已失效。");
      return null;
    }
  }

  /** 使用正式 Keycloak redirect flow 登入。 */
  async function login(returnTo = "/areas"): Promise<void> {
    saveReturnTo(returnTo);
    if (appConfig.authMode === "test") {
      navigate("/", { replace: true });
      return;
    }
    const keycloak = await initializeKeycloak();
    await keycloak.login({
      redirectUri: `${window.location.origin}/auth/callback`,
    });
  }

  /** 在 test auth mode 以固定角色登入。 */
  async function loginAsTestRole(role: TestAuthRole): Promise<void> {
    const token = TEST_ROLE_TOKENS[role];
    const principal = buildPrincipalFromTestToken(token);
    saveTokenBundle({ accessToken: token });
    saveTestPrincipal(principal);
    setState({
      isLoading: false,
      isAuthenticated: true,
      accessToken: token,
      principal,
    });
    const nextPath = consumeReturnTo() ?? "/areas";
    navigate(nextPath, { replace: true });
  }

  /** 清除 session，並在 keycloak mode 呼叫遠端 logout。 */
  async function logout(): Promise<void> {
    setError(null);
    const homepageUrl = `${window.location.origin}/`;
    clearTokenBundle();
    clearTestPrincipal();
    setState({
      isLoading: false,
      isAuthenticated: false,
      accessToken: null,
      principal: null,
    });

    if (appConfig.authMode === "test") {
      navigate("/", { replace: true });
      return;
    }

    const keycloak = getKeycloakClient();
    const logoutUrl = keycloak.createLogoutUrl({
      redirectUri: homepageUrl,
    });
    resetKeycloakClient();
    window.location.replace(logoutUrl);
  }

  /** 清除目前 auth 錯誤訊息。 */
  function clearAuthError(): void {
    setError(null);
  }

  /** callback 成功後在 provider 內重建 principal 與回跳。 */
  async function finalizeCallbackAuthentication(): Promise<void> {
    await initializeKeycloak();
    const token = await ensureFreshToken();
    if (!token) {
      throw new Error("找不到可用的 access token。");
    }
    const principal = await fetchAuthContext();
    setState({
      isLoading: false,
      isAuthenticated: true,
      accessToken: token,
      principal,
    });
    navigate(consumeReturnTo() ?? "/areas", { replace: true });
  }

  useEffect(() => {
    if (appConfig.authMode !== "keycloak") {
      return;
    }
    if (!window.location.pathname.startsWith("/auth/callback")) {
      return;
    }

    void finalizeCallbackAuthentication().catch((callbackError) => {
      setError(callbackError instanceof Error ? callbackError.message : "登入回跳處理失敗。");
      setState({
        isLoading: false,
        isAuthenticated: false,
        accessToken: null,
        principal: null,
      });
    });
  }, [navigate]);

  return (
    <AuthContext.Provider
      value={{
        ...state,
        error,
        login,
        loginAsTestRole,
        logout,
        ensureFreshToken,
        clearAuthError,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}


/** 讀取整個 React app 共用的 auth context。 */
export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth 必須在 AuthProvider 內使用。");
  }
  return context;
}
