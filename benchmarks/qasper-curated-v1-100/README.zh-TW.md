# qasper-curated-v1-100

此目錄是一份可重現的 `QASPER` benchmark package，將先前 pilot 擴充為 `100` 題外部 retrieval benchmark，同時維持本 repo 既有的 evaluation contract。

[English version](README.md)

## Purpose

此 package 的目的，是讓其他工程師可以重現同一份 `QASPER 100` curation 流程，並直接檢視：

- 建立 package 時使用的 `50` 篇 paper oversampling 範圍
- 哪些題目通過本 repo 目前的 `fact_lookup` 篩題規則
- 哪些題目是 deterministic auto alignment 通過、哪些題目是靠 `OpenAI` review 補成 gold span
- `production_like_v1` reference run 的完整指標

## What's Included

- `manifest.json`：benchmark 身分、package 統計與 reference evaluation profile
- `documents.jsonl`：最終 `100` 題實際涉及的 benchmark 文件清單
- `questions.jsonl`：最終 `100` 題題目
- `gold_spans.jsonl`：對齊到 `display_text` offset 的 gold spans
- `alignment_candidates.jsonl`：oversampled workspace 的 alignment 結果
- `alignment_review_queue.jsonl`：進入 LLM review 前仍 unresolved 的 deterministic queue
- `filter_report.json`：oversampled workspace 的篩題摘要
- `review_overrides.jsonl`：`OpenAI` review 核准後的 span override
- `openai_review_log.jsonl`：`OpenAI` review 證據鏈
- `reference_run_summary.json`：完成的 `production_like_v1` reference run 摘要
- `reproduce.md`：逐步重現說明

## Reference Run

- Dataset：`qasper-curated-v1-100`
- Dataset ID：`e836874e-5183-5f09-8241-eddb155adab1`
- 建立時使用的 Area 名稱：`qasper-100`
- Area ID：`204b0f87-bbbd-4549-ae3b-8064e535b453`
- Reference run ID：`54c297d7-260b-40eb-88cf-999026ca9d6d`
- Evaluation profile：`production_like_v1`
- 題數：`100`
- 最終文件數：`42`
- Oversampled filtered item 數：`132`
- Deterministic auto-matched 數：`122`
- `OpenAI` override 核准數：`2`

## Summary Metrics

| 階段 | nDCG@10 | Recall@10 | MRR@10 | Precision@10 | Doc Coverage@10 |
| --- | ---: | ---: | ---: | ---: | ---: |
| recall | 0.1883 | 0.3600 | 0.1390 | 0.0390 | 0.7300 |
| rerank | 0.3498 | 0.5400 | 0.2905 | 0.0590 | 0.8300 |
| assembled | 0.3812 | 0.5900 | 0.3153 | 0.0640 | 0.8100 |

## Notes

- 此 package 不是原始 `QASPER` leaderboard split，而是對齊本 repo `display_text` offset 與 `fact_lookup` contract 的 repository-specific benchmark。
- 最終 package 是從 oversampled workspace 中，依固定順序取前 `100` 個 approved items；超過 cutoff 的 approved items 會刻意排除。
- review contract 維持嚴格限制：只有能逐字對回 offset 的 quote 才能進入 `review_overrides.jsonl`。
