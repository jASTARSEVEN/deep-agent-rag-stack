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
- 資料庫：`PostgreSQL + pgvector + pg_jieba`
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
- 使用 `pg_jieba` 支援中文斷詞
- 查詢使用 `websearch_to_tsquery()`

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
4. 先建立 parent sections，再以 `LangChain RecursiveCharacterTextSplitter` 切分 child chunks
5. 產生 embedding
6. 產生 FTS `tsvector`
7. 寫入 `document_chunks`
8. 更新文件狀態

## 前端需求

目標頁面：
- Login / Callback
- Areas List
- Area Detail
- Files Tab
- Access Tab
- Activity Tab
- Chat

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

- `pg_jieba` 必須使用指定 fork，並固定到 commit SHA
- Keycloak token 中需穩定提供 `groups` claim；若 client mapper 缺失，group-based access 將無法成立
- Rerank 候選數與 chunk 長度必須受控，避免成本失控
- 本專案預設為單一組織、單 realm
