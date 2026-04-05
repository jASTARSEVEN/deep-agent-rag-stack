# drcd-curated-v1-100

此目錄是一份可重現的 `DRCD` benchmark package，將官方繁體中文閱讀理解資料集映射到本 repo 既有的 retrieval evaluation contract。

[English version](README.md)

## 目的

此 package 的存在，是為了讓其他工程師可以重現同一條 `DRCD 100` 建置流程，並檢查：

- 官方 `voidful/DRCD` `dev` split 如何被正規化成 repo 內可上傳的 markdown source documents
- 哪些題目通過目前 repo 的 `fact_lookup` curated 規則
- 有多少題是 deterministic 對齊完成，有多少題需要進 `OpenAI` review queue
- 在目前共用 baseline 下，`production_like_v1` 的正式 reference run 分數是多少

## 內含內容

- `manifest.json`：benchmark 身分、package 統計與 reference evaluation profile
- `documents.jsonl`：最終 `100` 題使用到的邏輯文件清單
- `questions.jsonl`：最終 `100` 題 benchmark 題目
- `gold_spans.jsonl`：以 `display_text` offsets 對齊的 gold spans
- `alignment_candidates.jsonl`：oversampled workspace 的 deterministic 對齊結果
- `alignment_review_queue.jsonl`：進入可選 `OpenAI` review 前的 queue
- `filter_report.json`：oversampled workspace 的篩題摘要
- `review_overrides.jsonl`：`OpenAI` review 核准的 span overrides
- `openai_review_log.jsonl`：`OpenAI` review 證據 log
- `reference_run_summary.json`：完成的 `production_like_v1` reference run 摘要
- `reproduce.md`：逐步重現指南

## Reference Run

- Dataset：`drcd-curated-v1-100`
- Dataset ID：`e82455ac-45fc-501e-a13d-333552c4a2ab`
- 建立時使用的 Area 名稱：`drcd-100`
- Area ID：`eb3d79be-220a-4658-9ecd-76ccaaf334f8`
- Reference run ID：`400921aa-3882-4504-8f3c-accf9054930e`
- Evaluation profile：`production_like_v1`
- 題目數：`100`
- 最終文件數：`6`
- Oversampled prepared item 數：`400`
- Oversampled filtered item 數：`400`
- Deterministic auto-matched 數：`400`
- Review queue 題目數：`0`
- 核准的 `OpenAI` overrides：`0`

## Summary Metrics

| 階段 | nDCG@10 | Recall@10 | MRR@10 | Precision@10 | Doc Coverage@10 |
| --- | ---: | ---: | ---: | ---: | ---: |
| recall | 0.9543 | 0.9900 | 0.9420 | 0.0990 | 1.0000 |
| rerank | 0.8650 | 0.9700 | 0.8308 | 0.0970 | 1.0000 |
| assembled | 0.8650 | 0.9700 | 0.8308 | 0.0970 | 1.0000 |

## 備註

- 此 package 直接使用 `hf://voidful/DRCD/default/dev`，保留官方繁體中文來源文字，沒有先轉成簡體或另外改寫成 retrieval-only surrogate document。
- 最終 package 保留 oversampled workspace 中 deterministic 排序後前 `100` 題核准題；由於 `alignment_review_queue` 為空，`OpenAI` review pass 實際上是 no-op，因此 `review_overrides.jsonl` 與 `openai_review_log.jsonl` 皆為空檔。
- `DRCD 100` 在目前 stack 下可視為高訊號的中文 lexical retrieval 檢查集：recall 幾乎到 ceiling，但 rerank 會輕微拉低排序。
