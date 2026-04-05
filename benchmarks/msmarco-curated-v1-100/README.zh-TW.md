# msmarco-curated-v1-100

此目錄是一份可重現的 `MS MARCO` benchmark package，將官方 QA validation split 映射到目前 repo 已存在的 retrieval benchmark contract。

[English README](README.md)

## Purpose

此 package 的目的，是讓另一位工程師可以重現同一條 `MS MARCO 100` curation 流程，並檢查：

- 官方 `MS MARCO v1.1` validation rows 如何被正規化成 snippet-bundle 文件
- 哪些題目通過目前 repo 的 `fact_lookup` 篩題規則
- 有多少 gold spans 是 deterministic auto-align，多少需要 `OpenAI` review 補齊
- 在目前共用 rerun baseline 下，`production_like_v1` 的實際 reference run 分數

## What's Included

- `manifest.json`：benchmark 身分、package stats 與 reference evaluation profile
- `documents.jsonl`：最終 `100` 題使用的邏輯文件清單
- `questions.jsonl`：最終 `100` 題 benchmark 題目
- `gold_spans.jsonl`：對齊到 `display_text` offsets 的 gold spans
- `alignment_candidates.jsonl`：oversampled workspace 的 deterministic alignment 結果
- `alignment_review_queue.jsonl`：進入 `OpenAI` review 前仍未解決的 queue
- `filter_report.json`：oversampled workspace 的 curation 摘要
- `review_overrides.jsonl`：`OpenAI` review 核准後的 span overrides
- `openai_review_log.jsonl`：`OpenAI` review 證據 log
- `reference_run_summary.json`：完成的 `production_like_v1` reference run 摘要
- `reproduce.md`：逐步重現指南

## Reference Run

- Dataset：`msmarco-curated-v1-100`
- Dataset ID：`4669417e-6276-54ae-89b3-95fcb7652096`
- 建立時使用的 Area 名稱：`msmarco-100`
- Area ID：`4a7a8c05-4aa2-403f-b101-d24ff28d1308`
- Reference run ID：`5e9de20b-4781-4711-a69e-03157e61d68a`
- Evaluation profile：`production_like_v1`
- 題目數：`100`
- 最終文件數：`100`
- Oversampled prepared item 數：`180`
- Oversampled filtered item 數：`154`
- Deterministic auto-matched 數：`103`
- `OpenAI` 核准 override 數：`47`
- 最終 `100` 題中實際納入的 review-approved 題數：`33`

## Summary Metrics

| 階段 | nDCG@10 | Recall@10 | MRR@10 | Precision@10 | Doc Coverage@10 |
| --- | ---: | ---: | ---: | ---: | ---: |
| recall | 0.7825 | 0.9900 | 0.7092 | 0.1110 | 1.0000 |
| rerank | 0.9674 | 1.0000 | 0.9550 | 0.1050 | 1.0000 |
| assembled | 0.9674 | 1.0000 | 0.9550 | 0.1050 | 1.0000 |

## Notes

- 此 package 來自官方 `MS MARCO v1.1` validation QA rows，但 repo 內的 benchmark 會把每一列 materialize 成單一 snippet-bundle 文件，而不是嘗試重建完整網站全文。
- 這條 curation 策略會先嘗試用答案字串做 deterministic alignment，只有 ambiguous rows 才交給 `OpenAI` 從候選視窗中回貼逐字 quote，因此 `gold_spans.jsonl` 仍維持 verbatim evidence offsets，而不是 paraphrased answers。
- 最終 package 只保留 review 後依序核准的前 `100` 題；超出 cutoff 的已核准題目會被刻意排除。
