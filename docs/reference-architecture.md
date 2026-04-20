# 參考架構

## 文件目的

本文件提供外部專案快速理解與借鏡的現行參考架構。內容只描述目前主線設計，不追溯 phase 歷史，也不取代根目錄 `ARCHITECTURE.md`、`Summary.md`、`ROADMAP.md` 與 `PROJECT_STATUS.md`。

適合讀者：
- 想在自己的專案實作自架式文件問答平台的工程團隊
- 想理解本專案模組邊界、資料流與安全邊界的架構審查者
- 想判斷哪些能力是最小可複製核心、哪些能力可延後實作的技術負責人

## 架構總覽

本專案是一個 area-scoped 的文件問答平台。使用者登入後，只能在已授權的 Knowledge Area 內管理文件與提問。所有問答證據都必須來自 `ready` 文件，且 retrieval 結果在回到 agent 或前端前必須先通過 SQL gate。

主要模組：
- `apps/web`：React + Tailwind 一頁式 Dashboard，負責登入、Area 導覽、文件管理、chat 與 citations 顯示。
- `apps/api`：FastAPI 應用，負責 JWT 驗證、RBAC、SQL gate、REST API、retrieval runtime、LangGraph chat runtime 與 evaluation API。
- `apps/worker`：Celery worker，負責文件解析、chunk tree、embedding、synopsis 與 ingest 狀態轉換。
- `infra`：Docker Compose、Caddy、Supabase/PostgreSQL、Redis、MinIO、Keycloak 與啟動設定。
- `benchmarks` / `app.evaluation`：retrieval 與 summary/compare benchmark，不屬於使用者正式問答路徑，但用來驗證品質與避免 regression。

## 最小可複製核心

其他專案若只想複製核心架構，建議先保留以下能力：
- Keycloak JWT 驗證，並穩定取得 `sub` 與 `groups` claims。
- Area-based RBAC，角色包含 `reader`、`maintainer`、`admin`。
- SQL 層 effective role gate，無有效角色時維持 deny-by-default。
- 文件生命週期：`uploaded -> processing -> ready | failed`。
- 只有 `status = ready` 的文件可進入 retrieval、chat、preview 與 evaluation。
- Parent-child chunk tree，child chunk 作為 recall 最小單位，parent 作為 assembly 邊界。
- Hybrid recall：vector recall + PGroonga FTS recall。
- Python 層 RRF、rerank、selection 與 assembler。
- 單一 agent tool：`retrieve_area_contexts`，避免 agent 直接碰 vector、FTS、rerank 或 raw document id。
- Contract 產生與檢查：REST OpenAPI、chat runtime schema、前端 generated types。

可延後實作的能力：
- 外部 benchmark package curation。
- summary/compare benchmark offline judge workflow。
- document synopsis 與 section synopsis 的進階 planning hint。
- Playwright smoke 覆蓋所有公開部署路徑。
- 多 provider embedding / rerank 的完整矩陣。

## 使用者請求流程

正式使用者流程如下：

1. 使用者進入 Web。
2. Web 導向 Keycloak 登入。
3. Keycloak callback 回 Web，Web 取得 access token。
4. Web 呼叫 API `GET /auth/context` 驗證 session。
5. 使用者選擇或建立 Knowledge Area。
6. Web 只呈現 API 回傳中使用者有權限的 Areas。
7. 使用者在 Area 內上傳文件、管理權限、提問或查看 citations。

關鍵原則：
- 前端只做保守呈現，不承擔真正授權。
- 所有受保護資料都必須由 API service 層做 SQL access check。
- 未授權與不存在資源應盡量維持 same-404，避免暴露資源存在性。

## 文件上傳與索引流程

文件 ingest 主線如下：

1. Web 上傳單一檔案到 `POST /areas/{area_id}/documents`。
2. API 驗證使用者至少為 area `maintainer`。
3. API 將原始檔寫入 MinIO 或 filesystem storage。
4. API 建立 `documents` 與 `ingest_jobs`，文件狀態為 `uploaded`，job 狀態為 `queued`。
5. API 派送 Celery task。
6. Worker 將 document/job 標記為 `processing`。
7. Worker 優先嘗試重用 parse artifacts；若不可重用則重新 parse。
8. Parser 輸出 block-aware `ParsedDocument`。
9. Chunker 建立 parent-child chunk tree 與 `display_text`。
10. Worker replace-all 寫入 `document_chunks`。
11. Worker 產生 child embeddings，必要時產生 document synopsis。
12. Worker 成功後才將 document 標為 `ready`；失敗時標為 `failed` 並清掉可檢索 chunks。

核心 contract：
- `ParsedDocument` 是 parser 與 chunker 的邊界。
- `ChunkDraft` 是 chunker 與資料庫寫入的邊界。
- `documents.display_text` 是全文 preview 與 citation offset 的基準。
- `document_chunks` 必須保留 SQL-first 欄位，不把重要查詢欄位藏在半結構 metadata。

## Retrieval 與 Chat 流程

目前正式問答主線如下：

1. Web 透過 LangGraph SDK thread/run 送出 area-scoped 問題。
2. LangGraph custom auth 驗證 Bearer token，並注入 `sub/groups`。
3. Deep Agents 主 agent 判斷是否呼叫單一 `retrieve_area_contexts` tool。
4. Tool 載入已授權且 ready 的文件集合。
5. 後端解析 document mention 與安全 document handles。
6. Routing 判斷 `fact_lookup`、`document_summary` 或 `cross_document_compare`。
7. Recall 只在 SQL gate 後的 ready 文件中執行 child hybrid recall。
8. Python 層執行 RRF、minimal ranking policy、parent-level rerank 與 scope-aware selection。
9. Assembler 以 parent 為 materialization 邊界，產生送入 LLM 的 assembled contexts。
10. Agent 使用 assembled contexts 回答，並以 `[[C1]]` 類 citation marker 連回 evidence。
11. Graph state 持久化 answer blocks、citations、assembled contexts 與 trace。
12. Web 顯示回答、citation chips、工具呼叫狀態與右側全文 preview。

安全邊界：
- Public chat 不接受 raw `document_id` override。
- Agent 不可直接呼叫 vector recall、FTS recall、rerank 或 assembler。
- `document_summary` 與 `cross_document_compare` 仍必須以 citation-ready assembled evidence 作為回答依據。
- Synopsis 只能作為 planning / orientation hint，不可替代 citation-ready evidence。

## Evaluation 與 Benchmark 邊界

Evaluation 是品質治理路徑，不是產品問答路徑。

正式邊界：
- `app.evaluation.retrieval` 可以直接串接 retrieval stage，用於候選預覽與 benchmark。
- `app.evaluation.summary_compare` 應透過 chat runtime contract 取得 answer、citations 與 trace。
- 產品 retrieval/chat runtime 不得反向依賴 evaluation package。
- Benchmark 可使用指定文件 scope，但這是 dataset contract，不得開放給 public chat。

設計目的：
- 用 retrieval-only benchmark 檢查 recall/rerank/assembled contexts 是否找對證據。
- 用 summary/compare checkpoint 檢查 unified Deep Agents answer path 是否滿足 citation 與 coverage contract。
- 用 baseline compare 避免為單一資料集過度調參。

## 部署模型

正式自架模型採單一公開入口：
- Caddy 對外提供 `80/443`。
- `/` 路由到 Web。
- `/api/*` 路由到 API。
- `/auth/*` 路由到 Keycloak。
- PostgreSQL/Supabase、Redis、MinIO、worker 與內部服務不直接作為客戶端入口。

資料庫升級由 Alembic migration runner 統一處理：
- compose 環境使用 `python -m app.db.migration_runner`。
- fresh database 與既有 database 都走同一路徑。

## 架構取捨

本專案刻意選擇：
- 用 area-level ACL，而不是 document-level ACL，降低 MVP 複雜度。
- 用 SQL gate 作為主要保護模型，而不是記憶體過濾。
- 用 PGroonga 而不是 `pg_trgm`，符合繁體中文檢索需求與產品邊界。
- 用 Python 層保留 RRF、rerank、selection 與 assembler，避免把快速演進策略鎖死在 SQL function。
- 用單一 retrieval tool 暴露給 agent，避免 agent 拆開呼叫底層檢索元件造成不可控行為。
- 用 generated frontend types 管控 contract drift，避免前後端各自猜 payload shape。

## 外部專案落地建議

若要在其他專案採用此架構，建議按以下順序移植：

1. 先實作 `sub/groups`、area roles 與 SQL gate。
2. 再實作 document lifecycle 與 ready-only。
3. 接著建立 parent-child chunk tree 與 preview offset contract。
4. 再加入 hybrid recall、RRF、rerank 與 assembler。
5. 最後接 agent runtime 與 citations UI。
6. 等正式流程穩定後，再加入 benchmark / evaluation / summary compare。

