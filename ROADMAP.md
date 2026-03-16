# ROADMAP

## 專案總覽

本專案採分階段實作，原則是：
- 先完成可執行骨架
- 再補 auth / data / upload / retrieval / chat
- 每一階段都維持最小可運作、可驗證、可延伸

## Phase 0 — Project Skeleton

目標：
- 建立 repo 與本機開發環境骨架

內容：
- Monorepo structure
- FastAPI skeleton
- React skeleton
- Celery worker skeleton
- Docker Compose
- Postgres base image
- Redis
- MinIO
- Keycloak
- README / env / health wiring

狀態：
- `已完成`

## Phase 1 — Auth & Platform Foundations

目標：
- 建立後續 business logic 需要的基礎能力

內容：
- API settings 分層
- DB session / migration skeleton
- Keycloak JWT 驗證 skeleton
- `sub` / `groups` claim 解析
- auth middleware / dependency 基礎
- shared contracts 規整
- `GET /auth/context` 驗證切片
- `GET /areas/{area_id}/access-check` 驗證切片
- 真實 Keycloak token 與 group-based access 的本機驗證手冊

狀態：
- `已完成`

## Phase 2 — Areas

目標：
- 使用者可以看到自己可存取的 Knowledge Areas
- 此階段以最小可驗證垂直切片為主，不包含完整 Areas CRUD

內容：
- area schema
- create area
- creator becomes admin
- effective role calculation
- list accessible areas
- area-level access placeholders
- read area detail
- area access management
- web 手動 token 驗證頁
- web Keycloak login / callback / logout flow
- Playwright E2E 基礎設施與 smoke/regression coverage

狀態：
- `已完成`

## Phase 3 — Documents & Ingestion

目標：
- 可上傳文件並完成背景處理

內容：
- upload API
- MinIO store
- `documents` / `ingest_jobs`
- worker status transitions
- parser / chunking skeleton
- embedding / FTS placeholders

狀態：
- `已完成（MVP 垂直切片）`

## Phase 3.5 — Document Lifecycle Hardening & Chunk Tree Foundation

目標：
- 讓文件 ingest 不只更新狀態，也能產出可供後續 retrieval 使用的 parent-child chunk tree

內容：
- `document_chunks` SQL-first schema
- `TXT/MD` parent-child chunk tree writer
- 保留 custom parent section builder，child chunk 採 `LangChain RecursiveCharacterTextSplitter`
- document delete / reindex
- ingest job stage 與 chunk observability
- Files UI chunk summary、reindex、delete
- API / worker / E2E 驗證補齊

狀態：
- `已完成`

## Phase 3.6 — Table-Aware Chunking for Markdown + HTML

目標：
- 讓 `document_chunks` 能辨識表格結構，而不是把表格當一般文字切分

內容：
- block-aware parser / chunking contract（`ParsedDocument`、`ParsedBlock`）
- `document_chunks.structure_kind` SQL-first 欄位
- Markdown table-aware parent sectioning
- 最小 HTML parser 與 HTML table-aware chunking
- table preserve / row-group split 策略
- `CHUNK_TABLE_PRESERVE_MAX_CHARS`、`CHUNK_TABLE_MAX_ROWS_PER_CHILD`
- API / worker table-aware 回歸測試

狀態：
- `已完成`

## Post-Phase 3 Backlog — Area Management Hardening

目標：
- 在 Documents MVP 穩定後補強 area 管理能力，但不阻擋主流程推進

內容：
- area rename / update
- area delete
- 視需要補齊完整 Areas CRUD 的 API、UI 與測試

狀態：
- `進行中`

## Phase 4.1 — Retrieval Foundation

目標：
- 建立可驗證的 ready-only hybrid recall foundation

內容：
- SQL authorization gate
- `pg_jieba` 與繁體中文詞庫固定化
- `document_chunks.embedding` / `fts_document` schema
- worker / inline ingest indexing
- HNSW-backed vector recall
- FTS recall
- RRF merge
- internal retrieval service

狀態：
- `已完成`

## Phase 4.2 — Retrieval Ranking & Assembly

目標：
- 讓 recall 結果能進一步收斂為可供 chat 使用的高品質候選

內容：
- rerank integration
- retrieval trace metadata
- table-aware retrieval assembler
- chat-ready context 與 citation-ready metadata contract
- assembler budget guardrails 與 trace

狀態：
- `已完成`

## Phase 5.1 — Chat MVP & One-Page Dashboard

目標：
- 使用者可在一頁式戰情室 (Dashboard) 內進行多輪問答，並即時管理文件與權限。

內容：
- **一頁式戰情室 (Dashboard) UI 重構 (已完成)**
- LangGraph Server 啟動與 `langgraph.json`
- LangGraph built-in thread/run 與 custom auth
- LangGraph SDK 前端 transport 與 `area_id -> thread_id` 多輪 thread UX
- Deep Agents 主 agent + 單一 `retrieve_area_contexts` tool
- assembled-context level citations / references contract
- `messages-tuple`、`custom`、`values` stream contract
- `phase` / `tool_call` custom event UI 與 `messages-tuple` token stream
- tool 輸入/輸出與 assembled contexts 的可縮放檢視

狀態：
- `進行中 (UI 重構已完成)`

## Phase 6 — Cloud Migration & Supabase Transition (Planned)

目標：
- 將專案從本機 Docker Compose 完整遷移至雲端 Serverless / Managed 環境。
- 以 Supabase 為核心架構，利用其 **SaaS 官方原生支援 PGroonga** 的優勢，解決雲端託管資料庫無法安裝 `pg_jieba` 的限制。

預期效果：
- **高品質中文檢索 (SaaS 支援)**：Supabase Cloud 內建 PGroonga，可提供比 N-gram 更精準的繁體中文分詞檢索，且無需自行維護詞庫檔。
- **大幅降低維運成本**：移除本機維護 Keycloak、Postgres (pg_jieba) 與 MinIO 的複雜度與資源消耗。
- **檢索效能極大化**：將 Python 層的 RRF 合併邏輯下放到資料庫層 (RPC)，實現「單次查詢 = 條件 + 向量 + 全文 + 排序」。
- **架構彈性**：核心綁定 Supabase，但可透過 Auth Hooks 相容 Auth0/Keycloak，並透過 S3 協定兼容 MinIO/AWS S3。

里程碑內容 (Milestones)：
1. **Database & Retrieval 重構 (Supabase Core)**
   - 引入 Supabase PostgreSQL 並啟用 `pgvector` 與 `PGroonga`。
   - 捨棄自編譯的 `pg_jieba`，將 FTS 語法轉換為 PGroonga `&@~` 運算子。
   - 撰寫 Supabase RPC (PostgreSQL Function)，將 `Metadata Filtering` + `Vector Search` + `FTS` + `RRF` 封裝為單次執行。
2. **Storage 漸進式切換 (Supabase Storage / S3)**
   - API 層相容 Supabase Storage Client，並保留對 AWS S3 協定的支援。
3. **Auth 漸進式切換 (Supabase Auth / 第三方 IdP)**
   - 使用 Supabase Auth 簡化架構，並透過 **Auth Hooks** 動態轉換外部 JWT (Auth0/Keycloak) 以驅動 RLS。
4. **前端與 Worker 部署**
   - Web 部署至 Vercel/Netlify；API 與 Worker 容器化部署至 AWS Fargate 或 Cloud Run。
5. **環境清理與解耦完成 (Final Cleanup)**
   - **移除純 PostgreSQL 依賴**：在遷移測試完成後，完整移除現有 `infra/docker/postgres` 中維護成本極高的自編譯 `pg_jieba` 映像檔與相關 Dockerfile。
   - **簡化 Infra 管理**：從 `docker-compose.yml` 中正式剔除 local Postgres 服務，達成 100% 雲端原生/地端 Supabase CLI 驅動的輕量化架構。

## Milestone 規則

- 每個 phase 至少要有一個可驗證的垂直切片
- 不得在上一階段尚未穩定前大幅展開下一階段
- 若某 phase 被拆成更小的子階段，需同步更新 `PROJECT_STATUS.md`

## 近期建議順序

1. Phase 5.1：Chat MVP on LangGraph Server
2. Post-Phase 3 Backlog：Area Management Hardening
