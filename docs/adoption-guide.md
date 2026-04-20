# 外部專案採用指南

## 文件目的

本文件提供其他專案參考本專案架構時的採用順序。它不是安裝教學，而是說明如何把本專案的設計拆成可逐步移植的能力，避免一開始就複製完整複雜度。

適合讀者：
- 想在既有產品加入文件問答能力的團隊
- 想從零建立自架式 RAG 平台的團隊
- 想借用本專案授權、ingest、retrieval 或 chat 架構的工程負責人

## 採用原則

採用此架構時，請先保護業務與安全語意，再增加 retrieval 品質與 agent 能力。

建議原則：
- 先做安全邊界，再做好看的 UI。
- 先做穩定資料生命週期，再做複雜 ranking。
- 先讓 contract 可測，再拆 service 或抽 shared package。
- 先做單一路徑，再加 provider abstraction。
- 先用自家文件驗證，再引入外部 benchmark。

## 推薦採用順序

### Step 1：建立身份與 Area 權限模型

先實作：
- 使用者登入。
- JWT 驗證。
- `sub` 與 `groups` claims。
- Knowledge Area。
- Area direct user role。
- Area group role。
- Effective role 計算。

最小角色：
- `reader`
- `maintainer`
- `admin`

此階段完成標準：
- 建立者自動成為 area admin。
- 使用者只能列出自己有權限的 areas。
- 無有效角色時，API 不回傳受保護資料。
- 授權邏輯集中在 service / SQL 層，而不是前端。

不建議此階段做：
- 文件上傳。
- Chat。
- Retrieval。
- Evaluation。

### Step 2：建立 Document Lifecycle

再實作：
- 文件上傳 API。
- 原始檔 storage。
- `documents` table。
- `ingest_jobs` table。
- Celery 或等價背景工作。
- 狀態轉換：`uploaded -> processing -> ready | failed`。

此階段完成標準：
- 只有 `maintainer` 以上能上傳。
- Reader 可列文件但不可上傳。
- Job 狀態可查。
- 失敗原因可觀測。
- 文件未 ready 前不能被 preview、retrieval 或 chat 使用。

不建議此階段做：
- 多 parser provider。
- OCR。
- 串流 ingest。
- 文件層級 ACL。

### Step 3：建立 Parser 與 Chunk Tree Contract

接著建立文件解析與 chunking 邊界。

建議 contract：
- Parser 統一輸出 `ParsedDocument`。
- `ParsedDocument` 內含 normalized text、source format 與 blocks。
- Chunker 統一輸出 parent-child chunk tree。
- Parent 是 assembly 邊界。
- Child 是 recall 最小單位。
- `display_text` 是 preview 與 citation offset 基準。

此階段完成標準：
- TXT/MD 至少可產出穩定 parent-child chunks。
- Child chunks 有 stable position、section index、child index 與 offsets。
- Failed ingest 會清除可檢索 chunks。
- Reindex 採 replace-all，避免殘留舊 chunk。

可延後：
- PDF 高保真表格。
- DOCX/PPTX/XLSX。
- Table-aware row group。
- PDF bounding boxes。

### Step 4：建立 Ready-Only Retrieval Foundation

再加入檢索。

建議最小 pipeline：
- SQL gate。
- Ready-only filter。
- Vector recall。
- FTS recall。
- RRF merge。
- Internal-only retrieval service。

此階段完成標準：
- Recall SQL 永遠限制 area 與 ready 文件。
- 無權使用者無法取得任何 candidate。
- `status != ready` 的文件不會出現在 candidate。
- 先能回傳 candidates 與 trace，不急著接 LLM。

可延後：
- Cohere / Hugging Face rerank。
- Scope-aware selection。
- Table-aware assembler。
- Document synopsis。

### Step 5：加入 Rerank 與 Assembler

當 recall 穩定後，再處理品質。

建議加入：
- Parent-level rerank。
- Rerank top-n 與 max chars guardrails。
- Fail-open fallback。
- Parent-level assembler。
- Citation-ready metadata。
- Assembled context budget。

此階段完成標準：
- Rerank 失敗只影響排序，不影響授權邊界。
- Assembler 不擴張 SQL gate 後的資料集合。
- Citation 可以對回 document、parent、child 與 offset。
- 送進 LLM 的 context 數量與字元數受控。

### Step 6：接 Chat Runtime

再接 agent 或 LLM runtime。

建議採用：
- 單一 retrieval tool。
- Agent 不直接碰 vector / FTS / rerank。
- Tool 輸出 assembled contexts 與 citations。
- 回答使用 citation marker。
- 前端用 answer blocks 與 citation chips 顯示。

此階段完成標準：
- Public chat 不接受 raw `document_id` override。
- Agent 無法繞過 SQL gate。
- 回答 citations 只來自 ready 文件。
- Reload 後仍可還原回答與 citations。

### Step 7：加入 Contract Generation

正式接前端後，應加入 contract generation。

建議保留：
- REST OpenAPI export。
- Chat runtime schema export。
- Frontend generated types。
- Build-time drift check。
- Contract shape tests。

此階段完成標準：
- 後端 response shape 改變時，前端 type check 或 generated check 會失敗。
- Chat stream / values payload 有測試鎖住。
- Contract 文件與實作對齊。

### Step 8：加入 Evaluation 與 Benchmark

最後再做品質治理。

建議先做：
- 自家 fact lookup dataset。
- Gold source spans。
- Recall / rerank / assembled stage metrics。
- Baseline compare。
- Per-query miss analysis。

再逐步加入：
- 外部 benchmark curation。
- Summary / compare checkpoint。
- Offline judge workflow。
- 多語言與 hard lane benchmark。

此階段完成標準：
- Benchmark 不會繞過產品安全邊界。
- Benchmark-only 指定文件 scope 不會進 public chat。
- 新策略必須與 baseline before/after 比較。
- 任何安全邊界退化都直接視為失敗。

## 不建議一開始複製的部分

以下能力有價值，但不適合作為第一輪採用目標：
- 多資料集 external benchmark curation。
- Summary/compare 雙語 benchmark scoring lane。
- Offline judge packet workflow。
- 多 provider embedding / rerank 矩陣。
- PDF provider 三路徑完整支援。
- LlamaParse / OpenDataLoader artifact reuse。
- Agentic follow-up loop。
- Document synopsis / section synopsis planning hints。
- Public HTTPS + Caddy + Keycloak 完整部署 hardening。

如果核心產品尚未穩定，過早加入這些能力會放大維護成本。

## 最小 MVP 切片

若外部專案只想做最小可用版本，建議切片如下：

1. Keycloak 或等價 OIDC 登入。
2. Area + direct user role。
3. Group role 可先保留資料表但不開 UI。
4. TXT/MD 上傳。
5. Worker 產生 parent-child chunks。
6. Deterministic 或 OpenAI embedding。
7. Vector recall + ready-only SQL gate。
8. 簡單 assembler。
9. Chat answer + citations。
10. Contract tests。

此 MVP 可先不做：
- PDF/DOCX/PPTX/XLSX。
- PGroonga。
- Rerank。
- Evaluation UI。
- Benchmark suite。
- Agentic loop。

## 常見移植錯誤

常見錯誤：
- 用前端控制取代後端授權。
- 先查全部文件再在記憶體過濾。
- 讓非 ready 文件被 retrieval 查到。
- 把 document id 直接交給 agent 或 public chat。
- 沒有 response contract，前後端靠人工同步 payload shape。
- Parser 對每種格式輸出不同資料形狀，導致 chunker 充滿特例。
- Rerank 失敗時吞錯但沒有 trace，造成 benchmark 誤判。
- Benchmark 為了分數加入 corpus-specific heuristic。
- 沒有 baseline compare 就調 retrieval 策略。

## 導入檢查清單

安全檢查：
- 是否所有受保護 route 都經過 service 層 access check？
- 是否未授權與 missing resource 維持 same-404？
- 是否只有 `ready` 文件可進 retrieval？
- 是否 public chat 不接受 raw document ids？

資料檢查：
- 是否有 document status lifecycle？
- 是否 failed ingest 會清掉可檢索 chunks？
- 是否 `display_text` 與 chunk offsets 對齊？
- 是否 migration 是單一路徑？

Contract 檢查：
- 是否能匯出 REST OpenAPI？
- 是否有 chat payload schema？
- 前端是否使用 generated types？
- CI 或 build 是否檢查 generated type drift？

品質檢查：
- 是否有最小 retrieval tests？
- 是否有 deny-by-default tests？
- 是否有 ready-only tests？
- 是否有 rerank fallback tests？
- 是否有 benchmark baseline compare？

## 與本專案保持差異的建議

其他專案不需要完全照搬本專案。

可以替換：
- Keycloak 可替換成其他 OIDC provider，但 claims contract 應固定。
- MinIO 可替換成 S3/GCS/Azure Blob，但 storage key lifecycle 應固定。
- PGroonga 可視語言需求替換，但不可引入與產品邊界衝突的 fuzzy search。
- LangGraph 可替換成其他 agent runtime，但應保留單一 retrieval tool 邊界。
- Cohere / Hugging Face / self-hosted rerank 可依成本與部署條件替換。

不建議替換：
- SQL gate 作為主要授權邊界。
- Ready-only retrieval。
- Parent-child chunk tree 的基本 contract。
- Generated contract types。
- Baseline-driven retrieval changes。

