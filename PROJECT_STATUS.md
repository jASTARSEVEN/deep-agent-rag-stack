# PROJECT_STATUS

## 專案概況

專案名稱：自架式 NotebookLM 風格文件問答平台  
目前定位：分階段實作中的 MVP  
固定技術棧：
- FastAPI
- PostgreSQL + pgvector + pg_jieba
- Celery + Redis
- MinIO
- Keycloak
- React + Tailwind
- LangChain + LangGraph
- OpenAI
- Cohere Rerank v4
- Docker Compose

## 目前狀態

當前主階段：`Phase 4.1 — Retrieval Foundation`

目前判定：
- `Phase 0` 核心骨架已完成
- `Phase 1` 授權與資料基礎骨架 MVP 已完成
- `Phase 2` Areas 垂直切片 MVP 已完成
- `Phase 3` Documents & Ingestion 垂直切片 MVP 已完成
- `Phase 3.5` Document lifecycle hardening 與 chunk tree foundation 已完成
- `Phase 3.6` Markdown / HTML 表格感知 chunking 已完成
- `Phase 4.1` Retrieval foundation 已完成
- 專案已具備可驗證的 auth context、area create/list/detail 與 area access management 基礎能力
- 專案已具備文件 upload、documents list、ingest job 狀態轉換與 Files UI 的最小主流程
- 專案已具備 document delete、reindex、chunk summary 與 parent-child chunk tree 最小主流程
- 專案已具備 ready-only 的 internal retrieval foundation，涵蓋 SQL gate、vector recall、FTS recall 與 RRF merge
- 已完成真實 Keycloak -> JWT -> API -> access-check 的本機端到端驗證

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
- `apps/api` 已加入 SQLAlchemy 與 Alembic migration skeleton
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
- 已實作 `GET /areas/{area_id}/access` 與 `PUT /areas/{area_id}/access` 的 area access management API
- 已落實 creator becomes admin 規則，建立 area 後自動寫入 direct `admin` 角色
- 已補 maintainer / admin 權限差異、未授權 `404` 與 access 更新的 API 測試
- Web 已由 landing page 擴為可手動貼 token 的 Area 管理操作頁
- Web 已可執行 auth context 驗證、area list、create area、area detail 與 access update 最小流程
- API 已補上 CORS middleware，支援本機 Web 直接呼叫 Phase 2 API
- `apps/web` 已建立 Playwright E2E 基礎設施，可在本機以 `AUTH_TEST_MODE=true` 驗證 Areas UI 主要流程
- Web 已接上 Keycloak 正式登入 / callback / logout 流程，並保留 test auth mode 供 Playwright E2E 使用

### Phase 3 — 已完成的 MVP 垂直切片
- 已實作 `POST /areas/{area_id}/documents`、`GET /areas/{area_id}/documents`、`GET /documents/{document_id}` 與 `GET /ingest-jobs/{job_id}`
- 文件 upload 已接上物件儲存、`documents` / `ingest_jobs` 建立與 Celery dispatch
- 已實作 `uploaded -> processing -> ready|failed` 與 `queued -> processing -> succeeded|failed` 狀態轉換
- Worker 已補最小 ingest task、`TXT/MD` parser 與其他檔案型別的受控失敗語意
- Web 已在 `/areas` 補上 Files 區塊、單檔 upload、文件狀態與失敗訊息顯示
- API 測試與 worker task 測試已補 upload 驗證、權限邊界、deny-by-default、狀態轉換與未支援格式案例
- Playwright E2E 已補 admin/maintainer upload、reader read-only 與 failed upload 顯示案例

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
- API 在 inline ingest 模式下已可於缺少 celery 套件的本機環境啟動與測試

### Phase 3.6 — 已完成的表格感知 chunking
- 已將 parser / chunking contract 升級為 block-aware，新增 `ParsedDocument` 與 `ParsedBlock`
- 已為 `document_chunks` 新增 SQL-first `structure_kind` 欄位，支援 `text | table`
- 已支援 Markdown table 辨識，並將同一 heading 內的 `text` 與 `table` blocks 拆開處理
- 已支援最小 HTML parser，可辨識 `h1~h3`、段落 / list 文字與 `<table>` 結構
- `table parent` 已明確獨立，不會與前後文字 parent 合併
- 小型表格會保留整表為單一 `child + table`
- 超大型表格會依 row groups 切分，並在每個 child 重複表頭
- 已新增 `CHUNK_TABLE_PRESERVE_MAX_CHARS` 與 `CHUNK_TABLE_MAX_ROWS_PER_CHILD`
- API 與 worker 測試已補 Markdown table、HTML table 與 table row-group split 驗證

### Phase 4.1 — 已完成的 retrieval foundation
- 已在 `document_chunks` 新增 retrieval-ready 的 `embedding` 與 `fts_document` SQL-first 欄位
- 已補 worker 與 inline ingest 的 indexing 流程，將文件處理改為 `parse -> chunk -> index -> ready`
- 已導入 embedding provider abstraction，初版支援 `openai`，並保留 `deterministic` 供離線測試
- 已導入 ready-only 的 internal retrieval service，涵蓋 SQL gate、vector recall、FTS recall 與 `RRF` merge
- 已補 PostgreSQL `pg_jieba` extension、繁體中文詞庫固定化與 `deep_agent_jieba` text search configuration
- 已將 vector ANN index 由 `ivfflat` 切換為 `hnsw`，並補上 `documents(area_id, status)` retrieval filter index
- API 與 worker 測試已補 embeddings/FTS payload、retrieval same-404、FTS builder 與 hybrid recall 驗證

## 目前階段重點

### Current Focus
- 穩定 `Phase 4.1` 的 retrieval foundation 與 `pg_jieba` 本機啟動路徑
- 穩定 `hnsw` vector recall 與 `pgvector >= 0.8.0` 查詢參數設定
- 穩定 `embedding` / `fts_document` 與既有 reindex / delete / observability 路徑的相容性
- 穩定 ready-only、deny-by-default 與 SQL gate 的 retrieval 語意
- 為 `Phase 4.2` 準備 rerank、retrieval trace metadata 與 table-aware retrieval assembler
- 保持 deny-by-default 與不暴露受保護資源存在性的錯誤語意
- area rename / delete 不列為 retrieval 前的阻擋項目，維持在 documents 主流程之後評估

## 下一步

### 最適合立即進行的工作
1. 為 `Phase 4.2` 接上 Cohere rerank、retrieval trace metadata 與 candidate 組裝細節
2. 定義 table-aware retrieval assembler，避免把整批 parent / table chunks 無控制地塞進 LLM prompt
3. 在 API 內將 internal retrieval service 串到後續 chat/citations flow
4. 補 `pg_jieba` 本機 compose 啟動與 migration 的整合驗證
5. Retrieval foundation 穩定後，再評估 area rename / delete 與完整 Areas CRUD 的管理補強範圍

## 尚未開始的功能

- Cohere rerank 正式整合
- public chat API 與 citations
- retrieval trace metadata
- area rename / delete

## Agent Rules

Agents must:
1. 先閱讀 `PROJECT_STATUS.md` 再開始規劃或實作
2. 只實作當前 phase 或使用者明確要求的範圍
3. 完成 major milestone 後更新「已完成功能」與「目前狀態」
4. 不得默默跳 phase
5. 若架構決策改變，必須同步更新 `ARCHITECTURE.md`
6. 若階段拆分或順序改變，必須同步更新 `ROADMAP.md`
