# ARCHITECTURE

## 目的

此文件描述專案的系統設計、模組責任、資料流與核心約束。  
它不負責記錄目前做到哪，而是回答「系統應該如何被設計」。

## 系統組成

### Web (One-Page Dashboard)
- React + Tailwind / Shadcn UI
- **DashboardLayout**: 負責全螢幕網格佈局與頂部全局狀態管理。
- **AreaSidebar**: 負責 Knowledge Areas 的導覽切換與快速建立，支援側邊欄收摺以最大化對話空間。
- **ChatPanel**: 視窗核心，負責多輪對話、串流狀態顯示、句尾 citation chips、工具調用透明化檢視，以及右側全文預覽欄的互動狀態。
- **DocumentPreviewPane**: 右側固定全文預覽欄，依 citation 所屬 `start_offset/end_offset` scroll 到對應位置，並以 child chunk 邊界做強/弱/hover 高亮。
- **DocumentsDrawer**: 負責不中斷對話的文件生命週期管理，透過右側滑出式抽屜提供文件上傳、列表、狀態追蹤，以及 ready 文件的 chunk-aware 全文檢視。
- **AccessModal**: 彈窗式權限管理，確保區域權限與角色設定不干擾主對話流程。
- 提供「登入 -> 側邊欄選取區域 -> 中央即時對話」的流暢戰情室體驗。

### API
- FastAPI
- 提供 HTTP / SSE 介面
- 負責 auth integration、RBAC 邊界、service orchestration
- 對外暴露 areas、documents、jobs、chat 相關 API
- 目前已提供 `auth/context`、`areas` 的 create/list/detail、`areas/{area_id}/access` 管理端點，以及 documents / ingest jobs 最小集合
- JWT 驗證目前以 Keycloak issuer + JWKS 為基礎，並要求 access token 內存在 `sub` 與 `groups`
- chat runtime 透過 LangGraph Server 啟動；正式 Web transport 已改為 LangGraph SDK 預設 thread/run 端點，不再維護產品自訂 bridge chat routes

### Worker
- Celery
- 負責背景 ingest / indexing 工作
- 目前已處理 parse routing、parent-child chunk tree、embedding、FTS payload 寫入與狀態轉換

### Infra
- PostgreSQL：主要資料庫 (使用 Supabase / PGroonga 支援繁體中文檢索)
- Redis：Celery broker/result backend
- MinIO：原始檔案儲存 (未來兼容 AWS S3)
- Keycloak：目前正式的身分與群組來源
- Supabase Migrations：位於 `supabase/migrations/`，是目前的 schema 正式來源

## 關鍵架構原則

### 1. deny-by-default
- 沒有有效角色的使用者，不得看到受保護資源
- 不能依靠前端隱藏按鈕當作授權機制

### 2. SQL gate 必須是主要保護層
- 不能先查全部資料再在記憶體過濾
- 未來 retrieval 與文件讀取都必須先套用 SQL gate

### 2.5. chunk schema 採 SQL-first
- `document_chunks` 的核心欄位必須以實體 SQL 欄位建模
- 不得以 `metadata_json` 或其他半結構欄位承載已知會參與查詢、排序、驗證或 observability 的資訊
- parent-child 關聯、position、section index、child index、heading、offset 等資料都必須可直接以 SQL 查詢

### 3. `documents.status = ready` 才可檢索
- `uploaded`
- `processing`
- `ready`
- `failed`

只有 `ready` 可進入 retrieval / chat。

### 4. phase-by-phase 實作
- 骨架完成前不實作完整 business logic
- auth / areas / documents / retrieval / chat 按階段前進
- area rename / delete 與完整 Areas CRUD 不屬於目前已驗證的 Areas MVP，預計在 Documents MVP 穩定後再補強

## 未來資料流

### 文件上傳流程
1. Web 上傳檔案
2. API 驗證請求並建立 `documents` / `ingest_jobs`
3. API 將原始檔存入 MinIO
4. Worker 執行 parse routing；其中 `PDF` 會先經 provider-based parsing：`local` 走 `Unstructured partition_pdf(strategy="fast")`，`llamaparse` 先轉成 Markdown
5. PDF 的 Markdown 會回到既有 Markdown parser，與 `TXT/MD/HTML` 一樣輸出 block-aware `ParsedDocument`
6. `XLSX` 會先由 `Unstructured partition_xlsx` 解析 worksheet，優先取 `text_as_html` 並回接既有 HTML table-aware parser
7. `DOCX` 與 `PPTX` 會先由 `Unstructured partition_docx` / `partition_pptx` 解析，再映射為既有 `text/table` block-aware contract
8. Worker 依 ParsedDocument 建立 parent section 與 child chunk
9. Worker 以 replace-all 方式重建 `document_chunks`
10. Worker 將 `ParsedDocument.normalized_text` 寫回 `documents.normalized_text`，作為全文 preview 的正式資料來源
11. Worker 為 child chunks 寫入 `embedding`
12. Worker 更新 document/job 狀態為 `ready` 或 `failed`

### 問答流程
1. Web 於 area 內建立或恢復對應的 LangGraph thread，並送出 chat run；每次 run 只附帶新的 user message，既有多輪歷史由 LangGraph thread state 保存
2. LangGraph Server 先透過 custom auth 驗證 Bearer token
3. Web 透過 LangGraph SDK 預設 thread/run 端點送出 `area_id` 與 `question`
4. LangGraph auth 在 server 端將已驗證 `sub/groups` 注入 graph input
5. graph 內的主 Deep Agent 可自行判斷是否需要呼叫單一 `retrieve_area_contexts` tool；該 tool 內固定套用 SQL gate、ready-only、vector recall、FTS recall、RRF、rerank 與 table-aware assembler
6. 若主 agent 呼叫 retrieval tool，最終 graph state 會帶出 `citations`、`assembled_contexts`、`answer_blocks` 與 `used_knowledge_base`；其中回答引用由 `[[C1]]` marker 解析為 UI 可用的 `answer_blocks`
7. LangGraph thread state 除 `messages` 外，另保存 `message_artifacts`；每個 assistant turn 會持久化 `answer_blocks`、`citations` 與 `used_knowledge_base`，供前端 reload 後還原 chips 與預覽互動
8. Web 直接消費 LangGraph SDK 的 `messages-tuple`、`custom` 與 `values` 事件：token delta 來自 `messages-tuple`，最終 answer / artifacts / citations 來自 `values`
9. `custom` 事件目前承載 `phase` 與 `tool_call`；前端可即時顯示搜尋 / 思考 / 工具呼叫狀態，以及 `retrieve_area_contexts` 的輸入 / 輸出
10. 前端正式引用 UX 為回答句尾 chips + 右側全文預覽欄；`Assembled Contexts`、工具輸入與工具輸出保留為 debug/details

### 文件管理預覽流程
1. 使用者在 `DocumentsDrawer` 中選取 `ready` 文件
2. 前端呼叫既有 `GET /documents/{document_id}/preview`
3. API 維持 ready-only、same-404 與 deny-by-default 語意
4. 前端以 `normalized_text + child chunk map` 建立 chunk list 與全文高亮，不新增第二條 inspector API
5. 點擊 chunk list 或全文中的 chunk 時，兩側同步作用中的 child chunk 狀態

### Web 登入流程
1. 匿名使用者可先進入首頁
2. 進入受保護頁面或按下登入按鈕後，Web 導向 Keycloak
3. Keycloak callback 回到 `/auth/callback`
4. 前端建立 session、取得 access token，並呼叫 `GET /auth/context`
5. 之後受保護 API 請求自動帶上 bearer token
6. token 接近過期時由前端 refresh；失敗則清 session 並回首頁

## 已驗證的 foundation 路徑

### Keycloak -> API auth context
1. 使用者透過 Keycloak 取得 access token
2. access token 必須包含 `sub` 與 `groups`
3. API 透過 issuer / JWKS 驗證 token
4. API 將 token 解析為 principal，提供 `GET /auth/context`

### Group-based area access check
1. `area_group_roles` 或 `area_user_roles` 提供 area 權限映射
2. API 以 SQL 查詢 direct role 與 group role
3. service 取最大值作為 effective role
4. 沒有有效角色者統一回 `404`，避免暴露資源存在性

### Area vertical slice
1. 使用者以 Bearer token 呼叫 `POST /areas`
2. API 建立 `areas` 記錄，並將建立者寫入 `area_user_roles=admin`
3. `GET /areas` 只回傳目前使用者可存取的 area，並附上 effective role
4. `GET /areas/{area_id}` 與 `GET /areas/{area_id}/access` 都先做 SQL access check
5. `PUT /areas/{area_id}/access` 僅允許 `admin` 以整體替換方式更新 direct user roles 與 group roles

### Documents & ingestion vertical slice
1. `POST /areas/{area_id}/documents` 僅允許 `maintainer` 以上上傳單一文件
2. API 先將原始檔寫入物件儲存，再建立 `documents=status=uploaded` 與 `ingest_jobs=status=queued`
3. 正式環境由 Celery worker 執行 ingest；測試模式可走 inline ingest 以維持本機驗證可重跑
4. Worker 與 API inline ingest 目前真正解析 `TXT`、`Markdown`、`HTML`、`PDF`、`XLSX`、`DOCX` 與 `PPTX`
5. `PDF` 採 provider-based parsing：`PDF_PARSER_PROVIDER=local|llamaparse`；`llamaparse` 只使用標準 Markdown 輸出，不啟用 agentic mode
6. `llamaparse` 路徑在進入既有 Markdown parser 前，會先清理常見頁碼 / 分隔符噪音；進入 chunking 前再做 PDF-specific block consolidation，優先合併同 heading 的碎片 text/table runs
7. `local` PDF parser 僅提供自架 fallback 與基本文字擷取；不承諾表格高保真，也不支援 OCR / 掃描 PDF
8. `POST /documents/{document_id}/reindex` 會先清除同 document 舊 chunks，再建立新 ingest job 重建 chunk tree
9. `DELETE /documents/{document_id}` 會移除 document、相關 jobs、document chunks 與原始檔
10. `GET /areas/{area_id}/documents`、`GET /documents/{document_id}`、`GET /ingest-jobs/{job_id}` 都必須先套 area access 邊界

### Document chunk tree
1. `document_chunks` 採固定兩層結構：`parent -> child`
2. parser 與 chunker 之間使用 block-aware contract：`ParsedDocument(normalized_text, source_format, blocks)` 與 `ParsedBlock(block_kind, heading, content, start_offset, end_offset)`
3. `PDF` 不直接寫入外部 SaaS chunk 結果；無論是 `local` 或 `llamaparse`，都必須先回到既有 parser/chunk tree contract
4. `document_chunks` 除 `chunk_type` 外，另有 `structure_kind=text|table`，供後續 retrieval、citation 與 observability 直接辨識內容結構
5. `parent` chunk 由 custom section builder 建立；TXT 以段落群組為主，Markdown 與 LlamaParse PDF Markdown 先以 heading 分界，再切出 `text/table` blocks，HTML 與 `XLSX` 產生的 worksheet HTML 則由最小 parser 輸出 `text/table` blocks，`DOCX/PPTX` 則由 Unstructured elements 映射到同一份 `text/table` block contract
6. `PDF + llamaparse` 會先做一次 PDF-specific block consolidation，降低同 heading 下因 page noise、碎表格或過短 text block 造成的 parent fragmentation
7. 若 `PDF + llamaparse` 命中同 heading 的短 `text -> table -> text` 模式，系統會建立單一 parent cluster，但仍保留 `text/table/text` children，避免破壞 table-aware retrieval 與 citations
8. parent normalization 採精準度優先策略：除既有短 `text parent` 合併外，過短 `table parent` 也可在同 heading、相鄰且語意連續時，與前後 `text parent` 合併為 mixed parent；合併後仍保留 `text/table/text` children 邊界
9. `text child` 以 `LangChain RecursiveCharacterTextSplitter` 建立，並保留 SQL-first 的 position、index 與 offset 欄位映射
10. `table child` 採 table-aware 規則：小型表格保留整表，大型表格依 row groups 切分並重複表頭
11. `child` chunk 才是後續 retrieval 的最小候選單位
12. child chunk embedding 的正式輸入為 `heading + content` 的自然拼接文字；若沒有 heading，則只使用 content
13. LangChain `metadata` 不直接進資料模型；只用來回推既有 SQL 欄位
14. `document.status = ready` 的成立條件包含 chunk tree 成功寫入
15. `status != ready` 的文件不得保留可供 retrieval 使用的 chunks
16. `documents.normalized_text` 是正式全文 preview 的資料來源；其內容必須與 `document_chunks.start_offset/end_offset` 對齊
17. reindex / failed ingest 開始時必須清空舊的 `documents.normalized_text`，避免全文 preview 與現存 chunks 不一致

### Retrieval foundation
1. retrieval 目前先作為 API 內部 service，不提供 public route
2. SQL gate 先以 area scope + effective role 驗證完成，之後才進入 recall
3. 只有 `documents.status=ready` 且 `chunk_type=child` 的 chunk 會進入 recall
4. `document_chunks.embedding` 與 `content` (經 PGroonga 索引) 都屬於 retrieval 的 SQL-first 欄位
5. PostgreSQL 正式路徑使用 `pgvector` 與 `PGroonga`；SQLite 測試路徑使用 deterministic fallback，僅供離線驗證
6. PostgreSQL vector recall 預設使用 `hnsw` index，並依賴 `pgvector >= 0.8.0` 提供 `hnsw.iterative_scan`
7. FTS 固定使用 `PGroonga` 進行繁體中文分詞檢索
8. retrieval 目前已擴充為 vector recall + FTS recall + Python `RRF` merge + parent-level rerank + table-aware assembler；正式 Web chat transport 改走 LangGraph SDK 預設 thread/run 端點
9. rerank 目前僅作為 API 內部 capability，不公開為 HTTP route；正式 provider 為 Cohere，測試與離線驗證使用 deterministic provider
10. rerank 只允許重排 RRF 後前 `RERANK_TOP_N` 個 parent-level 候選，且每筆送入文字受 `RERANK_MAX_CHARS_PER_DOC` 限制
11. parent-level rerank 會先以 `(document_id, parent_chunk_id, structure_kind)` 聚合同一 parent 下已命中的 child chunks，並以 `Header:` / `Content:` 前綴建立送入 rerank provider 的文字
12. assembler 會以 `document_id + parent_chunk_id` 作為 materialization 邊界，將 rerank 後的 child hits 展開為 chat-ready parent-level context 與 context-level reference metadata；最終 context `structure_kind` 以 parent 為準
13. assembler 不得擴張 SQL gate 後的資料集合，但可在同一 parent 內做 precision-first context materialization：小 parent 直接回完整 `parent.content`，大 parent 才以命中 child 為中心做 budget-aware sibling expansion
14. `ASSEMBLER_MAX_CHILDREN_PER_PARENT` 限制的是同一 parent 內可採信的命中 child 數；被此 guardrail 淘汰的 hit 不得在後續 expansion 階段再補回 context
15. 命中 `table` child 時，assembler 會優先補齊同一 parent 內相鄰的 table row-group children，再視 budget 補上前後緊鄰的 `text` child，形成較完整的 `text/table/text` 語意片段
16. `table` chunks 在 assembler 與 parent-level rerank 文字組裝內都維持 Markdown table 文字；同一 context 內多個 row-group child 合併時只保留一次表頭
17. assembler 受 `ASSEMBLER_MAX_CONTEXTS`、`ASSEMBLER_MAX_CHARS_PER_CONTEXT` 與 `ASSEMBLER_MAX_CHILDREN_PER_PARENT` 控制；其中 `ASSEMBLER_MAX_CONTEXTS` 就是送進 LLM 的 context 單位上限，也是前端顯示的 assembled context 上限，而 `ASSEMBLER_MAX_CHARS_PER_CONTEXT` 同時決定 full-parent 與 expanded-window 的 materialization budget
18. rerank runtime failure 採 fail-open fallback 回退到 `RRF` 結果，但不得改變 SQL gate、same-404 與 ready-only 的保護語意
19. retrieval / assembler trace metadata 目前只存在記憶體回傳結構，不落資料庫
20. public chat 採 LangGraph Server runtime，前端正式透過 LangGraph SDK 預設端點與 thread/run 模型互動；`CHAT_PROVIDER=deepagents` 時會以 `create_deep_agent()` 建立主 agent，並只暴露單一 `retrieve_area_contexts` tool
21. 多輪對話記憶必須以 LangGraph built-in thread state 為主，不能只在前端記住訊息列表卻不回寫 server-side state
22. retrieval pipeline 對 agent 僅以單一 tool 形式暴露，不允許 agent 直接拆呼叫 vector / FTS / rerank，也不再以關鍵字 heuristics 先行分流
23. Deep Agents 的對外 citations 已收斂為 assembled-context level references；前端顯示上限與送進 LLM 的 context 單位上限同為 `ASSEMBLER_MAX_CONTEXTS`
24. custom auth 會將 Bearer token 解析為 `identity/sub/groups`，供 LangGraph built-in routes 與 API app 共用
25. `custom` 事件目前是產品 UI 的正式補充通道：`phase` 用於高層狀態、`tool_call` 用於即時工具輸入輸出；token delta 的正式來源為 `messages-tuple`
26. `tool_call.completed.output` 只回傳 debug-safe 的 context 摘要；最終完整結果仍以 graph `values` 為準
27. retrieval tool 回給 LLM 的 payload 只保留 `context_label`、`context_index`、`document_name`、`heading` 與 `assembled_text`；`start_offset/end_offset` 僅屬於 UI locator payload，不送入 LLM
28. public documents API 新增 `GET /documents/{document_id}/preview`；此 route 必須維持 same-404 與 ready-only，且回傳 `normalized_text + child chunk map`
29. 全文預覽欄的 hover 高亮以 child chunk 為最小單位；主 citation 命中 chunk 強高亮，同一 context 其他 child 弱高亮，hover chunk 淡高亮

### Table-aware chunking 規則
1. Markdown table 必須至少包含 header row 與 delimiter row，且後續連續 pipe rows 視為同一張表
2. HTML parser 目前僅處理 `h1~h3`、段落 / list 文字與 `<table>` 的最小結構，不做 `rowspan/colspan` 高保真還原
3. `CHUNK_TABLE_PRESERVE_MAX_CHARS` 控制整表可否保留為單一 child
4. 超過 preserve 上限的表格以 `CHUNK_TABLE_MAX_ROWS_PER_CHILD` 分組；每個 child 只允許在 row boundary 切分
5. `table child.content` 允許重複表頭，因此可比 `normalized_text[start:end]` 多出 header，但 row payload 必須能回對原始 normalized text

## 雲端架構演進 (Supabase Migration) - 已完成

本專案在 Phase 6 遷移至以 Supabase 為核心的架構：

### 1. 資料庫層的混合搜尋封裝 (Hybrid Search RPC)
- **資料庫職責收斂**：`match_chunks` RPC 只負責 SQL gate 所需的 area/status/filter、向量召回、PGroonga 全文召回，以及回傳 `vector_rank` / `fts_rank` 等最小排序輸入；它不是最終 ranking policy 的真理來源。
- **PGroonga 支援 (SaaS 官方內建)**：利用 Supabase Cloud 官方支援的 PGroonga 擴充功能，在雲端環境獲得比 `pg_jieba` 更高效、且無需維護字典檔的繁體中文分詞檢索。
- **Python ranking layer**：最終 `RRF`、未來 business rules、source priors、freshness、section boosts、rerank 與 assembler 都保留在 Python 層，避免把常變邏輯鎖死在 SQL/RPC。

### 2. Runtime 收斂
- **正式 auth 路徑**：目前正式支援 `Keycloak` issuer + JWKS 驗證與 `sub/groups` claims。
- **正式 storage 路徑**：目前正式支援 `MinIO` 與 `filesystem`。
- **既有 DB 升級策略**：`supabase/migrations/` 是新環境 schema 的正式來源，但在專用 migration runner 落地前，既有資料庫仍由 Alembic 升級。

### 3. 開發環境的一致性 (Local Development Parity)
- **Supabase Docker Stack**：開發環境直接採用 Docker Compose 提供的 Supabase Postgres 容器。這套配置能重現 PGroonga / pgvector 能力，且不需要安裝額外 CLI 工具。
- **完整移除純 PostgreSQL 依賴**：轉換已完成，系統不再依賴於專案內自建的 `infra/docker/postgres` 及其複雜的 C-extension 編譯過程。現有的 PostgreSQL 容器與相關資產已正式退役，簡化了基礎設施的維護鏈。
- **地端部署支援**：此設計確保專案在遷移到雲端的同時，依然保有「地端自架 (Self-hosted)」的完整能力。開發者可以選擇在本機 Docker 中運行完整架構，或連接到雲端 Supabase 資料層，維持高度的環境一致性。

## 預期模組邊界

### `apps/api`
- `core`：settings、runtime helpers
- `auth`：JWT / Keycloak integration
- `chat`：Deep Agents 主 agent、agent tools 與 LangGraph runtime glue
- `db`：session / repository wiring
- `routes`：HTTP routes
- `services`：業務邏輯協調

### `apps/worker`
- `core`：worker settings
- `tasks`：Celery task modules
- `scripts`：操作用腳本

### `apps/web`
- `app`：主入口與 `DashboardLayout`
- `auth`：Keycloak / test auth mode、session restore、protected route
- `features/chat`：LangGraph SDK transport、`ChatPanel` 與對話狀態管理
- `features/areas`：`AreaSidebar` 與區域管理邏輯
- `features/documents`：`DocumentsDrawer` 與文件管理邏輯
- `pages`：匿名首頁、callback、`AreasPage` (Dashboard 主頁)
- `components`：可重用元件與 `AccessModal`
- `lib`：API / config / types
- 目前已接上正式 login / callback flow，並以一頁式 Dashboard 提供完整 RAG 操作體驗

### `infra`
- `docker-compose.yml`
- service Dockerfiles
- Keycloak bootstrap assets
