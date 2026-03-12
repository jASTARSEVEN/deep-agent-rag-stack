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

當前主階段：`Phase 2 — Areas`

目前判定：
- `Phase 0` 核心骨架已完成
- `Phase 1` 授權與資料基礎骨架 MVP 已完成
- `Phase 2` Areas 垂直切片 MVP 已完成
- 專案已具備可驗證的 auth context、area create/list/detail 與 area access management 基礎能力
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

## 目前階段重點

### Current Focus
- 穩定 `Phase 2` 的 Area create/list/detail 與 access management 垂直切片
- 穩定前端 Playwright E2E 與 test-mode API 驗證路徑
- 穩定前端 Keycloak 正式登入與 callback session flow
- 保持 deny-by-default 與不暴露受保護資源存在性的錯誤語意
- 準備進入 `Phase 3` 的 documents / upload / ingest 流程
- area rename / delete 不列為當前 phase 目標，預計於 Documents MVP 完成後再作為管理補強項目評估與排入

## 下一步

### 最適合立即進行的工作
1. 針對 documents / ingest_jobs 接上正式 upload vertical slice
2. 建立 MinIO 上傳、背景 job 建立與狀態轉換
3. 在 worker 補 parser / chunking / indexing skeleton
4. 為 Phase 3 準備 documents list、job progress 與 reindex / delete 權限邏輯
5. Documents MVP 穩定後，再評估 area rename / delete 與完整 Areas CRUD 的管理補強範圍

## 尚未開始的功能

- 文件上傳正式流程
- ingest / indexing 正式流程
- retrieval pipeline
- chat 與 citations
- SQL gate
- FTS / RRF / rerank 實作
- area rename / delete

## Agent Rules

Agents must:
1. 先閱讀 `PROJECT_STATUS.md` 再開始規劃或實作
2. 只實作當前 phase 或使用者明確要求的範圍
3. 完成 major milestone 後更新「已完成功能」與「目前狀態」
4. 不得默默跳 phase
5. 若架構決策改變，必須同步更新 `ARCHITECTURE.md`
6. 若階段拆分或順序改變，必須同步更新 `ROADMAP.md`
