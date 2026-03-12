# Keycloak 初始化資產

## 模組目的

此目錄存放本機開發用的 Keycloak realm 自動匯入資產，讓第一次啟動 stack 時即可建立固定的身份測試資料。

## 啟動方式

- 在專案根目錄執行：

```bash
cp .env.example .env
docker compose -f infra/docker-compose.yml --env-file .env up --build
```

- `keycloak` 服務會在啟動時讀取 `/opt/keycloak/data/import` 下的 realm JSON。
- 若 `keycloak-db` volume 是全新狀態，Keycloak 會建立 `deep-agent-dev` realm 與預設身份資料。
- 若 `keycloak-db` volume 已存在，日常重啟不會覆蓋已存在的 realm 內容。

## 環境變數

- `KEYCLOAK_REALM`
- `KEYCLOAK_CLIENT_ID`
- `KEYCLOAK_GROUPS_CLAIM`

## 主要目錄結構

- `deep-agent-dev-realm.json`：本機開發用 realm import 資產

## 預設身份資料

- realm：`deep-agent-dev`
- client：`deep-agent-web`
- groups claim：`groups`
- groups：
  - `/reader`
  - `/maintainer`
  - `/admin`
- users：
  - `alice / alice123`：`/reader`
  - `bob / bob123`：`/maintainer`
  - `carol / carol123`：`/admin`
  - `dave / dave123`：無群組，用於 deny-by-default 驗證
  - `erin / erin123`：`/reader` + `/maintainer`

## 對外介面

- `infra/docker-compose.yml` 會將本目錄下的 realm import JSON 掛載到 Keycloak import 目錄。

## 疑難排解

- 若你已經手動建立過其他 realm 或修改過 `deep-agent-dev`，日常重啟不會回到預設資料。
- 若要重建預設身份資料，請先刪除 `keycloak-db` volume 再重新啟動：

```bash
docker compose -f infra/docker-compose.yml --env-file .env down -v
docker compose -f infra/docker-compose.yml --env-file .env up --build
```

- API JWT 驗證目前假設 access token 中存在穩定的 `groups` claim。若 token 內缺少 `groups`，請先確認 `deep-agent-dev-realm.json` 內的 `groups` protocol mapper 未被移除。
