# QASPER Retrieval Miss Analysis（截至 2026-04-04，含 BGE rerank 最新重跑）

## 文件目的

此文件用來回答四件事：

1. 目前 QASPER retrieval 最佳 lane 是哪一條？
2. 歷史上哪些策略已經試過，哪些方向已被證明低 ROI？
3. 在 `QASPER` 與自家 benchmark `tw-insurance-rag-benchmark-v1` 上，各策略分別表現如何？
4. 下一輪若要繼續優化，最值得投入的唯一主假設是什麼？

> 本文件會同時保留：
> - **current HEAD 可直接重跑的最新 BGE benchmark**
> - **歷史策略脈絡**
> - **先前 deterministic gate 的剩餘 miss 分析**
>
> 產品決策註記：
> - README 目前已將 `qasper_guarded_evidence_synopsis_v3_bge` 視為主線 default
> - 本分析文件仍以策略比較與 benchmark 證據整理為主，不刻意改寫不同 lane 的客觀對照結果

---

## 一頁摘要

### 本輪方法學

- 日期：`2026-04-04`
- rerank provider：`BAAI/bge-reranker-v2-m3`
- 資料集：
  - `QASPER`：`qasper-curated-v1-pilot`
  - `self`：`tw-insurance-rag-benchmark-v1`
- 本輪 artifact：`.omx/tmp/bge-core-profiles-latest.json`
- 本輪已完成 BGE 重跑的 current HEAD profile：
  - `production_like_v1`
  - `qasper_guarded_assembler_v2_bge`
  - `qasper_guarded_evidence_synopsis_v2_bge`
  - `qasper_guarded_evidence_synopsis_v3_bge`

### 目前最佳 QASPER Recall（BGE）

- profile：`qasper_guarded_evidence_synopsis_v3_bge`
- assembled Recall@10：`0.8889`
- assembled nDCG@10：`0.5661`
- assembled MRR@10：`0.4609`

### 目前最佳 QASPER 綜合品質（BGE）

- profile：`qasper_guarded_evidence_synopsis_v2_bge`
- assembled Recall@10：`0.8519`
- assembled nDCG@10：`0.5743`
- assembled MRR@10：`0.4829`

### 目前最佳 weighted multi-benchmark 平衡（BGE）

- profile：`qasper_guarded_assembler_v2_bge`
- weighted Recall@10：`0.8711`
- weighted nDCG@10：`0.6860`
- weighted MRR@10：`0.6247`

### 核心結論

- 在 **同一個 BGE rerank provider** 下做 apples-to-apples 比較後：
  - `evidence_synopsis_v3` 仍然是 **QASPER recall 最佳**
  - `evidence_synopsis_v2` 是 **QASPER ranking quality 最佳**
  - `assembler_v2` 反而成為 **weighted 與 self benchmark 最穩定** 的 lane
- 這代表：
  - alias / task / metric bridge 仍然能明顯拉高 QASPER hit rate
  - 但 bridge 類強化在自家 benchmark 上仍有成本
  - 若決策目標是 weighted multi-benchmark，而不是只看 QASPER recall，當前最佳平衡點更接近 `assembler_v2`

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
| assembler lane | rerank 已命中，但 assembled retention 不足 | **BGE 最新**：QASPER Recall@10=`0.7778` / weighted Recall@10=`0.8711` | 已重跑 | 現在是 weighted 與 self benchmark 最穩定的 lane |
| fact-heavy child refinement + assembler v2 | 只對 Dataset / Setup / Metrics 類長 child 做 evidence-centric refinement，再搭配 assembler v2 | 歷史最佳 Recall@10=`0.7407` | retired lane，current HEAD 無法忠實重跑 | 仍代表 evidence density 是高 ROI 槓桿 |
| evidence synopsis v3 | 在 v2 基礎上補 alias bridge / task framing bridge / metric-aspect bridge | **BGE 最新**：QASPER Recall@10=`0.8889` / weighted Recall@10=`0.8756` | 已重跑 | QASPER recall 最佳，但 weighted nDCG / MRR 不如 assembler_v2 |
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
- 但在 2026-04-04 的 BGE apples-to-apples 重跑下，若把 self benchmark 一起算進來，`assembler_v2` 的整體平衡反而比 `evidence synopsis` 更穩

---

## 基準與主要候選

### Baseline：`production_like_v1`

- assembled Recall@10：`0.7037`
- assembled nDCG@10：`0.5201`
- assembled MRR@10：`0.4549`

### `qasper_guarded_assembler_v2_bge`

- assembled Recall@10：`0.7778`
- assembled nDCG@10：`0.5558`
- assembled MRR@10：`0.4787`

### `qasper_guarded_evidence_synopsis_v2_bge`

- assembled Recall@10：`0.8519`
- assembled nDCG@10：`0.5743`
- assembled MRR@10：`0.4829`

### `qasper_guarded_evidence_synopsis_v3_bge`

- assembled Recall@10：`0.8889`
- assembled nDCG@10：`0.5661`
- assembled MRR@10：`0.4609`

### 高階判讀

- 在 **QASPER 單 benchmark** 上：
  - `evidence_synopsis_v2` 是綜合品質最佳
  - `evidence_synopsis_v3` 是 recall 最佳
- 但在 **weighted / self benchmark** 上：
  - `assembler_v2` 反而是目前更穩定的平衡點

> 也就是說，  
> `evidence synopsis` 仍然有效，  
> 但它現在更像是「針對 QASPER 壓力測試的高 recall lane」，  
> 而不是 current HEAD 下最穩的 weighted default 候選。

---

## QASPER 分數變化總結

### 相對 `production_like_v1`

| Profile | Recall@10 delta | nDCG@10 delta | MRR@10 delta |
| --- | ---: | ---: | ---: |
| `qasper_guarded_assembler_v2_bge` | `+0.0741` | `+0.0357` | `+0.0238` |
| `qasper_guarded_evidence_synopsis_v2_bge` | `+0.1481` | `+0.0542` | `+0.0279` |
| `qasper_guarded_evidence_synopsis_v3_bge` | `+0.1852` | `+0.0460` | `+0.0060` |

### BGE 重跑下的高階判讀

- 若目標是 **QASPER ranking quality**，`v2` 仍優於 `v3`
- 若目標是 **QASPER pure recall**，`v3` 仍然更高
- `assembler_v2` 雖然 QASPER recall 不如 `v2/v3`，但整體沒有出現 self benchmark 的退化

---

## 雙 benchmark 對照：2026-04-04 BGE apples-to-apples 結果

除了 QASPER，也必須同步看 `tw-insurance-rag-benchmark-v1`。

### Assembled 指標總覽

| Profile | QASPER Recall@10 | QASPER nDCG@10 | QASPER MRR@10 | self Recall@10 | self nDCG@10 | self MRR@10 | weighted Recall@10 | weighted nDCG@10 | weighted MRR@10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `production_like_v1` | `0.7037` | `0.5201` | `0.4549` | `0.9000` | `0.7622` | `0.7178` | `0.8215` | `0.6654` | `0.6126` |
| `qasper_guarded_assembler_v2_bge` | `0.7778` | `0.5558` | `0.4787` | `0.9333` | `0.7727` | `0.7219` | `0.8711` | `0.6860` | `0.6247` |
| `qasper_guarded_evidence_synopsis_v2_bge` | `0.8519` | `0.5743` | `0.4829` | `0.8667` | `0.7254` | `0.6792` | `0.8607` | `0.6650` | `0.6007` |
| `qasper_guarded_evidence_synopsis_v3_bge` | `0.8889` | `0.5661` | `0.4609` | `0.8667` | `0.7283` | `0.6825` | `0.8756` | `0.6634` | `0.5939` |

### 關鍵判讀

1. 在 apples-to-apples 的 BGE 比較下，QASPER 單 benchmark 的最佳 lane 已更清楚：
   - recall：`evidence_synopsis_v3`
   - nDCG / MRR：`evidence_synopsis_v2`

2. 但 self benchmark 的最佳 lane 不是 `evidence synopsis`
   - `assembler_v2` 在 Recall / nDCG / MRR 全部優於 `production_like_v1`
   - `evidence_synopsis_v2/v3` 則都比 `production_like_v1` 略退

3. 若採 weighted multi-benchmark objective，當前最平衡的 lane 是 `assembler_v2`
   - weighted Recall@10：`0.8711`
   - weighted nDCG@10：`0.6860`
   - weighted MRR@10：`0.6247`

4. 因此目前更精準的結論應是：
   - `evidence synopsis` 是 **QASPER-oriented high-recall lane**
   - `assembler_v2` 是 **current HEAD + BGE 下的整體平衡最佳 lane**

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

> **讓 `evidence synopsis` 的 QASPER 增益只在需要時介入，並盡量保留 `assembler_v2` 在 self / weighted 上的穩定性**

換句話說，下一輪不應再只是把 bridge 加得更重，而應聚焦：

- 如何讓 alias / task / metric bridge 更 selective
- 如何讓 bridge 類補強只在高 semantic-gap 題型生效
- 如何在保住 `assembler_v2` 的 self benchmark 表現下，再吸收 `v2/v3` 的 QASPER recall 增益

### Secondary

只針對這題：

- `Which dataset do they use a starting point in generating fake reviews?`

建議再開 assembler carry-through 精修 lane：

- 若 rerank 已把某個短 child 排到前段，且該 child 直接覆蓋 gold span
- assembler 應優先保留該 child 原文，再做周邊補文

### 目前不建議優先做的方向

- 再加深 recall pool
- 再擴大 coverage lane
- 再回去做 generic fact alignment score 微調
- 再做粗粒度 parent lexical / RPC backfill
- 再把 assembler window 當主要策略擴張

原因很一致：

> 現在主問題不是候選池不夠大，  
> 而是 evidence 還不夠像 query 想找的答案，  
> 或在變得更像答案後，仍沒有被穩定排到正確位置。
