# Keycloak 初始化資產

[English README](README.md)

## 模組目的

此目錄存放本機開發用的 Keycloak realm 自動匯入資產，讓第一次啟動 stack 時即可建立固定的身份測試資料。

## 啟動方式

- 在專案根目錄執行：

```bash
cp .env.example .env
docker compose -f infra/docker-compose.yml --env-file .env up --build
```

- `keycloak` 服務會在啟動時讀取 `/opt/keycloak/data/import` 下的 realm JSON。
- 目前單一入口部署下，Keycloak 對外會以 `https://<PUBLIC_HOST>/auth` 形式提供服務。
- compose runtime 會固定 `KC_HTTP_RELATIVE_PATH=/auth`，並從 `PUBLIC_BASE_URL` 推導公開 `/auth` URL，避免瀏覽器端 URL、issuer metadata 與 API JWT 驗證彼此不一致。
- 若你修改 `deep-agent-dev-realm.json` 後希望套用到既有本機環境，單純重啟既有 container 不會生效，必須先重置 Keycloak 的持久化資料。

## 環境變數

- `KEYCLOAK_REALM`
- `KEYCLOAK_CLIENT_ID`
- `KEYCLOAK_GROUPS_CLAIM`
- `PUBLIC_BASE_URL`
- `KEYCLOAK_EXPOSE_ADMIN`

## 主要目錄結構

- `deep-agent-dev-realm.json`：本機開發用 realm import 資產

## 預設身份資料

- realm：`deep-agent-dev`
- client：`deep-agent-web`
- groups claim：`groups`
- groups：
  - `/dept/hr`
  - `/dept/finance`
  - `/dept/rd`
  - `/platform/knowledge-admins`
- users：
  - `alice / alice123`：`/dept/hr`
  - `bob / bob123`：`/dept/finance`
  - `carol / carol123`：`/dept/rd`
  - `dave / dave123`：無群組，用於 deny-by-default 驗證
  - `erin / erin123`：`/dept/hr` + `/dept/rd`
  - `frank / frank123`：`/platform/knowledge-admins`

## Redirect 與 Origin 規則

- 瀏覽器看到的 Keycloak URL 必須使用 `/auth`
- 前端 callback URI 為 `<PUBLIC_BASE_URL>/auth/callback`
- silent SSO 使用 `<PUBLIC_BASE_URL>/silent-check-sso.html`
- realm client redirect URIs 必須明確允許 callback URI 與 silent SSO URI
- `webOrigins` 應允許公開 web origin `<PUBLIC_BASE_URL>`

## 群組設計原則

- Keycloak `group` 代表組織或職能身分，不直接等於 area 角色
- area 內的 `reader`、`maintainer`、`admin` 權限，應由 API 資料層將 `group path` 映射到對應角色
- 本機開發預設只提供少量部門群組，目的是驗證：
  - 同一群組可在不同 area 映射到不同角色
  - 多群組使用者會取 direct role 與 group role 的最大值
  - 無群組使用者仍會被 deny-by-default 擋下

## 對外介面

- `infra/docker-compose.yml` 會將本目錄下的 realm import JSON 掛載到 Keycloak import 目錄

## 疑難排解

- 若你修改了 `deep-agent-dev-realm.json`，要讓新的 realm 設定、使用者、mapper、redirect URIs 或 web origins 生效，必須先重置 Keycloak 的持久化資料。
- 若瀏覽器登入顯示 `invalid_redirect_uri`，請先檢查 realm client 是否已包含 `/auth/callback` 與 `/silent-check-sso.html`。
- 若前端 callback 顯示 access token 驗證失敗，請確認 `PUBLIC_BASE_URL` 正確，且 realm 的 issuer metadata 與 redirect URI 仍對齊同一個 `/auth` 公開入口。
- `KEYCLOAK_EXPOSE_ADMIN=false` 會刻意在 proxy 層封鎖 `/auth/admin*`；只有在明確需要遠端管理主控台時才應改成 `true`。
