# External 100Q Miss Analysis（2026-04-04）

## 文件目的

此文件完整整理 `qasper-curated-v1-100` 與 `uda-curated-v1-100` 在 `production_like_v1` reference run 下的 miss 題目、失敗階段與原因歸類，供下一輪 benchmark-driven 改善直接決策。

本輪分析只看正式 reference run：

- `QASPER 100` run id：`54c297d7-260b-40eb-88cf-999026ca9d6d`
- `UDA 100` run id：`0274c530-8171-4f0f-bd86-bce82c15f5d7`

逐題診斷依據：

1. `run_retrieval_eval report` 的 `per_query`
2. 只針對 miss 題重跑 `preview_evaluation_candidates(top_k=10)`
3. 比對 gold span、recall/rerank/assembled candidates 的 `heading / excerpt / full_hit_rank`

---

## 總結

### Miss 統計

| Dataset | miss 總數 | `recall_only` | `rerank_only` | `assembled_only` |
| --- | ---: | ---: | ---: | ---: |
| `QASPER 100` | `41` | `37` | `2` | `2` |
| `UDA 100` | `17` | `15` | `2` | `0` |

### 診斷訊號

| Dataset | gold doc 已在 recall top1 | gold doc 已在 recall top3 | gold doc 已在 recall top5 | 任一 stage 存在 `full_hit_rank` |
| --- | ---: | ---: | ---: | ---: |
| `QASPER 100` | `5 / 41` | `11 / 41` | `15 / 41` | `5 / 41` |
| `UDA 100` | `14 / 17` | `17 / 17` | `17 / 17` | `5 / 17` |

### 直接結論

1. `QASPER 100` 的主問題是 **chunk-level semantic gap**，不是單純 recall pool 太淺。
2. `UDA 100` 的主問題是 **same-document locality / list-table answer localization**；大多數 miss 題其實第一頁就抓到正確文件，但停在 article lead、歷史段落或 revision noise。
3. `generic_field_focus_v1` 在這兩份 external 100Q 上幾乎沒有真正打到 miss 主戰場：
   - `QASPER 100`：只有 `2 / 100` 題啟用 planner；在 `41` 題 miss 中只有 `1` 題啟用。
   - `UDA 100`：`0 / 100` 題啟用 planner。
4. 因此下一輪最高 ROI 主假設不該是加深 recall depth，也不該再擴 assembler window，而是補目前 planner 與 rerank 都還沒理解到的 **英文 generic evidence field intent**。

---

## 原因代碼

| 代碼 | 含義 |
| --- | --- |
| `R1` | generic dataset / corpus / size / language / pretraining source 問法，與 gold chunk 的具體欄位名稱不對齊 |
| `R2` | baseline / benchmark / architecture / algorithm / state-of-the-art inventory 問法，與其他論文的 generic section 高度撞詞 |
| `R3` | experiments / metrics / robustness / comparison axes 問法太泛，retrieval 被其他 `Experiments` / `Results` 區塊吸走 |
| `R4` | method / task definition / annotation detail 問法需要更明確的 field alias，否則只會抓到 intro 或 related work |
| `R5` | 結論 / comparative finding / take-away 類問法，答案在 discussion/conclusion phrasing，不在顯眼 heading |
| `R6` | 已抓到正確文件，但答案在 later section / list / table / subsection；article lead 或 revision noise 壓過真正 span |
| `R7` | rerank 辨識失敗；generic baseline wording 或 entity-role wording 讓正確頁面被別的相似頁面壓下去 |
| `R8` | rerank 已接近正確 evidence，但 assembler 因長 parent / budget / context cap 沒保住真正 answer span |

---

## Batch 1：QASPER `R1` 資料集 / 語料 / 規模 / 屬性

此批共 `14` 題，特徵是 query 幾乎都在問 generic metadata，但 gold evidence 常寫成非常具體的欄位、數字或 appendix 語句；目前主線沒有把這些欄位做成 planner / rerank 可辨識的 field type。

| # | 題目 | miss | 原因 |
| --- | --- | --- | --- |
| 1 | `How big is seed lexicon used for training?` | `recall_only` | `R1`：gold 在 appendix 的 `15 positive / 15 negative words`；generic size 問法被 training setting chunks 吸走 |
| 2 | `How large is raw corpus used for training?` | `recall_only` | `R1`：gold 是 `about 100 million sentences` 這類 corpus scale 描述；query 沒帶 `event pairs / corpus` bridge |
| 3 | `Do they report results only on English data?` | `recall_only` | `R1`：語言範圍屬性問法；retrieval 漂到其他英德資料集說明 |
| 4 | `What data is the language model pretrained on?` | `recall_only` | `R1`：gold 是 `Chinese general corpus`；query 與 chunk wording 不對齊 |
| 12 | `How big is the dataset?` | `recall_only` | `R1`：generic dataset size；top hits是別的 corpus overview |
| 13 | `What is the size of this dataset?` | `recall_only` | `R1`：generic dataset size；沒有 bridge 到實際資料量描述 |
| 18 | `Which corpora do they use?` | `recall_only` | `R1`：generic corpora 問法；被其他 corpus sections 吸走 |
| 22 | `Which paired corpora did they use in the other experiment?` | `recall_only` | `R1`：`other experiment + paired corpora` 組合太弱，沒召回到正確 experiment paragraph |
| 24 | `What dataset do they use?` | `recall_only` | `R1`：generic dataset 問法；被同 paper 其他 BERT/KG 段落壓過 |
| 27 | `Which real-world datasets did they use?` | `recall_only` | `R1`：dataset list 問法；top hits是其他 papers 的 dataset sections |
| 28 | `Is the dataset multilingual?` | `recall_only` | `R1`：dataset property 問法；retrieval 漂到其他 multilingual corpus |
| 33 | `Over which datasets/corpora is this work evaluated?` | `recall_only` | `R1`：evaluation corpus 描述不在顯眼 dataset heading；generic query 沒定位到 setup span |
| 34 | `What are the corpora used for the task?` | `recall_only` | `R1`：task corpora 問法；抓到 generic dataset paragraphs，沒進到真正 experiment corpora 句子 |
| 39 | `what datasets were used?` | `recall_only` | `R1`：gold 在 `Reuters-21578 / LabelMe` 段落；generic dataset query 與 crowd setting 描述沒對齊 |

---

## Batch 2：QASPER `R2` baseline / model / architecture inventory

此批共 `8` 題。這些 query 的 wording 幾乎都只說 `baseline`、`benchmark`、`state-of-the-art`、`architecture`，導致 recall 很容易命中別篇論文也同樣含有 `Baselines` / `Experiments` heading 的段落。

| # | 題目 | miss | 原因 |
| --- | --- | --- | --- |
| 7 | `What are strong baseline models in specific tasks?` | `recall_only` | `R2`：baseline list 在 comparison paragraph；generic baseline wording 與其他 paper 強烈撞詞 |
| 10 | `Which baselines did they compare?` | `recall_only` | `R2`：generic baseline inventory；top hits多為別篇 paper 的 baseline sections |
| 15 | `What is the accuracy reported by state-of-the-art methods?` | `recall_only` | `R2`：SOTA accuracy 問法太泛；被其他 results sections 取代 |
| 16 | `What baseline is used for the experimental setup?` | `recall_only` | `R2`：baseline/setup wording 太 generic；未對齊到真正 implementation paragraph |
| 26 | `What is the algorithm used for the classification tasks?` | `recall_only` | `R2`：algorithm 名稱藏在方法細節；query 沒提供 method alias |
| 36 | `Which neural network architectures are employed?` | `recall_only` | `R2`：architecture inventory 問法；retrieval 被 generic neural network 描述吸走 |
| 38 | `what are the state of the art approaches?` | `recall_only` | `R2`：SOTA 問法與各種 results/related work 皆高度相似 |
| 40 | `What are the benchmark models?` | `recall_only` | `R2`：CrossWOZ 的 benchmark models 在 benchmark subsection；目前只抓到 broad benchmark intro |

---

## Batch 3：QASPER `R3` experiments / metrics / evaluation protocol

此批共 `5` 題。共同問題是 query 在問「做了哪些 experiments / metric / robustness measure」，但答案通常是多個具體 evaluation axis 的列舉，而不是單一關鍵字。

| # | 題目 | miss | 原因 |
| --- | --- | --- | --- |
| 8 | `What aspects have been compared between various language models?` | `recall_only` | `R3`：gold 是 `perplexity / R@3 / latency / energy` 四個 axis；query 沒明講 comparison axes |
| 17 | `Do they evaluate grammaticality of generated text?` | `recall_only` | `R3`：yes/no evaluation dimension；gold 在 evaluation subsection，不在明顯 heading |
| 20 | `Which experiments are perfomed?` | `recall_only` | `R3`：generic experiment inventory；只抓到其他 baseline/results sections |
| 30 | `How they measure robustness in experiments?` | `recall_only` | `R3`：robustness protocol 問法太泛；沒有 metric/procedure alias |
| 31 | `What experiments with large-scale features are performed?` | `recall_only` | `R3`：`large-scale features` 沒成功錨定到真正 experiment enumeration |

---

## Batch 4：QASPER `R4` method / task definition / annotation detail

此批共 `6` 題。這些題目其實不是 generic metadata，而是更細的 method field；但目前 query planner 沒把它們視為可 rewrite 的 target field。

| # | 題目 | miss | 原因 |
| --- | --- | --- | --- |
| 5 | `What are the specific tasks being unified?` | `recall_only` | `R4`：gold 是三種 QA question type 的列舉；query 沒 bridge 到 annotation sentence |
| 6 | `How they introduce domain-specific features into pre-trained language model?` | `recall_only` | `R4`：真正答案是 clinical named entity integration；目前只抓到 broad pre-trained LM 段落 |
| 14 | `How are the different senses annotated/labeled?` | `recall_only` | `R4`：annotation label schema 問法；需要 `sense inventory / label` alias |
| 25 | `How do they combine text representations with the knowledge graph embeddings?` | `recall_only` | `R4`：method integration 細節不在顯眼 heading；query 太抽象 |
| 32 | `Which ASR system(s) is used in this work?` | `recall_only` | `R4`：ASR setup buried in baseline/oracle notation；query 沒抓到 system setting clause |
| 41 | `How was the corpus annotated?` | `recall_only` | `R4`：annotation process 在 dialogue annotation paragraph；generic corpus wording 容易漂到別的 annotated corpus |

---

## Batch 5：QASPER 殘餘 `R5 / R7 / R8`

此批共 `8` 題。這些題目不是單純 metadata inventory，而是結論、比較結果或剩餘 ranking / assembler 問題。

| # | 題目 | miss | 原因 |
| --- | --- | --- | --- |
| 11 | `What turn out to be more important high volume or high quality data?` | `recall_only` | `R5`：comparative finding 在 conclusion phrasing，不在顯眼 setup heading |
| 19 | `What is the baseline for the experiments?` | `rerank_only` | `R7`：recall 第 `10` 名已碰到正確 paper，但 rerank 對 generic baseline wording 判別失敗 |
| 21 | `What misbehavior is identified?` | `recall_only` | `R5`：答案在 analysis/finding 段落；query 沒對齊具體 error pattern wording |
| 23 | `By how much do they outperform standard BERT?` | `recall_only` | `R5`：需要抓 numeric improvement claim；generic comparative phrasing 太弱 |
| 29 | `What experiments do the authors present to validate their system?` | `assembled_only` | `R8`：recall 第 `3` 名已命中、rerank 第 `10` 名仍保留，但 assembled context 沒保住真正 validation span |
| 35 | `What new metrics are suggested to track progress?` | `rerank_only` | `R7`：recall 第 `3` 名已在正確 paper，但 rerank 偏好 generic current metrics 段落，沒保住 future-work metrics |
| 37 | `what are the advantages of the proposed model?` | `recall_only` | `R5`：優勢是結論/比較結果，不是方法描述本身 |
| 9 | `How many reviews in total (both generated and true) do they evaluate on Amazon Mechanical Turk?` | `assembled_only` | `R8`：答案依賴同段內兩個數字 (`1006 + 994`)；rerank 已接近，但 assembled 沒保住核心數字 span |

---

## Batch 6：UDA `R6` same-document locality / list-table answer

此批共 `15` 題。它們的共同點是：**正確文件幾乎都已在 recall top1/top3，但 answer span 不在 article lead，而在 list、table、history、season subsection 或 cast/discography 區塊。**

| # | 題目 | miss | 原因 |
| --- | --- | --- | --- |
| 1 | `who did england play in 2002 world cup` | `recall_only` | `R6`：正確文件已 top1，但答案在 qualification / knockout 對戰列表，不在 lead |
| 2 | `who won the football world cup in 2002` | `recall_only` | `R6`：正確文件已 top1，但 champion 句子在 tournament narrative / knockout span |
| 3 | `who did boston beat in the 2004 world series` | `recall_only` | `R6`：正確文件已 top1，但對手資訊在 series matchup/history span，不在 lead |
| 4 | `how many goals has barcelona scored this season` | `recall_only` | `R6`：答案偏向 season stats/table；lead 與 month recap 壓過真正 aggregate stats |
| 5 | `when does season 12 of americas got talent end` | `recall_only` | `R6`：season finale date 在 `Season 12 (2017)` subsection；lead/season 13 noise 蓋過 |
| 6 | `where will this year's army-navy game be played` | `recall_only` | `R6`：future venue 在 `Venues / Future venues`，但 lead/history 先被抓到 |
| 7 | `where does the army navy game take place` | `recall_only` | `R6`：venue facts 在 venues section；目前停在 article lead |
| 8 | `where is the army navy game usually played` | `recall_only` | `R6`：habitual venue 在 history/venues span；lead 與 notable games noise 壓過 |
| 10 | `from the land of the moon movie cast` | `recall_only` | `R6`：cast list 在條列區塊，不是 article lead |
| 11 | `when was the last time georgia tech won a national championship` | `recall_only` | `R6`：最後一次冠軍年份在 history/achievements span；lead 沒給答案 |
| 12 | `who plays jackie in it's always sunny` | `recall_only` | `R6`：正確 bio page 已進前列，但角色 mention 在 career 段，不是 lead |
| 13 | `when does lauren daigle's album come out` | `recall_only` | `R6`：album release date 在 career/discography subsection；lead 沒覆蓋 |
| 14 | `when did you say by lauren daigle come out` | `recall_only` | `R6`：single release date 在 song/career span；article lead 壓過 |
| 15 | `who plays the male version of sophia in oitnb` | `recall_only` | `R6`：正確人物頁已在前列，但 role mention 在 later paragraph，不在 lead |
| 16 | `how many seasons did law and order criminal intent run` | `recall_only` | `R6`：答案在 `Episodes` / `Seasons` section；lead/overview 沒覆蓋 season count |

---

## Batch 7：UDA `R7` rerank entity-role confusion

此批共 `2` 題。兩題都不是 global recall 問題，而是 rerank 對 `entity + role/show/year` 的判別仍不穩。

| # | 題目 | miss | 原因 |
| --- | --- | --- | --- |
| 9 | `who plays benny on the tv show bull` | `rerank_only` | `R7`：recall 第 `3` 名已有 `Freddy Rodriguez`，但 rerank 把 generic actor pages 壓到前面 |
| 17 | `who is the violinist on dancing with the stars 2017` | `rerank_only` | `R7`：recall 第 `2` 名已有 `Lindsey Stirling`，但 rerank 被 `DWTS` page / references noise 帶走 |

---

## 跨資料集判讀

### 1. QASPER 不是加深 recall depth 就能解

- `41` 題 miss 中，只有 `5` 題在任一 stage 出現過 `full_hit_rank`。
- 只有 `15 / 41` 題在 recall top5 內已經抓到 gold document。
- 代表多數 miss 不是「答案在更深的位置而已」，而是 **query 沒把正確 evidence type 帶進來**。

### 2. UDA 不是 document recall 問題，而是 same-document localization 問題

- `17 / 17` 題 miss 在 recall top3 就已抓到 gold document。
- `14 / 17` 題甚至在 recall top1 就是正確文件。
- 但只有 `5 / 17` 題有 `full_hit_rank`，表示真正失敗點是 **正確頁面內的 later section / list / table 沒被命中**。

### 3. 目前 planner coverage 太窄

- `generic_field_focus_v1` 在 `QASPER 100` 只啟用 `2` 題，在 `UDA 100` 完全沒有啟用。
- 本次 miss 主要集中在 planner 尚未覆蓋的 evidence field：
  - `dataset / corpus / size / language scope`
  - `baseline / benchmark / architecture`
  - `experiments / metrics / robustness`
  - `annotation / method detail`

---

## 最有價值的改善方案

### Primary：`english_field_focus_v2`

下一輪唯一主假設建議明確鎖定：

> 對英文 generic evidence-field query 增加 field-aware planner / alias bridge，讓 retrieval 與 rerank 能在高信心時明確知道使用者是在找 `dataset`、`corpus`、`size`、`baseline`、`experiment`、`metric`、`annotation` 或 `pretraining source`。

建議最小實作方向：

1. 在 `query_focus` 增加英文高 ROI field intents：
   - `dataset_source`
   - `dataset_size`
   - `language_scope`
   - `pretraining_source`
   - `baseline_inventory`
   - `architecture_inventory`
   - `experiment_inventory`
   - `metric_inventory`
   - `annotation_scheme`
2. 對這些 intents 只在高信心時產生 field-aware focus query 與 rerank brief。
3. document-side 只補最小 alias，不做新基礎設施：
   - 例如將 `dataset / corpus / benchmark / data source / evaluated on`
   - `baseline / compare against / state-of-the-art`
   - `experiments / evaluation / robustness / metric`
   - `annotation / labels / schema`
   這些欄位詞，收斂到現有 evidence synopsis / rerank wording。

### 為什麼它是最高 ROI

1. 它直接對準 `QASPER` 最大宗 miss：
   - `R1 + R2 + R3 + R4 = 33 / 41`
2. 它也符合目前實測訊號：
   - 目前 planner 幾乎沒有在 external 100Q 啟用，表示 coverage 才是瓶頸。
3. 它不需要擴大 pipeline 邊界：
   - 仍維持 `SQL gate -> vector recall -> FTS recall -> RRF -> rerank -> assembler`
   - 不需要加深 recall pool、也不需要加新 infra。

### Secondary：`same_document_section_anchor_v1`

只有在 `english_field_focus_v2` 驗證完之後，才值得開下一條小 lane 處理 `UDA` 型 miss：

- 當 top1/top3 已是 gold document 時，額外對 page 內 `list / cast / episodes / venues / season / discography` section 做局部 anchor boost。
- 這條 lane 預期主要改善 `UDA`，但對 `QASPER` 的外溢收益有限，因此不應該先做。
