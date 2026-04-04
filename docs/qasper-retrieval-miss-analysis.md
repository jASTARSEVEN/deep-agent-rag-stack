# QASPER Retrieval Miss Analysis（截至 2026-04-04，evidence synopsis v2 後）

## 目的

此文件聚焦分析 **目前最佳 deterministic gate run** 仍未命中的題目，並據此判斷下一步最值得投入的改善策略。  
重點不是再回顧所有歷史 lane，而是回答三個問題：

1. 目前最佳 lane 是哪一條？
2. 它還剩哪些 miss？
3. 下一步應優先繼續擴張 evidence synopsis，還是回頭調整其他 retrieval 形狀？

---

## 基準與最佳候選

### Baseline
- run id：`6f1150df-1343-4905-a417-7334ea87c9d6`
- profile：`production_like_v1`
- assembled Recall@10：`0.5556`
- assembled nDCG@10：`0.4489`
- assembled MRR@10：`0.4105`

### 先前最佳：assembler v2
- run id：`d0e0d683-dc9f-4614-9ce9-9d957165d47c`
- profile：`qasper_guarded_assembler_v2_gate`
- assembled Recall@10：`0.7407`
- assembled nDCG@10：`0.4895`
- assembled MRR@10：`0.4134`

### 目前最佳：evidence synopsis v2
- run id：`caa035c6-5348-4deb-8adf-480ed74b0920`
- profile：`qasper_guarded_evidence_synopsis_v2_gate`
- assembled Recall@10：`0.7778`
- assembled nDCG@10：`0.5246`
- assembled MRR@10：`0.4481`

### 補充對照：evidence synopsis v1
- run id：`53138aaf-b538-4c9f-a208-0e4d47c9fb79`
- profile：`qasper_guarded_evidence_synopsis_v1_gate`
- assembled Recall@10：`0.7037`
- assembled nDCG@10：`0.5023`
- assembled MRR@10：`0.4399`

關鍵判讀：
- `evidence_synopsis_v2` 已經明確**超過** `assembler_v2`。
- 這證明上一輪判斷是對的：
  **現在的主瓶頸不是再調 generic ranking knob，而是讓 rerank / assembly 看到更像答案的 evidence 表示。**

---

## 分數變化總結

相對 `assembler_v2_gate`：
- assembled Recall@10：`0.7407 -> 0.7778`（`+0.0370`）
- assembled nDCG@10：`0.4895 -> 0.5246`（`+0.0351`）
- assembled MRR@10：`0.4134 -> 0.4481`（`+0.0347`）

相對 baseline：
- assembled Recall@10：`0.5556 -> 0.7778`（`+0.2222`）
- assembled nDCG@10：`0.4489 -> 0.5246`（`+0.0757`）
- assembled MRR@10：`0.4105 -> 0.4481`（`+0.0376`）

---

## `evidence_synopsis_v2` 剩餘 miss 分布

在 `qasper_guarded_evidence_synopsis_v2_gate` 下，27 題中已命中 21 題，仍有 6 題 miss：

- `4` 題：`recall_hit=false`
- `1` 題：`recall_hit=true` 但 `rerank_hit=false`
- `1` 題：`rerank_hit=true` 但 `assembled_hit=false`

和 `assembler_v2` 相比，改善點很清楚：
- 原本的兩題 rerank miss 中，**`How big is seed lexicon used for training?` 已被解掉**。
- assembled-only miss 仍然保留 1 題。
- 純 recall miss 仍然是 4 題，表示下一步要打的主戰場已經更聚焦：
  **剩下的 hardest cases 幾乎全是 query-to-evidence semantic gap。**

---

## `evidence_synopsis_v2` 剩餘 6 題逐題分析

## A. 純 recall miss（4 題）

### 1. `What are labels available in dataset for supervision?`
- file：`Minimally-Supervised-Learning-of-Affective-Events-Using-Discourse-Relations.md`
- gold span：`negative`（另一個 label 對應 `positive`）
- 所在 parent：`Abstract / Introduction`
- parent chars：`3089`
- child chars：`587`
- child 內容重點：
  - `positive or negative ways`
  - `score ranging from -1 (negative) to 1 (positive)`

判讀：
- evidence synopsis 已經幫助不少 fact-heavy dataset / metrics 類內容，但這題落在 `Introduction` 類敘述段。
- query 問的是 `labels available in dataset for supervision`，正文卻是在用自然語言解釋 polarity。
- 目前問題不是沒有 evidence，而是 **label/schema 語言沒有顯性化**。

### 2. `What are the specific tasks being unified?`
- file：`Question-Answering-based-Clinical-Text-Structuring-Using-Pre-trained-Language-Model.md`
- 所在 parent：`Experimental Studies ::: Dataset and Evaluation Metrics`
- parent chars：`1072`
- refined child chars：`176`
- child 內容重點：
  - `three types of questions, namely tumor size, proximal resection margin and distal resection margin`

判讀：
- 這題最接近「再做一點對的 synopsis 就可能翻過去」。
- 現在 child 已很短，但 query 用的是 `tasks being unified`，正文用的是 `types of questions`。
- 這是一個典型的 **task framing mismatch**。

### 3. `How big is QA-CTS task dataset?`
- file：`Question-Answering-based-Clinical-Text-Structuring-Using-Pre-trained-Language-Model.md`
- 所在 parent：`Experimental Studies ::: Dataset and Evaluation Metrics`
- parent chars：`1072`
- refined child chars：`81`
- child 內容重點：
  - `17,833 sentences, 826,987 characters and 2,714 question-answer pairs`

判讀：
- 這題仍然是最典型的 **dataset alias mismatch**。
- evidence synopsis 已證明「數值 summary」有用，但還不夠把 `QA-CTS` 這個 alias 補進 evidence 表示。
- 因此這題仍然卡在 query alias 與正文統計描述不對齊。

### 4. `What aspects have been compared between various language models?`
- file：`Progress-and-Tradeoffs-in-Neural-Language-Models.md`
- 所在 parent：`Experimental Setup`
- parent chars：`1138`
- 核心 child chars：`120` / `138`
- child 內容重點：
  - `perplexity, R@3 in next-word prediction, latency, energy usage`

判讀：
- 這題已經有良好的 metric list evidence，但 query 使用的是抽象詞 `aspects compared`。
- 現在的 synopsis 還不夠明確把「這些 metric 就是 compared aspects」講出來。
- 換句話說，**metric-list aware synopsis 已經接近有效，但還差最後一哩。**

---

## B. recall 命中，但 rerank 還保不住（1 題）

### 5. `How big is the Japanese data?`
- file：`Minimally-Supervised-Learning-of-Affective-Events-Using-Discourse-Relations.md`
- `evidence_synopsis_v2`：`recall_hit=true`, `rerank_hit=false`
- recall rank：`8`

關鍵特徵：
- gold evidence 不是一個單句，而是跨多段：
  - Japanese web corpus
  - 100 million sentences
  - ACP corpus / split
- 也就是說，這是一題 **multi-span, multi-parent numeric synthesis** 題。

判讀：
- 這題已經不像一般 fact lookup，而比較像「先聚 evidence 再回答」的小型 synthesis 問題。
- 目前 rerank text 即使加了 synopsis，仍然沒有把多段 evidence 合成成單一高信號文件表示。

結論：
- 這題不是下一輪主假設的最佳代表，因為它太像 edge case。
- 若要處理，應該是更後面的 **multi-span evidence synopsis** 或 **cross-window surrogate assembly**。

---

## C. rerank 命中，但 assembler retention 仍失敗（1 題）

### 6. `Which dataset do they use a starting point in generating fake reviews?`
- file：`Stay-On-Topic-Generating-Context-specific-Fake-Restaurant-Reviews.md`
- `evidence_synopsis_v2`：`recall_hit=true`, `rerank_hit=true`, `assembled_hit=false`
- recall rank：`5`
- rerank rank：`2`
- 所在 parent：`Generative Model`
- parent chars：`42574`
- answer-bearing child chars：`381`
- child 內容重點：
  - `we use the Yelp Challenge dataset`

判讀：
- 這題現在已經非常明確：
  - retrieval 不是問題
  - rerank 也不是問題
  - 問題只剩 assembler 沒把短而準的 hit child carry-through 到 final context
- 它是目前最純的 **assembler-only miss**。

結論：
- 這題應該列為下一輪的 secondary follow-up，而不是主假設。
- 最直接的做法是：
  - 當 rerank rank 很高、且 child 本身短而準時，assembler 應優先保留該 child verbatim。

---

## 這一輪 evidence synopsis 真正證明了什麼

### 1. 證明「evidence 表示」比 generic ranking knob 更重要
- `evidence_synopsis_v2` 已經超過 `assembler_v2`。
- 因此目前最佳提升來源，不是 recall 深度，不是 coverage，也不是 generic fact alignment score。

### 2. 證明剩餘 hardest cases 幾乎都在 semantic gap
- 6 題 miss 中有 4 題都是 pure recall miss。
- 而這 4 題都不是沒有 evidence，而是 **query framing 與 evidence framing 不同**。

### 3. 證明 assembler 問題已縮到單點修補
- assembled-only miss 現在只剩 1 題。
- 代表 assembler 不再是主戰場，只需要對 giant parent carry-through 做精修。

---

## 最值得的改善策略（最新判斷）

## Primary：深化 evidence synopsis，而不是回頭調整 retrieval 形狀

下一輪最值得投入的唯一主假設應該是：

> **benchmark-gated evidence synopsis v3：把 alias / task framing / metric framing 做得更顯性、更接近 query wording。**

### 最值得補強的三種 synopsis 能力

1. **dataset alias bridge**
- 目標題：`How big is QA-CTS task dataset?`
- 做法：讓 synopsis 顯性帶出 `dataset alias / task dataset / QA-CTS-style dataset statistics` 類橋接詞。

2. **task / label framing bridge**
- 目標題：
  - `What are the specific tasks being unified?`
  - `What are labels available in dataset for supervision?`
- 做法：讓 synopsis 不只是重述內容，而是明確翻成：
  - `This passage lists the task types being unified...`
  - `This passage states the supervision labels...`

3. **metric-aspect bridge**
- 目標題：`What aspects have been compared between various language models?`
- 做法：把 metric list 轉成更像 query wording 的 synopsis，例如：
  - `This passage states the compared aspects across models, including ...`

---

## Secondary：assembler carry-through 精修

只針對這一題：
- `Which dataset do they use a starting point in generating fake reviews?`

建議策略：
- 若 rerank 已把某個短 child 排到前段，且該 child 直接覆蓋 gold span，assembler 應先保留該 child 原文，再做周邊補文。
- 這應作為第二優先，不應和下一輪的 synopsis 主假設混在同一輪一起做。

---

## 目前不建議優先做的方向

- 再加深 recall pool
- 再擴大 coverage lane
- 再回去做 generic fact alignment score 微調
- 再做粗粒度 parent lexical / RPC backfill
- 再把 assembler window 當主要策略擴張

原因：
- 它們已被最新結果證明不是最高 ROI。
- 現在主問題不是候選池不夠大，而是 **evidence 還不夠像 query 想找的答案**。

---

## 後續建議

若要開下一輪，建議把唯一主假設設定為：

> **benchmark-gated evidence synopsis v3 for semantic-gap fact queries**

成功標準建議設定為：
- 先解掉以下 4 題中的至少 2 題：
  - `What are labels available in dataset for supervision?`
  - `What are the specific tasks being unified?`
  - `How big is QA-CTS task dataset?`
  - `What aspects have been compared between various language models?`
- 同時不得讓 `evidence_synopsis_v2` 已命中的 21 題退化
- giant-parent assembled-only miss 則作為下一個 secondary lane 處理
