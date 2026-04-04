# QASPER Retrieval Miss Analysis（截至 2026-04-04，含 evidence synopsis v3 實驗後）

## 文件目的

此文件用來回答四件事：

1. 目前 QASPER retrieval 最佳 lane 是哪一條？
2. 歷史上哪些策略已經試過，哪些方向已被證明低 ROI？
3. 在 `QASPER` 與自家 benchmark `tw-insurance-rag-benchmark-v1` 上，各策略分別表現如何？
4. 下一輪若要繼續優化，最值得投入的唯一主假設是什麼？

> 本文件會同時保留：
> - **歷史策略脈絡**
> - **目前最佳 lane 的剩餘 miss 分析**
> - **後續 v3 實驗更新**

---

## 一頁摘要

### 目前最佳 QASPER deterministic gate

- profile：`qasper_guarded_evidence_synopsis_v2_gate`
- assembled Recall@10：`0.7778`
- assembled nDCG@10：`0.5246`
- assembled MRR@10：`0.4481`

### 後續 v3 實驗結果

- profile：`qasper_guarded_evidence_synopsis_v3_gate`
- QASPER assembled Recall@10：`0.8519`
- QASPER assembled nDCG@10：`0.4499`
- QASPER assembled MRR@10：`0.3271`

### 核心結論

- `evidence synopsis v2` 是目前 **QASPER 綜合品質最佳** 的 deterministic gate lane。
- `evidence synopsis v3` 證明：
  - alias / task / metric bridge 對 **QASPER recall** 有效
  - 但目前沒有同步改善 ranking quality
- 在自家 benchmark `tw-insurance-rag-benchmark-v1` 上：
  - `production_like_v1` 仍明顯優於 `evidence synopsis v2/v3 gate`
- 因此在目前 **weighted multi-benchmark objective** 下：
  - `evidence synopsis v3_gate` **尚未通過**

---

## 歷史已試策略總覽

這一節保留實驗脈絡，避免之後重複回頭試已知低 ROI 的方向。

### 已試方法與其核心思想

| 方法 | 核心思想 | 最佳 Recall@10 | 判讀 |
| --- | --- | ---: | --- |
| depth lane | 先把召回池加深 | `0.4074` | 問題不只是池子太淺 |
| assembler lane | rerank 已命中，但 assembled retention 不足 | `0.7037` | 在未調整 chunking 前最有效 |
| fact-heavy child refinement + assembler v2 | 只對 Dataset / Setup / Metrics 類長 child 做 evidence-centric refinement，再搭配 assembler v2 | `0.7407` | 目前最佳，證明 chunk evidence density 是高 ROI 槓桿 |
| evidence synopsis v3 | 在 v2 基礎上補 alias bridge / task framing bridge / metric-aspect bridge | `0.8519` | 明顯拉高 QASPER recall，但 ranking quality 與 weighted objective 仍未過 |
| coverage lane | 在固定 output budget 下擴大 pre-assembly coverage | `0.3704` | 雜訊高、低 ROI |
| heading-aware recall | 用 heading lexical hit 補強召回 | `0.5185` | 有訊號，但不是主要瓶頸 |
| parent-first lexical recall | 先 parent lexical hit，再回填 child | `0.4444` | parent hit 太寬，回填仍不精準 |
| parent-group retrieval | child RRF 後先聚合 parent 再選 | `0.6296` | 有幫助，但仍不如 assembler v2 |
| RPC parent-content backfill | 在 `match_chunks` 內直接做 parent-content FTS 回填 | `0.4815` | DB 層回填太粗，效果差 |

### 歷史策略的高階判讀

- `depth / coverage / parent-first / RPC backfill` 已不是優先方向
- `assembler lane` 是第一個明顯有效的高 ROI lane
- `fact-heavy child refinement + assembler v2` 進一步證明：
  **真正高 ROI 的槓桿在 evidence density，而不是單純擴大候選池**
- 因此後續主假設才會自然收斂到 `evidence synopsis`

---

## 基準與主要候選

### Baseline：`production_like_v1`

- run id：`6f1150df-1343-4905-a417-7334ea87c9d6`
- assembled Recall@10：`0.5556`
- assembled nDCG@10：`0.4489`
- assembled MRR@10：`0.4105`

### 先前最佳：`qasper_guarded_assembler_v2_gate`

- run id：`d0e0d683-dc9f-4614-9ce9-9d957165d47c`
- assembled Recall@10：`0.7407`
- assembled nDCG@10：`0.4895`
- assembled MRR@10：`0.4134`

### 目前最佳：`qasper_guarded_evidence_synopsis_v2_gate`

- run id：`caa035c6-5348-4deb-8adf-480ed74b0920`
- assembled Recall@10：`0.7778`
- assembled nDCG@10：`0.5246`
- assembled MRR@10：`0.4481`

### 補充對照：`qasper_guarded_evidence_synopsis_v1_gate`

- run id：`53138aaf-b538-4c9f-a208-0e4d47c9fb79`
- assembled Recall@10：`0.7037`
- assembled nDCG@10：`0.5023`
- assembled MRR@10：`0.4399`

### 高階判讀

- `evidence_synopsis_v2` 已經明確超過 `assembler_v2`
- 這代表：

> 現在的主瓶頸不是再調 generic ranking knob，  
> 而是讓 rerank / assembly 看到更像答案的 evidence 表示

---

## QASPER 分數變化總結

### 相對 `assembler_v2_gate`

- Recall@10：`0.7407 -> 0.7778`（`+0.0370`）
- nDCG@10：`0.4895 -> 0.5246`（`+0.0351`）
- MRR@10：`0.4134 -> 0.4481`（`+0.0347`）

### 相對 baseline

- Recall@10：`0.5556 -> 0.7778`（`+0.2222`）
- nDCG@10：`0.4489 -> 0.5246`（`+0.0757`）
- MRR@10：`0.4105 -> 0.4481`（`+0.0376`）

---

## 雙 benchmark 對照：`production_like_v1` vs `evidence_synopsis_v2_gate / v3_gate`

除了 QASPER，也必須同步看 `tw-insurance-rag-benchmark-v1`。

### Assembled 指標總覽

| Dataset | Profile | Recall@10 | nDCG@10 | MRR@10 | Precision@10 | Doc Coverage@10 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `QASPER` | `production_like_v1` | `0.5556` | `0.4489` | `0.4105` | `0.0593` | `0.9630` |
| `QASPER` | `qasper_guarded_evidence_synopsis_v2_gate` | `0.7778` | `0.5246` | `0.4481` | — | — |
| `QASPER` | `qasper_guarded_evidence_synopsis_v3_gate` | `0.8519` | `0.4499` | `0.3271` | `0.0852` | `1.0000` |
| `tw-insurance-rag-benchmark-v1` | `production_like_v1` | `0.8667` | `0.8131` | `0.7944` | `0.0867` | `1.0000` |
| `tw-insurance-rag-benchmark-v1` | `qasper_guarded_evidence_synopsis_v2_gate` | `0.5667` | `0.2937` | `0.2123` | `0.0567` | `0.9000` |
| `tw-insurance-rag-benchmark-v1` | `qasper_guarded_evidence_synopsis_v3_gate` | `0.5667` | `0.2937` | `0.2123` | `0.0567` | `0.9000` |

> 註：
> - QASPER 這裡延用本文前段既有的最佳 gate 記錄。
> - QASPER 的 `Precision@10` / `Doc Coverage@10` 在此摘要未一併列出，因此以 `—` 保留。

### 自家 benchmark 的 stage-by-stage 對照

| Profile | Stage | Recall@10 | nDCG@10 | MRR@10 | Precision@10 | Doc Coverage@10 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `production_like_v1` | recall | `0.8667` | `0.6017` | `0.5260` | `0.1600` | `1.0000` |
| `production_like_v1` | rerank | `0.8667` | `0.8131` | `0.7944` | `0.0867` | `1.0000` |
| `production_like_v1` | assembled | `0.8667` | `0.8131` | `0.7944` | `0.0867` | `1.0000` |
| `qasper_guarded_evidence_synopsis_v2_gate` | recall | `0.8667` | `0.6017` | `0.5260` | `0.1600` | `1.0000` |
| `qasper_guarded_evidence_synopsis_v2_gate` | rerank | `0.5000` | `0.2583` | `0.1873` | `0.0500` | `0.9000` |
| `qasper_guarded_evidence_synopsis_v2_gate` | assembled | `0.5667` | `0.2937` | `0.2123` | `0.0567` | `0.9000` |
| `qasper_guarded_evidence_synopsis_v3_gate` | recall | `0.8667` | `0.6017` | `0.5260` | `0.1600` | `1.0000` |
| `qasper_guarded_evidence_synopsis_v3_gate` | rerank | `0.5000` | `0.2583` | `0.1873` | `0.0500` | `0.9000` |
| `qasper_guarded_evidence_synopsis_v3_gate` | assembled | `0.5667` | `0.2937` | `0.2123` | `0.0567` | `0.9000` |

### 關鍵判讀

1. 同一策略在兩個 benchmark 上反應方向不同
   - QASPER：`evidence_synopsis_v2_gate` 優於 `production_like_v1`
   - self benchmark：`production_like_v1` 明顯優於 `evidence_synopsis_v2_gate`

2. 自家 benchmark 的正式最佳仍是 `production_like_v1`
   - assembled Recall@10：`0.8667`
   - assembled nDCG@10：`0.8131`
   - assembled MRR@10：`0.7944`

3. `evidence_synopsis_v2_gate` 在自家 benchmark 上的主要退化發生在 rerank / assembled
   - recall stage 幾乎相同
   - 真正問題不在候選召回，而在 rerank 後與最終組裝

4. 這不是完全同質的 apples-to-apples 比較
   - `production_like_v1` 使用 **真實 Cohere rerank**
   - `qasper_guarded_evidence_synopsis_v2_gate` 使用 **deterministic rerank**
   - 因此這裡的用途主要是判讀：
     - 它能否作為 gate 的方向性訊號
     - 它是否在 self benchmark 上出現明顯退化

5. 這也解釋了為什麼後續必須改成 weighted multi-benchmark objective

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

- `evidence_synopsis_v2` 已經超過 `assembler_v2`
- 代表高 ROI 來源不是 recall 深度、coverage 或 generic fact alignment

### 2. hardest cases 幾乎都卡在 semantic gap

- 6 題 miss 中有 4 題是 pure recall miss
- 這 4 題都不是沒有 evidence，而是 **query framing 與 evidence framing 不一致**

### 3. assembler 問題已縮到單點修補

- assembled-only miss 只剩 1 題
- assembler 不再是主戰場

---

## 後續實驗更新：`evidence_synopsis_v3_gate`

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

> **在不再追 Recall 的前提下，修補 v3 的 ranking quality**

換句話說，下一輪不應再只是把 bridge 加得更重，而應聚焦：

- 如何讓 alias / task / metric bridge 不只提高 hit rate
- 還能維持或提升 rerank quality（nDCG / MRR）

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
