# AGENTS.md

此模組負責 React + Tailwind 前端。

## 聚焦範圍
- login / callback
- areas pages
- files / access / activity tabs
- upload progress / error
- chat with citations

## 關鍵規則
- 不要把真正授權只做在 UI
- 角色敏感操作要保守呈現
- MVP 以簡潔清楚為優先

## 測試與 E2E 規則
- 前端重大使用流程完成後，應優先補上 Playwright E2E。
- E2E 應優先覆蓋 login、areas、access、upload、chat 等使用者實際操作路徑。
- selector 優先使用可存取名稱、label、role；只有在不穩定或難以辨識時才補 `data-testid`。
- 前端 E2E 只能驗證 UI 與流程，不可取代 API / SQL gate / deny-by-default 的後端授權驗證。
- 若 E2E 採用 test mode、fake token、mock API 或 SQLite，必須明確註記其不能代表真實 Keycloak / Compose runtime 驗證。
- 若前端流程依賴新 env、dev server 啟動方式或測試腳本，必須同步更新 `README.md`。
