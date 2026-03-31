# API 模組

[English README](README.md)

## 模組目的

此模組包含專案的 FastAPI 服務。它目前提供：
- 最小 landing route 與 health route
- JWT / Keycloak 驗證骨架
- `sub` / `groups` claims 解析
- Knowledge Area create/list/detail 最小切片
- area access management API
- area access-check 驗證切片
- documents upload / list / detail API
- ingest jobs detail API
- LangGraph Server built-in thread/run chat runtime
- SQLAlchemy ORM 模型與 metadata

## 啟動方式

- 本機 Python 執行：
  - `python -m venv .venv && source .venv/bin/activate`
  - `pip install -e .[dev]`
  - (註：Alembic 是唯一正式 schema migration 來源；無論 fresh 或既有 PostgreSQL，都先執行 `python -m app.db.migration_runner` 再啟動 API)
  - `langgraph dev --config langgraph.json --host 0.0.0.0 --port 18000 --no-browser`
- 本機執行測試：
  - `pytest`
- Docker Compose：
  - `docker compose -f ../../infra/docker-compose.yml --env-file ../../.env up api`

## 環境變數

- `API_SERVICE_NAME`
- `API_VERSION`
- `API_HOST`
- `API_PORT`
- `API_CORS_ORIGINS`
- `DATABASE_URL`
- `DATABASE_ECHO`
- `REDIS_URL`
- `STORAGE_BACKEND`
- `MINIO_ENDPOINT`
- `MINIO_ACCESS_KEY`
- `MINIO_SECRET_KEY`
- `MINIO_SECURE`
- `MINIO_BUCKET`
- `LOCAL_STORAGE_PATH`
- `MAX_UPLOAD_SIZE_BYTES`
- `CELERY_BROKER_URL`
- `CELERY_RESULT_BACKEND`
- `EMBEDDING_PROVIDER`
- `EMBEDDING_MODEL`
- `EMBEDDING_DIMENSIONS`
- `OPENAI_API_KEY`
- `RERANK_PROVIDER`
- `RERANK_MODEL`
- `COHERE_API_KEY`
- `RERANK_TOP_N`
- `RERANK_MAX_CHARS_PER_DOC`
- `ASSEMBLER_MAX_CONTEXTS`
- `ASSEMBLER_MAX_CHARS_PER_CONTEXT`
- `ASSEMBLER_MAX_CHILDREN_PER_PARENT`
- `RETRIEVAL_VECTOR_TOP_K`
- `RETRIEVAL_FTS_TOP_K`
- `RETRIEVAL_MAX_CANDIDATES`
- `RETRIEVAL_RRF_K`
- `RETRIEVAL_HNSW_EF_SEARCH`
- `KEYCLOAK_URL`
- `KEYCLOAK_ISSUER`
- `KEYCLOAK_JWKS_URL`
- `KEYCLOAK_GROUPS_CLAIM`
- `AUTH_TEST_MODE`
- `CHAT_PROVIDER`
- `CHAT_MODEL`
- `CHAT_MAX_OUTPUT_TOKENS`
- `CHAT_TIMEOUT_SECONDS`
- `CHAT_INCLUDE_TRACE`
- `CHAT_STREAM_CHUNK_SIZE`
- `CHAT_STREAM_DEBUG`
- `LANGGRAPH_SERVICE_PORT`
- `LANGSMITH_TRACING`
- `LANGSMITH_API_KEY`
- `LANGSMITH_PROJECT`
- `LANGSMITH_ENDPOINT`
- `LANGSMITH_WORKSPACE_ID`

## 主要目錄結構

- `src/app/main.py`：FastAPI 應用程式進入點
- `src/app/core`：設定與共用執行期輔助元件
- `src/app/auth`：JWT 驗證、principal 解析與 auth dependency
- `src/app/chat`：Deep Agents 主 agent、agent tools 與 LangGraph runtime glue
- `src/app/db`：SQLAlchemy models、session 與 metadata
- `src/app/routes`: HTTP routes
- `src/app/services`：授權、storage、task dispatch、internal retrieval 與 assembler service
- `langgraph.json`：LangGraph Server 內建 thread/run runtime 的 loader 設定
- `tests`：授權與 API 測試

## 對外介面

- `GET /`
- `GET /health`
- `GET /auth/context`
- `POST /areas`
- `GET /areas`
- `GET /areas/{area_id}`
- `PUT /areas/{area_id}`
- `DELETE /areas/{area_id}`
- `GET /areas/{area_id}/access`
- `PUT /areas/{area_id}/access`
- `GET /areas/{area_id}/access-check`
- `POST /areas/{area_id}/documents`
- `GET /areas/{area_id}/documents`
- `GET /documents/{document_id}`
- `POST /documents/{document_id}/reindex`
- `DELETE /documents/{document_id}`
- `GET /ingest-jobs/{job_id}`

## 疑難排解

- 若 API 行程無法啟動，請先確認已安裝 `langgraph-cli[inmem]`，且 `apps/api` 內存在 `langgraph.json`。
- 若本機只想跑測試，可啟用 `AUTH_TEST_MODE=true`，以 `Bearer test::<sub>::<group1,group2>` 驗證 auth flow。
- `GET /areas/{area_id}`、`PUT /areas/{area_id}`、`DELETE /areas/{area_id}` 與 `GET /areas/{area_id}/access` 對未授權與不存在資源都會回 `404`，此為 deny-by-default 的既定語意。
- `AUTH_TEST_MODE=true` 常搭配 `STORAGE_BACKEND=filesystem` 供 API 測試使用；Playwright E2E 應一併啟動 API 與 worker。
- upload 與 reindex route 只負責建立 `documents=status=uploaded` 與 `ingest_jobs=status=queued`；parse、chunking、indexing 與最終狀態推進都由 worker 負責。
- reindex、delete 與新的 ingest 執行前都會先清理文件範圍內的 `artifacts/` 前綴，避免殘留舊 parse 產物。
- area delete 採 hard delete；API 會先清掉 area 內每份文件的原始檔與 parse artifacts，再刪除 area 與 cascaded database rows。
- `document_chunks` 已包含 `structure_kind=text|table`，供後續 retrieval 與 observability 直接辨識內容結構。
- 文字 child 會以 `LangChain RecursiveCharacterTextSplitter` 切分；表格 child 則採整表保留或 row-group split。
- `ready` 現在代表 chunk tree、embedding 與可供 PGroonga 使用的 retrieval content 都已完成。
- 本模組目前已具備 internal retrieval foundation，涵蓋 SQL gate、vector recall、PGroonga FTS recall、Python 層 `RRF`、minimal rerank 與 table-aware retrieval assembler，但尚未公開為 HTTP API。
- assembler 會將 rerank 後的 child chunks 組裝為 chat-ready contexts 與 citation-ready metadata，並以 budget guardrails 控制成本。
- rerank 預設可用 `RERANK_PROVIDER=deterministic` 做離線測試；正式 compose 建議改用 `RERANK_PROVIDER=cohere` 並提供 `COHERE_API_KEY`。
- 本模組目前只啟用 LlamaParse 的標準 Markdown 轉換路徑，未來才會再評估 agentic mode。
- 未支援格式仍維持受控 `failed`。
- chat 現已透過 LangGraph Server built-in thread/run endpoints 與 custom auth 提供；retrieval pipeline 仍維持 SQL gate 與 ready-only 邊界後才進入 answer layer。
