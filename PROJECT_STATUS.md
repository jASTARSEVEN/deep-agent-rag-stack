# PROJECT_STATUS

## 專案概況

專案名稱：自架式 NotebookLM 風格文件問答平台  
目前定位：分階段實作中的 MVP  
固定技術棧：
- FastAPI
- PostgreSQL + pgvector + PGroonga (Supabase)
- Celery + Redis
- MinIO
- Keycloak
- React + Tailwind
- LangChain + LangGraph
- OpenAI
- Cohere Rerank v4
- Docker Compose

## 目前狀態

當前主階段：`Phase 6.1 — Public HTTPS Entry & Migration Bootstrap Hardening (Completed)`

目前判定：
- `Phase 0` 核心骨架已完成
- `Phase 1` 授權與資料基礎骨架 MVP 已完成
- `Phase 2` Areas 垂直切片 MVP 已完成
- `Phase 3` Documents & Ingestion 垂直切片 MVP 已完成
- `Phase 3.5` Document lifecycle hardening 與 chunk tree foundation 已完成
- `Phase 3.6` Markdown / HTML 表格感知 chunking 已完成
- `Phase 4.1` Retrieval foundation 已完成
- `Phase 4.2` minimal rerank slice 已完成
- `Phase 4.2` table-aware retrieval assembler slice 已完成
- `Phase 5.1` Chat MVP on LangGraph Server 已完成
- `Phase 6` Supabase & PGroonga Migration 已完成
- `Phase 6.1` Public HTTPS Entry & Migration Bootstrap Hardening 已完成
- 專案已具備可驗證的 auth context、area create/list/detail 與 area access management 基礎能力
- 專案已具備 area update/delete 管理能力，涵蓋 admin-only rename、description update 與 hard-delete cleanup
- 專案已具備文件 upload、documents list、ingest job 狀態轉換與 Files UI 的最小主流程
- 專案已具備 document delete、reindex、chunk summary 與 parent-child chunk tree 最小主流程
- 專案已具備 ready-only 的 internal retrieval foundation，涵蓋 SQL gate、vector recall、FTS recall 與 RRF merge
- 專案已具備 internal-only 的 parent-level rerank 路徑，涵蓋 Cohere / deterministic rerank provider、`Header:` / `Content:` 組裝、retrieval trace metadata 與 fail-open fallback
- 專案已具備 internal-only 的 table-aware retrieval assembler，將 rerank 後 child chunks 組裝為 chat-ready contexts 與 citation-ready metadata
- assembler 已升級為 precision-first materializer：小 parent 直接回完整 parent，大 parent 以命中 child 為中心做 budget-aware expansion；table hit 會優先補齊完整表格與前後說明文字
- 專案已開始將 retrieval/assembler 收斂為單一 retrieval tool，供 LangGraph chat runtime 使用
- 專案已具備 LangGraph Server built-in thread/run chat runtime 與 Web chat UI
- 專案已具備 `phase`、`tool_call` 與工具輸入/輸出檢視的 chat custom event UI
- 專案已具備可選的 LangSmith tracing 與前後端 chat stream debug 設定，供 Phase 5.1 除錯與觀測使用
- 專案已具備 `documents.display_text` 全文持久化來源與 `GET /documents/{document_id}/preview`，供 ready-only 文件全文預覽與 chunk-aware UI 使用
- 專案已具備以 `[[C1]]` marker 解析的 `answer_blocks`、citation chips、LangGraph `message_artifacts` 持久化，以及 reload 後可恢復的右側全文預覽欄
- 專案已具備將 chunk-aware 全文預覽前移到 `DocumentsDrawer` 的能力，可在文件管理中直接檢視 ready 文件的 child chunk 清單與全文高亮
- 已完成真實 Keycloak -> JWT -> API -> access-check 的本機端到端驗證
- 已完成一頁式戰情室 (Dashboard) UI 重構，提供左側 Area 導覽、中央滿版對話、右側文件管理抽屜與彈窗權限管理
- 已完成遷移至 Supabase 樣式的 schema，並使用 PGroonga 替代 pg_jieba 進行高效中文檢索
- 已完成將 `match_chunks` 收斂為資料庫候選召回 RPC；最終 `RRF`、ranking policy、rerank 與 assembler 由 Python 層負責
- 已完成 provider-based PDF parsing：預設 `marker` 走 PDF -> Markdown -> 現有 Markdown parser -> 現有 chunk tree，`local` 走 `Unstructured partition_pdf(strategy="fast")`，`llamaparse` 走 PDF -> Markdown -> 現有 Markdown parser -> 現有 chunk tree
- 已補上 `MARKER_MODEL_CACHE_DIR` 設定，讓 Marker / Surya 模型快取可落在 compose 與本機可寫路徑
- 已將 parse artifact 收斂為可重建 parser 結果的最小 `md/html` 集合；reindex 會優先重用既有 artifacts，delete 與真正需要重跑 parser 的 ingest 才會清理舊 artifacts
- 已支援 `POST /documents/{document_id}/reindex?force_reparse=true`，可由前端要求 worker 忽略既有 `md/html` artifacts 並強制重跑 parser
- 已補上 `llamaparse` 的 Markdown noise cleanup 與 PDF-specific block consolidation，降低 parent chunks 在 PDF 路徑上的過度碎片化
- 已支援 `PDF + llamaparse` 的短 `text -> table -> text` cluster parent 規則：單一 parent、混合 `text/table/text` children，維持 table-aware retrieval/citation 語意
- 已新增 `XLSX -> Unstructured partition_xlsx -> HTML table-aware parser` 路徑，worksheet 可直接進入既有 table-aware chunking
- 已新增 `DOCX/PPTX -> Unstructured partition_docx/partition_pptx` 路徑，回接既有 `text/table` block-aware parser contract
- 已完成以 `Caddy` 為核心的單一公開 HTTPS 入口，將 Web、API、Keycloak 收斂到同一個 `PUBLIC_HOST`
- 已將 Keycloak 對外模型固定為 `/auth` base path，並支援以 `KEYCLOAK_EXPOSE_ADMIN` 預設封鎖 `/auth/admin*`
- 已新增並收斂 `app.db.migration_runner`，作為 fresh 與既有資料庫共用的唯一 Alembic 升級入口
- 已補上 `WEB_ALLOWED_HOSTS` 與瀏覽器非 secure context 的 Keycloak PKCE fallback，降低公開網域與本機開發切換時的登入失敗風險
- 已補上 Windows PowerShell 的 Marker worker 安裝 / 啟動腳本，並讓 compose worker 預設可請求 GPU runtime
- 已將資料庫 migration 收斂為單一 Alembic 路徑，移除 `supabase/migrations` 與 Alembic 並存造成的雙軌 schema 風險

## 已完成功能

### Phase 0 — 已完成
- Monorepo 基本目錄結構已建立
- `apps/api` FastAPI skeleton 已建立
- `apps/worker` Celery skeleton 已建立
- `apps/web` React + Tailwind skeleton 已建立
- `infra/docker-compose.yml` 已建立
- `postgres`、`redis`、`minio`、`keycloak-db`、`keycloak`、`api`、`worker`、`web` 已完成本機串接
- API `GET /` 與 `GET /health` 已可使用
- Worker `ping` task 與 healthcheck 腳本已可使用
- Web 首頁已可顯示 API health 與骨架說明
- `.env.example`、README、模組 README 已補齊
- 根目錄 `.env.example` 已補齊，並依參數類型提供中英雙語區段註解
- `.gitignore`、`.gitattributes` 已建立
- 本輪新增文件、註解與 docstring 已統一為台灣繁體中文用法

### Phase 1 — 已完成的 MVP 基礎
- API settings 已延伸為 app / auth / db 所需的最小設定集
- `apps/api` 已加入 SQLAlchemy ORM 模型與 metadata
- 已建立 `areas`、`area_user_roles`、`area_group_roles`、`documents`、`ingest_jobs` 最小資料模型
- 已建立 Bearer token 驗證介面與 `sub` / `groups` principal 解析
- 已建立 effective role 計算與 deny-by-default area access-check service
- 已新增 `GET /auth/context` 與 `GET /areas/{area_id}/access-check`
- 已新增授權與資訊洩漏保護的單元 / API 測試
- 已修正 API 容器缺少 PostgreSQL driver 的執行期依賴問題
- 已驗證 Keycloak client 需要 `Group Membership` mapper 才能讓 access token 輸出 `groups`
- 已完成 Keycloak realm / client / groups mapper / demo users 的首次啟動自動匯入
- 已完成 migration 執行、測試 area/access seed 與 group-based `reader` 權限驗證
- 已新增 `docs/phase1-auth-verification.md` 作為可重跑的驗證手冊

### Phase 2 — 已完成的 MVP 垂直切片
- 已實作 `POST /areas`、`GET /areas`、`GET /areas/{area_id}` 的最小 create/list/detail 流程
- 已實作 `PUT /areas/{area_id}` 與 `DELETE /areas/{area_id}`，補齊 admin-only area rename / description update / hard delete 管理能力
- 已實作 `GET /areas/{area_id}/access` 與 `PUT /areas/{area_id}/access` 的 area access management API
- 已落實 creator becomes admin 規則，建立 area 後自動寫入 direct `admin` 角色
- 已落實 area hard delete 先清理文件原始檔與 parse artifacts，再刪除 area/documents/jobs/chunks，避免 storage 殘留
- 已補 maintainer / admin 權限差異、未授權 `404` 與 access 更新的 API 測試
- Web 已補 area 編輯 modal 與刪除操作，admin 可於 Dashboard header 直接管理 area 基本資料
- Web 已由 landing page 擴為可手動貼 token 的 Area 管理操作頁
- Web 已可執行 auth context 驗證、area list、create area、area detail 與 access update 最小流程
- API 已補上 CORS middleware，支援本機 Web 直接呼叫 Phase 2 API
- `apps/web` 已建立 Playwright E2E 基礎設施，可在本機以 `AUTH_TEST_MODE=true` 驗證 Areas UI 主要流程
- Web 已接上 Keycloak 正式登入 / callback / logout 流程，並保留 test auth mode 供 Playwright E2E 使用

### Phase 3 — 已完成的 MVP 垂直切片
- 已實作 `POST /areas/{area_id}/documents`、`GET /areas/{area_id}/documents`、`GET /documents/{document_id}` 與 `GET /ingest-jobs/{job_id}`
- 文件 upload 已接上物件儲存、`documents` / `ingest_jobs` 建立與 Celery dispatch
- 已實作 `uploaded -> processing -> ready|failed` 與 `queued -> processing -> succeeded|failed` 狀態轉換
- Worker 已補最小 ingest task、`TXT/MD/PDF/HTML/XLSX/DOCX/PPTX` parser 與其他檔案型別的受控失敗語意
- Web 已在 `/areas` 補上 Files 區塊、單檔 upload、文件狀態與失敗訊息顯示
- API 測試與 worker task 測試已補 upload 驗證、權限邊界、deny-by-default、狀態轉換與未支援格式案例
- Playwright E2E 已補 admin/maintainer upload、reader read-only 與 failed upload 顯示案例
- 已為 `PDF` 新增 provider-based parsing，正式支援 `marker`、`local` 與 `llamaparse` 三條解析路徑
- 已新增 `LLAMAPARSE_DO_NOT_CACHE` 與 `LLAMAPARSE_MERGE_CONTINUED_TABLES` 設定，並將 agentic mode 保留為未來規劃

### Phase 3.5 — 已完成的 lifecycle hardening 與 chunk tree 基礎
- 已新增 `document_chunks` SQL-first schema，採固定 `parent -> child` 兩層結構
- 已為 `TXT/MD` 實作真正的 chunk tree 建立流程，並將 `document.status=ready` 與 chunking 成功綁定
- 已採 hybrid chunking 策略：保留 custom parent section builder，child chunk 改用 `LangChain RecursiveCharacterTextSplitter`
- 已擴充 `documents` 與 `ingest_jobs` observability，提供 chunk counts、stage 與 last indexed time
- 已實作 `POST /documents/{document_id}/reindex` 與 `DELETE /documents/{document_id}`
- 已落實 reindex replace-all 語意：重建前清除舊 chunks，不保留殘留資料
- 已落實 delete 會移除 document、ingest jobs、document_chunks 與原始檔
- Web Files UI 已補 chunk summary、reindex、delete 與失敗訊息顯示
- API、worker 與 Playwright E2E 已補 chunk tree、reindex、delete、same-404 與 read-only 驗證
- API ingest 已收斂為單一路徑：API 只建立 `documents` / `ingest_jobs` 並 dispatch worker，不再持有 inline ingest 鏡像實作

### Phase 3.6 — 已完成的表格感知 chunking
- 已將 parser / chunking contract 升級為 block-aware，新增 `ParsedDocument` 與 `ParsedBlock`
- 已為 `document_chunks` 新增 SQL-first `structure_kind` 欄位，支援 `text | table`
- 已支援 Markdown table 辨識，並將同一 heading 內的 `text` 與 `table` blocks 拆開處理
- 已支援最小 HTML parser，可辨識 `h1~h3`、段落 / list 文字與 `<table>` 結構
- 已將過短 `table parent` 納入 parent normalization：在同 heading、相鄰且語意連續時，會與前後文字 parent 合併為 mixed parent，但仍保留 `text/table/text` children 邊界
- 小型表格會保留整表為單一 `child + table`
- 超大型表格會依 row groups 切分，並在每個 child 重複表頭
- 已新增 `CHUNK_TABLE_PRESERVE_MAX_CHARS` 與 `CHUNK_TABLE_MAX_ROWS_PER_CHILD`
- API 與 worker 測試已補 Markdown table、HTML table 與 table row-group split 驗證

### Phase 4.1 — 已完成的 retrieval foundation
- 已在 `document_chunks` 新增 retrieval-ready 的 `embedding` SQL-first 欄位，並透過 PGroonga 對 `content` 進行索引
- 已補 worker indexing 流程，將文件處理改為 `parse -> chunk -> index -> ready`
- 已導入 embedding provider abstraction，初版支援 `openai`，並保留 `deterministic` 供離線測試
- 已將 child chunk embedding 輸入調整為 `heading + content` 的自然拼接文字，改善 chunk 被切碎時的主題召回
- 已導入 ready-only 的 internal retrieval service，涵蓋 SQL gate、vector recall、FTS recall (PGroonga) 與 `RRF` merge
- 已完成遷移至 Supabase 樣式的 schema，並使用 PGroonga 替代 pg_jieba
- 已將 vector ANN index 由 `ivfflat` 切換為 `hnsw`，並補上 `documents(area_id, status)` retrieval filter index
- API 與 worker 測試已補 embeddings、retrieval same-404 與 hybrid recall (PGroonga) 驗證

### Phase 4.2 — 已完成的 minimal rerank slice
- 已在 API 端加入 rerank provider abstraction，支援 `deterministic` 與 `cohere`
- 已在 internal retrieval service 將流程擴充為 SQL gate -> vector recall / FTS recall -> `RRF` -> rerank
- 已為 retrieval candidates 補上 `rrf_rank`、`rerank_rank`、`rerank_score` 與 `rerank_applied`
- 已新增 in-memory retrieval trace metadata，保留 query、top-k 設定與每筆 candidate 的 ranking trace
- 已實作 rerank 成本控制：僅重排前 `RERANK_TOP_N` 個 parent-level 候選，且每筆文件內容受 `RERANK_MAX_CHARS_PER_DOC` 限制
- 已將 rerank 輸入改為 parent-level 組裝文字，固定帶入 `Header:` / `Content:` 前綴，降低 child chunk 過度碎片化造成的排序偏差
- 已落實 rerank runtime failure 的 fail-open fallback，不影響 deny-by-default、same-404 與 ready-only 邊界
- API 測試已補 rerank provider factory、runtime fallback、rerank metadata 與 upload -> ingest -> retrieval 的近似 E2E 驗證

### Phase 4.2 — 已完成的 table-aware retrieval assembler slice
- 已新增 internal retrieval assembler service，將 rerank 後 child chunks 組裝為 chat-ready contexts 與 citation-ready metadata
- assembler 已改為以 parent 為單位的 precision-first context materializer：小 parent 直接回完整 parent，大 parent 才做 budget-aware sibling expansion
- assembler 已以 parent 邊界去重同一 parent 的多個 hits，並保留 context-level reference metadata
- assembler 已支援 table row-group child 合併，命中 table 時會優先補齊完整表格並在合併後僅保留一次表頭，再視 budget 補前後相鄰文字
- 已新增 `ASSEMBLER_MAX_CONTEXTS`、`ASSEMBLER_MAX_CHARS_PER_CONTEXT` 與 `ASSEMBLER_MAX_CHILDREN_PER_PARENT` guardrails
- `ASSEMBLER_MAX_CHILDREN_PER_PARENT` 目前明確限制每個 parent 可採信的 hit child 數，避免過度寬鬆擴張
- assembler trace 已補齊 kept/dropped chunk ids、per-context merge 結果與 truncation metadata
- API 測試已補 text merge、table merge、budget trace、citation offsets、rerank fallback 與 upload -> ingest -> retrieval -> assembly 近似 E2E 驗證

### Phase 5.1 — 已完成的 一頁式戰情室 (Dashboard) UI 重構
- 已實作 `DashboardLayout` 全螢幕網格與頂部全局狀態管理
- 已實作 `AreaSidebar` 負責 Knowledge Areas 的導覽切換與快速建立，支援側邊欄收摺
- 已實作 `ChatPanel` 作為中央視窗核心，負責多輪對話、串流狀態顯示與工具調用檢視
- 已將 `ChatPanel` 升級為雙欄佈局：左側回答與 citation chips、右側全文預覽欄
- 已新增 `DocumentPreviewPane`，支援依 citation 自動 scroll 到全文對應位置，並以 child chunk 做 active / related / hover 高亮
- 已實作 `DocumentsDrawer` 負責右側滑出式文件管理，支援在不中斷對話的情況下上傳、編輯與刪除文件
- 已將 `DocumentsDrawer` 擴充為列表 + chunk-aware 檢視器，可直接開啟 ready 文件的 child chunk 清單與全文預覽
- 已實作 `AccessModal` 負責區域權限管理，提供彈窗式角色與權限設定介面
- 已完成從「單純 Chat MVP」向「現代化 RAG 戰情室體驗」的 UI/UX 轉型

### Phase 6 — 已完成的 Supabase & PGroonga Migration
- 已完成遷移至 Supabase 樣式的 schema，並使用 PGroonga 替代 pg_jieba
- 已實作 `match_chunks` candidate-generation RPC，供 PostgreSQL 路徑回傳受 SQL gate 保護的 vector/FTS 候選與排序輸入
- 已將最終 `RRF`、未來 ranking policy、rerank 與 assembler 保留在 Python 層，為後續 business rules 預留擴充點
- 已移除未接線的 multi-provider auth/storage staged 內容，正式路徑維持 Keycloak + MinIO/filesystem
- 已移除對純 PostgreSQL (自編譯 pg_jieba) 的依賴，簡化基礎設施
- 已更新相關環境變數範本與系統文件

### Phase 6.1 — 已完成的 Public HTTPS Entry & Migration Bootstrap Hardening
- 已新增 `caddy` service，將正式對外流量收斂為 `https://<PUBLIC_HOST>/`、`/api/*` 與 `/auth/*`
- 已將 compose 內 `web`、`api`、`keycloak` 改為內部服務，正式客戶端入口只保留 `80/443`
- 已將 Keycloak bootstrap 與公開 issuer 對齊 `/auth` relative path，並更新 realm redirect URI / web origins
- 已將 compose migration command 收斂為 `python -m app.db.migration_runner`，fresh 與既有 volume 均走同一條 Alembic 升級路徑
- 已在前端補上 `WEB_ALLOWED_HOSTS` 與 PKCE fallback，讓 `https://<PUBLIC_HOST>` 與 `http://localhost` 都能維持可預期的登入行為
- 已補上 Windows PowerShell 的 Marker worker 安裝 / 啟動腳本，並讓 compose worker 可透過 `WORKER_GPUS` 與 `NVIDIA_*` 控制 GPU runtime

### Phase 5.1 — 已完成的 Chat MVP on LangGraph Server
- 已新增 LangGraph `agent` graph、custom auth 與 LangGraph HTTP app 入口
- 已將 `CHAT_PROVIDER=deepagents` 改為真正使用 `create_deep_agent()` 的主 agent 回答路徑，不再映射為 OpenAI Responses provider
- 已將 SQL gate、ready-only、vector recall、FTS recall、RRF、rerank 與 assembler 收斂為單一 `retrieve_area_contexts` tool，交由主 agent 自行判斷是否呼叫
- Web `/areas` 已新增多輪 thread chat panel，以 `area_id -> thread_id` 維持同 area 對話脈絡
- 已將既有 Web chat transport 改為 LangGraph SDK 預設 thread/run 端點，不再以自訂 bridge chat routes 作正式路徑
- 已將 LangGraph built-in thread state 正式接上 `messages` 累積記憶；同一 area thread 的多輪對話可延續先前上下文，前端切回既有 thread 時也會回填歷史訊息
- 已將 graph 輸出升級為 assembled-context level contract，前端顯示單位與實際送進 LLM 的 context 單位對齊
- 已將 Web chat stream 收斂為 LangGraph SDK `messages-tuple`、`custom` 與 `values` 事件；最終 answer / citations / assembled contexts / trace 直接來自 graph state
- `custom` 事件目前已收斂為 `phase` 與 `tool_call`；token delta 正式透過 `messages-tuple` 傳遞
- 前端已將 chat 拆為獨立 `features/chat`，並將 `Assembled Contexts` 降級為 debug 檢視；正式使用者互動改為回答句尾 chips 與右側全文預覽欄
- API chat 已收斂到 `app/chat` domain；LangGraph 相關程式僅保留 graph/auth/http app loader 與 runtime glue
- 已補 `retrieve_area_contexts` 完成事件的 context payload 測試，避免 tool output 與 assembled context contract 再出現欄位不一致
- 已為 Deep Agents runtime 新增可選 LangSmith tracing，會附帶 `area_id`、`principal_sub`、`groups` 數量、chat provider/model 與問題長度等 metadata
- 已為 `LANGSMITH_TRACING=true` 但缺少 `LANGSMITH_API_KEY` 的錯誤情境補上明確執行期驗證
- 已新增 `CHAT_STREAM_DEBUG` 與 `VITE_CHAT_STREAM_DEBUG`，可分別觀測 API 與 Web 端的 stream phase、tool call、values commit 與 token/message delta 時序
- 已新增以 `message_artifacts` 持久化的 assistant turn UI metadata，reload 後仍可恢復 `answer_blocks`、citations 與 `used_knowledge_base`
- 已新增全文 preview route 與 `documents.display_text`，讓 citation chips 可直接帶使用者跳到文件內對應 chunk 範圍

## 目前階段重點

### Current Focus
- 驗證 `PUBLIC_HOST + Caddy + Keycloak /auth` 的真實部署路徑與登入流程
- 驗證既有 Supabase volume 經 `migration_runner` 升級後，retrieval / chat / preview 路徑不退化
- 穩定 Deep Agents answer generation、tool call custom events、assembled-context references 與 LangGraph stream contract
- 穩定 citation chips、全文 preview、child chunk hover highlighting 與 ready-only preview API 在公開 HTTPS 環境下的整體一致性
- 穩定 LangSmith tracing 與前後端 chat stream debug 在 compose / 真實 provider 環境下的觀測一致性
- 保持 deny-by-default、same-404 與 rerank fail-open fallback 不退化
- 穩定 area update/delete 與既有 documents/access/chat 狀態切換的 UI 一致性

## 下一步

### 最適合立即進行的工作
1. 補齊真實 compose / Keycloak / LangGraph / Deep Agents smoke 與 E2E 驗證
2. 在 `PUBLIC_HOST + Caddy` 環境驗證 `messages-tuple`、`custom`、`values` 與前後端 chat stream debug 的時序一致性
3. 驗證 LangSmith tracing 在真實 provider 下的 trace、tags 與 metadata 是否符合預期
4. 補完 `migration_runner` 對既有 volume、缺少 `alembic_version` 與已在 head 狀態的回歸測試
5. 補強 area management 與 access / documents / chat 狀態切換交界的回歸驗證

## 尚未開始的功能

- 更完整的 area management 跨模組回歸驗證與誤用案例覆蓋

## Agent Rules

Agents must:
1. 先閱讀 `PROJECT_STATUS.md` 再開始規劃或實作
2. 只實作當前 phase 或使用者明確要求的範圍
3. 完成 major milestone 後更新「已完成功能」與「目前狀態」
4. 不得默默跳 phase
5. 若架構決策改變，必須同步更新 `ARCHITECTURE.md`
6. 若階段拆分或順序改變，必須同步更新 `ROADMAP.md`
