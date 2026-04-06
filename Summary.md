# 產品背景與需求總覽

## 文件定位

此文件用來說明本專案的產品背景、需求範圍、核心業務規則與固定技術選型。  
此文件**不負責記錄目前開發進度、當前 phase、下一步任務**。

若要掌握專案現況，請改讀：
- `PROJECT_STATUS.md`：目前做到哪
- `ROADMAP.md`：階段與里程碑順序
- `ARCHITECTURE.md`：系統設計與資料流

## 產品目標

建立一個可自架的 NotebookLM 風格文件問答平台，功能收斂為：
1. 使用者登入
2. 建立 Knowledge Area
3. 上傳檔案
4. 背景索引處理
5. 在授權範圍內進行問答並查看引用來源

此專案的核心特徵不是做出功能很多的 NotebookLM 替代品，而是：
- 只支援「上傳檔案」作為知識來源
- 強調企業內部可自架
- 強調文件授權、群組認證與存取範圍控制

## 固定技術棧

- 後端：`Python + FastAPI`
- 資料庫：`PostgreSQL + pgvector + PGroonga (Supabase)`
- 背景工作：`Celery + Redis`
- 物件儲存：`MinIO`
- 身分與授權：`Keycloak`
- 前端：`React + Tailwind`
- 檢索與流程編排：`LangChain loaders`、`LangChain text splitters`、`LangGraph`
- PDF 解析：`OpenDataLoader PDF`、`Unstructured partition_pdf`、`LlamaParse SaaS (optional)`
- Office 文件解析：`Unstructured partition_docx`、`partition_pptx`、`partition_xlsx`
- LLM / rerank / embedding：`OpenAI`、本機 `Hugging Face Rerank`（建議 `BAAI/bge-reranker-v2-m3` / `Qwen/Qwen3-Reranker-0.6B`）、本機 `Hugging Face Embedding`（建議 `Qwen/Qwen3-Embedding-0.6B`）、`Cohere Rerank v4 (optional)`、OpenAI-compatible self-hosted `/v1/rerank` / `/v1/embeddings` provider
- 本機編排：`Docker Compose`
- 對外入口：`Caddy reverse proxy + automatic TLS`
- 資料庫升級：`Alembic + migration runner`

## 產品範圍

### 範圍內
- 僅支援檔案上傳作為知識來源
- 檔案類型：`PDF`、`DOCX`、`TXT/MD`、`PPTX`、`HTML`、`XLSX`
- Knowledge Area 管理
- 以 Keycloak group 為基礎的授權
- 背景索引與進度顯示
- 以 area 為範圍的問答與 citations
- SQL gate + vector recall + FTS recall + `RRF` + rerank
- 單一公開入口的 HTTPS 部署與自動憑證續期

### 範圍外
- NotebookLM workspace / studio 類功能
- 檔案層級 ACL
- OCR / 掃描 PDF
- 上傳期間的串流式 ingest
- `pg_trgm`
- Multi-tenant / multi-realm

## 核心業務規則

### Knowledge Area
- 使用者可建立 `Knowledge Area`
- 建立者自動成為該區域 `admin`
- 區域可綁定多個 Keycloak `group path`

### 角色
- `reader`：可列文件、問答、查看 citations
- `maintainer`：`reader` + 上傳文件、刪除文件、重跑索引、查看進度與錯誤
- `admin`：`maintainer` + 管理區域設定與 Access

### 授權
- JWT claims 使用 `sub` 與 `groups`
- Keycloak access token 必須透過 mapper 穩定提供 `groups` claim，且建議使用完整 group path
- effective role = 使用者直接角色與群組角色中的最大值
- 沒有有效角色者，必須在 SQL / 資料存取層直接擋下
- 授權採 deny-by-default

### 文件狀態
- `uploaded | processing | ready | failed`
- 只有 `ready` 可進入檢索與問答

## 檢索需求

### 目前主線檢索路徑
目前主線實作通常會包含：
1. 先做 SQL gate
2. 再做 vector recall 與 / 或 FTS recall
3. 視策略需要做候選合併（目前常見為 `RRF`）
4. 視策略需要做 rerank（自架本機預設選項為 `Hugging Face Rerank / BAAI/bge-reranker-v2-m3`，可選 `Qwen/Qwen3-Reranker-0.6B`、`Cohere Rerank v4` 與 OpenAI-compatible self-hosted `/v1/rerank` provider）
5. 將候選內容交給 LLM 生成回答與 citations

補充約束：
- `SQL gate`、`deny-by-default` 與 `ready-only` 仍是不可放寬的保護邊界
- 其餘檢索 / ranking / assembly 組合屬於可演進的實作策略，不再視為不可繞過的固定順序

### 關鍵字檢索
- 使用 Postgres FTS
- 使用 `PGroonga` 支援中文斷詞
- 查詢使用 `&@~` 運算子或 `pgroonga.match_search`

### RRF 規則
- 採用 `Reciprocal Rank Fusion`
- 預設 `RRF_K = 60`
- 不做 vector 分數與 FTS 分數的線性 normalization

### Benchmark 治理原則
- benchmark 策略調整的第一核心是「不得造成 domain overfit」
- benchmark profile 與 runtime default 都必須維持 generic-first，不得用 domain-specific wording、query rewrite 或 corpus-specific heuristic 換分數
- 若某策略只能在特定 benchmark population 上成立、卻破壞通用檢索語意，必須直接視為失敗並回退

## 對外存取與部署邊界

### 單一公開入口
- 正式對外主機名稱固定為單一網域，例如 `https://easypinex.duckdns.org`
- 對外只提供單一客戶端入口 `443`
- `80` 僅保留給 ACME 驗證與 HTTP 轉 HTTPS
- `13000`、`18000`、`18080` 不再作為客戶端直接連線入口

### 對外路由
- `/` -> Web
- `/api/*` -> API
- `/auth/*` -> Keycloak

### 憑證與反向代理
- `Caddy` 為唯一對外 reverse proxy
- TLS 憑證由 `Caddy` 自動申請、續約與熱更新
- Web、API、Keycloak 共用同一張以 `PUBLIC_HOST` 綁定的憑證
- Keycloak 公開 base path 固定為 `/auth`
- `/auth/admin*` 是否對外公開，必須由明確設定控制，預設應關閉
- compose 內既有資料庫升級入口固定為 `python -m app.db.migration_runner`

## 預期公開能力

### Areas
- 建立 area
- 列出可存取的 areas
- 讀取 area
- 管理 area access

### Documents
- 上傳文件
- 列出文件
- 查詢處理進度
- 刪除文件
- 重跑索引

### Chat
- 在 area 內提問
- 取得回答與 citations
- 保留 retrieval trace metadata 供觀測用途

## 背景索引需求

預期流程：
1. API 收檔並存入 MinIO
2. 建立 `documents` 與 `ingest_jobs`
3. Worker 解析文件
4. `PDF` 先經 provider-based parsing：預設 `opendataloader` 走 `PDF -> JSON + Markdown`，`local` 走 `Unstructured partition_pdf(strategy="fast")`，`llamaparse` 則先轉成 Markdown
5. Worker 先輸出 block-aware `ParsedDocument / ParsedBlock`，區分 `text` 與 `table`
6. `XLSX` 使用 `Unstructured partition_xlsx` 解析 worksheet，優先以 `text_as_html` 回接既有 HTML table-aware parser
7. `DOCX` 與 `PPTX` 使用 `Unstructured partition_docx` / `partition_pptx` 解析，映射回既有 `text/table` block-aware contract
8. 先建立 parent sections，再依內容型別切分 child chunks
9. `text` child 使用 `LangChain RecursiveCharacterTextSplitter`
10. `table` child 優先保留整表，超大表格才依 row groups 切分
11. 產生 embedding（預設 `OpenAI text-embedding-3-small`；本機自架選項為 `Hugging Face Embedding / Qwen/Qwen3-Embedding-0.6B`）
12. PGroonga 直接使用 content 欄位索引，不需產生 `tsvector`
13. 寫入 `document_chunks`
14. 更新文件狀態

補充約束：
- `document_chunks` 必須以 SQL-first 欄位保存 `chunk_type` 與 `structure_kind`
- `LlamaParse` 正式路徑只使用標準 Markdown 輸出模式；agentic mode 僅保留未來擴充空間
- `Markdown + HTML + LlamaParse PDF->Markdown + XLSX + DOCX/PPTX(Unstructured)` 本輪支援 block-aware chunking；其中表格感知正式覆蓋 Markdown、HTML、XLSX 與可辨識 table element 的 DOCX/PPTX
- `opendataloader PDF parser` 為正式預設路徑，會依官方建議輸出 `json,markdown`，並持久化 `opendataloader.json` 與 `opendataloader.cleaned.md`
- `local PDF parser` 僅作為自架 fallback，不承諾表格高保真
- `TXT` 不做表格感知

## 前端需求

### One-Page Dashboard
- Login / Callback：基礎登入與 Session 恢復頁面
- DashboardLayout：全螢幕戰情室佈局，整合頂部全局狀態
- AreaSidebar：側邊區域導覽，提供快速切換、搜尋與建立 Area
- ChatPanel：中央主視窗，提供串流對話、檢索追蹤與引用來源顯示
- DocumentsDrawer：右側滑出式文件管理，不中斷對話即可管理文件
- AccessModal：彈窗式權限設定，集中管理區域成員與角色
- HomePage：匿名入口與產品簡介

### 核心流程
1. 登入後進入 Dashboard 並自動加載最近使用的區域
2. 透過左側 `AreaSidebar` 快速切換不同知識庫
3. 在中央 `ChatPanel` 進行即時對話，並可隨時檢視檢索路徑與引用來源
4. 若需上傳或管理文件，點擊右上角按鈕開啟 `DocumentsDrawer`，操作過程中對話不中斷

## 未來雲端部署策略

為降低維運成本並提升擴充性，專案計畫支援基於 Supabase 的雲端託管架構。此策略的核心為**「SaaS 驅動的高效資料層 + 本地 Docker 開發一致性」**：

- 高效檢索資料層：利用 Supabase Cloud 原生支援的 `PGroonga` 與 `pgvector`，將 SQL gate 所需過濾、向量召回與中文全文召回放在資料庫側完成；最終 `RRF`、ranking rules、rerank 與 assembler 仍保留在 Python 層
- 單一路徑認證與儲存：目前正式支援 `Keycloak` 作為身分來源，`MinIO / filesystem` 作為儲存後端
- 本地/地端支援：開發階段優先採用 Docker Compose 直接啟動 Supabase Postgres、API、Worker、Keycloak、MinIO、Web、Caddy
- 基礎設施簡化：遷移完成後，完整移除對純 PostgreSQL（自編譯 pg_jieba）的依賴，降低維護成本
- 既有資料庫承接：統一由 migration runner 執行 Alembic 升級，不再維持雙軌 bootstrap / upgrade migration

## 非功能性要求

### 文件與註解
- 每個檔案都要有檔案層級說明
- 每個 class 都要有 class docstring
- 每個 function / method 都要有函式層級 docstring
- 每個 module-level constant / global variable 都要有用途註解
- 所有說明文件與 docstring 均使用台灣繁體中文

### 模組 README
- `apps/*`、`infra/*`、`packages/*` 的每個頂層模組都要有 `README.md`
- 每個獨立 `pyproject.toml` / `package.json` 模組也要有 `README.md`
- 所有英文 README 都必須同步維護對應的 `README.zh-TW.md`

## 風險與假設

- Keycloak token 中需穩定提供 `groups` claim；若 client mapper 缺失，group-based access 將無法成立
- Rerank 候選數與 chunk 長度必須受控，避免成本失控
- 本專案預設為單一組織、單一 realm
- 正式 HTTPS 環境假設 `PUBLIC_HOST` 可由公網解析，且 `80/443` 已正確轉發到部署主機
