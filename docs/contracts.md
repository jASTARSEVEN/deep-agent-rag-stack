# Contract 地圖

## 文件目的

本文件集中整理本專案目前最重要的 contract。它用來協助外部專案理解「哪些資料形狀與行為不可任意更動」，也協助本專案未來重構時判斷哪些邊界必須先 freeze。

本文件不取代實際程式碼、OpenAPI schema、Alembic migration 或測試；正式來源仍以程式與 migration 為準。

## Contract 分層

本專案的 contract 可分為六層：

- 身分與授權 contract
- REST API contract
- Chat runtime contract
- Retrieval tool contract
- Ingest / chunking contract
- DB / migration contract

所有 contract 的共同原則：
- 不得破壞 deny-by-default。
- 不得讓未授權使用者透過錯誤細節推測資源存在。
- 不得讓 `status != ready` 的文件進入 retrieval、chat、preview 或 benchmark 候選。
- 不得讓 agent 或前端直接覆寫 SQL gate 後的資料範圍。

## 身分與授權 Contract

JWT claims：
- `sub`：使用者唯一識別。
- `groups`：Keycloak group path 清單，建議使用完整 group path。

角色：
- `reader`
- `maintainer`
- `admin`

Effective role：
- 使用者直接角色與 Keycloak group 映射角色中的最大值。
- 無角色代表沒有有效權限。

授權行為：
- 無有效角色時，受保護資源應回 same-404。
- 角色不足但資源已在授權邊界內時，可回 403。
- 真正授權必須在 API service / SQL 查詢層完成，前端隱藏按鈕不算授權。

主要程式位置：
- `apps/api/src/app/services/access.py`
- `apps/api/src/app/auth/verifier.py`
- `apps/api/src/app/auth/dependencies.py`

## REST API Contract

REST contract 的正式來源是 FastAPI OpenAPI schema。

匯出方式：

```bash
cd apps/api
python -m app.scripts.export_openapi --output -
```

前端型別產生方式：

```bash
cd apps/web
npm run generate:rest-types
```

前端 drift 檢查：

```bash
cd apps/web
npm run check:rest-types
```

主要 payload 類別：
- `AuthContextResponse`
- `AreaSummaryResponse`
- `AreaAccessManagementResponse`
- `DocumentSummary`
- `DocumentPreviewResponse`
- `ChatSessionSummaryResponse`
- `EvaluationCandidatePreviewResponse`
- `EvaluationRunReportResponse`

主要程式位置：
- `apps/api/src/app/schemas/*.py`
- `apps/api/src/app/routes/*.py`
- `apps/web/src/generated/rest.ts`

重構注意事項：
- Route 應維持薄層，業務規則放 service。
- 若 response shape 改變，必須同步 regenerate frontend types。
- 若 API shape 改變但前端 generated types 沒更新，`npm run build` 應失敗。

## Chat Runtime Contract

Chat runtime contract 的正式來源是 `app.chat.contracts.types`。

匯出方式：

```bash
cd apps/api
python -m app.scripts.export_chat_contracts --output -
```

前端型別產生方式：

```bash
cd apps/web
npm run generate:chat-types
```

前端 drift 檢查：

```bash
cd apps/web
npm run check:chat-types
```

核心 contract：
- `ChatRuntimeResult`
- `ChatAnswerBlock`
- `ChatCitation`
- `ChatAssembledContext`
- `ChatMessageArtifact`
- `ChatTrace`
- `ChatPhaseEventPayload`
- `ChatToolCallEventPayload`
- `ChatReferencesEventPayload`

LangGraph stream 事件：
- `messages-tuple`：正式 token delta 來源。
- `custom.phase`：高層狀態，例如 preparing、searching、drafting。
- `custom.tool_call`：工具輸入與 debug-safe 輸出。
- `custom.references`：assembled context references。
- `values`：最終 answer、citations、assembled contexts 與 message artifacts。

主要程式位置：
- `apps/api/src/app/chat/contracts/types.py`
- `apps/api/src/app/chat/agent/runtime.py`
- `apps/api/src/app/chat/runtime/langgraph_agent.py`
- `apps/web/src/generated/chat.ts`
- `apps/web/src/features/chat/transport/langgraph.ts`

重構注意事項：
- `message_artifacts` 必須能支援 reload 後還原 answer blocks 與 citation chips。
- `ChatCitation` 與 `ChatAssembledContext` 必須保留 document、chunk、offset 與 locator 欄位，供 UI preview 使用。
- Tool debug output 可以精簡，但 graph `values` 的正式 payload 不應降級。

## Retrieval Tool Contract

對 Deep Agents 暴露的正式 retrieval capability 是單一 `retrieve_area_contexts` tool。

Public tool 輸入可包含：
- `question`
- `task_type` 提示
- `document_scope` 提示
- `summary_strategy` 提示
- `query_variant`
- `document_handles`
- `inspect_synopsis_handles`
- `followup_reason`

Public tool 不可包含：
- raw `document_id`
- SQL filter 條件
- vector / FTS / rerank 內部參數
- 可繞過後端 routing 的完整 profile override

Tool 輸出包含：
- `assembled_contexts`
- `citations`
- `planning_documents`
- `coverage_signals`
- `next_best_followups`
- `evidence_cue_texts`
- `synopsis_hints`
- `loop_trace_delta`
- `trace`

安全前置條件：
- Tool 必須先載入已授權且 ready 的文件集合。
- `document_handles` 只能解析到已授權 ready 文件。
- Benchmark/test-only `allowed_document_ids_override` 不得從 public tool 入口傳入。
- Agent 回答不得用 synopsis hints 補成沒有 citation-ready evidence 的結論。

主要程式位置：
- `apps/api/src/app/chat/tools/retrieval.py`
- `apps/api/src/app/chat/tools/retrieval_planning.py`
- `apps/api/src/app/chat/tools/retrieval_serialization.py`
- `apps/api/src/app/services/retrieval_runtime.py`
- `apps/api/src/app/services/retrieval_types.py`

## Retrieval Pipeline Contract

正式 retrieval runtime 分為六個階段：

1. `routing`
2. `recall`
3. `rerank`
4. `selection`
5. `assembler`
6. `tool serialization`

階段責任：
- `retrieval_routing`：query type、document scope、summary strategy 與 effective settings。
- `retrieval_recall`：PostgreSQL RPC、SQLite fallback、vector recall、FTS recall 與 RRF 輸入。
- `retrieval_rerank`：minimal ranking policy、parent-level rerank 與 fail-open。
- `retrieval_selection`：scope-aware diversified selection。
- `retrieval_assembler`：parent/materialization/citation-ready contexts。
- `chat.tools.retrieval_serialization`：tool payload、LLM payload 與 UI citation payload。

不可變條件：
- Recall 只能查 `documents.status = 'ready'`。
- Recall 只能查 `chunk_type = child`。
- SQL gate 必須在候選回到使用者或 agent 前完成。
- Rerank fail-open 只能回退排序，不得放寬 SQL gate、same-404 或 ready-only。
- Assembler 不得擴張 SQL gate 後的資料集合。

主要程式位置：
- `apps/api/src/app/services/retrieval_runtime.py`
- `apps/api/src/app/services/retrieval_recall.py`
- `apps/api/src/app/services/retrieval_rerank.py`
- `apps/api/src/app/services/retrieval_selection.py`
- `apps/api/src/app/services/retrieval_assembler.py`
- `apps/api/src/app/services/retrieval_types.py`

## Ingest / Chunking Contract

Parser 輸出：
- `ParsedDocument`
- `ParsedBlock`
- `ParsedRegion`
- `ParseArtifact`

Chunker 輸出：
- `ChunkingResult`
- `ChunkDraft`
- `SectionDraft`
- `SectionComponent`

資料庫輸出：
- `documents.normalized_text`
- `documents.display_text`
- `document_chunks`
- `document_chunk_regions`
- `documents.synopsis_text`
- `documents.synopsis_embedding`
- `documents.synopsis_updated_at`

生命週期：
- API 建立 document 時狀態為 `uploaded`。
- Worker 接手後狀態改為 `processing`。
- Chunk tree、embedding 與必要 synopsis 成功後才可標為 `ready`。
- 失敗時必須標為 `failed`，並清除可檢索 chunks。

主要程式位置：
- `apps/worker/src/worker/parsers.py`
- `apps/worker/src/worker/chunking.py`
- `apps/worker/src/worker/tasks/ingest.py`
- `apps/worker/src/worker/tasks/indexing.py`
- `apps/worker/src/worker/db.py`

重構注意事項：
- Parser provider 可替換，但必須回到 `ParsedDocument` contract。
- `display_text` 必須和 child chunk offsets 對齊。
- `table` chunk 可以重複表頭，但 offset 仍必須可對回 display text。
- Reindex 應維持 replace-all 語意。

## DB / Migration Contract

正式 schema 來源：
- `apps/api/alembic/versions/*.py`
- `apps/api/src/app/db/models.py`

Worker 會定義最小 ORM mirror：
- `apps/worker/src/worker/db.py`

啟動檢查：
- API schema guard：`apps/api/src/app/db/schema_guard.py`
- Worker schema guard：`apps/worker/src/worker/schema_guard.py`

升級入口：

```bash
cd apps/api
python -m app.db.migration_runner
```

資料庫重要 contract：
- `areas`
- `area_user_roles`
- `area_group_roles`
- `documents`
- `ingest_jobs`
- `document_chunks`
- `document_chunk_regions`
- `area_chat_sessions`
- `retrieval_eval_*`

重構注意事項：
- API 與 Worker 的 enum / model mirror 需要同步治理。
- 新增 Worker 會寫入或讀取的欄位時，Worker schema guard 也應同步檢查。
- 不應重新引入 Alembic 與其他 migration 系統雙軌。

## Evaluation / Benchmark Contract

Retrieval evaluation contract：
- Dataset、item、span、run 與 artifact 都是 SQL-first。
- Gold truth 長期來源是 source spans，不直接綁定某版 chunk id。
- 評分階段至少包含 recall、rerank、assembled。

Summary/compare benchmark contract：
- 正式 answer path 必須走 chat runtime。
- Report 固定輸出 run metadata、aggregate metrics、gate results、per-item results、judge scores 與 hard blockers。
- Offline judge 只替換 judge 執行方式，不替換 runtime answer path。

Benchmark-only 例外：
- 部分外部資料集可使用指定文件 scope。
- 指定文件 scope 必須先驗證 area、權限與 `ready`。
- 此能力不得開放給 public chat。

主要程式位置：
- `apps/api/src/app/evaluation/retrieval/*`
- `apps/api/src/app/evaluation/summary_compare/*`
- `apps/api/src/app/scripts/run_retrieval_eval.py`
- `apps/api/src/app/scripts/run_summary_compare_checkpoint.py`
- `apps/api/src/app/scripts/run_summary_compare_benchmark.py`

## Contract 驗證入口

建議重構前後至少執行：

```bash
cd apps/api
pytest tests/test_contract_shapes.py
pytest tests/test_auth_access.py
pytest tests/test_retrieval.py
pytest tests/test_chat_retrieval_tool.py
```

```bash
cd apps/worker
pytest tests/test_ingest_task.py tests/test_parsers.py tests/test_indexing.py
```

```bash
cd apps/web
npm run build
```

若是 retrieval 或 benchmark 相關重構，還應依任務性質跑對應 benchmark baseline compare。

