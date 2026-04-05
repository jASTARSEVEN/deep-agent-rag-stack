# External 100Q Miss Analysis（2026-04-05 重跑版）

## 文件目的

此文件整理 `qasper-curated-v1-100` 與 `uda-curated-v1-100` 在 `2026-04-05` 重新執行 `production_like_v1` 後的最新 miss 題目、失敗階段與原因歸類。

本輪只看新的兩個 run：

- `QASPER 100` run id：`653032cb-9694-4878-915a-d73ebddd006d`
- `UDA 100` run id：`986c130d-6ccf-45b8-a47f-a07e15753ec0`

本輪 `production_like_v1` 的重要前提：

- `retrieval_evidence_synopsis_variant = generic_v1`
- `retrieval_query_focus_enabled = false`
- `assembler = 10 x 3600`

因此，這份文件不再沿用舊版「`generic_field_focus_v1` 已在主線啟用」的假設。

## 總結

### Assembled 指標

| Dataset | Recall@10 | nDCG@10 | MRR@10 |
| --- | ---: | ---: | ---: |
| `QASPER 100` | `0.6200` | `0.3903` | `0.3183` |
| `UDA 100` | `0.8600` | `0.6972` | `0.6447` |

### Miss 統計

| Dataset | miss 總數 | `recall_only` | `rerank_only` | `assembled_only` |
| --- | ---: | ---: | ---: | ---: |
| `QASPER 100` | `38` | `35` | `2` | `1` |
| `UDA 100` | `14` | `12` | `2` | `0` |

### 直接結論

1. `QASPER 100` 的主問題仍是英文 generic evidence-field semantic gap。
2. `UDA 100` 的主問題仍是 same-document locality / list-table / later-section localization。
3. 這一輪 `production_like_v1` 沒有啟用 query focus，因此 planner coverage 為：
   - `QASPER 100`：`0 / 100`
   - `UDA 100`：`0 / 100`
4. 舊版文件裡「planner coverage 太窄」的結論，現在要改寫成：
   - current baseline 根本沒有打開 planner
   - 若要驗證 `english_field_focus_v2`，必須以新的 guarded lane 額外比較

## 原因代碼

| 代碼 | 含義 |
| --- | --- |
| `R1` | generic dataset / corpus / size / language / pretraining source 問法，與 gold chunk 的具體欄位名稱不對齊 |
| `R2` | baseline / benchmark / architecture / algorithm / state-of-the-art inventory 問法，與其他論文的 generic section 高度撞詞 |
| `R3` | experiments / metrics / robustness / comparison axes 問法太泛，retrieval 被其他 `Experiments` / `Results` 區塊吸走 |
| `R4` | method / task definition / annotation detail 問法需要更明確的 field alias，否則只會抓到 intro 或 related work |
| `R5` | 結論 / comparative finding / take-away 類問法，答案在 discussion/conclusion phrasing，不在顯眼 heading |
| `R6` | 已抓到正確文件，但答案在 later section / list / table / subsection；article lead 或歷史段落壓過真正 span |
| `R7` | rerank 辨識失敗；generic baseline wording 或 entity-role wording 讓正確頁面被別的相似頁面壓下去 |
| `R8` | rerank 已接近正確 evidence，但 assembler 因長 parent / budget / context cap 沒保住真正 answer span |

## Batch 1：QASPER `R1` 資料集 / 語料 / 規模 / 屬性

此批共 `14` 題。

| 題目 | miss | 原因 |
| --- | --- | --- |
| `How big is seed lexicon used for training?` | `recall_only` | `R1`：gold 在 appendix 的 `15 positive / 15 negative words`；generic size 問法被 training setting chunks 吸走 |
| `How large is raw corpus used for training?` | `recall_only` | `R1`：gold 是 `about 100 million sentences` 類 corpus scale 描述；query 沒帶 `event pairs / corpus` bridge |
| `Do they report results only on English data?` | `recall_only` | `R1`：語言範圍屬性問法；retrieval 漂到其他資料集說明 |
| `What data is the language model pretrained on?` | `recall_only` | `R1`：gold 是 `Chinese general corpus`；query 與 chunk wording 不對齊 |
| `How big is the dataset?` | `recall_only` | `R1`：generic dataset size；top hits 仍是別的 corpus overview |
| `What is the size of this dataset?` | `recall_only` | `R1`：generic dataset size；沒有 bridge 到實際資料量描述 |
| `Which corpora do they use?` | `recall_only` | `R1`：generic corpora 問法；被其他 corpus sections 吸走 |
| `Which paired corpora did they use in the other experiment?` | `recall_only` | `R1`：`other experiment + paired corpora` 組合太弱，沒召回到正確 experiment paragraph |
| `What dataset do they use?` | `recall_only` | `R1`：generic dataset 問法；被同 paper 其他段落壓過 |
| `Which real-world datasets did they use?` | `recall_only` | `R1`：dataset list 問法；top hits 是其他 papers 的 dataset sections |
| `Is the dataset multilingual?` | `recall_only` | `R1`：dataset property 問法；retrieval 漂到其他 multilingual corpus |
| `Over which datasets/corpora is this work evaluated?` | `recall_only` | `R1`：evaluation corpus 描述不在顯眼 dataset heading；generic query 沒定位到 setup span |
| `What are the corpora used for the task?` | `recall_only` | `R1`：task corpora 問法；抓到 generic dataset paragraphs，沒進到真正 experiment corpora 句子 |
| `what datasets were used?` | `recall_only` | `R1`：gold 在具體資料集列舉句；generic dataset query 仍與 crowd/overview wording 沒對齊 |

## Batch 2：QASPER `R2` baseline / model / architecture inventory

此批共 `7` 題，比舊版少 `1` 題；`what are the state of the art approaches?` 已不再屬於最新 miss 集合。

| 題目 | miss | 原因 |
| --- | --- | --- |
| `What are strong baseline models in specific tasks?` | `recall_only` | `R2`：baseline list 在 comparison paragraph；generic baseline wording 與其他 paper 強烈撞詞 |
| `Which baselines did they compare?` | `recall_only` | `R2`：generic baseline inventory；top hits 多為別篇 paper 的 baseline sections |
| `What is the accuracy reported by state-of-the-art methods?` | `recall_only` | `R2`：SOTA accuracy 問法太泛；被其他 results sections 取代 |
| `What baseline is used for the experimental setup?` | `recall_only` | `R2`：baseline/setup wording 太 generic；未對齊到真正 implementation paragraph |
| `What is the algorithm used for the classification tasks?` | `recall_only` | `R2`：algorithm 名稱藏在方法細節；query 沒提供 method alias |
| `Which neural network architectures are employed?` | `recall_only` | `R2`：architecture inventory 問法；retrieval 被 generic neural network 描述吸走 |
| `What are the benchmark models?` | `recall_only` | `R2`：benchmark models 在 benchmark subsection；目前仍只抓到 broad benchmark intro |

## Batch 3：QASPER `R3` experiments / metrics / evaluation protocol

此批共 `4` 題，比舊版少 `1` 題；`What aspects have been compared between various language models?` 已不再屬於最新 miss 集合。

| 題目 | miss | 原因 |
| --- | --- | --- |
| `Do they evaluate grammaticality of generated text?` | `recall_only` | `R3`：yes/no evaluation dimension；gold 在 evaluation subsection，不在明顯 heading |
| `Which experiments are perfomed?` | `recall_only` | `R3`：generic experiment inventory；只抓到其他 baseline/results sections |
| `How they measure robustness in experiments?` | `recall_only` | `R3`：robustness protocol 問法太泛；沒有 metric/procedure alias |
| `What experiments with large-scale features are performed?` | `recall_only` | `R3`：`large-scale features` 沒成功錨定到真正 experiment enumeration |

## Batch 4：QASPER `R4` method / task definition / annotation detail

此批維持 `6` 題。

| 題目 | miss | 原因 |
| --- | --- | --- |
| `What are the specific tasks being unified?` | `recall_only` | `R4`：gold 是多種 question type 的列舉；query 沒 bridge 到 annotation sentence |
| `How they introduce domain-specific features into pre-trained language model?` | `recall_only` | `R4`：真正答案是 specific integration 細節；目前只抓到 broad pre-trained LM 段落 |
| `How are the different senses annotated/labeled?` | `recall_only` | `R4`：annotation label schema 問法；需要 `sense inventory / label` alias |
| `How do they combine text representations with the knowledge graph embeddings?` | `recall_only` | `R4`：method integration 細節不在顯眼 heading；query 太抽象 |
| `Which ASR system(s) is used in this work?` | `recall_only` | `R4`：ASR setup buried in baseline/oracle notation；query 沒抓到 system setting clause |
| `How was the corpus annotated?` | `recall_only` | `R4`：annotation process 在 dialogue annotation paragraph；generic corpus wording 容易漂到別的 annotated corpus |

## Batch 5：QASPER 殘餘 `R5 / R7 / R8`

此批共 `7` 題，比舊版少 `1` 題；`What experiments do the authors present to validate their system?` 已不再屬於最新 miss 集合。

| 題目 | miss | 原因 |
| --- | --- | --- |
| `How many reviews in total (both generated and true) do they evaluate on Amazon Mechanical Turk?` | `assembled_only` | `R8`：答案依賴同段內兩個數字；rerank 已接近，但 assembled 沒保住核心數字 span |
| `What turn out to be more important high volume or high quality data?` | `recall_only` | `R5`：comparative finding 在 conclusion phrasing，不在顯眼 setup heading |
| `What is the baseline for the experiments?` | `rerank_only` | `R7`：recall 已碰到正確 evidence，但 rerank 對 generic baseline wording 判別仍不穩 |
| `What misbehavior is identified?` | `recall_only` | `R5`：答案在 analysis/finding 段落；query 沒對齊具體 error pattern wording |
| `By how much do they outperform standard BERT?` | `recall_only` | `R5`：需要抓 numeric improvement claim；generic comparative phrasing 太弱 |
| `What new metrics are suggested to track progress?` | `rerank_only` | `R7`：recall 已在正確 paper，但 rerank 偏好 generic current metrics 段落，沒保住 future-work metrics |
| `what are the advantages of the proposed model?` | `recall_only` | `R5`：優勢是結論/比較結果，不是方法描述本身 |

## Batch 6：UDA `R6` same-document locality / list-table answer

此批共 `12` 題，比舊版少 `3` 題；以下三題已不再屬於最新 miss：

- `how many goals has barcelona scored this season`
- `where will this year's army-navy game be played`
- `where is the army navy game usually played`

| 題目 | miss | 原因 |
| --- | --- | --- |
| `who did england play in 2002 world cup` | `recall_only` | `R6`：答案在 qualification / knockout 對戰列表，不在 lead |
| `who won the football world cup in 2002` | `recall_only` | `R6`：champion 句子在 tournament narrative / knockout span |
| `who did boston beat in the 2004 world series` | `recall_only` | `R6`：對手資訊在 series matchup/history span，不在 lead |
| `when does season 12 of americas got talent end` | `recall_only` | `R6`：season finale date 在 `Season 12 (2017)` subsection；lead/season 13 noise 仍會蓋過 |
| `where does the army navy game take place` | `recall_only` | `R6`：venue facts 在 venues section；目前仍停在 article lead |
| `from the land of the moon movie cast` | `recall_only` | `R6`：cast list 在條列區塊，不是 article lead |
| `when was the last time georgia tech won a national championship` | `recall_only` | `R6`：最後一次冠軍年份在 history/achievements span；lead 沒給答案 |
| `who plays jackie in it's always sunny` | `recall_only` | `R6`：角色 mention 在 later paragraph，不是 lead |
| `when does lauren daigle's album come out` | `recall_only` | `R6`：album release date 在 career/discography subsection；lead 沒覆蓋 |
| `when did you say by lauren daigle come out` | `recall_only` | `R6`：single release date 在 song/career span；article lead 壓過 |
| `who plays the male version of sophia in oitnb` | `recall_only` | `R6`：正確人物頁已在前列，但 role mention 在 later paragraph，不在 lead |
| `how many seasons did law and order criminal intent run` | `recall_only` | `R6`：答案在 `Episodes / Seasons` section；lead/overview 沒覆蓋 season count |

## Batch 7：UDA `R7` rerank entity-role confusion

此批仍為 `2` 題。

| 題目 | miss | 原因 |
| --- | --- | --- |
| `who plays benny on the tv show bull` | `rerank_only` | `R7`：recall 已有 `Freddy Rodriguez`，但 rerank 把 generic actor pages 壓到前面 |
| `who is the violinist on dancing with the stars 2017` | `rerank_only` | `R7`：recall 已有 `Lindsey Stirling`，但 rerank 被 `DWTS` page / references noise 帶走 |

## 跨資料集判讀

### 1. QASPER 仍然不是單純加深 recall depth 就能解

- 最新 `38` 題 miss 中，`35` 題仍是 `recall_only`。
- 問題仍集中在 `dataset / corpus / size / baseline / experiment / annotation` 這批 generic field wording。
- `assembled_only` 只剩 `1` 題，表示主戰場不是 assembler 擴窗。

### 2. UDA 仍然不是 document recall 問題，而是頁內 localization 問題

- 最新 `14` 題 miss 中，`12` 題仍是 `recall_only`。
- 題型仍集中在 cast、venue、season、release-date、history 這種 later section / list / subsection answer。
- 這說明 current baseline 的主要缺口，仍是「進到正確 wiki page 後沒有打到正確 section」。

### 3. current `production_like_v1` 沒有 planner coverage

- `QASPER 100`：`0 / 100`
- `UDA 100`：`0 / 100`

因此舊版「planner 只打到少數題」的說法，現在要改成：

> current baseline 沒有啟用 query focus；若下一輪要處理英文 semantic-gap，必須把 planner / field-focus 當成顯式 guarded lane 來驗證。

## 最有價值的改善方案

### Primary：`english_field_focus_v2`

下一輪唯一主假設仍建議鎖定：

> 對英文 generic evidence-field query 增加 field-aware planner / alias bridge，讓 retrieval 與 rerank 在高信心時能更明確知道使用者是在找 `dataset`、`corpus`、`size`、`baseline`、`experiment`、`metric`、`annotation` 或 `pretraining source`。

但這次要明確補一個限制：

- 它必須是新的 guarded lane
- 不能再把它描述成 `production_like_v1` 既有能力

### Secondary：`same_document_section_anchor_v1`

只有在 `english_field_focus_v2` 驗證完之後，才值得開下一條 lane 去處理 `UDA` 型 miss：

- 當 top document 已正確時，對 page 內 `cast / venues / seasons / discography / release` 這類 section 做局部 anchor boost
- 預期主要改善 `UDA`
- 不應該搶在英文 field semantic-gap 之前
