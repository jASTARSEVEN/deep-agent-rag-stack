# Keycloak 初始化預留目錄

## 模組目的

此目錄預留給未來 Keycloak realm、client、mapper 初始化資產使用。

## 啟動方式

- 本輪尚未實作自動匯入。
- stack 啟動後，請透過 Keycloak 管理介面手動設定 realm 與 client。

## 環境變數

- `KEYCLOAK_REALM`
- `KEYCLOAK_CLIENT_ID`
- `KEYCLOAK_GROUPS_CLAIM`

## 主要目錄結構

- 後續可在此加入 realm export、import JSON 或 setup script。

## 對外介面

- 本輪無。

## 疑難排解

- 後續 JWT auth 實作會假設 access token 中存在穩定的 `groups` claim。
