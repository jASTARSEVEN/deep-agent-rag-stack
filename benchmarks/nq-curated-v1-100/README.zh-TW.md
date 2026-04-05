# nq-curated-v1-100

此目錄是一份可重現的 `Natural Questions` benchmark package，將 curated 的 `100` 題子集收斂到本 repo 既有的 retrieval evaluation contract。

[English version](README.md)

## Purpose

此 package 的目的，是讓其他工程師可以重現同一份 `NQ 100` curation 流程，並直接檢視：

- 建立 package 時使用的 `Natural Questions` validation rows
- 哪些題目通過本 repo 目前的 `fact_lookup` 篩題規則
- deterministic `display_text` 對齊結果
- `production_like_v1` reference run 的完整指標

## What's Included

- `manifest.json`：benchmark 身分、package 統計與 reference evaluation profile
- `documents.jsonl`：最終 `100` 題實際涉及的 benchmark 文件清單
- `questions.jsonl`：最終 `100` 題題目
- `gold_spans.jsonl`：對齊到 `display_text` offset 的 gold spans
- `alignment_candidates.jsonl`：oversampled workspace 的 alignment 結果
- `alignment_review_queue.jsonl`：deterministic review queue；本次 reference package 內容為空
- `filter_report.json`：oversampled workspace 的篩題摘要
- `reference_run_summary.json`：完成的 `production_like_v1` reference run 摘要
- `reproduce.md`：逐步重現說明

## Reference Run

- Dataset：`nq-curated-v1-100`
- Dataset ID：`c1fef25a-7f8a-59d0-8974-f44ace477600`
- 建立時使用的 Area 名稱：`nq-100`
- Area ID：`9d89e5b3-3a31-43d6-9441-8d1de9dd6e0b`
- Reference run ID：`3e07bb70-7068-483c-81d0-35ad43092dfb`
- Evaluation profile：`production_like_v1`
- 題數：`100`
- 最終文件數：`100`
- Oversampled prepared item 數：`260`
- Oversampled filtered item 數：`250`
- Deterministic auto-matched 數：`250`
- `OpenAI` override 核准數：`0`

## Summary Metrics

| 階段 | nDCG@10 | Recall@10 | MRR@10 | Precision@10 | Doc Coverage@10 |
| --- | ---: | ---: | ---: | ---: | ---: |
| recall | 0.5019 | 0.8100 | 0.4166 | 0.1110 | 0.9700 |
| rerank | 0.9569 | 0.9700 | 0.9525 | 0.0970 | 1.0000 |
| assembled | 0.7443 | 0.7500 | 0.7425 | 0.0750 | 1.0000 |

## Notes

- 此 package 是 repository-specific benchmark，不是原始 `Natural Questions` leaderboard split。
- 最終 package 是從 oversampled workspace 中，依固定順序取前 `100` 個 approved items。
- 這次 reference package 不需要 `OpenAI` review pass，因為 `needs_review = 0`；若未來 rerun 產生非空 queue，則應將那些題目交給 `review_external_benchmark_with_openai.py` 處理。
- 這份 package 最有價值的訊號，是 `rerank` 與 `assembled` 之間仍有明顯落差，因此它適合作為 assembler regression 哨兵。
