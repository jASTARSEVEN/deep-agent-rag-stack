# PROJECT_STATUS

## 專案概況

專案名稱：自架式 NotebookLM 風格文件問答平台  
目前定位：分階段實作中的 MVP  
固定技術棧：
- FastAPI
- PostgreSQL + pgvector + PGroonga (Supabase)
- Celery + Redis
- MinIO
- Keycloak
- React + Tailwind
- LangChain + LangGraph
- OpenAI
- Hugging Face Rerank (`BAAI/bge-reranker-v2-m3`, `Qwen/Qwen3-Reranker-0.6B`)
- Hugging Face Embedding (`Qwen/Qwen3-Embedding-0.6B`)
- Cohere Rerank v4 (optional)
- OpenAI-compatible self-hosted `/v1/rerank` / `/v1/embeddings` provider (optional)
- Docker Compose

## 目前狀態

當前主階段：`Post-Phase 8A — Child-Based Retrieval Hardening (In Progress)`

目前判定：
- `Phase 0` 核心骨架已完成
- `Phase 1` 授權與資料基礎骨架 MVP 已完成
- `Phase 2` Areas 垂直切片 MVP 已完成
- `Phase 3` Documents & Ingestion 垂直切片 MVP 已完成
- `Phase 3.5` Document lifecycle hardening 與 chunk tree foundation 已完成
- `Phase 3.6` Markdown / HTML 表格感知 chunking 已完成
- `Phase 4.1` Retrieval foundation 已完成
- `Phase 4.2` minimal rerank slice 已完成
- `Phase 4.2` table-aware retrieval assembler slice 已完成
- `Phase 5.1` Chat MVP on LangGraph Server 已完成
- `Phase 6` Supabase & PGroonga Migration 已完成
- `Phase 6.1` Public HTTPS Entry & Migration Bootstrap Hardening 已完成
- `Phase 7` Retrieval Correctness Evaluation v1 已完成
- `Phase 8.1` Query-Aware Retrieval Profiles routing skeleton 已完成
- `Phase 8.2` Diversified Selection Before Assembly 已完成
- `Phase 8.3` Document-Level Representations 已完成
- 專案已具備可驗證的 auth context、area create/list/detail 與 area access management 基礎能力
- 專案已具備 area update/delete 管理能力，涵蓋 admin-only rename、description update 與 hard-delete cleanup
- 專案已具備文件 upload、documents list、ingest job 狀態轉換與 Files UI 的最小主流程
- 專案已具備 document delete、reindex、chunk summary 與 parent-child chunk tree 最小主流程
- 專案已具備 ready-only 的 internal retrieval foundation，涵蓋 SQL gate、vector recall、FTS recall 與 RRF merge
- 專案目前 embedding 主線預設仍為 `openai / text-embedding-3-small`，retrieval schema 與 `match_chunks` RPC 固定使用 `1536` 維
- 專案已新增 `self-hosted` embedding provider，走 `POST /v1/embeddings` 與 Bearer auth；建議模型為 `Qwen/Qwen3-Embedding-0.6B`，較短向量會在寫入前補齊到 `1536` 維 schema
- 專案已新增本機 `Hugging Face Embedding` provider，建議模型為 `Qwen/Qwen3-Embedding-0.6B`；query 端會套用官方 instruction prompt，並使用目前 API / worker 行程的本機 CPU 或 GPU 資源推論
- `1536` 維主線仍位於 `pgvector` `hnsw` 可支援範圍，因此向量召回維持 ANN 路徑
- 專案已具備 internal-only 的 parent-level rerank 路徑，涵蓋 `Hugging Face` / Cohere / `self-hosted` / deterministic rerank provider、`Header:` / `Content:` 組裝、retrieval trace metadata 與 fail-open fallback
- 專案已將本機 rerank 命名收斂為通用 `Hugging Face Rerank` provider，支援 `BAAI/bge-reranker-v2-m3` 與 `Qwen/Qwen3-Reranker-0.6B`，並保留舊的 `bge` / `qwen` 設定值作為相容 alias
- 由於 runtime 預設仍以 `openai embedding + self-hosted/cohere rerank` 為主，`torch` / `transformers` 已改為 optional 依賴；只有在啟用本機 Hugging Face provider 時才需要安裝
- 專案已具備 internal-only 的 table-aware retrieval assembler，將 rerank 後 child chunks 組裝為 chat-ready contexts 與 citation-ready metadata
- assembler 已升級為 precision-first materializer：小 parent 直接回完整 parent，大 parent 以命中 child 為中心做 budget-aware expansion；table hit 會優先補齊完整表格與前後說明文字
- 專案已開始將 retrieval/assembler 收斂為單一 retrieval tool，供 LangGraph chat runtime 使用
- 專案已具備 LangGraph Server built-in thread/run chat runtime 與 Web chat UI
- 專案已具備 `phase`、`tool_call` 與工具輸入/輸出檢視的 chat custom event UI
- 專案已具備可選的 LangSmith tracing 與前後端 chat stream debug 設定，供 Phase 5.1 除錯與觀測使用
- 專案已具備 `documents.display_text` 全文持久化來源與 `GET /documents/{document_id}/preview`，供 ready-only 文件全文預覽與 chunk-aware UI 使用
- 專案已具備 retrieval correctness evaluation SQL-first schema、area-scoped dataset/item/span/run APIs，以及 CLI-first benchmark runner
- 專案已具備 `EvaluationDrawer` reviewer UI，可在 `/areas` 內建立 `fact_lookup` dataset、複核 recall/rerank/assembled 候選、標註 gold spans、標記 `retrieval_miss` 並檢視 run report
- 專案已具備 retrieval evaluation summary/per-query metrics、baseline compare 與 JSON artifact 持久化
- 目前 `Phase 7` 的 retrieval correctness evaluation 已擴充 additive `evidence_recall` stage 與 evidence trace 欄位，但正式 promotion gate 仍待用 `QASPER 100 / NQ 100 / DRCD 100 / phase8a-summary-compare-v1` 跑完後確認
- benchmark strategy governance 已收斂為「單一 evaluation profile registry + 單一 strategy lane registry」；未來新增策略應以 registry data 擴充，`retrieval_eval_runs` 與 artifacts 維持通用 schema，不新增策略專用欄位
- benchmark strategy governance 已將「不得造成 domain overfit」落成第一核心 guardrail：先檢查 generic-first，再看 benchmark 分數是否提升
- 已新增並更新 `docs/retrieval-benchmark-strategy-analysis.md`，整理 retrieval benchmark 的策略對照、三資料集綜合判讀與目前最高 ROI 改善建議
- 專案已將主線 retrieval default 收斂為 generic-first 策略組合：runtime 預設為 `self-hosted / BAAI/bge-reranker-v2-m3` + `retrieval_evidence_synopsis_enabled=true` + `retrieval_evidence_synopsis_variant=generic_v1`，並同步將 assembler budget 收斂到 sweet spot：`max_contexts=9` / `max_chars_per_context=3000` / `max_children_per_parent=7`
- benchmark 改善策略已改為：先實際跑分建立 baseline；若新策略退化，只保留分析文件，其餘改動一律回退；若新策略提升，則在保留改動的前提下重新分析 miss 題與當前 chunks，再決定下一輪最有價值策略
- benchmark 治理已同步改為 generic-first，不再保留查詢改寫 profile lane 或 benchmark-specific profile naming
- retrieval trace、evaluation preview 與 benchmark per-query detail 已移除查詢改寫相關欄位，後續語意落差診斷回到原始 query、routing、rerank 與 assembled contexts
- 舊小樣本 package 已自 current benchmark 集合移除，後續比較以正式 `100Q` 與自家 benchmark 為準
- 已新增 `apps/api/src/app/scripts/review_external_benchmark_with_openai.py`，可對 external benchmark workspace 直接執行 `OpenAI API` review，輸出 `review_overrides.jsonl` 與 `openai_review_log.jsonl`
- 已新增 `apps/api/src/app/scripts/prepare_uda_full_source.py`，可將官方 `UDA-Benchmark` `extended_qa_info_bench` 與 full-source docs 正規化為現有 `prepare_external_benchmark --dataset uda` 可直接使用的 JSONL row contract
- 已將 `apps/api/src/app/scripts/prepare_external_benchmark.py` 擴充為支援 `msmarco`、`nq`、`drcd` 與 `dureader`，可直接吃 `hf://microsoft/ms_marco/v1.1/validation`、`hf://google-research-datasets/natural_questions/default/validation`、`hf://voidful/DRCD/default/dev` 這類 Hugging Face dataset-server 參照，也可吃官方 `DuReader-robust` `dev.json` / `DuReader 2.0` 類本機 row contract，並沿用既有 `filter -> align -> OpenAI review -> build snapshot` 流程
- 已新增六份正式 external `100Q` package，且目前共同 baseline 以 `2026-04-05` 的 current `production_like_v1` snapshot 為準：
  - `benchmarks/dureader-robust-curated-v1-100`：官方 `DuReader-robust` `dev.json` wrapper、`220` prepared items、`220` filtered items、`220` auto-matched、`0` 個 `OpenAI` review overrides，最終 `100` 題 / `100` 份 paragraph 文件 / `100` 個 gold spans，最新 reference run assembled `Recall@10=1.0000`、`nDCG@10=0.9677`、`MRR@10=0.9570`
  - `benchmarks/msmarco-curated-v1-100`：官方 `MS MARCO v1.1` validation QA rows、`180` prepared items、`154` filtered items、`103` auto-matched、`47` 個 `OpenAI` review overrides，最終 `100` 題 / `100` 份 snippet-bundle 文件 / `114` 個 gold spans，最新 rerun assembled `Recall@10=1.0000`、`nDCG@10=0.9674`、`MRR@10=0.9550`
  - `benchmarks/drcd-curated-v1-100`：官方 `voidful/DRCD` `dev` split、`400` prepared items、`400` filtered items、`400` auto-matched、`0` 個 `OpenAI` review overrides，最終 `100` 題 / `6` 份繁體中文文件 / `100` 個 gold spans；目前 benchmark runner 會依 gold span 指定文件查詢，最新指定文件 run assembled `Recall@10=1.0000`、`nDCG@10=0.8894`、`MRR@10=0.8517`
  - `benchmarks/nq-curated-v1-100`：官方 `Natural Questions` validation rows、`260` prepared items、`250` filtered items、`250` auto-matched、`0` 個 `OpenAI` review overrides，最終 `100` 題 / `100` 份文件 / `100` 個 gold spans，最新 reference run assembled `Recall@10=0.7500`、`nDCG@10=0.7443`、`MRR@10=0.7425`
  - `benchmarks/uda-curated-v1-100`：官方 `UDA-QA` `nq` full-source 子集、`140` oversampled items、`102` auto-matched、無需 LLM review；目前 benchmark runner 會依 gold span 指定文件查詢，最新指定文件 run assembled `Recall@10=0.7900`、`nDCG@10=0.6537`、`MRR@10=0.6104`
  - `benchmarks/qasper-curated-v1-100`：`50` 篇 paper oversampling、`132` filtered items、`122` auto-matched、`2` 個 `OpenAI` review overrides；目前 benchmark runner 會依 gold span 指定文件查詢，最新指定文件 run assembled `Recall@10=0.9300`、`nDCG@10=0.5905`、`MRR@10=0.4813`
- 已將 `production_like_v1` benchmark profile 固定為目前主線設定；目前 current baseline 為 `generic_v1 + 9x3000`
- 已將 `task_type + summary_strategy` routing 收斂為統一 classifier framework：兩層都採 `deterministic anchors -> embedding classifier -> LLM fallback`，並保留 `source / confidence / embedding margin / fallback_used / fallback_reason` 可觀測欄位
- `Phase 8A` 的規劃已將 runtime routing 收斂為 2 層模型：第一層 `task_type` 為 `fact_lookup | document_summary | cross_document_compare`，第二層 `summary_strategy` 僅在 `document_summary` 下細分為 `document_overview | section_focused | multi_document_theme`
- 已新增 runtime retrieval profile registry，依 query type 套用 skeleton profile，並將 `query_type`、routing source/confidence、selected profile 與 resolved settings 寫入 retrieval trace、evaluation preview 與 benchmark per-query detail
- 已將 evaluation datasets / items / preview / run report / snapshot tooling 擴充為三種 query type，Web `EvaluationDrawer` 亦可建立並檢視三種題型
- 查詢改寫功能已自 runtime、settings、trace 與 evaluation profile lane 移除；routing skeleton 不再保留其相容欄位或 knobs
- 已為 `document_summary` 新增 `single_document | multi_document` 第二層 routing，透過 `documents.file_name` 的 deterministic mention resolver 解析單文件摘要與多文件摘要 scope，且只在已授權 `ready` 文件集合內運作
- 已在 `rerank -> assembler` 間新增 scope-aware diversified selection layer：`fact_lookup` 維持 bypass，`document_summary` 採 coverage-first + fill 策略，`cross_document_compare` 採雙輪 coverage pass 後再依 rerank 補位
- retrieval trace、chat tool output summary、evaluation preview 與 benchmark per-query detail 已新增 `summary_scope`、`resolved_document_ids`、document mention 與 selection metadata；`document_summary` 與 `cross_document_compare` 已不再停留在 skeleton profile
- 已為 `documents` 新增 SQL-first `synopsis_text`、`synopsis_embedding` 與 `synopsis_updated_at`，作為 document-level representation 的正式持久化欄位
- worker ingest / reindex 正式納入 document synopsis 生成：以全 parent coverage 壓縮後交給 LLM 產生 `synopsis_text`，再寫入 synopsis embedding；若 synopsis 生成或 embedding 失敗，文件不得進入 `ready`
- worker ingest / reindex 目前正式預設只生成 `document synopsis`；`section synopsis` 已改為 repo-wide opt-in，避免在主線與 benchmark 預設路徑增加成本
- `document_summary` 與 `cross_document_compare` 的 retrieval 正式主線已回到 `mention-scoped or area-scoped child recall -> rerank -> selection -> assembler`；`fact_lookup` 維持同一路徑
- retrieval routing 已將文件 mention scope 調整為與 `task_type` 正交：`fact_lookup` 若高信心提及已授權且 `ready` 文件，也會保留 `resolved_document_ids` 並用於 recall 收斂，不再只把 scope 視為 summary / compare 的附屬資訊
- Deep Agents 可見的 retrieval tool contract 已移除舊的單一 `retrieval_strategy`，且不再讓 agent 提供 `task_type`、`document_scope` 或 `summary_strategy`；三者保留為後端 router 的正交 trace / evaluation contract，實際文件白名單只由後端 mention resolver 在已授權且 `ready` 文件中解析
- `Phase 8B` 的 enrichment lane 已取消並移除：worker 不再生成該 enrichment，API 不再執行 query-time merge，evaluation / chat trace 不再輸出其欄位，schema 由 migration 回收
- `Phase 8A` 已將 query-time routing 正式擴充為 `task_type + summary_strategy`；`document_summary` 會依 query 與 scope 走 `document_overview | section_focused | multi_document_theme`
- `Phase 8A` routing 現已不再是單層 rule-only 決策；第一層 `task_type` 與第二層 `summary_strategy` 皆共用相同 routing engine，低信心時會正式啟用 `LLM fallback`
- `Phase 8A` routing 仍維持 `task_type + summary_strategy` 的兩層統一 classifier framework，但其下游正式主線已改為 unified `Deep Agents` answer path
- chat runtime 現在統一為單一路徑 `deepagents_unified`：`fact_lookup`、`document_summary` 與 `cross_document_compare` 都由主 `Deep Agents` agent 自行決定何時呼叫 `retrieve_area_contexts` 並完成回答
- `thinking_mode` 前後端欄位與 checkpoint metadata 仍保留相容，但後端不再用它分流；trace 只保留 `answer_path="deepagents_unified"`、`thinking_mode` 與 `thinking_mode_ignored`
- retrieval trace、chat tool output summary、evaluation preview 與 benchmark per-query detail 已移除 `document_recall`、`section_recall` 與 `selected_synopsis_level` 等 synopsis-stage contract
- `Phase 8A` 已新增 CLI-first 的 summary/compare evaluation checkpoint：`python -m app.scripts.run_summary_compare_checkpoint`
- checkpoint 會以固定 dataset 直接跑真實 chat runtime，再用 `LLM-as-judge` 評 `completeness / faithfulness / structure / compare_coverage`，並以 deterministic hard blockers 擋 `task_type`、`summary_strategy`、`ready-only citations`、必需文件覆蓋、timeout 與 token budget
- checkpoint run metadata 已新增固定 `answer_path="deepagents_unified"`，用來明確標示目前正式驗證的是主 Deep Agents answer path
- `Phase 8A` 目前的正式驗收定義已不再要求 query-time synopsis recall 或 summary/compare 專用 synthesis lane；驗收核心改為 unified Deep Agents path 是否能在固定 checkpoint 上穩定過線
- synopsis 的再利用目前不屬於 `Phase 8A` 或 `Phase 8B` 正式交付；`Phase 8C` 已改為 agentic evidence-seeking loop，synopsis 僅能作為文件選擇與補檢索 planning hint，不得作為 citation payload 或最終回答證據
- repo 已新增固定 benchmark package `benchmarks/phase8a-summary-compare-v1`，包含 `16` 題 summary/compare checkpoint fixtures 與對應 source documents
- `Phase 8A` 已完成最新一輪正式驗收 checkpoint；最新 accepted artifact 為 `parallel-6` runner 輸出，雖未通過原先 `passed=true` gate，但專案已判定目前優化接近現階段上限，因此接受當前 ceiling 並以現況結案
- 最新 accepted checkpoint 觀測值為：`task_type_accuracy=0.75`、`summary_strategy_accuracy=0.5`、`required_document_coverage=0.9062`、`citation_coverage=0.9062`、`section_coverage=0.9062`、`avg_completeness=4.8125`、`avg_faithfulness_to_citations=4.375`、`avg_structure_quality=4.875`、`avg_compare_coverage=4.625`、`avg_overall_score=4.6719`、`p95_latency_seconds=21.0378`
- `2026-04-10` 已用目前 task routing / unified Deep Agents 主線重跑 `phase8a-summary-compare-v1` 正式 checkpoint，artifact 位於 `artifacts/phase8a-summary-compare-report-20260410-task-routing.json`。最新結果確認 `task_type_accuracy=1.0000` 已滿分，但整體 `passed=false`，`summary_strategy_accuracy=0.9375`、`required_document_coverage=0.9062`、`citation_coverage=0.9062`、`section_coverage=0.9062`、`avg_faithfulness_to_citations=4.5625`、`avg_overall_score=4.6562`、`p95_latency_seconds=31.4785`；未過 gate 的主因為 `hard_blocker_failures=6` 與 `p95_latency_seconds` 超過 `30.0000` 門檻
- 此輪 `phase8a-summary-compare-v1` 未達「滿分」：失敗分布為 `summary_strategy_mismatch=1`、`required_document_not_cited=3`、`insufficient_evidence_not_acknowledged=2`，另有 judge 低分分類 `judge_low_faithfulness=5`、`judge_low_completeness=1`、`judge_low_coverage=1`
- 已完成 `Phase 8.3` closeout 所需的三條 sentinel rerun：
  - `DRCD 100`：assembled `nDCG@10` 由 `0.8650` 提升到 `0.9900`，`Recall@10` 由 `0.9700` 提升到 `0.9900`
  - `NQ 100`：assembled 指標與 reference 持平，`nDCG@10=0.7443`、`Recall@10=0.7500`
  - `QASPER 100`：assembled `nDCG@10` 由 `0.3797` 降至 `0.3739`、`Recall@10` 由 `0.5900` 降至 `0.5800`
- 依本輪結案判定，`QASPER 100` 的小幅回歸已被接受為可承受代價，因此 `Phase 8.3` 仍視為完成；相關 compare artifacts 保留於 `/tmp/phase83-sentinel-reruns/{drcd,nq,qasper}`
- 已於 `2026-04-05` 將長期 benchmark 文件收斂為七個正式 dataset：六個 external `100Q` package 加上自家 `tw-insurance-rag-benchmark-v1`；舊的 `UDA` / `QASPER` 小樣本 package 已移出 current benchmark 集合。目前 `QASPER 100`、`UDA 100` 與 `DRCD 100` 的 benchmark contract 已改為使用 gold span `document_id` 作為指定文件 scope，避免把原始資料集的文件上下文誤當成 area-wide ambiguous query。
- `docs/retrieval-benchmark-strategy-analysis.md` 已更新為七資料集 current 基線，並把 `External 100Q` 壓力測試集合維持為 `QASPER 100`、`UDA 100`、`MS MARCO 100`、`NQ 100`、`DRCD 100` 與 `DuReader-robust 100`
- 已完成 `QASPER 100`、`UDA 100`、`MS MARCO 100`、`NQ 100`、`DRCD 100` 與 `DuReader-robust 100` 的最新 external `100Q` 基線判讀：指定文件後 `QASPER 100` assembled `Recall@10=0.9300`、`nDCG@10=0.5905`、`MRR@10=0.4813`，證明舊 area-wide 低分主要混入 document disambiguation；`DRCD 100` 指定文件後 assembled `Recall@10=1.0000`、`nDCG@10=0.8894`、`MRR@10=0.8517`；`UDA 100` 指定文件後 assembled `Recall@10=0.7900`、`nDCG@10=0.6537`、`MRR@10=0.6104`。`NQ` 仍是 assembler 壓力測試 lane，`DuReader-robust` 與 `MS MARCO` 維持 sanity-check lane；舊的 [`docs/external-100q-miss-analysis-2026-04-04.md`](docs/external-100q-miss-analysis-2026-04-04.md) 仍保留舊版 `QASPER + UDA` 詳細 miss 清單
- `retrieval_text` 的 evidence synopsis 已升級為「語言無關 evidence categories + language profile registry」架構，正式支援 `en` 與 `zh-TW`，並保留未來新增其他語言時以新增 profile 擴充的路徑
- 目前最佳 deterministic gate 已更新為 `generic_guarded_evidence_synopsis_v2_gate`，assembled `Recall@10=0.7778`、`nDCG@10=0.5246`、`MRR@10=0.4481`
- 舊的 depth / fact-alignment / parent-group / parent-recall / recall-quality / coverage 實驗 lane 已自程式移除，僅保留於 run artifacts 與紀錄文件
- 專案已具備以 `[[C1]]` marker 解析的 `answer_blocks`、citation chips、LangGraph `message_artifacts` 持久化，以及 reload 後可恢復的右側全文預覽欄
- 專案已具備將 chunk-aware 全文預覽前移到 `DocumentsDrawer` 的能力，可在文件管理中直接檢視 ready 文件的 child chunk 清單與全文高亮
- 已完成真實 Keycloak -> JWT -> API -> access-check 的本機端到端驗證
- 已完成一頁式戰情室 (Dashboard) UI 重構，提供左側 Area 導覽、中央滿版對話、右側文件管理抽屜與彈窗權限管理
- 已完成遷移至 Supabase 樣式的 schema，並使用 PGroonga 替代 pg_jieba 進行高效中文檢索
- 已完成將 `match_chunks` 收斂為資料庫候選召回 RPC；最終 `RRF`、ranking policy、rerank 與 assembler 由 Python 層負責
- 已完成 provider-based PDF parsing：預設 `opendataloader` 走 `PDF -> JSON + Markdown -> 現有 parser/chunk tree`，`local` 走 `Unstructured partition_pdf(strategy="fast")`，`llamaparse` 走 PDF -> Markdown -> 現有 Markdown parser -> 現有 chunk tree
- 已完成 OpenDataLoader JSON-aware PDF ingest，將 `page + bounding box` 落入 SQL-first locator 與 chat/document API payload
- 已將 parse artifact 收斂為可重建 parser 結果的最小 `md/html` 集合；reindex 會優先重用既有 artifacts，delete 與真正需要重跑 parser 的 ingest 才會清理舊 artifacts
- 已支援 `POST /documents/{document_id}/reindex?force_reparse=true`，可由前端要求 worker 忽略既有 `md/html` artifacts 並強制重跑 parser
- 已補上 `llamaparse` 的 Markdown noise cleanup 與 PDF-specific block consolidation，降低 parent chunks 在 PDF 路徑上的過度碎片化
- 已支援 `PDF + llamaparse` 的短 `text -> table -> text` cluster parent 規則：單一 parent、混合 `text/table/text` children，維持 table-aware retrieval/citation 語意
- 已新增 `XLSX -> Unstructured partition_xlsx -> HTML table-aware parser` 路徑，worksheet 可直接進入既有 table-aware chunking
- 已新增 `DOCX/PPTX -> Unstructured partition_docx/partition_pptx` 路徑，回接既有 `text/table` block-aware parser contract
- 已完成以 `Caddy` 為核心的單一公開 HTTPS 入口，將 Web、API、Keycloak 收斂到同一個 `PUBLIC_HOST`
- 已將 Keycloak 對外模型固定為 `/auth` base path，並支援以 `KEYCLOAK_EXPOSE_ADMIN` 預設封鎖 `/auth/admin*`
- 已新增並收斂 `app.db.migration_runner`，作為 fresh 與既有資料庫共用的唯一 Alembic 升級入口
- 已補上 `WEB_ALLOWED_HOSTS` 與瀏覽器非 secure context 的 Keycloak PKCE fallback，降低公開網域與本機開發切換時的登入失敗風險
- Playwright smoke 現已預設透過 `http://localhost` 的 Caddy 公開入口驗證真實 Keycloak `/auth/*` 流程，不再依賴舊的 `web` / `keycloak` 直連埠；`keycloak-auth`、`pdf-upload` 與 `phase6-full-flow` smoke 已在此路徑下通過
- 已補上 Windows PowerShell 的本地 worker 啟動腳本，相容保留 `start-worker-marker.ps1` 入口，支援 `compose` 與 `hybrid` 兩種模式
- 本機 hybrid worker 已改為固定共用專案根目錄 `.venv`，不再維護獨立 worker virtualenv
- 已將資料庫 migration 收斂為單一 Alembic 路徑，移除 `supabase/migrations` 與 Alembic 並存造成的雙軌 schema 風險
- 已完成單機版自測路徑：`api + worker + web` 本機啟動、SQLite + filesystem + deterministic providers、Playwright E2E 可直接驗證 retrieval evaluation 主流程

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
- `apps/api` 已加入 SQLAlchemy ORM 模型與 metadata
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
- 已實作 `PUT /areas/{area_id}` 與 `DELETE /areas/{area_id}`，補齊 admin-only area rename / description update / hard delete 管理能力
- 已實作 `GET /areas/{area_id}/access` 與 `PUT /areas/{area_id}/access` 的 area access management API
- 已落實 creator becomes admin 規則，建立 area 後自動寫入 direct `admin` 角色
- 已落實 area hard delete 先清理文件原始檔與 parse artifacts，再刪除 area/documents/jobs/chunks，避免 storage 殘留
- 已補 maintainer / admin 權限差異、未授權 `404` 與 access 更新的 API 測試
- Web 已補 area 編輯 modal 與刪除操作，admin 可於 Dashboard header 直接管理 area 基本資料
- Web 已由 landing page 擴為可手動貼 token 的 Area 管理操作頁
- Web 已可執行 auth context 驗證、area list、create area、area detail 與 access update 最小流程
- API 已補上 CORS middleware，支援本機 Web 直接呼叫 Phase 2 API
- `apps/web` 已建立 Playwright E2E 基礎設施，可在本機以 `AUTH_TEST_MODE=true` 驗證 Areas UI 主要流程
- Web 已接上 Keycloak 正式登入 / callback / logout 流程，並保留 test auth mode 供 Playwright E2E 使用

### Phase 3 — 已完成的 MVP 垂直切片
- 已實作 `POST /areas/{area_id}/documents`、`GET /areas/{area_id}/documents`、`GET /documents/{document_id}` 與 `GET /ingest-jobs/{job_id}`
- 文件 upload 已接上物件儲存、`documents` / `ingest_jobs` 建立與 Celery dispatch
- 已實作 `uploaded -> processing -> ready|failed` 與 `queued -> processing -> succeeded|failed` 狀態轉換
- Worker 已補最小 ingest task、`TXT/MD/PDF/HTML/XLSX/DOCX/PPTX` parser 與其他檔案型別的受控失敗語意
- Web 已在 `/areas` 補上 Files 區塊、單檔 upload、文件狀態與失敗訊息顯示
- API 測試與 worker task 測試已補 upload 驗證、權限邊界、deny-by-default、狀態轉換與未支援格式案例
- Playwright E2E 已補 admin/maintainer upload、reader read-only 與 failed upload 顯示案例
- 已為 `PDF` 新增 provider-based parsing，正式支援 `opendataloader`、`local` 與 `llamaparse` 三條解析路徑
- 已新增 `LLAMAPARSE_DO_NOT_CACHE` 與 `LLAMAPARSE_MERGE_CONTINUED_TABLES` 設定，並將 agentic mode 保留為未來規劃

### Phase 3.5 — 已完成的 lifecycle hardening 與 chunk tree 基礎
- 已新增 `document_chunks` SQL-first schema，採固定 `parent -> child` 兩層結構
- 已為 `TXT/MD` 實作真正的 chunk tree 建立流程，並將 `document.status=ready` 與 chunking 成功綁定
- 已採 hybrid chunking 策略：保留 custom parent section builder，child chunk 改用 `LangChain RecursiveCharacterTextSplitter`
- repo 內仍保留一條可選的 fact-heavy evidence-centric child refinement 路徑，會針對 `dataset / setup / metrics` 類 heading 改用句界 windows 切分；此能力目前預設關閉，且未納入 current benchmark baseline
- 已擴充 `documents` 與 `ingest_jobs` observability，提供 chunk counts、stage 與 last indexed time
- 已實作 `POST /documents/{document_id}/reindex` 與 `DELETE /documents/{document_id}`
- 已落實 reindex replace-all 語意：重建前清除舊 chunks，不保留殘留資料
- 已落實 delete 會移除 document、ingest jobs、document_chunks 與原始檔
- Web Files UI 已補 chunk summary、reindex、delete 與失敗訊息顯示
- API、worker 與 Playwright E2E 已補 chunk tree、reindex、delete、same-404 與 read-only 驗證
- API ingest 已收斂為單一路徑：API 只建立 `documents` / `ingest_jobs` 並 dispatch worker，不再持有 inline ingest 鏡像實作

### Phase 3.6 — 已完成的表格感知 chunking
- 已將 parser / chunking contract 升級為 block-aware，新增 `ParsedDocument` 與 `ParsedBlock`
- 已為 `document_chunks` 新增 SQL-first `structure_kind` 欄位，支援 `text | table`
- 已支援 Markdown table 辨識，並將同一 heading 內的 `text` 與 `table` blocks 拆開處理
- 已支援最小 HTML parser，可辨識 `h1~h3`、段落 / list 文字與 `<table>` 結構
- 已將過短 `table parent` 納入 parent normalization：在同 heading、相鄰且語意連續時，會與前後文字 parent 合併為 mixed parent，但仍保留 `text/table/text` children 邊界
- 小型表格會保留整表為單一 `child + table`
- 超大型表格會依 row groups 切分，並在每個 child 重複表頭
- 已新增 `CHUNK_TABLE_PRESERVE_MAX_CHARS` 與 `CHUNK_TABLE_MAX_ROWS_PER_CHILD`
- API 與 worker 測試已補 Markdown table、HTML table 與 table row-group split 驗證

### Phase 4.1 — 已完成的 retrieval foundation
- 已在 `document_chunks` 新增 retrieval-ready 的 `embedding` SQL-first 欄位，並透過 PGroonga 對 `content` 進行索引
- 已補 worker indexing 流程，將文件處理改為 `parse -> chunk -> index -> ready`
- 已導入 embedding provider abstraction，現支援 `huggingface`、`self-hosted`、`openrouter`、`openai` 與 `deterministic`，其中主線預設為 `openai / text-embedding-3-small`
- 已將 child chunk embedding 輸入調整為 `heading + content` 的自然拼接文字，改善 chunk 被切碎時的主題召回
- 已導入 ready-only 的 internal retrieval service，涵蓋 SQL gate、vector recall、FTS recall (PGroonga) 與 `RRF` merge
- 已完成遷移至 Supabase 樣式的 schema，並使用 PGroonga 替代 pg_jieba
- 已將 vector ANN index 由 `ivfflat` 切換為 `hnsw`，並補上 `documents(area_id, status)` retrieval filter index
- API 與 worker 測試已補 embeddings、retrieval same-404 與 hybrid recall (PGroonga) 驗證

### Phase 4.2 — 已完成的 minimal rerank slice
- 已在 API 端加入 rerank provider abstraction，現支援 `deterministic`、`huggingface`、`cohere` 與 `self-hosted`；舊的 `bge` / `qwen` 值會映射到 `huggingface`
- 已將 production 預設 rerank provider 改為 `self-hosted`，預設 model 為 `BAAI/bge-reranker-v2-m3`；本機 `Hugging Face Rerank` 可選 `BAAI/bge-reranker-v2-m3` 或 `Qwen/Qwen3-Reranker-0.6B`
- 已在 internal retrieval service 將流程擴充為 SQL gate -> vector recall / FTS recall -> `RRF` -> rerank
- 已為 retrieval candidates 補上 `rrf_rank`、`rerank_rank`、`rerank_score` 與 `rerank_applied`
- 已新增 in-memory retrieval trace metadata，保留 query、top-k 設定與每筆 candidate 的 ranking trace
- 已實作 rerank 成本控制：僅重排前 `RERANK_TOP_N` 個 parent-level 候選，且每筆文件內容受 `RERANK_MAX_CHARS_PER_DOC` 限制
- 已將 rerank 輸入改為 parent-level 組裝文字，固定帶入 `Header:` / `Content:` 前綴，降低 child chunk 過度碎片化造成的排序偏差
- 已落實 rerank runtime failure 的 fail-open fallback，不影響 deny-by-default、same-404 與 ready-only 邊界
- API 測試已補 rerank provider factory、runtime fallback、rerank metadata 與 upload -> ingest -> retrieval 的近似 E2E 驗證

### Phase 4.2 — 已完成的 table-aware retrieval assembler slice
- 已新增 internal retrieval assembler service，將 rerank 後 child chunks 組裝為 chat-ready contexts 與 citation-ready metadata
- assembler 已改為以 parent 為單位的 precision-first context materializer：小 parent 直接回完整 parent，大 parent 才做 budget-aware sibling expansion
- assembler 已以 parent 邊界去重同一 parent 的多個 hits，並保留 context-level reference metadata
- assembler 已支援 table row-group child 合併，命中 table 時會優先補齊完整表格並在合併後僅保留一次表頭，再視 budget 補前後相鄰文字
- 已新增 `ASSEMBLER_MAX_CONTEXTS`、`ASSEMBLER_MAX_CHARS_PER_CONTEXT` 與 `ASSEMBLER_MAX_CHILDREN_PER_PARENT` guardrails
- `ASSEMBLER_MAX_CHILDREN_PER_PARENT` 目前明確限制每個 parent 可採信的 hit child 數，避免過度寬鬆擴張
- assembler trace 已補齊 kept/dropped chunk ids、per-context merge 結果與 truncation metadata
- API 測試已補 text merge、table merge、budget trace、citation offsets、rerank fallback 與 upload -> ingest -> retrieval -> assembly 近似 E2E 驗證

### Phase 5.1 — 已完成的 一頁式戰情室 (Dashboard) UI 重構
- 已實作 `DashboardLayout` 全螢幕網格與頂部全局狀態管理
- 已實作 `AreaSidebar` 負責 Knowledge Areas 的導覽切換與快速建立，支援側邊欄收摺
- 已實作 `ChatPanel` 作為中央視窗核心，負責多輪對話、串流狀態顯示與工具調用檢視
- 已將 `ChatPanel` 升級為雙欄佈局：左側回答與 citation chips、右側全文預覽欄
- 已新增 `DocumentPreviewPane`，支援依 citation 自動 scroll 到全文對應位置，並以 child chunk 做 active / related / hover 高亮
- 已實作 `DocumentsDrawer` 負責右側滑出式文件管理，支援在不中斷對話的情況下上傳、編輯與刪除文件
- 已將 `DocumentsDrawer` 擴充為列表 + chunk-aware 檢視器，可直接開啟 ready 文件的 child chunk 清單與全文預覽
- 已實作 `AccessModal` 負責區域權限管理，提供彈窗式角色與權限設定介面
- 已完成從「單純 Chat MVP」向「現代化 RAG 戰情室體驗」的 UI/UX 轉型

### Phase 6 — 已完成的 Supabase & PGroonga Migration
- 已完成遷移至 Supabase 樣式的 schema，並使用 PGroonga 替代 pg_jieba
- 已實作 `match_chunks` candidate-generation RPC，供 PostgreSQL 路徑回傳受 SQL gate 保護的 vector/FTS 候選與排序輸入
- 已將最終 `RRF`、未來 ranking policy、rerank 與 assembler 保留在 Python 層，為後續 business rules 預留擴充點
- 已移除未接線的 multi-provider auth/storage staged 內容，正式路徑維持 Keycloak + MinIO/filesystem
- 已移除對純 PostgreSQL (自編譯 pg_jieba) 的依賴，簡化基礎設施
- 已更新相關環境變數範本與系統文件

### Phase 6.1 — 已完成的 Public HTTPS Entry & Migration Bootstrap Hardening
- 已新增 `caddy` service，將正式對外流量收斂為 `https://<PUBLIC_HOST>/`、`/api/*` 與 `/auth/*`
- 已將 compose 內 `web`、`api`、`keycloak` 改為內部服務，正式客戶端入口只保留 `80/443`
- 已將 Keycloak bootstrap 與公開 issuer 對齊 `/auth` relative path，並更新 realm redirect URI / web origins
- 已將 compose migration command 收斂為 `python -m app.db.migration_runner`，fresh 與既有 volume 均走同一條 Alembic 升級路徑
- 已在前端補上 `WEB_ALLOWED_HOSTS` 與 PKCE fallback，讓 `https://<PUBLIC_HOST>` 與 `http://localhost` 都能維持可預期的登入行為
- 已補上 Windows PowerShell 的本地 worker 啟動腳本，相容保留 `start-worker-marker.ps1` 入口；compose worker 現在預設為 CPU-safe 啟動，不再主動要求 GPU runtime

### Phase 7 — 已完成的 Retrieval Correctness Evaluation v1
- 已新增 `retrieval_eval_datasets`、`retrieval_eval_items`、`retrieval_eval_item_spans`、`retrieval_eval_runs`、`retrieval_eval_run_artifacts` SQL-first schema 與 migration
- 已新增 evaluation services：dataset、mapping、metrics、runner；run 會直接重用既有 `retrieve_area_candidates()` 與 `assemble_retrieval_result()`
- 已新增 area-scoped evaluation APIs，涵蓋 dataset/item/span 建立、candidate preview、`retrieval_miss`、benchmark run 與 run report 查詢
- 已新增 `python -m app.scripts.run_retrieval_eval` CLI，支援 `prepare-candidates`、`run` 與 `report`
- 已新增 benchmark snapshot tooling，涵蓋 `import_benchmark_snapshot`、`export_benchmark_snapshot`、`compare_benchmark_runs` 與 `scripts/reproduce_benchmark.sh`
- 已新增 `prepare_external_benchmark` CLI，可將 `QASPER` / `UDA` 類資料集以 `prepare-source -> filter-items -> align-spans -> build-snapshot -> report` 流程收斂為現有 retrieval benchmark snapshot，並以 `display_text` offsets 作為正式 gold span 來源
- 已新增 `EvaluationDrawer`，支援 dataset 建立、`fact_lookup` 題目、候選複核、文件內搜尋、span 標註、`retrieval_miss` 與 benchmark report 檢視
- 已落實權限邊界：`admin` 與 `maintainer` 可操作，`reader` 與無權限者維持 deny-by-default / same-404
- 已落實 ready-only 邊界：non-ready 文件不得進入 evaluation candidate preview、document search 或 benchmark run
- 已新增 evaluation 專屬 API/worker/Web 測試矩陣，涵蓋 metrics、runner、artifact、same-404、權限與本機 E2E reviewer flow
- 已為 retrieval evaluation 補上 rerank fail-open observability：provider runtime failure 會記 warning log，並在 preview / benchmark per-query detail 顯示 `fallback_reason`
- 已為 Cohere rerank 補上僅針對 `HTTP 429 Too Many Requests` 的 retry/backoff；其他 HTTP/network 錯誤仍直接 fail-open，不會無差別重試
- HTTP 429 retry/backoff 現在會加入 jitter，避免 benchmark 批次中的多題在相同等待秒數後同時重撞 Cohere rate limit
- 已新增外部 benchmark curation 測試，驗證 `QASPER` prepare/filter 與 `align/build/import` round-trip 不會破壞既有 snapshot contract

### Phase 5.1 — 已完成的 Chat MVP on LangGraph Server
- 已新增 LangGraph `agent` graph、custom auth 與 LangGraph HTTP app 入口
- 已將 `CHAT_PROVIDER=deepagents` 改為真正使用 `create_deep_agent()` 的主 agent 回答路徑，不再映射為 OpenAI Responses provider
- 已將 SQL gate、ready-only、vector recall、FTS recall、RRF、rerank 與 assembler 收斂為單一 `retrieve_area_contexts` tool，交由主 agent 自行判斷是否呼叫
- Web `/areas` 已新增多輪 thread chat panel，以 `area_id -> thread_id` 維持同 area 對話脈絡
- 已將既有 Web chat transport 改為 LangGraph SDK 預設 thread/run 端點，不再以自訂 bridge chat routes 作正式路徑
- 已將 LangGraph built-in thread state 正式接上 `messages` 累積記憶；同一 area thread 的多輪對話可延續先前上下文，前端切回既有 thread 時也會回填歷史訊息
- 已將 graph 輸出升級為 assembled-context level contract，前端顯示單位與實際送進 LLM 的 context 單位對齊
- 已將 Web chat stream 收斂為 LangGraph SDK `messages-tuple`、`custom` 與 `values` 事件；最終 answer / citations / assembled contexts / trace 直接來自 graph state
- `custom` 事件目前已收斂為 `phase` 與 `tool_call`；token delta 正式透過 `messages-tuple` 傳遞
- 前端已將 chat 拆為獨立 `features/chat`，並將 `Assembled Contexts` 降級為 debug 檢視；正式使用者互動改為回答句尾 chips 與右側全文預覽欄
- API chat 已收斂到 `app/chat` domain；LangGraph 相關程式僅保留 graph/auth/http app loader 與 runtime glue
- 已補 `retrieve_area_contexts` 完成事件的 context payload 測試，避免 tool output 與 assembled context contract 再出現欄位不一致
- 已為 Deep Agents runtime 新增可選 LangSmith tracing，會附帶 `area_id`、`principal_sub`、`groups` 數量、chat provider/model 與問題長度等 metadata
- 已為 `LANGSMITH_TRACING=true` 但缺少 `LANGSMITH_API_KEY` 的錯誤情境補上明確執行期驗證
- 已新增 `CHAT_STREAM_DEBUG` 與 `VITE_CHAT_STREAM_DEBUG`，可分別觀測 API 與 Web 端的 stream phase、tool call、values commit 與 token/message delta 時序
- 已新增以 `message_artifacts` 持久化的 assistant turn UI metadata，reload 後仍可恢復 `answer_blocks`、citations 與 `used_knowledge_base`
- 已新增全文 preview route 與 `documents.display_text`，讓 citation chips 可直接帶使用者跳到文件內對應 chunk 範圍

## 目前階段重點

### Current Focus
- `Phase 8B` enrichment lane 已取消；目前 focus 回到既有 `child hybrid recall -> rerank -> selection -> assembler` 主線的 benchmark 驗證與 regression guardrails
- `Phase 8C` 路線已改為 agentic evidence-seeking loop：主 `Deep Agents` agent 可在初次 retrieval 證據不足時，受控查看已授權 `ready` 文件名稱、讀取 selected synopsis hints，並以文件 scope 多次補 retrieval
- 持續以 Phase 7 benchmark 驗證 retrieval ranking、coverage 與 baseline regression
- 驗證 `PUBLIC_HOST + Caddy + Keycloak /auth` 的真實部署路徑與登入流程不影響既有 retrieval / evaluation / chat
- 保持 deny-by-default、same-404、ready-only 與 rerank fail-open fallback 不退化
- 保留 `phase8a-summary-compare-v1` checkpoint 作為已接受 closeout artifact；`2026-04-10` 重跑已確認 task type routing 達 `1.0000`，但整體 checkpoint 仍因 hard blockers 與 p95 latency 未通過，因此不把 8A 調分重新升為當前主線目標

## 下一步

### 最適合立即進行的工作
1. 設計 `Phase 8C` 的 agentic evidence-seeking 工具契約與 guardrails，包含已授權 ready 文件清單工具、synopsis inspection / ranking 工具、bounded scoped retrieval，以及每回合工具呼叫 / 文件數 / token / latency 上限
2. 補一輪 `reindex` consistency 驗證，確認 `section synopsis` 預設關閉後 worker 仍可穩定 `ready`
3. 以 `phase8a-summary-compare-v1` 建立 8C 前後對照，優先觀測 `required_document_not_cited`、`insufficient_evidence_not_acknowledged`、faithfulness、overall score 與 p95 latency；同時跑 `QASPER 100`、`NQ 100`、`DRCD 100` regression 哨兵
4. 在 `PUBLIC_HOST + Caddy` 環境驗證 `messages-tuple`、`custom`、`values` 與前後端 chat stream debug 的時序一致性
5. 不得重新引入已移除的 enrichment schema、query-time merge lane、查詢改寫 lane，也不得讓 synopsis hints 成為 citation 或 SQL gate 的替代品

## 尚未開始的功能

- 更完整的 area management 跨模組回歸驗證與誤用案例覆蓋

## Agent Rules

Agents must:
1. 先閱讀 `PROJECT_STATUS.md` 再開始規劃或實作
2. 只實作當前 phase 或使用者明確要求的範圍
3. 完成 major milestone 後更新「已完成功能」與「目前狀態」
4. 不得默默跳 phase
5. 若架構決策改變，必須同步更新 `ARCHITECTURE.md`
6. 若階段拆分或順序改變，必須同步更新 `ROADMAP.md`
