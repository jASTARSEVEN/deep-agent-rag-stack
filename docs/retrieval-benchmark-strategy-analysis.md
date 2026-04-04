# Retrieval Benchmark Strategy Analysis（截至 2026-04-04，含 `easypinex-host` 實跑更新）

## 文件目的

此文件目前改成回答五件事：

1. 在 **BGE apples-to-apples 對照** 下，哪條 lane 的平均 `nDCG@10 uplift` 最好？
2. 在 **目前正式 runtime（`easypinex-host + BAAI/bge-reranker-v2-m3`）** 下，三資料集的真實分數是多少？
3. 最新一輪實作後，miss 主戰場是 `recall`、`rerank` 還是 `assembler`？
4. 哪些策略仍值得保留在 current HEAD 的常規比較集合中？
5. 歷史上的 miss 類型與已知低 ROI 方向有哪些，避免之後重複回頭試？

> 本文件會同時保留：
> - **current HEAD 可直接重跑的最新 BGE benchmark**
> - **current HEAD 以 `easypinex-host` 實際執行的正式 runtime benchmark**
> - **歷史策略脈絡**
> - **先前 deterministic gate 的剩餘 miss 分析**
>
> 產品決策註記：
> - runtime 預設目前已切到 `easypinex-host + BAAI/bge-reranker-v2-m3 + qasper_v3`
> - 但 BGE apples-to-apples 對照仍保留，因為它可以隔離 provider 差異
> - 本文件的主排序目標仍是 **三資料集平均 `nDCG@10 uplift`**
> - 也就是說，QASPER 單點最佳仍不自動等於「整體最佳」

---

## 一頁摘要

### 本輪方法學（BGE apples-to-apples 參考）

- 日期：`2026-04-04`
- rerank provider：`BAAI/bge-reranker-v2-m3`
- 資料集：
  - `QASPER`：`qasper-curated-v1-pilot`
  - `self`：`tw-insurance-rag-benchmark-v1`
  - `UDA`：`uda-curated-v1-pilot`（OpenAI review 擴充版）
- 本輪 artifact：
  - `QASPER + self`：`.omx/tmp/bge-core-profiles-latest.json`
  - `UDA`：`benchmarks/uda-curated-v1-pilot/bge_core_profiles_summary.json`
- 本輪已完成 BGE 重跑的 current HEAD profile：
  - `production_like_v1`
  - `qasper_guarded_assembler_v2_bge`
  - `qasper_guarded_evidence_synopsis_v2_bge`
  - `qasper_guarded_evidence_synopsis_v3_bge`
- `UDA` pilot package 補充：
  - benchmark package：`benchmarks/uda-curated-v1-pilot`
  - source scope：官方 `UDA-Benchmark` 的 `extended_qa_info_bench + src_doc_files_example`
  - 最終收斂：`12` 份文件、`26` 題、`38` 個 gold spans
  - `9` 題 auto-matched，`21` 題由 `OpenAI API` review 核准，再補 `4` 題 deterministic override

### BGE apples-to-apples：三資料集平均 nDCG@10 uplift 排名

| Profile | QASPER nDCG@10 | self nDCG@10 | UDA nDCG@10 | 三資料集平均 nDCG@10 | 相對 baseline 平均 uplift |
| --- | ---: | ---: | ---: | ---: | ---: |
| `production_like_v1` | `0.5201` | `0.7622` | `0.5288` | `0.6037` | `+0.0000` |
| `qasper_guarded_assembler_v2_bge` | `0.5558` | `0.7727` | `0.5288` | `0.6191` | `+0.0154` |
| `qasper_guarded_evidence_synopsis_v2_bge` | `0.5743` | `0.7254` | `0.5264` | `0.6087` | `+0.0050` |
| `qasper_guarded_evidence_synopsis_v3_bge` | `0.5661` | `0.7283` | `0.5288` | `0.6077` | `+0.0040` |

### BGE apples-to-apples：三資料集平均 recall / MRR 補充

| Profile | 平均 Recall@10 | Recall uplift | 平均 MRR@10 | MRR uplift |
| --- | ---: | ---: | ---: | ---: |
| `production_like_v1` | `0.7525` | `+0.0000` | `0.5565` | `+0.0000` |
| `qasper_guarded_assembler_v2_bge` | `0.7883` | `+0.0358` | `0.5658` | `+0.0093` |
| `qasper_guarded_evidence_synopsis_v2_bge` | `0.7908` | `+0.0383` | `0.5519` | `-0.0046` |
| `qasper_guarded_evidence_synopsis_v3_bge` | `0.8031` | `+0.0506` | `0.5467` | `-0.0098` |

### BGE apples-to-apples：核心結論

1. 若主目標是 **隔離 provider 差異後的三資料集平均 nDCG@10 uplift**，最佳 lane 仍是 `qasper_guarded_assembler_v2_bge`
   - 平均 nDCG@10：`0.6191`
   - 相對 baseline 平均 uplift：`+0.0154`

2. `evidence synopsis` 仍然有效，但它們現在更像是 **QASPER-leaning lane**
   - `v2` 在 QASPER nDCG@10 最好：`0.5743`
   - `v3` 在 QASPER Recall@10 最好：`0.8889`
   - 但兩者在 self 與 UDA 上都沒有形成更好的平均 nDCG uplift

3. `assembler_v2` 是目前最接近「跨資料集都不太失真」的 lane
   - QASPER：有明確 uplift
   - self：三條 lane 中最佳
   - UDA：與 baseline / `v3` 持平，沒有額外退化

4. 若目標不是平均 nDCG，而是平均 recall，排序會變
   - `v3` 的平均 Recall uplift 最大：`+0.0506`
   - 但它的平均 MRR uplift 是負值：`-0.0098`
   - 因此它不符合本輪「綜合三資料集、以 nDCG 為主」的優先目標

---

## 正式 runtime 更新：`easypinex-host + BAAI/bge-reranker-v2-m3`

### 2026-04-04 實跑前置修正

在正式 runtime 路徑上，這一輪先確認了兩個重要事實：

1. `Easypinex-host /v1/rerank` 不是不能用，而是先前 `10s` timeout 太短
   - 最小 probe 首次成功回應約需 `28.96s`
   - 因此若維持 `10s`，benchmark 會大量走 fail-open fallback，而那不是有效的 hosted rerank 分數
2. `easypinex-host` 目前接受的 `RERANK_MODEL` 需使用真實 model 名稱
   - 這一輪正式對齊為 `BAAI/bge-reranker-v2-m3`
   - `bge-rerank` 這種 alias 不應再視為正式可用值

因此本節所有 hosted 分數，均是在：

- `RERANK_PROVIDER=easypinex-host`
- `RERANK_MODEL=BAAI/bge-reranker-v2-m3`
- `EASYPINEX_HOST_RERANK_TIMEOUT_SECONDS=60`
- `RETRIEVAL_EVIDENCE_SYNOPSIS_VARIANT=qasper_v3`

之下取得的正式 runtime benchmark。

### 正式 runtime：最新主線分數

| Dataset | before（hosted baseline） | after（query-aware assembler anchor） | uplift |
| --- | ---: | ---: | ---: |
| `QASPER` nDCG@10 | `0.5661` | `0.5846` | `+0.0185` |
| `tw-insurance-rag-benchmark-v1` nDCG@10 | `0.7283` | `0.7283` | `+0.0000` |
| `UDA` nDCG@10 | `0.5288` | `0.7353` | `+0.2065` |
| 三資料集平均 nDCG@10 | `0.6077` | `0.6827` | `+0.0750` |

### 正式 runtime：平均 Recall / MRR 補充

| 指標 | before（hosted baseline） | after（query-aware assembler anchor） | uplift |
| --- | ---: | ---: | ---: |
| 平均 Recall@10 | `0.8031` | `0.8672` | `+0.0641` |
| 平均 MRR@10 | `0.5467` | `0.6255` | `+0.0787` |

### 正式 runtime：核心結論

1. 目前正式 runtime 下，最有效的槓桿已不是 `recall depth`
   - 單靠把 provider 路徑修正為真的 hosted rerank，`QASPER/self/UDA` 已對齊先前 `qasper_v3_bge` 的主線結果
   - 再加上本輪 `query-aware assembler anchor` 後，平均 `nDCG@10` 再提升 `+0.0750`

2. 本輪最明顯的收益來自 **assembler retention**
   - `UDA` assembled `nDCG@10` 從 `0.5288` 直接升到 `0.7353`
   - 代表先前大量題目不是 retrieval miss，也不是 rerank miss，而是 **rerank hit 但 assembler 把正確 child 丟掉**

3. `self` 幾乎不受這個 assembler 策略影響
   - `self nDCG@10` 維持 `0.7283`
   - 這表示本輪修正對中文保險資料集沒有造成新的明顯 side effect

4. `QASPER` 有穩定提升，但還沒有達標
   - `QASPER nDCG@10` 從 `0.5661` 升到 `0.5846`
   - 代表純 assembler 問題已經收回一部分，但剩下的主戰場已回到 `semantic gap / rerank discrimination`

### 正式 runtime：miss 分布更新

#### `QASPER`

- assembled miss 總數：`3`
- 分布：
  - `1` 題：`recall_only`
  - `1` 題：`rerank_only`
  - `1` 題：`assembled_only`

代表題：
- `What are the specific tasks being unified?`
  - `recall_only`
- `What are strong baseline models in specific tasks?`
  - `rerank_only`
- `How many reviews in total (both generated and true) do they evaluate on Amazon Mechanical Turk?`
  - `assembled_only`

#### `tw-insurance-rag-benchmark-v1`

- assembled miss 總數：`4`
- 分布：
  - `3` 題：`recall_only`
  - `1` 題：`rerank_only`

代表題：
- `新傳承富利利率變動型終身壽險幾歲可以投保？各年期的限制是什麼？`
  - `recall_only`
- `珍傳愛小額終身壽險可投保年齡是幾歲及各年齡可投保年期是多少`
  - `rerank_only`
- `保單更約權的申請時間`
  - `recall_only`
- `網路保險申請保單借款的身分限制`
  - `recall_only`

#### `UDA-Benchmark pilot`

- assembled miss 總數：`4`
- 分布：
  - `3` 題：`recall_only`
  - `1` 題：`assembled_only`

代表題：
- `What baselines did they consider?`
  - `recall_only`
- `What is the average Net income for Years Ended December 31, 2018 to 2019?`
  - `recall_only`
- `In which year was Operating Leases greater than 100,000?`
  - `recall_only`
- `Does this approach perform better in the multi-domain or single-domain setting?`
  - `assembled_only`

### 正式 runtime：本輪實作真正證明了什麼

1. `query-aware assembler anchor` 是高 ROI 槓桿
   - 尤其對長 parent、單一 parent 內多個 child 同時入榜的情境
   - 原本 `child_index-first` 會把後段正確 child 擠掉；改成先保留最像 query 的 hit child 後，`UDA` 的 assembled 指標大幅改善

2. assembler 不再是主要瓶頸
   - `UDA` 的 assembled-only miss 從 `6` 題降到 `1` 題
   - `QASPER` 的 `Which dataset do they use a starting point in generating fake reviews?` 已被收回

3. 下一輪主戰場已轉移
   - `QASPER` 現在主戰場是 `recall_only + rerank_only`
   - `self` 主戰場幾乎全是 `recall_only`
   - `UDA` 剩下的主要問題也轉為 `recall_only`

換句話說，現在最值得做的，不再是繼續擴 assembler window，而是：

> **讓 recall / rerank 更能理解 query 想找的 evidence type，而不是只讓 assembler 更努力保留已命中的內容。**

## 三資料集綜合判讀

### 1. `QASPER`

- 最佳 nDCG@10：`qasper_guarded_evidence_synopsis_v2_bge = 0.5743`
- 最佳 Recall@10：`qasper_guarded_evidence_synopsis_v3_bge = 0.8889`
- 判讀：
  - alias / task / metric bridge 的確對 QASPER 有利
  - 但這個 gain 不是免費的，因為它沒有自動跨到其他資料集
  - 在正式 runtime 上，本輪 `query-aware assembler anchor` 已把主線 `production_like_v1` 拉到 `0.5846`
  - 但距離目標 `0.65` 仍差 `0.0654`，剩餘 gap 主要已不是 assembler retention

### 2. `tw-insurance-rag-benchmark-v1`

- 最佳 nDCG@10：`qasper_guarded_assembler_v2_bge = 0.7727`
- 最佳 MRR@10：`qasper_guarded_assembler_v2_bge = 0.7219`
- 判讀：
  - self benchmark 目前仍明確偏向 `assembler_v2`
  - `evidence synopsis` 在 self 上沒有帶來同等級的 quality uplift
  - 正式 runtime 目前仍停在 `0.7283`
  - 距離目標 `0.8` 仍差 `0.0717`，主要缺口明顯落在 recall

### 3. `UDA-Benchmark pilot`

- 最新 reference run（`production_like_v1`）：
  - assembled Recall@10：`0.6538`
  - assembled nDCG@10：`0.5288`
  - assembled MRR@10：`0.4968`
- 四條 current-head lane 的 assembled nDCG@10：
  - `production_like_v1 = 0.5288`
  - `assembler_v2 = 0.5288`
  - `evidence_synopsis_v2 = 0.5264`
  - `evidence_synopsis_v3 = 0.5288`
- 判讀：
  - `UDA` 這一輪的主收益，不是來自策略切換，而是來自 benchmark governance 擴充
  - 也就是 `auto-align + OpenAI review + deterministic override`
  - 在 current HEAD lane 層級，UDA 目前沒有提供足夠強的訊號去推翻 `assembler_v2` 的平均 nDCG 優勢
  - 但在正式 runtime 上，本輪 `query-aware assembler anchor` 已把 `UDA` 拉到 `nDCG@10 = 0.7353`
  - 因此對 `UDA` 而言，先前真正拖分的主因並不是 provider 或 governance，而是 assembled retention

### 三資料集綜合決策

- 若主目標是 **隔離 provider 差異的平均 nDCG uplift**：
  - 仍以 `qasper_guarded_assembler_v2_bge` 作為 apples-to-apples 參考
- 若主目標是 **正式 runtime 的當前主線表現**：
  - 以 `easypinex-host + BAAI/bge-reranker-v2-m3 + qasper_v3 + query-aware assembler anchor` 作為最新 baseline
- 若主目標是 **QASPER recall 壓力測試**：
  - 選 `qasper_guarded_evidence_synopsis_v3_bge`
- 若主目標是 **QASPER ranking quality 壓力測試**：
  - 選 `qasper_guarded_evidence_synopsis_v2_bge`

---

## 歷史已試策略總覽

這一節保留實驗脈絡，避免之後重複回頭試已知低 ROI 的方向。

### 2026-04-04 BGE 重跑狀態

不是所有歷史 lane 都能在 current HEAD 上直接忠實重跑：

- 已完成 BGE 重跑：
  - `production_like_v1`
  - `assembler_v2`
  - `evidence_synopsis_v2`
  - `evidence_synopsis_v3`
- 仍保留歷史數值、但本輪**無法忠實以 BGE 直接重跑**的 retired lane：
  - `fact-heavy child refinement + assembler v2`
  - `heading-aware recall`
  - `parent-first lexical recall`
  - `parent-group retrieval`
  - `RPC parent-content backfill`

原因是這些 lane 對應的 benchmark-only 旗標或分支邏輯已自 current HEAD 移除；若要重跑，需先回補舊實作，而不是單純切 rerank provider。

### 已試方法與其核心思想

| 方法 | 核心思想 | 最新可用數值 | 狀態 | 判讀 |
| --- | --- | --- | --- | --- |
| depth lane | 先把召回池加深 | 歷史最佳 Recall@10=`0.4074` | 本輪未納入 BGE 長跑批 | 問題不只是池子太淺 |
| assembler lane | rerank 已命中，但 assembled retention 不足 | **BGE 最新**：QASPER Recall@10=`0.7778` / 三資料集平均 nDCG uplift=`+0.0154` | 已重跑 | 目前是平均 nDCG 目標下的最佳 lane |
| fact-heavy child refinement + assembler v2 | 只對 Dataset / Setup / Metrics 類長 child 做 evidence-centric refinement，再搭配 assembler v2 | 歷史最佳 Recall@10=`0.7407` | retired lane，current HEAD 無法忠實重跑 | 仍代表 evidence density 是高 ROI 槓桿 |
| evidence synopsis v3 | 在 v2 基礎上補 alias bridge / task framing bridge / metric-aspect bridge | **BGE 最新**：QASPER Recall@10=`0.8889` / 平均 Recall uplift=`+0.0506` | 已重跑 | QASPER recall 最佳，但平均 nDCG 不是最佳 |
| coverage lane | 在固定 output budget 下擴大 pre-assembly coverage | 歷史最佳 Recall@10=`0.3704` | 本輪未納入 BGE 長跑批 | 雜訊高、低 ROI |
| heading-aware recall | 用 heading lexical hit 補強召回 | 歷史最佳 Recall@10=`0.5185` | retired lane，current HEAD 無法忠實重跑 | 有訊號，但不是主要瓶頸 |
| parent-first lexical recall | 先 parent lexical hit，再回填 child | 歷史最佳 Recall@10=`0.4444` | retired lane，current HEAD 無法忠實重跑 | parent hit 太寬，回填仍不精準 |
| parent-group retrieval | child RRF 後先聚合 parent 再選 | 歷史最佳 Recall@10=`0.6296` | retired lane，current HEAD 無法忠實重跑 | 有幫助，但仍不如 assembler v2 |
| RPC parent-content backfill | 在 `match_chunks` 內直接做 parent-content FTS 回填 | 歷史最佳 Recall@10=`0.4815` | retired lane，current HEAD 無法忠實重跑 | DB 層回填太粗，效果差 |

### 歷史策略的高階判讀

- `depth / coverage / parent-first / RPC backfill` 已不是優先方向
- `assembler lane` 是第一個明顯有效的高 ROI lane
- `fact-heavy child refinement + assembler v2` 與後續 `evidence synopsis` 都指向同一件事：
  **真正高 ROI 的槓桿在 evidence density，而不是單純擴大候選池**
- 但在 current HEAD 的三資料集平均 `nDCG@10 uplift` 目標下，`assembler_v2` 仍是最佳平衡點

---

---

## 方法學註記：下方 miss 分析仍屬歷史 deterministic artifact

以下 `v2` 剩餘 miss 與逐題分析，仍然是先前 deterministic gate / 歷史 artifact 的診斷內容。  
它的價值仍在於說明 miss 類型與主假設方向，但**不應與本頁前半段的 2026-04-04 BGE 重跑數值直接混讀成同一輪 benchmark**。

---

## v2 剩餘 miss 概況

在 `qasper_guarded_evidence_synopsis_v2_gate` 下：

- 27 題中已命中 21 題
- 仍有 6 題 miss

### miss 類型分布

- `4` 題：`recall_hit=false`
- `1` 題：`recall_hit=true` 但 `rerank_hit=false`
- `1` 題：`rerank_hit=true` 但 `assembled_hit=false`

### 高階判讀

- assembled-only miss 已縮到 `1` 題
- 純 recall miss 仍有 `4` 題
- 這表示主戰場已集中到：
  **query-to-evidence semantic gap**

---

## v2 剩餘 6 題逐題分析

### A. 純 recall miss（4 題）

#### 1. `What are labels available in dataset for supervision?`

- file：`Minimally-Supervised-Learning-of-Affective-Events-Using-Discourse-Relations.md`
- gold span：`negative`（另一個 label 對應 `positive`）
- 所在 parent：`Abstract / Introduction`
- parent chars：`3089`
- child chars：`587`

**child 內容重點**
- `positive or negative ways`
- `score ranging from -1 (negative) to 1 (positive)`

**判讀**
- query 在問 `labels available in dataset for supervision`
- evidence 用自然語言表達 polarity
- 問題不是沒有 evidence，而是 **label/schema 語言沒有顯性化**

#### 2. `What are the specific tasks being unified?`

- file：`Question-Answering-based-Clinical-Text-Structuring-Using-Pre-trained-Language-Model.md`
- 所在 parent：`Experimental Studies ::: Dataset and Evaluation Metrics`
- parent chars：`1072`
- refined child chars：`176`

**child 內容重點**
- `three types of questions, namely tumor size, proximal resection margin and distal resection margin`

**判讀**
- query 用的是 `tasks being unified`
- evidence 用的是 `types of questions`
- 這是典型的 **task framing mismatch**

#### 3. `How big is QA-CTS task dataset?`

- file：`Question-Answering-based-Clinical-Text-Structuring-Using-Pre-trained-Language-Model.md`
- 所在 parent：`Experimental Studies ::: Dataset and Evaluation Metrics`
- parent chars：`1072`
- refined child chars：`81`

**child 內容重點**
- `17,833 sentences, 826,987 characters and 2,714 question-answer pairs`

**判讀**
- 這是最典型的 **dataset alias mismatch**
- 數值 evidence 已在，但 `QA-CTS` alias 沒被顯性橋接

#### 4. `What aspects have been compared between various language models?`

- file：`Progress-and-Tradeoffs-in-Neural-Language-Models.md`
- 所在 parent：`Experimental Setup`
- parent chars：`1138`
- 核心 child chars：`120` / `138`

**child 內容重點**
- `perplexity, R@3 in next-word prediction, latency, energy usage`

**判讀**
- evidence 已列出 metrics
- query 問的是抽象詞 `aspects compared`
- 這是 **metric framing mismatch**

### B. recall 命中，但 rerank 還保不住（1 題）

#### 5. `How big is the Japanese data?`

- file：`Minimally-Supervised-Learning-of-Affective-Events-Using-Discourse-Relations.md`
- `evidence_synopsis_v2`：`recall_hit=true`, `rerank_hit=false`
- recall rank：`8`

**關鍵特徵**
- gold evidence 跨多段：
  - Japanese web corpus
  - 100 million sentences
  - ACP corpus / split

**判讀**
- 這更像是 **multi-span, multi-parent numeric synthesis**
- 不適合作為下一輪唯一主假設的代表題

### C. rerank 命中，但 assembler retention 仍失敗（1 題）

#### 6. `Which dataset do they use a starting point in generating fake reviews?`

- file：`Stay-On-Topic-Generating-Context-specific-Fake-Restaurant-Reviews.md`
- `evidence_synopsis_v2`：`recall_hit=true`, `rerank_hit=true`, `assembled_hit=false`
- recall rank：`5`
- rerank rank：`2`
- 所在 parent：`Generative Model`
- parent chars：`42574`
- answer-bearing child chars：`381`

**child 內容重點**
- `we use the Yelp Challenge dataset`

**判讀**
- retrieval 不是問題
- rerank 也不是問題
- 問題只剩 assembler 沒把短而準的 child 保留下來
- 這是最純的 **assembler-only miss**

---

## v2 階段真正證明了什麼

### 1. evidence 表示比 generic ranking knob 更重要

- 在當時的 deterministic gate 上，`evidence_synopsis_v2` 已經超過 `assembler_v2`
- 代表高 ROI 來源不是 recall 深度、coverage 或 generic fact alignment

### 2. hardest cases 幾乎都卡在 semantic gap

- 6 題 miss 中有 4 題是 pure recall miss
- 這 4 題都不是沒有 evidence，而是 **query framing 與 evidence framing 不一致**

### 3. assembler 問題已縮到單點修補

- assembled-only miss 只剩 1 題
- assembler 不再是主戰場

---

## 歷史 deterministic 更新：`evidence_synopsis_v3_gate`

根據 v2 階段的判斷，後續實作了 **benchmark-gated evidence synopsis v3**。

### v3 的唯一主假設

- dataset alias bridge
- task framing bridge
- metric-aspect bridge

### `qasper_guarded_evidence_synopsis_v3_gate` 實測結果

#### QASPER

- assembled Recall@10：`0.8519`
- assembled nDCG@10：`0.4499`
- assembled MRR@10：`0.3271`

#### `tw-insurance-rag-benchmark-v1`

- assembled Recall@10：`0.5667`
- assembled nDCG@10：`0.2937`
- assembled MRR@10：`0.2123`

#### weighted（self=0.6, qasper=0.4）

- assembled Recall@10：`0.6807`
- assembled nDCG@10：`0.3562`
- assembled MRR@10：`0.2582`

### v3 assembled 指標表

| Dataset | Profile | Recall@10 | nDCG@10 | MRR@10 | Precision@10 | Doc Coverage@10 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `QASPER` | `qasper_guarded_evidence_synopsis_v3_gate` | `0.8519` | `0.4499` | `0.3271` | `0.0852` | `1.0000` |
| `tw-insurance-rag-benchmark-v1` | `qasper_guarded_evidence_synopsis_v3_gate` | `0.5667` | `0.2937` | `0.2123` | `0.0567` | `0.9000` |
| `weighted (self=0.6, qasper=0.4)` | `qasper_guarded_evidence_synopsis_v3_gate` | `0.6807` | `0.3562` | `0.2582` | `0.0681` | `0.9400` |

### v3 的判讀

- `v3` 的確把 **QASPER Recall@10** 從 `0.7778` 拉升到 `0.8519`
- 但 **QASPER nDCG / MRR** 明顯下降
- self benchmark 沒有改善
- 因此在目前 weighted objective 下，`v3_gate` 仍未通過 deterministic gate

> 結論：  
> `evidence synopsis v3` 已證明 alias / task / metric bridge 對 **QASPER recall** 有效，  
> 但目前仍是「高 recall、未同步提升 ranking quality、且未通過 weighted objective」的受控實驗 lane。

---

## 後續建議

### Primary

若要繼續開下一輪，最值得的唯一主假設應是：

> **讓 `evidence synopsis / recall phrasing` 只在真正需要時介入，專注收斂 `recall_only` 與 `rerank_only` 的 semantic-gap miss。**

換句話說，下一輪不應再只是把 bridge 加得更重，而應聚焦：

- 如何讓 alias / task / metric / baseline-list 類 bridge 更 selective
- 如何讓 bridge 類補強只在 `recall_only` 或 `rerank_only` 題型生效
- 如何在不破壞 `self` 的前提下，補強中文保險 query 與條款 phrasing 的 lexical / semantic 對齊
- 如何讓長 numeric / tabular question 的 query wording 更容易撞到正確 evidence 類型

### Secondary

若只看這一輪剩下的 assembler 題，才值得開小型 secondary lane：

- `QASPER`
  - `How many reviews in total (both generated and true) do they evaluate on Amazon Mechanical Turk?`
- `UDA`
  - `Does this approach perform better in the multi-domain or single-domain setting?`

這兩題都屬於 **rerank 已命中，但 parent 內仍有局部保留策略可再收斂**。  
但相較於目前大量 `recall_only` 題，它們已不再是主假設優先級。

### 目前不建議優先做的方向

- 再加深 recall pool
- 再擴大 coverage lane
- 再回去做 generic fact alignment score 微調
- 再做粗粒度 parent lexical / RPC backfill
- 再把 assembler window 當主要策略擴張

原因很一致：

> 現在主問題已不再是 assembler 保不住 evidence，  
> 而是 recall / rerank 還不夠理解 query 想找的證據型別，  
> 導致正確 evidence 不是沒進池，就是沒被穩定排到前面。
