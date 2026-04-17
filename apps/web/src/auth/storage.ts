/** 前端 auth session 持久化所需的 sessionStorage 輔助函式。 */

import type { AuthContextPayload } from "../generated/rest";


/** access token 在 sessionStorage 使用的 key。 */
const ACCESS_TOKEN_KEY = "deep-agent-auth-access-token";

/** refresh token 在 sessionStorage 使用的 key。 */
const REFRESH_TOKEN_KEY = "deep-agent-auth-refresh-token";

/** id token 在 sessionStorage 使用的 key。 */
const ID_TOKEN_KEY = "deep-agent-auth-id-token";

/** callback 後回跳目標在 sessionStorage 使用的 key。 */
const RETURN_TO_KEY = "deep-agent-auth-return-to";

/** test mode principal 在 sessionStorage 使用的 key。 */
const TEST_PRINCIPAL_KEY = "deep-agent-auth-test-principal";


/** 儲存 bearer token 組合。 */
export function saveTokenBundle(tokens: {
  accessToken: string;
  refreshToken?: string | null;
  idToken?: string | null;
}): void {
  sessionStorage.setItem(ACCESS_TOKEN_KEY, tokens.accessToken);
  if (tokens.refreshToken) {
    sessionStorage.setItem(REFRESH_TOKEN_KEY, tokens.refreshToken);
  } else {
    sessionStorage.removeItem(REFRESH_TOKEN_KEY);
  }
  if (tokens.idToken) {
    sessionStorage.setItem(ID_TOKEN_KEY, tokens.idToken);
  } else {
    sessionStorage.removeItem(ID_TOKEN_KEY);
  }
}


/** 讀取目前 token bundle。 */
export function readTokenBundle(): { accessToken: string | null; refreshToken: string | null; idToken: string | null } {
  return {
    accessToken: sessionStorage.getItem(ACCESS_TOKEN_KEY),
    refreshToken: sessionStorage.getItem(REFRESH_TOKEN_KEY),
    idToken: sessionStorage.getItem(ID_TOKEN_KEY),
  };
}


/** 清除目前 token bundle。 */
export function clearTokenBundle(): void {
  sessionStorage.removeItem(ACCESS_TOKEN_KEY);
  sessionStorage.removeItem(REFRESH_TOKEN_KEY);
  sessionStorage.removeItem(ID_TOKEN_KEY);
}


/** 暫存登入後回跳目標。 */
export function saveReturnTo(pathname: string): void {
  sessionStorage.setItem(RETURN_TO_KEY, pathname);
}


/** 讀取並移除登入後回跳目標。 */
export function consumeReturnTo(): string | null {
  const value = sessionStorage.getItem(RETURN_TO_KEY);
  sessionStorage.removeItem(RETURN_TO_KEY);
  return value;
}


/** 儲存 test mode principal。 */
export function saveTestPrincipal(principal: AuthContextPayload): void {
  sessionStorage.setItem(TEST_PRINCIPAL_KEY, JSON.stringify(principal));
}


/** 讀取 test mode principal。 */
export function readTestPrincipal(): AuthContextPayload | null {
  const rawValue = sessionStorage.getItem(TEST_PRINCIPAL_KEY);
  if (!rawValue) {
    return null;
  }
  try {
    return JSON.parse(rawValue) as AuthContextPayload;
  } catch {
    sessionStorage.removeItem(TEST_PRINCIPAL_KEY);
    return null;
  }
}


/** 清除 test mode principal。 */
export function clearTestPrincipal(): void {
  sessionStorage.removeItem(TEST_PRINCIPAL_KEY);
}
