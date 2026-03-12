/** Keycloak client 初始化與 token lifecycle 輔助函式。 */

import Keycloak from "keycloak-js";

import { appConfig } from "../lib/config";
import { clearTokenBundle, readTokenBundle, saveTokenBundle } from "./storage";


/** 單例 Keycloak client，避免重複初始化。 */
let keycloakClient: Keycloak | null = null;

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
      pkceMethod: "S256",
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
