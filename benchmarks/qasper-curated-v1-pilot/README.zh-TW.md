# qasper-curated-v1-pilot

此目錄是將小型 `QASPER` 子集映射到本 repo 既有 retrieval evaluation contract 的可重現 pilot benchmark package。

[English README](README.md)

## Purpose

此 package 的目的，是讓另一位工程師可以重跑同一組 pilot benchmark，並審查：

- 哪些 `QASPER` 題目在 `fact_lookup` curated v1 規則下被保留
- 有多少題可自動對齊到系統 `display_text`
- 哪些題目仍需要人工複核
- reference run 的設定與 summary metrics

## 內容

- `manifest.json`：benchmark 身分與資料集統計
- `documents.jsonl`：邏輯上的 benchmark 文件清單
- `questions.jsonl`：curated pilot 題目
- `gold_spans.jsonl`：對齊系統 `display_text` offsets 的 gold spans
- `alignment_candidates.jsonl`：所有保留題目的對齊結果
- `alignment_review_queue.jsonl`：未自動核准的題目
- `filter_report.json`：篩題摘要
- `reference_run_summary.json`：reference run id、config snapshot 與 summary metrics
- `reproduce.md`：逐步重現說明

## Reference Run

- Dataset：`qasper-curated-v1-pilot`
- Dataset ID：`db6d581c-2feb-5914-afb8-b4f1fa2092e2`
- 建立時使用的 area 名稱：`qasper-pilot`
- Reference run ID：`6f1150df-1343-4905-a417-7334ea87c9d6`
- Evaluation profile：`production_like_v1`
- 題數：`27`
- Curation 時的自動對齊率：`0.931034`

## Summary Metrics

| 階段 | nDCG@10 | Recall@10 | MRR@10 | Precision@10 | Doc Coverage@10 |
| --- | ---: | ---: | ---: | ---: | ---: |
| recall | 0.2920 | 0.5556 | 0.2062 | 0.0630 | 0.9630 |
| rerank | 0.4590 | 0.5556 | 0.4228 | 0.0593 | 0.9630 |
| assembled | 0.4489 | 0.5556 | 0.4105 | 0.0593 | 0.9630 |

## 備註

- 這是一組 pilot benchmark，不是完整 `QASPER` leaderboard 成績。
- gold truth 是綁定本 repo 的 `display_text` offsets，而不是原始資料集 offsets。
- curation 過程中有 `1` 題 `needs_review` 與 `1` 題 `rejected`；這兩題都沒有進入最後分數。
