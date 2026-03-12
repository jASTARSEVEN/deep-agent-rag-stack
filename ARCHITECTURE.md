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

### API
- FastAPI
- 提供 HTTP / SSE 介面
- 負責 auth integration、RBAC 邊界、service orchestration
- 對外暴露 areas、documents、jobs、chat 相關 API
- 在 foundation 階段先提供 `auth/context` 與 `areas/{area_id}/access-check` 驗證切片
- JWT 驗證目前以 Keycloak issuer + JWKS 為基礎，並要求 access token 內存在 `sub` 與 `groups`

### Worker
- Celery
- 負責背景 ingest / indexing 工作
- 處理 parse、chunk、embed、FTS preparation、status transition

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

### 3. `documents.status = ready` 才可檢索
- `uploaded`
- `processing`
- `ready`
- `failed`

只有 `ready` 可進入 retrieval / chat。

### 4. phase-by-phase 實作
- 骨架完成前不實作完整 business logic
- auth / areas / documents / retrieval / chat 按階段前進

## 未來資料流

### 文件上傳流程
1. Web 上傳檔案
2. API 驗證請求並建立 `documents` / `ingest_jobs`
3. API 將原始檔存入 MinIO
4. Worker 執行 parse / chunk / embed / FTS preparation
5. Worker 更新狀態為 `ready` 或 `failed`

### 問答流程
1. Web 發送 chat request
2. API 驗證 JWT 與 area scope
3. Retrieval 先套 SQL gate
4. 執行 vector recall + FTS recall
5. 用 RRF 合併候選
6. 用 Cohere rerank
7. 用 LLM 生成回答與 citations
8. API 以 SSE 或 HTTP 回傳前端

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
- `pages`：路由層頁面
- `components`：可重用元件
- `lib`：API / config / types

### `infra`
- `docker-compose.yml`
- service Dockerfiles
- Keycloak bootstrap assets
