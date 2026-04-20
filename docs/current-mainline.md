# 目前正式主線

## 文件目的

本文件用一頁式摘要說明本專案目前正式主線。它協助外部讀者快速判斷「今天應該看哪條路徑」，避免被歷史 phase、已取消實驗或 benchmark-only 能力混淆。

若本文件與根目錄長期文件不同步，應以 `Summary.md`、`ARCHITECTURE.md`、`PROJECT_STATUS.md` 與實際程式碼為準，並更新本文件。

## 產品主線

目前產品主線是：

- 自架式 NotebookLM 風格文件問答平台。
- 使用者登入後進入一頁式 Dashboard。
- 使用者在 Knowledge Area 內管理文件與提問。
- 文件來源只支援上傳檔案。
- 問答必須附 citations。
- 授權以 Keycloak group 與 direct user role 計算 effective role。
- Retrieval 只在 area scope 內運作。

目前不做：
- NotebookLM workspace / studio 類功能。
- 文件層級 ACL。
- OCR / 掃描 PDF。
- 上傳期間串流 ingest。
- `pg_trgm`。
- Multi-tenant / multi-realm。

## 技術主線

固定技術棧：
- API：Python + FastAPI。
- Worker：Celery + Redis。
- Database：PostgreSQL / Supabase + pgvector + PGroonga。
- Storage：MinIO 或 filesystem。
- Auth：Keycloak。
- Web：React + Tailwind。
- Chat runtime：LangGraph Server + Deep Agents。
- Retrieval orchestration：Python service layer。
- LLM / embedding / rerank：OpenAI、Hugging Face、自架 OpenAI-compatible provider、Cohere optional。
- Local orchestration：Docker Compose。
- Public entry：Caddy。

## 安全主線

不可退化的安全規則：
- Deny-by-default。
- JWT claims 使用 `sub` 與 `groups`。
- Effective role 是 direct user role 與 group role 的最大值。
- 沒有有效角色者不得取得受保護資料。
- 未授權與不存在資源盡量維持 same-404。
- SQL gate 是主要保護層。
- 不可以先查全量資料再在記憶體過濾。
- 只有 `status = ready` 的文件可以 preview、retrieval、chat 或 evaluation。
- Public chat 不接受 raw `document_id` override。

## Area / Documents 主線

Area：
- 建立者自動成為 `admin`。
- `reader` 可列文件、問答與看 citations。
- `maintainer` 可上傳、刪除、reindex 與看處理狀態。
- `admin` 可管理 area 與 access。

Documents：
- API 收檔並存 storage。
- API 建立 `documents` 與 `ingest_jobs`。
- Worker 負責 parse、chunk、embedding、indexing 與狀態轉換。
- Reindex 使用 replace-all chunk 語意。
- Delete 會清原始檔、parse artifacts、jobs 與 chunks。
- Preview 使用 `documents.display_text + child chunk map`。

正式支援檔案：
- PDF
- DOCX
- TXT / MD
- PPTX
- HTML
- XLSX

## Ingest 主線

正式 ingest path：

1. API 建立 `uploaded` document 與 `queued` job。
2. Worker 將 document/job 改為 `processing`。
3. Worker 解析文件，產生 `ParsedDocument`。
4. Worker 建立 parent-child chunk tree。
5. Worker 寫入 `documents.display_text`。
6. Worker replace-all 寫入 `document_chunks`。
7. Worker 產生 child embeddings。
8. Worker 產生 document synopsis。
9. Worker 成功後才標記 document `ready`。
10. Worker 失敗時標記 document `failed` 並清掉可檢索 chunks。

PDF 主線：
- 預設 `opendataloader`。
- `local` 只作 fallback。
- `llamaparse` 為 optional provider。

Chunk 主線：
- 固定 parent-child 兩層。
- Child 是 recall 最小單位。
- Parent 是 assembler materialization 邊界。
- Markdown / HTML / XLSX / 可辨識 table 的 DOCX/PPTX 走 table-aware chunking。
- TXT 不做 table-aware。

## Retrieval 主線

目前正式 query-time retrieval 主線：

1. Document mention / scope resolver。
2. Layer 1 routing：`fact_lookup | document_summary | cross_document_compare`。
3. Layer 2 routing：只在 `document_summary` 下判斷 summary strategy。
4. Child hybrid recall。
5. Python RRF。
6. Minimal ranking policy。
7. Parent-level rerank。
8. Scope-aware selection。
9. Parent-level assembler。
10. Tool serialization。

正式路徑不使用：
- Query rewrite。
- Rerank-query rewrite。
- Evidence enrichment table。
- Query-time document synopsis recall。
- Query-time section synopsis recall。
- Agent 直接提供 routing 參數。
- Agent 直接提供 raw document ids。

## Chat 主線

目前正式 answer path：
- `deepagents_unified`
- Deep Agents 主 agent。
- 單一 `retrieve_area_contexts` tool。
- 前端使用 LangGraph SDK thread/run。
- 多輪記憶以 LangGraph thread state 為主。
- Session metadata 存在 `area_chat_sessions`。
- 回答引用用 `[[C1]]` marker 解析成 answer blocks。
- UI 顯示 citation chips 與右側全文 preview。

Chat stream 主線：
- Token delta 來自 `messages-tuple`。
- `custom.phase` 提供高層狀態。
- `custom.tool_call` 提供工具呼叫透明化。
- `values` 提供最終 answer / citations / assembled contexts / trace。

## Evaluation / Benchmark 主線

Retrieval evaluation：
- `app.evaluation.retrieval`
- 評分 recall、rerank、assembled stages。
- Gold truth 使用 source spans。
- 只作內部品質治理，不是 public product route。

Summary/compare checkpoint：
- `app.evaluation.summary_compare`
- 透過正式 chat runtime 取得 answers。
- `phase8a-summary-compare-v1` 是唯一產品 gate。
- `summary-compare-real-curated-v1` 是 tuning / observability suite。

Benchmark 原則：
- 先跑 baseline。
- 每輪只做單一主假設。
- 改動後重跑 benchmark。
- 若退化，除分析文件外回退改動。
- 不得為 benchmark 分數引入 domain overfit。

## Contract 主線

目前正式 contract 管理：
- REST contract 由 FastAPI OpenAPI 匯出。
- Chat contract 由 Pydantic / TypedDict schema 匯出。
- Web 使用 generated TypeScript types。
- `npm run build` 會檢查 REST 與 chat generated types 是否 drift。
- Contract shape tests 驗證 REST、LangGraph state、message artifacts 與 custom events。

主要入口：
- `python -m app.scripts.export_openapi`
- `python -m app.scripts.export_chat_contracts`
- `npm run generate:rest-types`
- `npm run generate:chat-types`
- `npm run check:rest-types`
- `npm run check:chat-types`

## 已取消或不應重啟的路徑

目前不應重新引入：
- Phase 8B enrichment lane。
- Evidence enrichment schema。
- Query-time enrichment merge lane。
- Query rewrite lane。
- Rerank-query rewrite lane。
- 以 synopsis 作為正式 recall stage。
- Public chat raw `document_id` override。
- `pg_trgm` fuzzy search。
- 文件層級 ACL。

## 外部讀者優先閱讀順序

若只想快速理解目前主線，建議順序：

1. 本文件。
2. `docs/reference-architecture.md`。
3. `docs/contracts.md`。
4. `docs/adoption-guide.md`。
5. 根目錄 `ARCHITECTURE.md`。
6. 根目錄 `Summary.md`。
7. 根目錄 `PROJECT_STATUS.md`。

若要實作或改程式，仍必須回到根目錄長期文件與對應模組 `AGENTS.md`。

