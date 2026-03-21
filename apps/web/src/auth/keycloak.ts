/** Keycloak client 初始化與 token lifecycle 輔助函式。 */

import Keycloak from "keycloak-js";

import { appConfig } from "../lib/config";
import { clearTokenBundle, readTokenBundle, saveTokenBundle } from "./storage";


/** 單例 Keycloak client，避免重複初始化。 */
let keycloakClient: Keycloak | null = null;
/**
 * 判斷目前瀏覽器環境是否可提供 PKCE 所需的 Web Crypto API。
 *
 * @returns 若目前執行環境可安全使用 `window.crypto.subtle` 則回傳 `true`；否則回傳 `false`。
 */
function isWebCryptoAvailable(): boolean {
  return (
    window.isSecureContext &&
    typeof window.crypto !== "undefined" &&
    typeof window.crypto.subtle !== "undefined"
  );
}

/**
 * 根據瀏覽器能力決定是否啟用 Keycloak PKCE 流程。
 *
 * @returns 若可使用 Web Crypto API 則回傳 `S256`；否則回傳 `false` 以停用 PKCE。
 */
function resolvePkceMethod(): "S256" | false {
  if (isWebCryptoAvailable()) {
    return "S256";
  }

  console.warn(
    "Web Crypto API is unavailable; falling back to Keycloak without PKCE. " +
      "Use https:// or http://localhost during development to keep PKCE enabled.",
  );
  return false;
}

/** 單例初始化 promise，避免 callback 與 app bootstrap 並發重複 init。 */
let keycloakInitializationPromise: Promise<Keycloak> | null = null;


/** 取得共用 Keycloak client。 */
export function getKeycloakClient(): Keycloak {
  if (!keycloakClient) {
    keycloakClient = new Keycloak({
      url: appConfig.keycloakUrl,
      realm: appConfig.keycloakRealm,
      clientId: appConfig.keycloakClientId,
    });
  }
  return keycloakClient;
}


/** 初始化 Keycloak client，並嘗試從 sessionStorage 恢復 token。 */
export async function initializeKeycloak(): Promise<Keycloak> {
  if (keycloakInitializationPromise) {
    return keycloakInitializationPromise;
  }

  const keycloak = getKeycloakClient();
  const storedTokens = readTokenBundle();

  keycloakInitializationPromise = (async () => {
    await keycloak.init({
      onLoad: "check-sso",
      pkceMethod: resolvePkceMethod(),
      responseMode: "query",
      checkLoginIframe: false,
      silentCheckSsoRedirectUri: `${window.location.origin}/silent-check-sso.html`,
      token: storedTokens.accessToken ?? undefined,
      refreshToken: storedTokens.refreshToken ?? undefined,
      idToken: storedTokens.idToken ?? undefined,
    });

    if (keycloak.authenticated && keycloak.token) {
      saveTokenBundle({
        accessToken: keycloak.token,
        refreshToken: keycloak.refreshToken,
        idToken: keycloak.idToken,
      });
    } else {
      clearTokenBundle();
    }

    keycloak.onAuthRefreshSuccess = () => {
      if (!keycloak.token) {
        clearTokenBundle();
        return;
      }
      saveTokenBundle({
        accessToken: keycloak.token,
        refreshToken: keycloak.refreshToken,
        idToken: keycloak.idToken,
      });
    };

    keycloak.onAuthLogout = () => {
      clearTokenBundle();
    };

    return keycloak;
  })();

  try {
    return await keycloakInitializationPromise;
  } catch (error) {
    keycloakInitializationPromise = null;
    throw error;
  }
}


/** 清除前端記憶中的 Keycloak client/init 狀態。 */
export function resetKeycloakClient(): void {
  keycloakInitializationPromise = null;
  keycloakClient = null;
}
