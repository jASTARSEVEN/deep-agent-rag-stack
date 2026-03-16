# Deep Agent RAG Stack

![權限管理介面測試](access-modal-test.png)
![實際畫面預覽](actual-dashboard-live.png)

具備 OAuth2 認證、RBAC 與多策略檢索設計的企業知識助理雛形。

[English README](README.md)

## 模組目的

此倉庫是一個以可自架、NotebookLM 風格企業知識聊天應用為主題的工程實作專案，並作為多 agent 協作開發流程的實驗性雛形。其開發過程採用 multi-agent collaboration 進行任務拆分與實作協作。專案聚焦在真實企業場景常見的系統問題，包括文件上傳與背景處理、`RAG` 多策略搜尋、`Keycloak` OAuth2 認證整合、以群組與角色為核心的 `RBAC` 授權模型，以及對 Knowledge Area 與文件資源採取 `deny-by-default` 的存取控制設計。

這裡提到的多 Agents 指的是開發過程中的任務拆分、角色分工與協作模式，而不是產品對外提供的功能。這個專案的目的，不只是做出聊天介面，而是整理出一套可延伸到企業等級應用場景的知識系統架構，驗證從 auth、資料邊界、背景工作到檢索策略的整體落地能力。

## Why This Project

企業在導入知識聊天應用時，真正的難點通常不只是接上 LLM，而是如何讓內部文件能被安全地整理、授權、索引與檢索，並在可控成本下提供可信的回答品質。這個專案聚焦的正是這些落地問題，目標是驗證一套更接近真實企業需求的知識系統雛形。

## 未來展望

這個專案未來不只會停留在文件問答，而是希望進一步結合 `Deep Agents` 能力，讓系統從「回答問題」走向「能理解上下文、可調用工具、可執行任務」的真正助理。下一步的願景包括接上 `MCP`、整合可重用的 `Skill`、擴充多步驟任務協作與外部系統操作能力，讓知識系統不只是提供資訊，而是能進一步參與企業流程、協助決策與實際完成工作。

## What Makes This Project Different

相較於常見只聚焦在聊天介面或單一路徑向量檢索的 RAG demo，這個專案從一開始就把企業場景中更關鍵的問題放進核心設計，包括 `Keycloak` 群組式授權、`deny-by-default`、`ready-only` 文件生命週期控制，以及規劃中的 `SQL gate + vector recall + FTS recall + RRF + rerank` 多策略搜尋流程。目標不是只做出能回答問題的系統，而是做出一個更接近企業實際可採用條件的知識助理基礎架構。

## 工程亮點

- 以 `Keycloak groups` 與 direct role 合併計算 effective role，落實 area-level `RBAC`
- 在資料存取層維持 `deny-by-default`，並用一致的未授權 `404` 避免暴露受保護資源存在性
- 將文件生命週期拆為 `uploaded -> processing -> ready|failed`，避免未完成資料進入檢索
- 已實作 `SQL gate + vector recall + FTS recall + RRF + rerank + assembled-context citations` 的聊天檢索基礎
- 以 `Deep Agents` 作為正式 chat 核心，並以 `LangGraph Server` 內建 `thread/run` 作為 runtime 與 streaming 承載層
- 以 `FastAPI + PostgreSQL + Celery + Redis + MinIO + React` 建立可本機重現的完整垂直切片

## 我主導的內容

- 專案需求收斂、模組拆分與 phase-by-phase 實作順序規劃
- 認證授權設計，包括 JWT claims、group-based access 與 area access management
- API、worker、web 與 Docker Compose 的本機整合
- 文件 upload / ingest 狀態流、測試策略與 E2E 驗證基礎
- README、架構文件與專案長期文件的整理與維護

## 目前已完成

目前專案處於 `Phase 5.1 — Chat MVP on LangGraph Server`。在下班後與零碎閒暇時間進行的 multi-agent 協作開發中，到了第二天，整個倉庫已從原本的 auth / upload / retrieval foundation 進一步推進到可運作的 `Deep Agents + LangGraph Server` area-scoped chat 垂直切片。

- Monorepo、Docker Compose 與本機開發環境骨架
- `FastAPI` API、`Celery` worker、`React + Tailwind` Web 應用基本串接
- `Keycloak` OAuth2 登入流程、JWT claims 解析與 auth context 驗證
- 以使用者角色與群組角色整合的 area-level `RBAC`
- `deny-by-default` 的 area / document 存存控制與未授權 `404` 保護
- **友善的權限管理介面**：整合 `@` 關鍵字觸發使用者與群組的自動完成功能 (Autocomplete)，並統一以 `username` 進行識別與顯示，提供更直覺的操作體驗。
- Knowledge Area 的 create / list / detail / access management MVP

- 文件上傳、物件儲存、ingest job 建立與 `uploaded -> processing -> ready|failed` 狀態轉換
- 已建立 SQL-first 的 `parent -> child` chunk tree，並以 `structure_kind=text|table` 支援 `TXT`、`Markdown` 與表格感知 `HTML`
- 採 hybrid chunking：保留 custom parent section，文字 child 使用 LangChain，表格則採整表保留 / row-group split
- ready-only retrieval foundation，涵蓋 SQL gate、vector recall、FTS recall、`RRF`、rerank 與 table-aware context assembly
- 正式以 `Deep Agents` 主 agent 加上單一 `retrieve_area_contexts` tool 執行 chat
- `LangGraph Server` 內建 `thread/run` runtime、custom auth principal 注入與 Web streaming
- 已實作一頁式戰情室 (Dashboard)，整合左側區域導覽、中央即時對話、右側文件管理抽屜與彈窗式權限設定，提供流暢的 RAG 操作體驗

## 目前尚未完成

- area rename / delete 等管理補強功能
- 真實 `Keycloak + LangGraph + Deep Agents` compose smoke 的更完整覆蓋
- tool failure、no-context answers 與 streaming edge cases 的更多整合驗證
- 未來 `Deep Agents` 擴充點，例如 sub-agents、`MCP` 與可重用 `Skill`

## TODO / 未來補充

- 補上系統架構圖，清楚呈現 Web、API、Worker、DB、MinIO、Keycloak 與 retrieval flow 的關係
- 補上 E2E demo，展示從登入、上傳、處理到文件存取驗證的完整主流程
- 補上測試覆蓋重點，整理授權、狀態轉換、API 邊界與 E2E 驗證範圍
- 補上權限邊界案例，說明不同角色與群組在 area / document / chat 的實際存取差異
- 補上失敗處理流程，整理 upload、ingest、未支援格式與授權失敗時的系統行為

## 授權

本專案採用 `Apache-2.0` 授權，完整條款請參考根目錄的 `LICENSE`。

## 聯絡方式

- 維護者：卓品至
- Email：`easypinex@gmail.com`

## 倉庫結構

- `apps/api`：FastAPI API、JWT 驗證、RBAC、internal retrieval services、`app/chat` Deep Agents domain 與 LangGraph loader/runtime glue
- `apps/worker`：Celery 背景工作、文件 ingest 與狀態轉換流程
- `apps/web`：React + Tailwind 前端、登入流程、一頁式 Dashboard 戰情室 (整合區域導覽、對話中心與文件抽屜)
- `infra`：Docker Compose 與容器建置資產
- `packages/shared`：共用型別與設定的預留模組

## 啟動方式

1. 複製環境變數檔：
   - `cp .env.example .env`
2. 可選的本機 Python 依賴安裝：
   - `python -m venv .venv && source .venv/bin/activate`
   - `pip install -e ./apps/api -e ./apps/worker`
3. 建置並啟動本機 stack：
   - `docker compose -f infra/docker-compose.yml --env-file .env up --build`
4. 開啟本機服務：
   - Web: `http://localhost:13000`
   - API: `http://localhost:18000`
   - API health: `http://localhost:18000/health`
   - Keycloak: `http://localhost:18080`
   - MinIO API: `http://localhost:19000`
   - MinIO Console: `http://localhost:19001`

## 環境變數

完整本機預設值請參考 `.env.example`。範本已依參數類型補上分段的中英雙語註解。

## 驗證方式

- API health：
  - `curl http://localhost:18000/health`
- Auth context：
  - `curl -H "Authorization: Bearer <access-token>" http://localhost:18000/auth/context`
- LangGraph chat runtime：
  - `cd apps/api && langgraph dev --config langgraph.json --host 0.0.0.0 --port 18000 --no-browser`
- Worker ping task：
  - `docker compose -f infra/docker-compose.yml exec worker python -m worker.scripts.healthcheck`
- Web / Areas / Files / Chat：
  - 開啟 `http://localhost:13000`，登入後進入一頁式 Dashboard，驗證區域切換、對話串流、點擊右上角按鈕開啟文件抽屜並進行管理
- Phase 1 auth 驗證手冊：
  - `docs/phase1-auth-verification.md`

## 疑難排解

- 若 Docker 映像建置失敗，請確認 Docker Desktop 正在執行，且能存取套件來源。
- 若 Keycloak 啟動較慢，請等到 `keycloak` health check 通過後再開啟 UI。
- 若 web 無法連到 API，請確認 `.env` 中的 `VITE_API_BASE_URL`。
