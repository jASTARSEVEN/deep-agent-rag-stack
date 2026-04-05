# uda-curated-v1-100

此目錄是一份可重現的 `UDA` benchmark package，來源是官方 full-source `nq` subset，並對齊本 repo 現有的 retrieval evaluation contract。

[English version](README.md)

## Purpose

此 package 的目的，是讓其他工程師可以重現同一份 `UDA 100` curation 流程，並直接檢視：

- 官方 `UDA` `nq` subset 如何透過本 repo 的 helper CLI 正規化
- 哪些題目通過目前的 `fact_lookup` 篩題規則
- 有多少題是純 deterministic alignment 就取得 gold span
- `production_like_v1` reference run 的完整指標

## What's Included

- `manifest.json`：benchmark 身分、package 統計與 reference evaluation profile
- `documents.jsonl`：最終 `100` 題實際涉及的 benchmark 文件清單
- `questions.jsonl`：最終 `100` 題題目
- `gold_spans.jsonl`：對齊到 `display_text` offset 的 gold spans
- `alignment_candidates.jsonl`：oversampled workspace 的 deterministic alignment 結果
- `alignment_review_queue.jsonl`：可選 review 前的 unresolved queue
- `filter_report.json`：oversampled workspace 的篩題摘要
- `reference_run_summary.json`：完成的 `production_like_v1` reference run 摘要
- `reproduce.md`：逐步重現說明

## Reference Run

- Dataset：`uda-curated-v1-100`
- Dataset ID：`3cca653e-ffd5-5ab8-8464-27aaac194bb4`
- 建立時使用的 Area 名稱：`uda-100`
- Area ID：`2edabc25-1a54-43ab-b987-efd4e040114f`
- Reference run ID：`0274c530-8171-4f0f-bd86-bce82c15f5d7`
- Evaluation profile：`production_like_v1`
- 題數：`100`
- 最終文件數：`45`
- Oversampled filtered item 數：`140`
- Deterministic auto-matched 數：`102`
- `OpenAI` override 核准數：`0`

## Summary Metrics

| 階段 | nDCG@10 | Recall@10 | MRR@10 | Precision@10 | Doc Coverage@10 |
| --- | ---: | ---: | ---: | ---: | ---: |
| recall | 0.4544 | 0.6500 | 0.3956 | 0.0660 | 1.0000 |
| rerank | 0.6802 | 0.8200 | 0.6347 | 0.0820 | 1.0000 |
| assembled | 0.6816 | 0.8300 | 0.6336 | 0.0830 | 1.0000 |

## Notes

- 此 package 使用官方 `UDA-QA` 的 `wiki_nq_docs` source zip 與官方 `bench_nq_qa.json` benchmark annotations。
- 最終 package 不需要 LLM review，因為 oversampled workspace 已經直接得到 `102` 題 deterministic approval。
- 最終 package 是從 oversampled workspace 中，依固定順序取前 `100` 個 approved items。
