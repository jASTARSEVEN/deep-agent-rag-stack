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
- LLM / rerank：`OpenAI`、`Cohere Rerank v4`
- 本機編排：`Docker Compose`

## 產品範圍

### 範圍內
- 僅支援檔案上傳作為知識來源
- 檔案類型：`PDF`、`DOCX`、`TXT/MD`、`PPTX`、`HTML`
- Knowledge Area 管理
- 以 Keycloak group 為基礎的授權
- 背景索引與進度顯示
- 以 area 為範圍的問答與 citations
- SQL gate + vector recall + FTS recall + `RRF` + rerank

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

### 檢索順序
1. 先做 SQL gate
2. 再做 vector recall
3. 再做 FTS recall
4. 用 `RRF` 合併候選
5. 用 `Cohere Rerank v4` 重排
6. 將候選內容交給 LLM 生成回答與 citations

### 關鍵字檢索
- 使用 Postgres FTS
- 使用 `PGroonga` 支援中文斷詞
- 查詢使用 `&@~` 運算子或 `pgroonga.match_search`

### RRF 規則
- 採用 `Reciprocal Rank Fusion`
- 預設 `RRF_K = 60`
- 不做 vector 分數與 FTS 分數的線性 normalization

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
4. Worker 先輸出 block-aware `ParsedDocument / ParsedBlock`，區分 `text` 與 `table`
5. 先建立 parent sections，再依內容型別切分 child chunks
6. `text` child 使用 `LangChain RecursiveCharacterTextSplitter`
7. `table` child 優先保留整表，超大表格才依 row groups 切分
8. 產生 embedding
9. (跳過) PGroonga 直接使用 content 欄位索引，不需產生 tsvector
10. 寫入 `document_chunks`
11. 更新文件狀態

補充約束：
- `document_chunks` 必須以 SQL-first 欄位保存 `chunk_type` 與 `structure_kind`
- `Markdown + HTML` 本輪支援表格感知 chunking
- `TXT` 不做表格感知

## 前端需求 (One-Page Dashboard)

佈局架構：
- **Login / Callback**: 基礎登入與 Session 恢復頁面。
- **DashboardLayout**: 全螢幕戰情室佈局，整合頂部全局狀態。
- **AreaSidebar**: 側邊區域導覽，提供快速切換、搜尋與建立 Area。
- **ChatPanel**: 中央主視窗，提供串流對話、檢索追蹤與引用來源顯示。
- **DocumentsDrawer**: 右側滑出式文件管理，不中斷對話即可管理文件。
- **AccessModal**: 彈窗式權限設定，集中管理區域成員與角色。
- **HomePage**: 匿名入口與產品簡介。

核心流程：
1. 登入後進入 Dashboard 並自動加載最近使用的區域。
2. 透過左側 `AreaSidebar` 快速切換不同知識庫。
3. 在中央 `ChatPanel` 進行即時對話，並可隨時檢視檢索路徑與引用來源。
4. 若需上傳或管理文件，點擊右上角按鈕開啟 `DocumentsDrawer`，操作過程中對話不中斷。

## 未來雲端部署策略 (Supabase)

為降低維運成本並提升擴充性，專案計畫支援基於 Supabase 的雲端託管架構。此策略的核心為 **「SaaS 驅動的高效資料層 + 本地 Docker 開發一致性」**：

- **高效檢索資料層 (PGroonga + pgvector + candidate RPC)**：利用 Supabase Cloud 原生支援的 **PGroonga** 與 `pgvector`，將 SQL gate 所需過濾、向量召回與中文全文召回放在資料庫側完成；最終 `RRF`、未來 ranking rules、rerank 與 assembler 仍保留在 Python 層，以維持可測試性與規則擴充彈性。
- **單一路徑認證與儲存**：目前正式支援 `Keycloak` 作為身分來源，`MinIO / filesystem` 作為儲存後端；多 provider auth/storage 不在本輪完成範圍。
- **本地/地端支援**：開發階段優先採用 **Docker Compose** 直接啟動 Supabase Postgres、API、Worker、Keycloak、MinIO 與 Web，降低額外 CLI 安裝門檻，並維持地端自架一致性。
- **基礎設施簡化**：遷移完成後，將**完整移除對純 PostgreSQL (自編譯 pg_jieba) 的依賴**，大幅降低基礎設施維護難度與映像檔體積。

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

## 風險與假設

- Keycloak token 中需穩定提供 `groups` claim；若 client mapper 缺失，group-based access 將無法成立
- Rerank 候選數與 chunk 長度必須受控，避免成本失控
- 本專案預設為單一組織、單 realm
