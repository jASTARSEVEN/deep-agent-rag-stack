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

當前主階段：`Phase 0 — Project Skeleton`

目前判定：
- `Phase 0` 核心骨架已完成
- 專案已具備本機可啟動 stack
- 尚未進入正式 business logic 實作

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

## 目前階段重點

### Current Focus
- 保持 `Phase 0` 完成態可穩定啟動
- 為下一階段的 DB wiring、auth skeleton、document vertical slice 做好延伸點
- 避免在沒有明確要求前提前實作未來 phase

## 下一步

### 最適合立即進行的工作
1. 建立 API 設定分層與 DB wiring 骨架
2. 建立 migration 基礎與資料模型占位
3. 建立 Keycloak auth middleware skeleton
4. 建立文件上傳最小垂直切片的 API / worker 契約

## 尚未開始的功能

- Knowledge Area CRUD
- Area-level RBAC
- 文件上傳正式流程
- ingest / indexing 正式流程
- retrieval pipeline
- chat 與 citations
- SQL gate
- FTS / RRF / rerank 實作

## Agent Rules

Agents must:
1. 先閱讀 `PROJECT_STATUS.md` 再開始規劃或實作
2. 只實作當前 phase 或使用者明確要求的範圍
3. 完成 major milestone 後更新「已完成功能」與「目前狀態」
4. 不得默默跳 phase
5. 若架構決策改變，必須同步更新 `ARCHITECTURE.md`
6. 若階段拆分或順序改變，必須同步更新 `ROADMAP.md`
