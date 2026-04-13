# Retrieval Benchmark Strategy Analysis（截至 2026-04-13）

## 文件目的

此文件現在只保留對後續 benchmark 治理最有用的六件事：

1. 目前 `production_like_v1` 的真實設定與最新分數。
2. 七個正式 benchmark package 的 current assembled 指標。
3. 七個正式 benchmark package 的客觀 corpus profile，例如主要語系、題數、文件數與 gold span 密度。
4. external `100Q` 各資料集基線的最新狀態。
5. `DuReader-robust 100`、`DRCD 100`、`NQ 100` 與 `MS MARCO 100` 應如何解讀，不要把高分 lane 誤判成整體 hard case 已解完。
6. 下一輪 benchmark-driven 優化仍該把力氣放在哪裡。

## Summary/Compare Pilot Lane

除了現有 retrieval benchmark 主線之外，repo 目前也已新增一條真資料 summary/compare suite：`benchmarks/summary-compare-real-curated-v1`。

此 lane 的定位固定為：

- `phase8a-summary-compare-v1` 仍是唯一 release gate
- 這條 suite 只用於 tuning、橫向比較與長期觀測
- 主輸出只有 `summary_benchmark_score` 與 `compare_benchmark_score`
- benchmark/test retrieval 允許 `explicit_document_ids`，但此能力只屬於 benchmark contract，不進 public chat runtime

### 目前資料集組成

目前 summary/compare 真資料 suite 的 package 組成為：

| Package | 類型 | 來源 |
| --- | --- | --- |
| `qmsum-query-summary-curated-pilot-v1` | `summary` | `QMSum` 官方 test split |
| `multinews-multi-doc-summary-curated-pilot-v1` | `summary` | `Multi-News` 官方 test split |
| `cocotrip-compare-curated-pilot-v1` | `compare` | `CoCoTrip / cocosum` 官方 `anno.json` |
| `lcsts-news-summary-curated-pilot-v1` | `summary` | `LCSTS` 官方 test split |
| `cnewsum-news-summary-curated-pilot-v1` | `summary` | `CNewSum processed` test split |

### 2026-04-13 真資料 suite 最新實跑分數

本輪 current canonical baseline 採 package-level consolidated baseline，而不是單一 aggregate suite artifact。

正式採信的 artifact 如下：

- `artifacts/qmsum-query-summary-curated-pilot-v1-run.json`
- `artifacts/multinews-multi-doc-summary-curated-pilot-v1-run.json`
- `artifacts/lcsts-news-summary-curated-pilot-v1-run.json`
- `artifacts/cnewsum-news-summary-curated-pilot-v1-run.json`
- `artifacts/cocotrip-compare-curated-pilot-v1-run.json`
- `artifacts/cocotrip-rerun-subset.json`

各 package 主分數：

| Package | Family | Main Metric | Score | Run Quality |
| --- | --- | --- | ---: | --- |
| `qmsum-query-summary-curated-pilot-v1` | `summary` | `bert_score_f1` | `0.730954` | clean |
| `multinews-multi-doc-summary-curated-pilot-v1` | `summary` | `bert_score_f1` | `0.709126` | clean |
| `lcsts-news-summary-curated-pilot-v1` | `summary` | `bert_score_f1` | `0.624256` | clean |
| `cnewsum-news-summary-curated-pilot-v1` | `summary` | `bert_score_f1` | `0.621386` | clean |
| `cocotrip-compare-curated-pilot-v1` | `compare` | `pairwise_rubric_judge_win_rate` | `0.000000` | package run partial, but the two affected items were rerun separately and still stayed at `0.0` |

目前可直接彙整的 task-family 主分數為：

| Score | Value |
| --- | ---: |
| `summary_benchmark_score` | `0.671431` |
| `compare_benchmark_score` | `0.000000` |

其中 `summary_benchmark_score` 為四個 summary package 的等權平均：

- `(0.730954 + 0.709126 + 0.624256 + 0.621386) / 4 = 0.671431`

### 這輪分數代表什麼

1. `QMSum` 與 `Multi-News` 都高於 `0.70`，表示在真實英文 summary 資料集上，主線 answer path 已具備中高強度的摘要相似度表現，但距離「可放心當 release gate」仍有差距。
2. `LCSTS` 與 `CNewSum` 分數都落在 `0.62` 左右，顯示中文新聞摘要能力已有穩定基線，但仍低於英文 meeting/news summary 的結果，後續可再觀察中文文風與壓縮率對 `BERTScore` 的影響。
3. `CoCoTrip` 目前主分數仍是 `0.0`。這不是因為技術性 judge 錯誤沒有排除，而是排除後仍維持 `0.0`，因此目前真正的問題在 compare answer quality 本身，而不是 benchmark 執行故障。
4. `CoCoTrip` 原始 package run 雖有 `2` 題 `judge_failed`，但將 `cocotrip-compare-3` 與 `cocotrip-compare-9` 拉出來單獨 rerun 後，兩題都變成 `partial=false`，且 pairwise verdict 仍為 `reference`。所以 `0.0` 應視為目前真實 compare 基線，而不是暫時性執行噪音。
5. `qafacteval_score` 仍未正式接線，因此這輪 summary package 分數仍主要反映 `BERTScore` 相似度，不代表 groundedness guardrail 已完整成立。

### 評分方法與欄位解讀

真資料 summary/compare suite 目前的評分方法固定如下：

| Metric | 用途 | 方法來源 | `standard_level` | 實作說明 |
| --- | --- | --- | --- | --- |
| `bert_score_f1` | `summary` 主分數 | `BERTScore (Zhang et al., 2019)` | `standard` | 目前實作使用英文 `roberta-large` 與中文 `bert-base-chinese` 路徑；每個 summary package 的主分數直接取單題 `BERTScore F1` 平均值 |
| `pairwise_rubric_judge_win_rate` | `compare` 主分數 | `LLM-as-a-judge rubric / pairwise evaluation` | `semi_standard` | compare 題把 candidate answer 與 `reference_answer` 做 pairwise judge；`candidate=1.0`、`tie=0.5`、`reference=0.0`，再對 package 內題目平均 |
| `qafacteval_score` | `summary` groundedness guardrail | `QAFactEval (Fabbri et al., 2021)` | `semi_standard` | runner 已保留欄位與 registry，但目前仍待正式 scorer 接線 |
| `required_document_coverage` | supporting metric | `product evidence contract` | `project_contract` | 必需文件是否都有被 citation 命中 |
| `citation_coverage` | supporting metric | `product evidence contract` | `project_contract` | citation 是否覆蓋 gold evidence spans |
| `section_coverage` | supporting metric | `product evidence contract` | `project_contract` | summary 題是否涵蓋預期章節；compare 題目前多數會是 `0.0`，因 compare 不以章節聚焦為主 |
| `required_document_not_cited_rate` | supporting metric | `product evidence contract` | `project_contract` | 必需文件未被引用的比例 |
| `insufficient_evidence_not_acknowledged_rate` | supporting metric | `product evidence contract` | `project_contract` | 允許證據不足的題目中，回答未承認證據不足的比例 |
| `avg_overall_score` | supporting metric | `LLM judge rubric aggregate` | `project_contract` | 來自 supporting rubric judge 的四維平均值，不可取代主分數 |

### 舊分數狀態

## 2026-04-11 目前基線範圍

目前 current 基線由四批 `2026-04-05` run 組成：

- 第一批是同一條 `production_like_v1` snapshot 下的六資料集 rerun。
- 第二批是新加入 `nq-curated-v1-100` 後，在同一條 config snapshot 下補跑的 reference run。
- 第三批是新加入 `drcd-curated-v1-100` 後，在同一條 config snapshot 下補跑的 reference run。
- 第四批是新加入 `dureader-robust-curated-v1-100` 後，在同一條 config snapshot 下補跑的 reference run。

目前納入長期文件的七個正式 dataset 與 run id 如下：

| Dataset | Run ID |
| --- | --- |
| `dureader-robust-curated-v1-100` | `6befc441-39ba-4580-9d9c-f5d795158f1b` |
| `msmarco-curated-v1-100` | `5e9de20b-4781-4711-a69e-03157e61d68a` |
| `drcd-curated-v1-100` | `2ab402c2-6390-4b6f-9e99-70df6c999806` |
| `nq-curated-v1-100` | `70f7f3fb-99b0-486b-9805-f8872b0eaef4` |
| `tw-insurance-rag-benchmark-v1` | `4ec132d3-3abd-4398-8122-08cf64e5cda4` |
| `uda-curated-v1-100` | `6f57b5ca-0609-4c95-9dae-929768f3b6b9` |
| `qasper-curated-v1-100` | `2ab66532-fc2d-403f-aaf8-b2cfa6e2a3d7` |

## `production_like_v1` 目前真實設定快照

這七個 run 的 `config_snapshot` 目前以同一條 mainline 為準；current HEAD 下 `production_like_v1` 的最新 baseline 為：

- rerank provider：`self-hosted`
- rerank model：`BAAI/bge-reranker-v2-m3`
- rerank top N：`30`
- rerank max chars per doc：`2000`
- vector / FTS / max candidates：`30 / 30 / 30`
- assembler budget：`9 x 3000`
- assembler max children per parent：`7`

這一點很重要：

> 目前 `production_like_v1` 已固定為 current mainline baseline；舊的 evidence synopsis / 查詢改寫實驗數字只能視為歷史比較，不可再當成 current mainline baseline。

## 最新 assembled 指標

### 七個正式 dataset 的最新總表

| Dataset | 主要語系 | 查詢範圍 | 題數 | 文件數 | Gold Spans | 平均 Spans / 題 | 多 Span 題比例 | Recall@10 | nDCG@10 | MRR@10 | Precision@10 | Doc Coverage@10 | 難度 |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `dureader-robust-curated-v1-100` | `zh-TW` | `多文件查詢` | `100` | `100` | `100` | `1.00` | `0%` | `1.0000` | `0.9677` | `0.9570` | `0.1000` | `1.0000` | `1/5` |
| `msmarco-curated-v1-100` | `en` | `多文件查詢` | `100` | `100` | `114` | `1.14` | `11%` | `1.0000` | `0.9674` | `0.9550` | `0.1050` | `1.0000` | `1/5` |
| `drcd-curated-v1-100` | `zh-TW` | `指定文件查詢` | `100` | `6` | `100` | `1.00` | `0%` | `1.0000` | `0.8894` | `0.8517` | `0.1000` | `1.0000` | `2/5` |
| `nq-curated-v1-100` | `en` | `多文件查詢` | `100` | `100` | `100` | `1.00` | `0%` | `0.7600` | `0.7600` | `0.7600` | `0.0760` | `1.0000` | `3/5` |
| `tw-insurance-rag-benchmark-v1` | `zh-TW` | `多文件查詢` | `30` | `4` | `30` | `1.00` | `0%` | `0.9333` | `0.7578` | `0.7136` | `0.1033` | `1.0000` | `3/5` |
| `uda-curated-v1-100` | `en` | `指定文件查詢` | `100` | `45` | `100` | `1.00` | `0%` | `0.7900` | `0.6492` | `0.6044` | `0.0790` | `1.0000` | `3/5` |
| `qasper-curated-v1-100` | `en` | `指定文件查詢` | `100` | `42` | `164` | `1.64` | `30%` | `0.9200` | `0.6105` | `0.5127` | `0.1090` | `1.0000` | `4/5` |


## 客觀 corpus profile

### 目前長期文件應該能直接回答的欄位

上表已經把目前長期文件最需要的 corpus profile 與 assembled 指標放在同一張表，避免閱讀時來回對照。

### 欄位定義

- `主要語系`：以 `questions.jsonl.language` 的主分布為準；目前七個正式 dataset 都是單一主語系。
- `Gold Spans`：正式 gold evidence span 總數；比單看題數更能看出 evidence supervision 密度。
- `平均 Spans / 題`：`gold_spans.jsonl` 依 `question_id` 分組後的平均值；用來回答「每題通常需要幾段正確 evidence」。
- `多 Span 題比例`：至少有 `2` 個 gold spans 的題目占比；這比只列總 span 數更直觀。
- `難度`：依 current assembled baseline 的 repo 內部啟發式分級，不是通用 leaderboard。規則為：
  - `1/5`：`Recall@10 >= 0.95` 且 `nDCG@10 >= 0.90`
  - `2/5`：`Recall@10 >= 0.90` 且 `nDCG@10 >= 0.80`
  - `3/5`：`Recall@10 >= 0.75` 且 `nDCG@10 >= 0.65`
  - `4/5`：`Recall@10 >= 0.65` 且 `nDCG@10 >= 0.45`
  - `5/5`：其餘

### 哪些欄位重要，哪些目前不值得放首頁

建議保留在長期文件首頁的欄位：

- `主要語系`
- `題數`
- `文件數`
- `Gold Spans`
- `平均 Spans / 題`
- `多 Span 題比例`
- assembled `Recall@10`、`nDCG@10`、`MRR@10`
- `難度`

建議不要塞進根目錄 README 主表、改留在 package README 或 artifact 的欄位：

- `總 chunk 數`
- 全部 `run id`
- oversampling / filter / review queue 的中間產物筆數
- `OpenAI` override 細節
- 單純重複 `題數` 的 `question_with_gold_span_count`

目前看起來不太有資訊量的欄位：

- `平均 gold 文件數 / 題`：這七個正式 dataset 目前幾乎都是 `1.0`，首頁列出來辨識度很低。
- 只有原始檔大小、沒有 chunk snapshot 的 `總 corpus bytes`：對 retrieval 難度的解釋力有限，容易讓讀者誤以為檔案大就一定比較難。

## 對目前基線的直接判讀

1. 目前依 assembled `nDCG@10` 由相對簡單到困難排序，可近似看成：`DuReader-robust 100 -> MS MARCO 100 -> DRCD 100 -> NQ 100 -> self -> UDA 100 -> QASPER 100`；其中 `QASPER 100`、`UDA 100` 與 `DRCD 100` 已是指定文件 scope 分數。
2. `DuReader-robust 100` 目前是新的最高分 external lane，assembled `Recall@10=1.0000`、`nDCG@10=0.9677`；它比較像「中文 paragraph-level extractive QA + rerank sanity check」，不應誤判成整體中文 retrieval frontier 已解完。
3. `QASPER 100` 在指定文件 scope 後 assembled `Recall@10=0.9200`、`nDCG@10=0.6105`；這表示舊 area-wide 低分主要混入 document disambiguation，而 current mainline 在 scientific evidence-field semantic gap 上仍有進步空間。
4. `DRCD 100` 這條線仍保留原本訊號：`recall` 高於 rerank / assembled，代表它更像「繁體中文 lexical retrieval + rerank regression sentinel」，而不是 candidate generation 或 assembler budget 問題。
5. `NQ 100` 仍保留它原本的訊號：assembled 已回升到 `0.7600`，但它仍主要像「full-page wiki answer localization + assembler budget / materialization」壓力測試，而不是單純 candidate generation 問題。
6. `UDA 100` 仍顯著比 `QASPER 100` 友善，但 latest mainline assembled `nDCG@10=0.6492`、`MRR@10=0.6044`，代表 same-document wiki 類 evidence 雖穩定，仍會受 rerank 文本組裝策略影響。
7. `MS MARCO 100` 這次 assembled 仍接近天花板，但不能把它解讀成「通用 web retrieval 問題已解完」；它在此 repo 內的 contract 仍是每題一份 snippet-bundle 文件，壓力測試重心比較接近 query-to-passage matching 與 answer localization sanity check。
8. 因此，真正仍在拉低 external hard lane 的主因依然是 `QASPER 100`；`NQ 100` 補出 assembler 壓力點，`DRCD 100` 補出中文 rerank regression 觀測點，而 `DuReader-robust 100` 則更適合作為近 ceiling 中文 sanity check。

## 建議保留的常規比較集合

| 類別 | 應保留項目 | 保留理由 |
| --- | --- | --- |
| current mainline baseline | `production_like_v1` | 這是目前真正會被拿來回歸檢查的 baseline；`QASPER`、`UDA`、`DRCD` 需同時保留指定文件 scope 語意。 |
| internal stability set | `tw-insurance-rag-benchmark-v1` | 這份最適合檢查主線策略是否在既有自家 benchmark 上失穩。 |
| external pressure-test sextet | `dureader-robust-curated-v1-100`、`msmarco-curated-v1-100`、`drcd-curated-v1-100`、`nq-curated-v1-100`、`uda-curated-v1-100`、`qasper-curated-v1-100` | 六者合併後可以同時觀察中文 extractive sanity check、snippet-bundle sanity check、繁體中文 lexical retrieval / rerank、wiki page answer localization / assembly、same-document localization 與英文 semantic-gap。 |
| hard external lane | `qasper-curated-v1-100` | 若要找下一輪最高 ROI 的 hard case，仍應優先看這份。 |

## External `100Q` 最新摘要

### 最新 assembled 分數

| Dataset | Recall@10 | nDCG@10 | MRR@10 |
| --- | ---: | ---: | ---: |
| `dureader-robust-curated-v1-100` | `1.0000` | `0.9677` | `0.9570` |
| `msmarco-curated-v1-100` | `1.0000` | `0.9674` | `0.9550` |
| `drcd-curated-v1-100` | `1.0000` | `0.8894` | `0.8517` |
| `nq-curated-v1-100` | `0.7600` | `0.7600` | `0.7600` |
| `uda-curated-v1-100` | `0.7900` | `0.6492` | `0.6044` |
| `qasper-curated-v1-100` | `0.9200` | `0.6105` | `0.5127` |

### 最新 miss 分布

| Dataset | miss 總數 | `recall_only` | `rerank_only` | `assembled_only` | `rerank_hit_but_assembled_miss` | `all_miss` | 查詢改寫套用 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `DuReader-robust 100` | `0` | `0` | `0` | `0` | `0` | `0` | `0` |
| `MS MARCO 100` | `0` | `0` | `0` | `0` | `0` | `0` | `0` |
| `DRCD 100` | `0` | `0` | `0` | `0` | `0` | `0` | `0` |
| `NQ 100` | `25` | `2` | `0` | `8` | `14` | `3` | `0` |
| `UDA 100` | `21` | `21` | `0` | `0` | `0` | `21` | `0` |
| `QASPER 100` | `7` | `5` | `1` | `1` | `1` | `5` | `0` |

### 這輪代表什麼

1. `QASPER 100` 指定文件後 miss 總數由舊 area-wide contract 的 `41` 降到 `7`，顯示原先低分主要混入 document disambiguation；剩餘 miss 仍以英文 generic evidence-field semantic gap 為主。
2. `DuReader-robust 100` 目前沒有 miss，因此它更像中文 extractive sanity check，而不是下一輪 hard frontier。
3. `DRCD 100` 指定文件後目前沒有 assembled miss；真正值得觀察的不是 miss 數，而是 rerank / assembled 指標整體比 recall 低，表示這份資料更像中文 rerank 排序回歸哨兵，而不是 hard frontier。
4. `NQ 100` 這輪最值得注意的是 `rerank_hit_but_assembled_miss = 14` 與 `assembled_only = 8`；也就是 rerank 已經把 gold evidence 拉到前面，但 assembler 仍把它 materialize 掉，這是一條與 `QASPER` 完全不同的 hard lane。
5. `UDA 100` 仍以 same-document section / list / cast / release-date localization 為主。
6. `MS MARCO 100` 在目前 snippet-bundle contract 下沒有 assembled miss，因此它更像 sanity check，而不是下一輪 hard frontier。
7. 若要看逐題的 legacy 詳細 miss log，仍可參考 [`docs/external-100q-miss-analysis-2026-04-04.md`](./external-100q-miss-analysis-2026-04-04.md)，但那份文件只覆蓋舊的 `QASPER 100 + UDA 100` 組合；`DuReader-robust 100`、`MS MARCO 100`、`DRCD 100` 與 `NQ 100` 目前尚未另外拆出獨立 miss 清單。

## 下一輪最高 ROI 假設

如果後續還要做 benchmark-driven 優化，最值得維持的主假設仍是：

> 在 current `production_like_v1` 之上，仍優先針對 `QASPER 100` 的 `recall_only` 英文 semantic-gap 再開一條更強的 generic lane，例如 `english_field_focus_v2`；但並行的第二優先觀測點，應同時包含 `NQ 100` 的 assembler miss 與 `DRCD 100` 的 rerank regression，分別確認 materializer 是否在高品質 rerank 命中的 wiki 長段落上過度裁切，以及中文 rerank 是否在近乎完美的 lexical candidate set 上反而造成排序退化。`DuReader-robust 100` 則維持作為近 ceiling 中文 sanity check，不應拿來主導下一輪優化方向。

這個方向仍符合產品邊界，因為它：

- 不引入新基礎設施
- 不放寬 `SQL gate`、`deny-by-default` 與 `ready-only` 這些安全邊界
- 主要處理目前 external `100Q` 真正仍有大量空間的 `QASPER 100` `recall_only` miss
- 同時把 `NQ 100` 視為 assembler regression 哨兵，避免 rerank 已解、assembled 卻掉分的情況長期被忽略
- 也把 `DRCD 100` 視為中文 rerank regression 哨兵，避免在高品質中文 lexical 候選上把原本已正確的排序拉壞
