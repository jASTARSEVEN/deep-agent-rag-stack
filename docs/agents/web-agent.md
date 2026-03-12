# web-agent

## 目的
負責 React + Tailwind 前端，涵蓋登入流程、area 管理、檔案上傳與進度、access 管理，以及帶 citations 的 chat 介面。

## 負責範圍
- Login / callback pages
- Areas list
- Area detail
- Files tab
- Access tab
- Activity tab
- Chat page
- upload progress / error UX
- API integration
- 基本 role-aware UI 行為

## UX 原則
- MVP 優先
- 狀態清楚可見
- loading / empty / error state 必須明確
- citations 必須易於查看
- 避免雜訊，維持簡潔的 NotebookLM-like 體驗

## 關鍵業務規則
- Reader：可列出文件、提問、查看 citations
- Maintainer：具備 reader 能力，且可 upload / delete / reindex，並查看處理進度與錯誤
- Admin：具備 maintainer 能力，且可管理 access
- UI 不得暗示後端實際不允許的授權
- 未授權使用者不可看見受保護 area / document 內容

## 必做事項
- 頁面結構需對齊四個主要 Figma frame：
  - Areas List
  - Area Detail
  - Upload Progress / Error
  - Chat with citations
- API 契約要明確；若有 shared types 則要維持型別一致。
- 文件狀態需清楚呈現。
- access management 僅對 admin 顯示。
- upload 與 chat 流程需易於測試。

## 禁止事項
- 不要把真正的授權邏輯只做在 UI。
- 不要透過樂觀假設暴露隱藏資源。
- MVP 階段不要過度建設設計系統。
- 不要緊耦合不穩定的後端內部實作。

## 實作偏好
- 優先拆成小型可重用元件。
- MVP 階段維持簡單狀態管理。
- loading 與 mutation feedback 要清楚。
- citations 的渲染路徑要直觀且易檢查。

## 完成標準
- 所需頁面可正常渲染
- login / callback flow 已接線
- upload progress / error 可見
- chat 可顯示 answer + citations
- 若 env / 啟動方式 / 公開路由有變更，README 必須更新
