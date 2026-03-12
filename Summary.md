# 全新專案實作計劃：極簡 NotebookLM 風格文件問答平台

## Summary
建立一個自架式文件問答系統，功能收斂為「登入 → 建立知識區域 → 上傳檔案 → 背景索引 → 問答引用」，強調以 Keycloak 群組做區域級授權，並把授權與文件狀態 gate 落在 PostgreSQL SQL 層，採 deny-by-default。  
技術選型固定為：`Python + FastAPI`、`PostgreSQL + pgvector + pg_jieba(FTS)`、`Celery + Redis`、`MinIO`、`Keycloak`、`React + Tailwind`、`LangChain loaders`、`LangGraph`、`OpenAI`、`Cohere Rerank v4`、`Docker Compose`。

## 產品範圍
### In scope
- 只支援「上傳檔案」作為知識來源
- 檔案類型：`PDF`、`DOCX`、`TXT/MD`、`PPTX`、`HTML`
- 知識區域管理
- Keycloak 群組授權
- 文件背景索引與進度顯示
- 區域內問答與 citations
- SQL gate + vector recall + FTS recall + `RRF` 合併 + Cohere rerank

### Out of scope
- NotebookLM 的 workspace/studio 類功能
- 檔案層級 ACL
- OCR / 掃描 PDF
- 邊上傳邊查詢的 streaming ingest
- `pg_trgm`
- 多租戶 / 多 realm

## 核心業務規則
### 知識區域
- 使用者可建立 `Knowledge Area`
- 建立者自動成為該區域 `admin`
- 區域可綁定多個 Keycloak `group path`，每個群組有一個角色

### 角色
- `reader`：可列文件、問答、查看 citations
- `maintainer`：`reader` + 上傳文件、刪除文件、重跑索引、查看處理錯誤與進度
- `admin`：`maintainer` + 管理區域設定與 Access

### 授權
- JWT 取 `sub` 與 `groups`
- effective role = 使用者直接角色與群組角色的最大權限
- 沒有角色者一律 SQL 層擋掉，不回傳任何資料

### 文件狀態
- `uploaded | processing | ready | failed`
- 只有 `ready` 可進入檢索與問答

## 檢索架構
### 檢索順序
1. SQL gate：先過濾 `authorized_areas` 與 `documents.status='ready'`
2. 向量召回：`pgvector`
3. 關鍵字召回：Postgres FTS + `pg_jieba` + `websearch_to_tsquery`
4. 以 `RRF` 合併兩路召回結果
5. `Cohere Rerank v4`
6. 將 top chunks 餵給 LLM 生成答案與 citations

### 關鍵字檢索
- 使用 `pg_jieba` 支援中文 FTS
- 索引使用較精確的斷詞結果生成 `tsvector`
- 查詢使用 `websearch_to_tsquery()` 提供接近搜尋引擎的查詢語法

### RRF 合併規則
- 採用 `Reciprocal Rank Fusion`
- 每個候選 chunk 的總分：
  - `rrf_score = Σ 1 / (rrf_k + rank_i)`
- `rank_i` 來自：
  - vector recall 排名
  - FTS recall 排名
- 預設 `rrf_k = 60`
- 未出現在某一路召回的 chunk，不計該路分數
- 依 `rrf_score DESC` 取 `topN_rrf` 候選，再送 Cohere rerank
- 不做 vector 分數與 FTS 分數的線性 normalization，也不做權重混分

### 檢索預設參數
- `K_VEC = 60`
- `K_FTS = 60`
- `RRF_K = 60`
- `TOPN_RERANK = 80`
- `CONTEXT_TOP = 12`

## 系統架構
### 服務
- `postgres`：自製 image，內含 `pgvector` 與 `pg_jieba`
- `redis`：Celery broker/result backend
- `minio`：原始檔案儲存
- `keycloak` + `keycloak-db`
- `api`：FastAPI
- `worker`：Celery worker
- `web`：React + Tailwind

### Repo 結構
- `apps/api`
- `apps/worker`
- `apps/web`
- `infra`
- `packages/shared`（若需要共用型別/設定）

## 資料模型
### 主要資料表
- `knowledge_areas`
- `knowledge_area_group_roles`
- `knowledge_area_user_roles`
- `documents`
- `ingest_jobs`
- `document_chunks`
- `chat_threads`
- `chat_messages`
- `audit_events`

### `document_chunks` 關鍵欄位
- `text`
- `tsv`
- `embedding`
- `metadata`
- `knowledge_area_id`
- `document_id`
- `chunk_index`

## 公開介面 / API
### Areas
- `POST /api/areas`
- `GET /api/areas`
- `GET /api/areas/{id}`
- `PUT /api/areas/{id}`
- `GET /api/areas/{id}/access`
- `PUT /api/areas/{id}/access`

### Documents
- `POST /api/areas/{id}/documents`
- `GET /api/areas/{id}/documents`
- `GET /api/documents/{doc_id}/job`
- `DELETE /api/documents/{doc_id}`
- `POST /api/documents/{doc_id}/reindex`

### Chat
- `POST /api/areas/{id}/chat/stream`
- SSE 事件中保留 retrieval trace metadata：
  - `vector_hits_count`
  - `fts_hits_count`
  - `rrf_candidates_count`
  - `rerank_candidates_count`
- 這些欄位只做 observability，不回傳原始未授權內容

## 背景索引流程
1. API 收 multipart 檔案並存入 MinIO
2. 建立 `documents` 與 `ingest_jobs`
3. Celery 任務依副檔名選 LangChain loader
4. 解析後 chunking
5. 產生 embeddings
6. 產生 FTS `tsvector`
7. 寫入 `document_chunks`
8. 更新 `documents.status='ready'`

## 前端頁面
- `Login / Callback`
- `Areas List`
- `Area Detail`
- `Files Tab`
- `Access Tab`
- `Activity Tab`
- `Chat`

## Figma 規劃
先畫 4 個 frame：
- Areas List
- Area Detail
- Upload Progress / Error
- Chat with citations

## 實作限制
### 註解規範
- 每個檔案必須有檔案層級說明
- 每個 class 必須有 class docstring
- 每個 function / method 必須有函式層級 docstring
- 每個 global variable / module-level constant 必須有用途註解
- 安全、授權、SQL gate、RRF 合併、外部整合點的 docstring 必須寫清楚前置條件與風險

### 模組 README 規範
- 任何 `apps/*`、`infra/*`、`packages/*` 頂層模組都必須有 `README.md`
- 任何獨立 `pyproject.toml` / `package.json` 模組也必須有 `README.md`
- 每份 README 至少包含：
  - 模組用途
  - 啟動方法
  - 環境變數
  - 主要目錄結構
  - 對外介面
  - Troubleshooting

## 測試與驗收
### 單元測試
- effective role 計算正確
- deny-by-default 正確
- `documents.status != ready` 不可檢索
- RRF 合併結果正確：
  - 同時命中兩路的 chunk 應高於只命中單一路的 chunk
  - 改變 `RRF_K` 會影響排序平滑度，但不改變授權結果
- Cohere rerank 前後候選資料結構正確
- FTS query builder 與 SQL 組裝正確

### 整合測試
- Keycloak 群組 A 可讀 area1，群組 B 不可讀
- 上傳文件後狀態從 `uploaded -> processing -> ready`
- area 有權限者可問答並看到 citations
- 無權限者 areas/documents/chat 全部看不到或回 403
- maintainer 可刪除文件與重跑索引
- admin 可修改 access，maintainer 不可修改 access
- vector 與 FTS 各自可獨立召回時，RRF 合併結果仍穩定可 rerank

### 驗收情境
1. 使用者登入後建立 area，自動成為 admin
2. admin 指派某群組為 reader
3. maintainer 上傳 PDF，看到進度
4. 文件 ready 後，reader 可問答且有 citations
5. 無權限群組問同題，不會取得任何相關內容
6. 專有名詞由 FTS 命中、語義近似由向量命中時，RRF 合併後仍能進入 rerank 候選集

## 風險與控制
- `pg_jieba` 需使用你 fork 的版本，並固定 commit SHA，避免 build 不可重現
- 中文 FTS 品質依字典與 user dict 調整，需預留 user dictionary 擴充流程
- Rerank 成本需限制候選數量與 chunk 長度
- Keycloak groups claim 必須確認 token 中穩定存在，否則需補 mapper 設定
- RRF 只能解決多路召回的排序融合，不取代權限過濾與 rerank

## 明確假設
- `PG_JIEBA_REPO_URL=https://github.com/easypinex/pg_jieba.git`
- `PG_JIEBA_REF` 在實作 kickoff 時固定為 commit SHA，不使用浮動 branch
- LLM/embedding 使用 OpenAI
- rerank 使用 Cohere v4
- 單一組織、單 realm
- FTS 為 keyword 主力方案，不導入 BM25 extension
- 多路召回合併固定採 `RRF`
