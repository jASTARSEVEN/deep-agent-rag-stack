# ARCHITECTURE

## 目的

此文件描述專案的系統設計、模組責任、資料流與核心約束。  
它不負責記錄目前做到哪，而是回答「系統應該如何被設計」。

## 系統組成

### Web
- React + Tailwind
- 提供登入後的操作介面
- 顯示 areas、files、access、activity、chat
- 不承擔真正授權判斷
- 目前以匿名首頁 + Keycloak callback + 受保護的 `/areas` 路由組成最小登入體驗

### API
- FastAPI
- 提供 HTTP / SSE 介面
- 負責 auth integration、RBAC 邊界、service orchestration
- 對外暴露 areas、documents、jobs、chat 相關 API
- 目前已提供 `auth/context`、`areas` 的 create/list/detail、`areas/{area_id}/access` 管理端點，以及 documents / ingest jobs 最小集合
- JWT 驗證目前以 Keycloak issuer + JWKS 為基礎，並要求 access token 內存在 `sub` 與 `groups`

### Worker
- Celery
- 負責背景 ingest / indexing 工作
- 目前已處理 parse routing、parent-child chunk tree 寫入與狀態轉換；embed、FTS preparation 與 retrieval indexing 仍待後續 phase

### Infra
- PostgreSQL：主要資料庫
- Redis：Celery broker/result backend
- MinIO：原始檔案儲存
- Keycloak：身分與群組來源
- Alembic：資料庫 schema versioning 與 migration 執行入口

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
4. Worker 執行 parse routing、parent section 建立與 child chunk 切分
5. Worker 以 replace-all 方式重建 `document_chunks`
6. Worker 更新 document/job 狀態為 `ready` 或 `failed`

### 問答流程
1. Web 發送 chat request
2. API 驗證 JWT 與 area scope
3. Retrieval 先套 SQL gate
4. 執行 vector recall + FTS recall
5. 用 RRF 合併候選
6. 用 Cohere rerank
7. 用 LLM 生成回答與 citations
8. API 以 SSE 或 HTTP 回傳前端

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
4. Worker 目前真正解析 `TXT`、`Markdown` 與 `HTML`；其中 `Markdown / HTML` 已支援表格感知 chunking
5. `POST /documents/{document_id}/reindex` 會先清除同 document 舊 chunks，再建立新 ingest job 重建 chunk tree
6. `DELETE /documents/{document_id}` 會移除 document、相關 jobs、document chunks 與原始檔
7. `GET /areas/{area_id}/documents`、`GET /documents/{document_id}`、`GET /ingest-jobs/{job_id}` 都必須先套 area access 邊界

### Document chunk tree
1. `document_chunks` 採固定兩層結構：`parent -> child`
2. parser 與 chunker 之間使用 block-aware contract：`ParsedDocument(normalized_text, source_format, blocks)` 與 `ParsedBlock(block_kind, heading, content, start_offset, end_offset)`
3. `document_chunks` 除 `chunk_type` 外，另有 `structure_kind=text|table`，供後續 retrieval、citation 與 observability 直接辨識內容結構
4. `parent` chunk 由 custom section builder 建立；TXT 以段落群組為主，Markdown 先以 heading 分界，再切出 `text/table` blocks，HTML 則由最小 parser 輸出 `text/table` blocks
5. `table parent` 不與前後 `text parent` 合併；只有 `text parent` 會套用最小長度合併規則
6. `text child` 以 `LangChain RecursiveCharacterTextSplitter` 建立，並保留 SQL-first 的 position、index 與 offset 欄位映射
7. `table child` 採 table-aware 規則：小型表格保留整表，大型表格依 row groups 切分並重複表頭
8. `child` chunk 才是後續 retrieval 的最小候選單位
9. LangChain `metadata` 不直接進資料模型；只用來回推既有 SQL 欄位
10. `document.status = ready` 的成立條件包含 chunk tree 成功寫入
11. `status != ready` 的文件不得保留可供 retrieval 使用的 chunks

### Table-aware chunking 規則
1. Markdown table 必須至少包含 header row 與 delimiter row，且後續連續 pipe rows 視為同一張表
2. HTML parser 目前僅處理 `h1~h3`、段落 / list 文字與 `<table>` 的最小結構，不做 `rowspan/colspan` 高保真還原
3. `CHUNK_TABLE_PRESERVE_MAX_CHARS` 控制整表可否保留為單一 child
4. 超過 preserve 上限的表格以 `CHUNK_TABLE_MAX_ROWS_PER_CHILD` 分組；每個 child 只允許在 row boundary 切分
5. `table child.content` 允許重複表頭，因此可比 `normalized_text[start:end]` 多出 header，但 row payload 必須能回對原始 normalized text

## 預期模組邊界

### `apps/api`
- `core`：settings、runtime helpers
- `auth`：JWT / Keycloak integration
- `db`：session / repository wiring
- `routes`：HTTP routes
- `schemas`：Pydantic models
- `services`：業務邏輯協調
- `alembic`：migration skeleton 與 schema versioning

### `apps/worker`
- `core`：worker settings
- `tasks`：Celery task modules
- `scripts`：操作用腳本

### `apps/web`
- `app`：主入口
- `auth`：Keycloak / test auth mode、session restore、protected route
- `pages`：匿名首頁、callback、areas 等路由層頁面
- `components`：可重用元件
- `lib`：API / config / types
- 目前已接上正式 login / callback flow，並以 test auth mode 維持 Playwright E2E 可重跑性

### `infra`
- `docker-compose.yml`
- service Dockerfiles
- Keycloak bootstrap assets
