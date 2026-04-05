# dureader-robust-curated-v1-100

此目錄是一份可重現的 `DuReader-robust` benchmark package，將官方 development split 映射到本 repo 既有的 retrieval evaluation contract。

[English README](README.md)

## Purpose

此 package 的目的，是讓其他工程師可以重現同一份 `DuReader-robust 100` curation 流程，並直接檢視：

- 官方 `DuReader-robust` `dev.json` wrapper 如何被正規化成 paragraph-level benchmark 文件
- 哪些題目通過本 repo 目前的 `fact_lookup` 篩題規則
- 有多少 gold spans 是 deterministic auto-align，多少需要 `OpenAI` review override
- 在目前共用 current baseline 下，`production_like_v1` 的實際 reference run 分數

## What's Included

- `manifest.json`：benchmark 身分、package stats 與 reference evaluation profile
- `documents.jsonl`：最終 `100` 題實際涉及的 benchmark 文件清單
- `questions.jsonl`：最終 `100` 題題目
- `gold_spans.jsonl`：對齊到 `display_text` offset 的 gold spans
- `alignment_candidates.jsonl`：oversampled workspace 的 deterministic alignment 結果
- `alignment_review_queue.jsonl`：進入 `OpenAI` pass 前的 review queue；本次 reference package 內容為空
- `filter_report.json`：oversampled workspace 的篩題摘要
- `reference_run_summary.json`：完成的 `production_like_v1` reference run 摘要
- `reproduce.md`：逐步重現說明

## Reference Run

- Dataset：`dureader-robust-curated-v1-100`
- Dataset ID：`f4a91b45-64fa-5cd7-b815-9a454888bf9c`
- 建立時使用的 Area 名稱：`dureader-robust-100`
- Area ID：`d9cd72a9-5684-47cc-ae17-088606160377`
- Reference run ID：`6befc441-39ba-4580-9d9c-f5d795158f1b`
- Evaluation profile：`production_like_v1`
- 題數：`100`
- 最終文件數：`100`
- Oversampled prepared item 數：`220`
- Oversampled filtered item 數：`220`
- Deterministic auto-matched 數：`220`
- `OpenAI` override 核准數：`0`

## Summary Metrics

| 階段 | nDCG@10 | Recall@10 | MRR@10 | Precision@10 | Doc Coverage@10 |
| --- | ---: | ---: | ---: | ---: | ---: |
| recall | `0.8867` | `0.9800` | `0.8566` | `0.0990` | `0.9800` |
| rerank | `0.9677` | `1.0000` | `0.9570` | `0.1000` | `1.0000` |
| assembled | `0.9677` | `1.0000` | `0.9570` | `0.1000` | `1.0000` |

## Notes

- 此 package 是 repository-specific benchmark，不是原始 `DuReader-robust` leaderboard split。
- 官方來源檔是 `dureader_robust-data/dev.json`，它採用 SQuAD 風格的 `data -> paragraphs -> qas` wrapper；本 package 會把每個 paragraph materialize 成單一 benchmark 文件。
- 最終 package 是從前 `220` 題 prepared items 中，依固定順序取前 `100` 個 approved items。
- 這次 reference package 不需要 `OpenAI` review pass，因為 `needs_review = 0`；若未來 rerun 產生非空 queue，則應將那些題目交給 `review_external_benchmark_with_openai.py` 處理。
- 在目前 baseline 下，`DuReader-robust 100` 比較像接近 ceiling 的中文 extractive sanity check：rerank 會補齊 recall 剩餘缺口，而 assembler 幾乎不再造成額外損耗。
