# ROADMAP

## 專案總覽

本專案採分階段實作，原則是：
- 先完成可執行骨架
- 再補 auth / data / upload / retrieval / chat
- 每一階段都維持最小可運作、可驗證、可延伸

## Phase 0 — Project Skeleton

目標：
- 建立 repo 與本機開發環境骨架

內容：
- Monorepo structure
- FastAPI skeleton
- React skeleton
- Celery worker skeleton
- Docker Compose
- Postgres base image
- Redis
- MinIO
- Keycloak
- README / env / health wiring

狀態：
- `已完成`

## Phase 1 — Auth & Platform Foundations

目標：
- 建立後續 business logic 需要的基礎能力

內容：
- API settings 分層
- DB session / migration skeleton
- Keycloak JWT 驗證 skeleton
- `sub` / `groups` claim 解析
- auth middleware / dependency 基礎
- shared contracts 規整
- `GET /auth/context` 驗證切片
- `GET /areas/{area_id}/access-check` 驗證切片
- 真實 Keycloak token 與 group-based access 的本機驗證手冊

狀態：
- `已完成`

## Phase 2 — Areas

目標：
- 使用者可以看到自己可存取的 Knowledge Areas
- 此階段以最小可驗證垂直切片為主，不包含完整 Areas CRUD

內容：
- area schema
- create area
- creator becomes admin
- effective role calculation
- list accessible areas
- area-level access placeholders
- read area detail
- area access management
- web 手動 token 驗證頁
- web Keycloak login / callback / logout flow
- Playwright E2E 基礎設施與 smoke/regression coverage

狀態：
- `已完成`

## Phase 3 — Documents & Ingestion

目標：
- 可上傳文件並完成背景處理

內容：
- upload API
- MinIO store
- `documents` / `ingest_jobs`
- worker status transitions
- parser / chunking skeleton
- embedding / FTS placeholders

狀態：
- `已完成（MVP 垂直切片，含 XLSX worksheet table-aware parsing）`
- 補充：PDF provider 已擴充為 `opendataloader | local | llamaparse`，其中 `opendataloader` 為目前預設路徑

## Phase 3.5 — Document Lifecycle Hardening & Chunk Tree Foundation

目標：
- 讓文件 ingest 不只更新狀態，也能產出可供後續 retrieval 使用的 parent-child chunk tree

內容：
- `document_chunks` SQL-first schema
- `TXT/MD` parent-child chunk tree writer
- 保留 custom parent section builder，child chunk 採 `LangChain RecursiveCharacterTextSplitter`
- document delete / reindex
- ingest job stage 與 chunk observability
- Files UI chunk summary、reindex、delete
- API / worker / E2E 驗證補齊

狀態：
- `已完成`

## Phase 3.6 — Table-Aware Chunking for Markdown + HTML

目標：
- 讓 `document_chunks` 能辨識表格結構，而不是把表格當一般文字切分

內容：
- block-aware parser / chunking contract（`ParsedDocument`、`ParsedBlock`）
- `document_chunks.structure_kind` SQL-first 欄位
- Markdown table-aware parent sectioning
- 最小 HTML parser 與 HTML table-aware chunking
- table preserve / row-group split 策略
- `CHUNK_TABLE_PRESERVE_MAX_CHARS`、`CHUNK_TABLE_MAX_ROWS_PER_CHILD`
- API / worker table-aware 回歸測試

狀態：
- `已完成`

## Post-Phase 3 Backlog — Area Management Hardening

目標：
- 在 Documents MVP 穩定後補強 area 管理能力，但不阻擋主流程推進

內容：
- area rename / update
- area delete
- 補齊完整 Areas CRUD 的 API、UI 與測試

狀態：
- `已完成`

## Phase 4.1 — Retrieval Foundation

目標：
- 建立可驗證的 ready-only hybrid recall foundation

內容：
- SQL authorization gate
- PGroonga 繁體中文檢索整合
- `document_chunks.embedding` / `content` schema
- worker ingest indexing
- vector recall
- FTS recall (PGroonga)
- RRF merge
- internal retrieval service

狀態：
- `已完成`

## Phase 4.2 — Retrieval Ranking & Assembly

目標：
- 讓 recall 結果能進一步收斂為可供 chat 使用的高品質候選

內容：
- rerank integration
- retrieval trace metadata
- table-aware retrieval assembler
- chat-ready context 與 citation-ready metadata contract
- assembler budget guardrails 與 trace

狀態：
- `已完成`

## Phase 5.1 — Chat MVP & One-Page Dashboard

目標：
- 使用者可在一頁式戰情室 (Dashboard) 內進行多輪問答，並即時管理文件與權限。

內容：
- **一頁式戰情室 (Dashboard) UI 重構 (已完成)**
- LangGraph Server 啟動與 `langgraph.json`
- LangGraph built-in thread/run 與 custom auth
- LangGraph SDK 前端 transport 與 `area_id -> thread_id` 多輪 thread UX
- Deep Agents 主 agent + 單一 `retrieve_area_contexts` tool
- assembled-context level citations / references contract
- `messages-tuple`、`custom`、`values` stream contract
- `phase` / `tool_call` custom event UI 與 `messages-tuple` token stream
- tool 輸入/輸出與 assembled contexts 的可縮放檢視

狀態：
- `已完成`

## Phase 6 — Cloud Migration & Supabase Transition

目標：
- 將專案資料層遷移為 Supabase / PGroonga / pgvector 兼容架構，同時維持本機 Docker Compose 與地端自架路徑。
- 以 Supabase 為核心資料庫架構，利用其 **SaaS 官方原生支援 PGroonga** 的優勢，解決雲端託管資料庫無法安裝 `pg_jieba` 的限制。

預期效果：
- **高品質中文檢索 (SaaS 支援)**：Supabase Cloud 內建 PGroonga，可提供比 N-gram 更精準的繁體中文分詞檢索，且無需自行維護詞庫檔。
- **大幅降低維運成本**：移除本機維護 Postgres (pg_jieba) 的複雜度與資源消耗，保留既有 Keycloak / MinIO 自架能力。
- **檢索效能與演進平衡**：將 SQL gate、向量召回與全文召回下放到資料庫層，最終 `RRF` 與未來 ranking policy 保留在 Python 層，以支援 business rules 擴充。
- **架構彈性**：核心綁定 Supabase 資料層，正式 auth/storage 路徑仍為 Keycloak + MinIO/filesystem。

里程碑內容 (Milestones)：
1. **Database & Retrieval 重構 (Supabase Core) (已完成)**
   - 引入 Supabase PostgreSQL 並啟用 `pgvector` 與 `PGroonga`。
   - 捨棄自編譯的 `pg_jieba`，將 FTS 語法轉換為 PGroonga `&@~` 運算子。
   - 撰寫 Supabase RPC (PostgreSQL Function)，只負責 `Metadata Filtering` + `Vector Search` + `FTS` 的候選召回與排序輸入輸出；最終 `RRF` 保留在 Python。
2. **Runtime 收斂 (已完成)**
   - 撤回未接線的 multi-provider auth/storage staged 內容，正式路徑維持 Keycloak + MinIO/filesystem。
   - 恢復 Alembic 作為既有資料庫升級路徑，直到專用 migration runner 落地。
3. **前端與 Worker 部署 (已完成)**
   - Web 部署至 Vercel/Netlify；API 與 Worker 容器化部署至 AWS Fargate 或 Cloud Run。
4. **環境清理與解耦完成 (Final Cleanup) (已完成)**
   - **移除純 PostgreSQL 依賴**：完整移除現有 `infra/docker/postgres` 中維護成本極高的自編譯 `pg_jieba` 映像檔與相關 Dockerfile。
   - **簡化 Infra 管理**：將 Supabase 核心元件完整併入 `docker-compose.yml` 統一管理，達成單一編排工具啟動所有基礎設施的輕量化目標，降低對外部 CLI 工具的依賴。
狀態：
- `已完成`

## Phase 6.1 — Public HTTPS Entry & Migration Bootstrap Hardening

目標：
- 讓部署入口、Keycloak 公開 URL 與既有資料庫升級流程對齊目前正式的自架模型。

內容：
- 新增 `Caddy` 作為唯一對外 `80/443` 入口，統一路由 `/`、`/api/*`、`/auth/*`
- 將 Keycloak 公開 base path 固定為 `/auth`，並以 `KEYCLOAK_EXPOSE_ADMIN` 控制 `/auth/admin*` 是否對外可達
- 將 web / api / keycloak 的公開 URL 與 compose 預設環境變數改為 `PUBLIC_HOST` 單一來源
- 新增 `python -m app.db.migration_runner`，作為 fresh 與既有資料庫共用的 Alembic 升級入口
- 補上 `WEB_ALLOWED_HOSTS`、瀏覽器非 secure context 的 PKCE fallback，以及 Windows Marker worker 安裝 / 啟動腳本

狀態：
- `已完成`

## Milestone 規則

- 每個 phase 至少要有一個可驗證的垂直切片
- 不得在上一階段尚未穩定前大幅展開下一階段
- 若某 phase 被拆成更小的子階段，需同步更新 `PROJECT_STATUS.md`
- benchmark-driven 調整必須先通過 anti-domain-overfit 檢查；分數提升若依賴 domain-specific heuristic，不得進主線

## 近期建議順序

1. 以 `2026-04-05` 的 current `production_like_v1` snapshot 固定九資料集 baseline，正式以 `generic_v1 + 9x3000` 作為後續所有 benchmark-driven 調整的唯一比較基準
2. `Phase 8A` 已以 closeout accepted 方式結束；summary/compare 的 unified Deep Agents 主線與其 checkpoint artifacts 保留作為後續 phase 的 baseline
3. `Phase 8B` enrichment lane 已取消並移除；後續不得再以已移除的 enrichment schema、query-time merge lane 或查詢改寫 lane 作為 summary/compare 改善前提
4. `Phase 8C` 改為 agentic evidence-seeking loop：讓主 `Deep Agents` agent 在初次 retrieval 證據不足時，可受控查看已授權 `ready` 文件名稱、讀取 selected synopsis hints，再以文件 scope 多次補 retrieval
5. 8C 的 synopsis 只作為文件選擇與檢索規劃 hint，不得作為 citation payload、SQL scope 的唯一依據或最終回答證據；最終答案仍必須引用 assembled `parent/child` evidence contexts
6. benchmark 驅動優化仍先聚焦 `QASPER 100` 的 `recall_only` semantic-gap 問題；同時把 `NQ 100` 視為 assembler / synthesis materialization regression 哨兵、`DRCD 100` 視為繁體中文 rerank regression 哨兵
7. 補齊真實 `PUBLIC_HOST + Caddy + Keycloak /auth` 的 smoke 與 E2E 驗證，確認正式部署路徑不影響 retrieval / evaluation / chat
8. 補強 area management 與 access / documents / chat / evaluation 狀態切換交界的回歸驗證

## Phase 7 — Retrieval Correctness Evaluation

目標：
- 建立獨立於最終 LLM 回答品質的 retrieval correctness evaluation，專注評估正確 `source span / chunk / assembled context` 是否被找對、排對、組對。
- 本 phase 明確不以 answer wording、answer completeness 或 answer faithfulness 作為主要評分對象。
- 第一版評估範圍先鎖定 `fact_lookup`，以控制標註成本並建立穩定的 retrieval benchmark。
- retrieval correctness evaluation 必須同時涵蓋繁體中文、英文與必要時的中英混合查詢。

內容：
- 正式 benchmark corpus 以自家文件為主，不以外部 benchmark 作為第一版主資料來源。
- benchmark 文件需走正式 ingest pipeline，並以系統內的 `display_text` 作為標註與 offset 對齊基準。
- 建立 retrieval evaluation dataset，第一版只覆蓋 `fact_lookup` query。
- 長期 gold truth 以 source span 保存，而非直接綁定某一版 chunk 或 assembled context。
- 主評分單位固定採 `assembled context`，以對齊目前實際送進 LLM 的 context 單位；評分前由程式將 gold source spans 映射到當前版本的 chunk 與 assembled context。
- dataset 標註需保留 source-span traceability，可追回原始 `document / parent / child chunks`。
- relevance 標註採簡化 graded relevance，第一版至少支援：
  - `3`：核心證據
  - `2`：可接受但非最佳證據
  - `0`：不相關
- 標註流程採半自動對齊 + 人工複核，而非純人工從零搜尋。
- 系統需先為每題 `fact_lookup` query 產生 top candidates，供標註者快速複核。
- 人工複核介面不得假設正確答案一定出現在 top 3~5；除快速複核入口外，還需提供 fallback：
  - 展開更多候選（例如 top 20）
  - 文件內搜尋
  - 直接在全文中框選正確 source span
  - 將案例標記為 `retrieval_miss`
- 建立 retrieval-only benchmark runner，分層輸出至少以下階段的結果：
  - recall
  - rerank
  - assembled contexts
- 至少量測以下 retrieval metrics：
  - `nDCG@k`
  - `Recall@k`
  - `MRR@k`
  - `Precision@k`
  - `Document Coverage@k`
- 指標報表需可按以下維度切分：
  - `zh-TW`
  - `en`
  - `mixed`
  - `fact_lookup`
  - `recall / rerank / assembled` pipeline stage
- benchmark 輸出先以離線報表為主，至少包含：
  - summary metrics
  - per-query 明細
  - 與 baseline run 的 regression compare
- per-query 明細需能看出正確證據首次出現的 rank，以及是否屬於 `retrieval_miss`。
- Phase 7 完成後需固定一組 retrieval profile 作為 baseline；後續 `Phase 8.*` 的 retrieval profile、selection、synopsis 或 synthesis 相關調整，都應回到本 phase benchmark 比較 span/chunk/context ranking 與 coverage 是否退化。

狀態：
- `已完成（v1：Full Reviewer UI + CLI-first runner + baseline compare + 單機 E2E）`

本 phase 已交付：
- SQL-first evaluation schema：`retrieval_eval_datasets`、`retrieval_eval_items`、`retrieval_eval_item_spans`、`retrieval_eval_runs`、`retrieval_eval_run_artifacts`
- area-scoped API：dataset/item/span/run CRUD、candidate preview、`retrieval_miss`、run report
- CLI：`python -m app.scripts.run_retrieval_eval prepare-candidates|run|report`
- reviewer UI：`EvaluationDrawer`，提供 dataset 建立、`fact_lookup` 題目、候選複核、文件內搜尋、span 標註與 benchmark report
- metrics：`nDCG@k`、`Recall@k`、`MRR@k`、`Precision@k`、`Document Coverage@k`
- baseline compare：新 run 完成後可與 dataset baseline run 比較 summary / per-query 差異
- 單機自測：`api + worker + web` 本機啟動，SQLite + filesystem + deterministic providers，可直接執行 Playwright E2E reviewer flow

目前 benchmark 現況：
- 目前長期 benchmark 已收斂為七個正式 dataset，且共同 current baseline 以 `2026-04-05` 的 `production_like_v1` snapshot 為準；正式主線設定固定為 `generic_v1 + assembler 9x3000`，舊小樣本 package 與舊查詢改寫實驗分數只保留歷史參考價值，不再作為 current mainline baseline。
- `QASPER 100`、`UDA 100` 與 `DRCD 100` 的原始資料集 contract 都包含指定文件上下文；目前 benchmark runner 已改為對這三類 dataset 使用 gold span 的 `document_id` 作為指定文件 scope，再執行 child recall / rerank / assembler。這些指定文件結果不得與舊的 area-wide ambiguous query 分數混讀。
- external `100Q` 六資料集的最新 assembled 指標如下：
  - `DuReader-robust 100`：`Recall@10=1.0000`、`nDCG@10=0.9677`、`MRR@10=0.9570`
  - `MS MARCO 100`：`Recall@10=1.0000`、`nDCG@10=0.9674`、`MRR@10=0.9550`
  - `DRCD 100`（指定文件）：`Recall@10=1.0000`、`nDCG@10=0.8894`、`MRR@10=0.8517`
  - `NQ 100`：`Recall@10=0.7500`、`nDCG@10=0.7443`、`MRR@10=0.7425`
  - `UDA 100`（指定文件）：`Recall@10=0.7900`、`nDCG@10=0.6537`、`MRR@10=0.6104`
  - `QASPER 100`（指定文件）：`Recall@10=0.9300`、`nDCG@10=0.5905`、`MRR@10=0.4813`
- 目前依 assembled 指標來看，`DuReader-robust 100` 與 `MS MARCO 100` 已接近 ceiling，較適合作為 sanity check；真正仍在拉低 external hard lane 的主因仍是 `QASPER 100`。
- `NQ 100` 已補出一條與 `QASPER` 不同的壓力測試 lane：`rerank` 幾乎接近 ceiling，但 `assembled` 仍顯著掉分，代表 wiki 長段落 evidence 的 materialization / budget 仍需特別關注。
- `DRCD 100` 目前更適合作為繁體中文 rerank regression 哨兵，而不是下一輪主優化目標；`DuReader-robust 100` 則應維持近 ceiling 中文 sanity check 角色，不應拿來主導策略方向。
- 後續所有 benchmark-driven 調整都必須先在目前 baseline 上建立 before / after；若新策略造成退化，除分析文件外其餘改動一律回退；若提升，則需重新分析最新 miss 題與當前 chunks，再決定下一輪假設。

後續改善重點：
- 主優先方向仍是以 generic-first 方式處理 `QASPER 100` 在指定文件後仍存在的 evidence-field semantic-gap miss；舊的 area-wide QASPER 低分主要反映缺少原始 paper scope，不再作為純 evidence retrieval 的主判斷。
- 第二優先觀測點是 `NQ 100` 的 `rerank_hit_but_assembled_miss` 與 `assembled_only` 題目，用來驗證 assembler 是否在高品質 rerank 命中的 wiki 長段落上過度裁切。
- 第三優先觀測點是 `DRCD 100` 的中文 rerank regression；任何新 lane 若讓近乎到頂的 lexical candidate set 反而掉分，應直接視為失敗。
- `DuReader-robust 100` 與 `MS MARCO 100` 應維持為近 ceiling sanity check，不作為下一輪優化方向的主依據。
- benchmark 主流程預設只顯示最新 completed run，但資料庫仍保留歷史 run 以供回歸比較與異常追查；若要做穩定 regression gate，仍應補一條 deterministic evaluation profile，避免真實 provider rate limit 與暫時性外部失敗污染品質判讀。

## Phase 8.1 — Query-Aware Retrieval Profiles

目標：
- 讓 retrieval 不再只依賴單一固定 `top_n -> rerank -> assemble` 路徑，而能依問題型態切換不同策略。
- 先以 benchmark 驅動方式收斂 `fact_lookup` 的 generic-first profile lane，再逐步補齊「事實查詢 vs 文件摘要 vs 跨文件比較」三類主要問答場景的最小能力。
- 本 phase 的 query-aware retrieval 必須同時支援台灣繁體中文與英文，不可只以單一語言調參後視為完成。

內容：
- 在 chat / retrieval 入口新增 query intent classification，至少區分：
  - `fact_lookup`
  - `document_summary`
  - `cross_document_compare`
- query intent classification、retrieval profile 與 trace metadata 必須可覆蓋繁體中文 query、英文 query，以及中英混合關鍵詞的真實使用情境。
- 依 query type 套用不同 retrieval profile，而不是共用同一組固定參數。
- 本 phase 僅建立 routing/profile/trace skeleton，不取得 document-level synopsis，也不宣稱已完成 summary / compare 的文件級語意表示。
- rollout 順序以 `fact_lookup` 優先；在 `fact_lookup` lane 穩定前，不擴大 summary / compare 的 runtime 複雜度。
- `fact_lookup` 維持現有 precision-first 路線，但需把 generic-first 的 candidate lane registry 顯式化。
- `document_summary` 提高 recall coverage，允許較大的候選集與較寬鬆的 assembled context budget。
- `cross_document_compare` 在本 phase 只提供 skeleton profile，不在此階段保證跨文件 coverage；真正的 diversity guardrail 留給 `Phase 8.2`。
- 將 profile 相關參數顯式設定化，例如：
  - recall candidate 上限
  - rerank top-n
  - assembler contexts 上限
- 每個新 profile lane 都必須直接對 current baseline 比較，且至少同時觀測 `QASPER 100`、`NQ 100` 與 `DRCD 100`；若造成 assembler 或中文 rerank 哨兵退化，應回退。
- retrieval trace metadata 需補上 query type、routing source/confidence 與所套用 profile；查詢改寫欄位與環境設定已自正式 contract 移除。

狀態：
- `已完成（routing/profile/trace skeleton）`

## Phase 8.2 — Diversified Selection Before Assembly

目標：
- 在不破壞 SQL gate、deny-by-default 與 ready-only 保護前提下，提升摘要 / 比較問題的文件覆蓋率。
- diversified selection 的策略與 guardrails 必須同時適用於繁體中文與英文查詢，不得只以中文檢索分布校調。

內容：
- 在 RRF / rerank 之後、assembler 之前，新增 diversified selection layer。
- `document_summary` 在本 phase 先新增第二層 routing：`single_document | multi_document`；scope 由 area-scoped、ready-only 的 deterministic document mention resolver 解析，不依賴 UI/runtime hint，也不讓 deep-agent 直接提供 `document_id`
- `document_summary_single_document_diversified_v1` 先將候選限縮到唯一高信心命中的文件，再在單一文件內做 parent-level diversity
- `document_summary_multi_document_diversified_v1` 採 `coverage pass + fill pass`：先保留多文件代表 parent，再依 rerank 排名補位；在所有入選文件都尚未拿到第二個 parent 前，不讓單一文件先拿第三個 parent
- `cross_document_compare_diversified_v1` 採 `coverage pass #1 -> coverage pass #2 -> score-first fill pass`；先保證每文件至少有代表 parent，再依 rerank 排名補位，不設「兩文件最多 4 parents」的硬上限
- selection trace 補上：
  - `summary_scope`
  - `resolved_document_ids`
  - document mention source / confidence / candidates
  - 被保留的文件數
  - 每文件採信的 parent 數
  - 因 diversity guardrail 被淘汰的候選
- 測試補齊多文件 coverage 與單文件壟斷退化案例。

狀態：
- `已完成`

## Phase 8.3 — Document-Level Representations

目標：
- 補齊文件級任務所需的高階語意表示，避免系統只能以 child chunk 作為唯一召回單位。
- document-level representation 必須可支撐繁體中文與英文文件，不得只對單一語言建立 synopsis 品質假設。

內容：
- 在 ingest pipeline 為每份 `ready` 文件建立 document-level synopsis。
- document-level synopsis 的正式取得時機固定為 upload ingest 與 reindex pipeline 內，而不是在 query 當下臨時生成。
- 本 phase 明確不做 section-level synopsis，避免在尚未驗證 document-level 路徑前過早擴張索引與成本。
- document synopsis 需保持 SQL-first 可查詢與可觀測，不可只存在暫時記憶體。
- retrieval 新增兩階段策略：
  - 第一階段先做 document-level recall，找出值得深入的文件集合
  - 第二階段再於入選文件內做既有 parent / child recall 與 assembler
- document synopsis 應涵蓋：
  - 主題
  - 重要章節
  - 主要結論
  - 可辨識的表格 / 結構重點
- synopsis 生成、embedding 與更新策略需明確驗證繁體中文與英文文件的品質、成本與 reindex 一致性。
- 評估 synopsis 的 embedding、更新時機、reindex 一致性與失敗回復策略。
- section-level synopsis 若未來要做，需等 document-level recall 的品質與成本先被驗證後，再另立 phase 規劃。

狀態：
- `已完成（closeout 已以 DRCD / NQ / QASPER sentinel rerun、public-entry smoke 與 document recall observability 驗證；其中 QASPER 100 的輕微退化被接受為可承受代價）`

## Phase 8A — Unified Deep Agents Summary / Compare Stabilization

### Phase 8 Query Flow Overview

本段落用來收斂 Phase 8 之後的 query-time 主線資料流，避免各 phase 各自描述卻缺少整體路徑。

共同原則：
- 正式 retrieval 主線目前以 `child hybrid recall -> rerank -> diversified selection -> assembler` 為準，並以 routing scope / mention scope 做 SQL-first 收斂。
- `document synopsis` 與 `section synopsis` 都不是最終 citation 單位；它們若存在，最多只屬於 ingest-side 表示或未來 optional enhancement。
- 最終 citation 一律回到 `child chunk / source span`；`parent` 只作為 materialization 邊界。
- 送進 LLM 的正式主體必須是 assembled `parent/child` evidence contexts；任何 hints 都只能是次要輔助。
- 正式 routing 模型採 2 層，而不是平面 5 類：
  - 第一層 `task_type`：`fact_lookup | document_summary | cross_document_compare`
  - 第二層 `summary_strategy`：僅在 `task_type=document_summary` 時啟用，至少支援 `document_overview | section_focused | multi_document_theme`

建議 route-by-route 主線如下：
- 第一層 `task_type=fact_lookup`
  - 主線：`child hybrid recall -> parent-level rerank -> assembler`
- 第一層 `task_type=document_summary` + 第二層 `summary_strategy=document_overview`
  - 主線：`routing scope -> child hybrid recall -> rerank -> diversified selection -> assembler -> unified Deep Agents answer`
  - overview 的摘要責任由主 `Deep Agents` agent 根據 assembled contexts 完成，不再依賴 query-time synopsis recall
- 第一層 `task_type=document_summary` + 第二層 `summary_strategy=section_focused`
  - 主線：`document scope resolve -> child hybrid recall -> rerank -> diversified selection -> assembler -> unified Deep Agents answer`
- 第一層 `task_type=document_summary` + 第二層 `summary_strategy=multi_document_theme`
  - 主線：`routing scope -> child hybrid recall -> rerank -> diversified selection -> assembler -> unified Deep Agents answer`
- 第一層 `task_type=cross_document_compare`
  - 主線：`routing scope -> child hybrid recall -> rerank -> diversified selection -> assembler -> unified Deep Agents answer`

LLM 輸入規則：
- 預設只送 assembled `parent/child` evidence contexts 給 LLM。
- `document synopsis` 與 `section synopsis` 若未來重新接回 runtime，也只應以 selected / compressed hints 形式送入，不得與 citation-ready contexts 混成同權重主體。
- 不得將 `document synopsis` 或 `section synopsis` 直接當作最終 citation payload。

目標：
- 以較少 phase 快速穩定 `document_summary` / `cross_document_compare` 的 unified Deep Agents answer path。
- 把舊 `8.4 ~ 8.6` 收斂為單一交付批次：一次完成正式 task routing、unified answer path、selection contract 與最小 evaluation checkpoint。
- summary/compare 的正式產品能力，以主 `Deep Agents` agent 搭配 `retrieve_area_contexts` tool 的端到端表現為準。

內容：
- 在 LangGraph chat runtime 將 `fact_lookup`、`document_summary` 與 `cross_document_compare` 統一到同一條主 `Deep Agents` answer path。
- `thinking_mode` 前後端欄位短期保留為相容 metadata，但不再決定 answer lane。
- 保留 worker 已落地的 `document synopsis` / `section synopsis` 生成與持久化，但它們不再屬於 `Phase 8A` query-time 依賴。
- 正式 task routing 收斂為 2 層統一 classifier framework：
  - 第一層 `task_type`：`fact_lookup | document_summary | cross_document_compare`
  - 第二層 `summary_strategy`：僅在 `task_type=document_summary` 時啟用，至少支援 `document_overview | section_focused | multi_document_theme`
  - 兩層都採 `deterministic anchors -> embedding classifier -> LLM fallback`
  - `LLM fallback` 輸入僅限 query、language、document mention summary 與 label options，不得讀全文、不得改寫 query
- rollout 優先順序以快速交付為原則：
  - 先穩定 `document_summary`
  - `document_overview` 與 `section_focused` 優先於 `multi_document_theme`
  - `cross_document_compare` 在 `8A` 先以保守 coverage-first 版本落地，不導入額外 enrichment 依賴
- 本 phase 不新增 enrichment schema、獨立 enrichment table 或新的 ingest stage。
- citation contract 需維持可追溯到原始 document / parent / child chunks，不可只引用中間摘要節點。
- trace metadata 需至少補上：
  - `task_type`
  - `task_type_source / confidence`
  - `summary_strategy`
  - `summary_strategy_source / confidence`
  - `answer_path`
  - `thinking_mode`
  - `thinking_mode_ignored`
  - fallback reason
  - retrieval / assembler 的主要 candidate 與 selection 摘要
- 對比較型問題定義較穩定的輸出結構，例如：
  - 共通點
  - 差異點
  - 各文件立場 / 結論
  - 不足證據或矛盾處
- `Phase 8A` 的 exit criteria 內建最小 evaluation checkpoint 與 guardrails，不再額外拆成獨立 phase：
  - 建立摘要 / 比較專用 evaluation set，覆蓋：
  - 單長文件摘要
  - 多文件共同主題摘要
  - 多文件差異比較
  - 文件間互相矛盾資訊
- evaluation set 需同時包含繁體中文、英文與中英混合 query，避免 profile 只對單一語言穩定。
- 量測與追蹤至少以下指標：
  - 文件覆蓋率
  - citation 覆蓋率
  - synthesis completeness
  - answer faithfulness
  - map / reduce token 成本
  - 回答延遲
- guardrails 至少限制：
  - 最大入選文件數
  - 最大 map / reduce token 預算
  - synopsis 長度
  - 比較型問題的每文件 context 配額
- 本 checkpoint 至少覆蓋：
  - unified Deep Agents answer path 的 completeness / faithfulness / latency
  - `task_type` accuracy
  - `summary_strategy` accuracy
  - 文件 / citation / section coverage
  - fallback rate
- 將 evaluation 結果回饋到 prompt、selection、routing 與 tool contract 調整，避免單次 heuristic 長期失真。
- `fact_lookup` 的 retrieval-only benchmark、evidence ranking 與 `nDCG@k / Recall@k / MRR@k` 等指標，由 `Phase 7 — Retrieval Correctness Evaluation` 統一負責。

狀態：
- `已完成（closeout accepted；已保留 unified answer path、兩層 routing 與 CLI-first checkpoint artifacts 作為後續 baseline。最新 accepted 驗收 run 雖未滿足原先全部 gate，但經產品決策接受目前 ceiling，8A 不再繼續調參收分）`
- `2026-04-10` 以目前 task routing / unified Deep Agents 主線重跑 `phase8a-summary-compare-v1`：`task_type_accuracy=1.0000` 已滿分，但整體仍為 `passed=false`，`summary_strategy_accuracy=0.9375`，未過 gate 主要來自 hard blockers 與 `p95_latency_seconds=31.4785` 超過 `30.0000` 門檻；因此此 run 作為 post-closeout regression 記錄，不改變 8A 已結案且不繼續調分的判定

## Phase 8B — Canceled Retrieval Enrichment Lane

目標：
- 取消先前規劃的 enrichment lane，將正式 retrieval 主線維持在 `child hybrid recall -> rerank -> diversified selection -> assembler`。
- 移除已落地的 worker 生成流程、query-time merge、evaluation trace、設定與 schema，降低 ingest 成本與 runtime 複雜度。
- 後續 retrieval 改善必須優先基於既有 child chunks、document scope、rerank 與 selection，不得依賴已移除的 enrichment tables 或查詢改寫 lane。

內容：
- 移除 worker enrichment module 與相關環境設定。
- 移除 API retrieval 的 query-time merge lane、trace 欄位、evaluation preview stage 與 profile lane。
- 移除 ORM model、schema guard 要求與 documents observability 欄位。
- 以 Alembic migration 回收已建立的資料表與欄位。
- 保留 `document synopsis` 與 opt-in `section synopsis` 既有能力；它們不得成為 citation payload。

狀態：
- `已取消並移除（後續工作回到 child-based retrieval hardening 與 benchmark regression guardrails）`

## Phase 8C — Agentic Evidence-Seeking Loop for Summary / Compare

目標：
- 讓 `document_summary` 與 `cross_document_compare` 在初次 retrieval 證據不足時，能由主 `Deep Agents` agent 以受控方式補查文件範圍與證據。
- 將既有 `document synopsis` / opt-in `section synopsis` 定位為文件選擇與 retrieval planning hints，而不是 recall gate、selection gate、citation 單位或最終回答證據。
- 改善 `phase8a-summary-compare-v1` 中仍存在的 required document coverage、insufficient evidence acknowledgement 與 faithfulness 問題，同時避免 p95 latency 與 token budget 繼續惡化。

內容：
- 新增 agent 可見但安全受控的文件清單工具，例如 `list_authorized_ready_documents`：
  - 僅回傳目前使用者在該 area 已授權且 `status=ready` 的文件名稱與短期 handle
  - 不回傳全文、不回傳非 ready 文件、不暴露未授權文件是否存在
  - 仍以 SQL gate / deny-by-default / same-404 為保護邊界
- 新增 agent 可見的 synopsis inspection / ranking 工具，例如 `inspect_document_synopses` 或 `rank_document_synopses`：
  - 只允許查詢已授權且 `ready` 的文件
  - synopsis 僅作為 orientation / planning hint
  - synopsis 不得產生 citation，不得直接餵成最終答案依據
  - 輸出需控制長度、文件數與呼叫次數
- 將 `retrieve_area_contexts` 從單次零參數快取模型演進為 bounded multi-call retrieval：
  - agent 第一次仍以原始問題做 area-scoped retrieval
  - 若 assembled contexts 對必要文件、章節或比較軸覆蓋不足，可依工具回傳的短期 handle 指定一份或多份文件做 scoped retrieval
  - scoped retrieval 必須在後端重新驗證 handle 對應的 area、使用者權限與 `ready` 狀態，再轉成 SQL `allowed_document_ids`
  - 不允許 agent 直接提供原始 `document_id` 作為權限繞路
- 加入 loop guardrails：
  - 每回合最大 retrieval 呼叫次數
  - 每回合最大 synopsis inspection 次數
  - 每次 scoped retrieval 的最大文件數
  - 全回合 token budget、context budget 與 latency budget
  - 無新增 evidence 時停止補查，並要求回答明確標示證據不足
- 最終回答規則：
  - 最終 citation 一律來自 scoped retrieval 回傳的 assembled contexts
  - synopsis hints、文件名稱清單與 agent planning trace 不得成為 citation
  - 若某個比較面向或文件沒有 citation-ready evidence，回答必須明確說明證據不足，不得用 synopsis 補結論
- trace / evaluation 需補上：
  - 初次 retrieval 與每次 scoped retrieval 的 tool call summary
  - 文件清單工具是否被呼叫、回傳文件數與被選文件 handles
  - synopsis hint 是否被使用、其來源文件與壓縮長度
  - 每次補查帶來的新文件 / section / citation coverage
  - 停止補查原因
- 驗證方式：
  - 先以 `phase8a-summary-compare-v1` 建立 before / after，比較 `required_document_not_cited`、`insufficient_evidence_not_acknowledged`、faithfulness、overall score 與 p95 latency
  - 同步跑 `QASPER 100`、`NQ 100`、`DRCD 100` regression 哨兵，避免 summary/compare 的 agentic loop 破壞 generic-first retrieval 主線
  - 若品質沒有穩定提升，或 latency / token 成本超過 gate，應回退 runtime 改動，只保留分析文件

狀態：
- `未開始（已改為 agentic evidence-seeking loop 路線；下一步是設計工具契約、guardrails 與 checkpoint before / after 驗證）`
