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
- `已完成（MVP 垂直切片，含 XLSX worksheet table-aware parsing）`
- 補充：PDF provider 已擴充為 `marker | local | llamaparse`，其中 `marker` 為目前預設路徑

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
- 補齊完整 Areas CRUD 的 API、UI 與測試

狀態：
- `已完成`

## Phase 4.1 — Retrieval Foundation

目標：
- 建立可驗證的 ready-only hybrid recall foundation

內容：
- SQL authorization gate
- PGroonga 繁體中文檢索整合
- `document_chunks.embedding` / `content` schema
- worker ingest indexing
- vector recall
- FTS recall (PGroonga)
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
- `已完成`

## Phase 6 — Cloud Migration & Supabase Transition

目標：
- 將專案資料層遷移為 Supabase / PGroonga / pgvector 兼容架構，同時維持本機 Docker Compose 與地端自架路徑。
- 以 Supabase 為核心資料庫架構，利用其 **SaaS 官方原生支援 PGroonga** 的優勢，解決雲端託管資料庫無法安裝 `pg_jieba` 的限制。

預期效果：
- **高品質中文檢索 (SaaS 支援)**：Supabase Cloud 內建 PGroonga，可提供比 N-gram 更精準的繁體中文分詞檢索，且無需自行維護詞庫檔。
- **大幅降低維運成本**：移除本機維護 Postgres (pg_jieba) 的複雜度與資源消耗，保留既有 Keycloak / MinIO 自架能力。
- **檢索效能與演進平衡**：將 SQL gate、向量召回與全文召回下放到資料庫層，最終 `RRF` 與未來 ranking policy 保留在 Python 層，以支援 business rules 擴充。
- **架構彈性**：核心綁定 Supabase 資料層，正式 auth/storage 路徑仍為 Keycloak + MinIO/filesystem。

里程碑內容 (Milestones)：
1. **Database & Retrieval 重構 (Supabase Core) (已完成)**
   - 引入 Supabase PostgreSQL 並啟用 `pgvector` 與 `PGroonga`。
   - 捨棄自編譯的 `pg_jieba`，將 FTS 語法轉換為 PGroonga `&@~` 運算子。
   - 撰寫 Supabase RPC (PostgreSQL Function)，只負責 `Metadata Filtering` + `Vector Search` + `FTS` 的候選召回與排序輸入輸出；最終 `RRF` 保留在 Python。
2. **Runtime 收斂 (已完成)**
   - 撤回未接線的 multi-provider auth/storage staged 內容，正式路徑維持 Keycloak + MinIO/filesystem。
   - 恢復 Alembic 作為既有資料庫升級路徑，直到專用 migration runner 落地。
3. **前端與 Worker 部署 (已完成)**
   - Web 部署至 Vercel/Netlify；API 與 Worker 容器化部署至 AWS Fargate 或 Cloud Run。
4. **環境清理與解耦完成 (Final Cleanup) (已完成)**
   - **移除純 PostgreSQL 依賴**：完整移除現有 `infra/docker/postgres` 中維護成本極高的自編譯 `pg_jieba` 映像檔與相關 Dockerfile。
   - **簡化 Infra 管理**：將 Supabase 核心元件完整併入 `docker-compose.yml` 統一管理，達成單一編排工具啟動所有基礎設施的輕量化目標，降低對外部 CLI 工具的依賴。
狀態：
- `已完成`

## Phase 6.1 — Public HTTPS Entry & Migration Bootstrap Hardening

目標：
- 讓部署入口、Keycloak 公開 URL 與既有資料庫升級流程對齊目前正式的自架模型。

內容：
- 新增 `Caddy` 作為唯一對外 `80/443` 入口，統一路由 `/`、`/api/*`、`/auth/*`
- 將 Keycloak 公開 base path 固定為 `/auth`，並以 `KEYCLOAK_EXPOSE_ADMIN` 控制 `/auth/admin*` 是否對外可達
- 將 web / api / keycloak 的公開 URL 與 compose 預設環境變數改為 `PUBLIC_HOST` 單一來源
- 新增 `python -m app.db.migration_runner`，可辨識既有 Supabase bootstrap schema、補 Alembic stamp，並升級到 head
- 補上 `WEB_ALLOWED_HOSTS`、瀏覽器非 secure context 的 PKCE fallback，以及 Windows Marker worker 安裝 / 啟動腳本

狀態：
- `已完成`

## Milestone 規則

- 每個 phase 至少要有一個可驗證的垂直切片
- 不得在上一階段尚未穩定前大幅展開下一階段
- 若某 phase 被拆成更小的子階段，需同步更新 `PROJECT_STATUS.md`

## 近期建議順序

1. 補齊真實 `PUBLIC_HOST + Caddy + Keycloak /auth` 的 smoke 與 E2E 驗證
2. 驗證既有 Supabase volume 經 `migration_runner` 升級後的 retrieval / chat 穩定性
3. 補強 area management 與 access / documents / chat 狀態切換交界的回歸驗證
4. 規劃文件級摘要 / 比較能力的 retrieval 與 synthesis phase，避免 chat 只依賴固定 top-n chunk assemble

## Phase 7.1 — Query-Aware Retrieval Profiles

目標：
- 讓 retrieval 不再只依賴單一固定 `top_n -> rerank -> assemble` 路徑，而能依問題型態切換不同策略。
- 先補齊「事實查詢 vs 文件摘要 vs 跨文件比較」三類主要問答場景的最小能力。

內容：
- 在 chat / retrieval 入口新增 query intent classification，至少區分：
  - `fact_lookup`
  - `document_summary`
  - `cross_document_compare`
- 依 query type 套用不同 retrieval profile，而不是共用同一組固定參數。
- `fact_lookup` 維持現有 precision-first 路線。
- `document_summary` 提高 recall coverage，允許較大的候選集與較寬鬆的 assembled context budget。
- `cross_document_compare` 強制保留跨文件 coverage，避免 rerank 後的 top hits 被單一文件壟斷。
- 將 profile 相關參數顯式設定化，例如：
  - recall candidate 上限
  - rerank top-n
  - assembler contexts 上限
  - 每文件可採信 parent 數上限
- retrieval trace metadata 補上 query type 與所套用 profile，便於觀測與回歸測試。

狀態：
- `未開始`

## Phase 7.2 — Diversified Selection Before Assembly

目標：
- 在不破壞 SQL gate、deny-by-default 與 ready-only 保護前提下，提升摘要 / 比較問題的文件覆蓋率。

內容：
- 在 RRF / rerank 之後、assembler 之前，新增 diversified selection layer。
- selection policy 不再只按分數排序，還要納入：
  - 文件分散度
  - parent 分散度
  - 每份文件的代表片段數上限
- 比較型問題優先保留「每份入選文件至少一個代表 parent」。
- 摘要型問題優先保留「多文件代表片段」，而不是同文件相鄰高相似片段連續佔滿 budget。
- assembler trace 補上：
  - 被保留的文件數
  - 每文件採信的 parent 數
  - 因 diversity guardrail 被淘汰的候選
- 測試補齊多文件 coverage 與單文件壟斷退化案例。

狀態：
- `未開始`

## Phase 7.3 — Document-Level Representations

目標：
- 補齊文件級任務所需的高階語意表示，避免系統只能以 child chunk 作為唯一召回單位。

內容：
- 在 ingest pipeline 為每份 `ready` 文件建立 document-level synopsis。
- 本 phase 明確不做 section-level synopsis，避免在尚未驗證 document-level 路徑前過早擴張索引與成本。
- document synopsis 需保持 SQL-first 可查詢與可觀測，不可只存在暫時記憶體。
- retrieval 新增兩階段策略：
  - 第一階段先做 document-level recall，找出值得深入的文件集合
  - 第二階段再於入選文件內做既有 parent / child recall 與 assembler
- document synopsis 應涵蓋：
  - 主題
  - 重要章節
  - 主要結論
  - 可辨識的表格 / 結構重點
- 評估 synopsis 的 embedding、更新時機、reindex 一致性與失敗回復策略。
- section-level synopsis 若未來要做，需等 document-level recall 的品質與成本先被驗證後，再另立 phase 規劃。

狀態：
- `未開始`

## Phase 7.4 — Hierarchical Synthesis for Summary / Compare

目標：
- 讓長文件摘要與多文件比較改走分階段 synthesize，而不是單次把 assemble 結果全部塞進 LLM。

內容：
- 在 LangGraph chat runtime 導入 hierarchical synthesis flow。
- 對 `document_summary` 與 `cross_document_compare` 類問題，採用至少兩段式流程：
  - map：先對單文件或單群組 context 產生局部摘要 / 比較筆記
  - reduce：再合成最終回答與 citations
- 必要時支援 refine step，處理 context 過長或文件數偏多的情境。
- citation contract 需維持可追溯到原始 document / parent / child chunks，不可只引用中間摘要節點。
- trace metadata 補上 map/reduce 階段輸入輸出摘要，便於 debug 與成本觀測。
- 對比較型問題定義較穩定的輸出結構，例如：
  - 共通點
  - 差異點
  - 各文件立場 / 結論
  - 不足證據或矛盾處

狀態：
- `未開始`

## Phase 7.5 — Evaluation & Guardrails for Coverage-Oriented RAG

目標：
- 為文件級摘要 / 比較能力建立可回歸的品質衡量，避免只調大 top-n 導致成本上升卻沒有真正改善答案品質。

內容：
- 建立摘要 / 比較專用 evaluation set，覆蓋：
  - 單長文件摘要
  - 多文件共同主題摘要
  - 多文件差異比較
  - 文件間互相矛盾資訊
- 量測與追蹤至少以下指標：
  - 文件覆蓋率
  - citation 覆蓋率
  - answer faithfulness
  - rerank / synthesis token 成本
  - 回答延遲
- 補 guardrails，限制：
  - 最大入選文件數
  - 最大 map/reduce token 預算
  - synopsis 長度
  - 比較型問題的每文件 context 配額
- 將 evaluation 結果回饋到 profile 參數調整，避免單次 heuristic 長期失真。

狀態：
- `未開始`
