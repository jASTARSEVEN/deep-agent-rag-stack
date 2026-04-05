# uda-curated-v1-pilot

此目錄是將官方 `UDA-Benchmark` sample 子集映射到本 repo 既有 retrieval evaluation contract 的可重現 pilot benchmark package。

[English README](README.md)

## Purpose

此 package 的目的，是讓另一位工程師可以重跑同一組 pilot benchmark，並審查：

- 官方 `UDA-Benchmark` sample 題目在目前 `fact_lookup` curated v1 規則下留下了哪些題目
- 有多少題可以自動對齊到系統 `display_text`
- 有多少題是透過 `OpenAI API` review pass 補進正式 snapshot
- 擴充到 `26` 題之後的 reference run 分數

## 內容

- `manifest.json`：benchmark 身分與資料集統計
- `documents.jsonl`：邏輯上的 benchmark 文件清單
- `questions.jsonl`：curated pilot 題目
- `gold_spans.jsonl`：對齊系統 `display_text` offsets 的 gold spans
- `alignment_candidates.jsonl`：人工覆核前的原始對齊結果
- `alignment_review_queue.jsonl`：所有無法自動核准的題目
- `filter_report.json`：篩題摘要
- `review_overrides.jsonl`：建立正式 snapshot 時採用的最終核准 span overrides
- `openai_review_log.jsonl`：`OpenAI API` review log
- `reference_run_summary.json`：reference run id、config snapshot 與 summary metrics
- `bge_core_profiles_summary.json`：四條 current-head BGE profile 的 assembled 指標對照
- `reproduce.md`：逐步重現說明

## Reference Run

- Dataset：`uda-curated-v1-pilot`
- Dataset ID：`3d779672-b561-5d64-aa76-035d37d4e0b4`
- 建立時使用的 area 名稱：`uda-pilot`
- Area ID：`58afaf23-423d-4526-b90d-43ea19711eaf`
- Reference run ID：`593638b8-a3c7-4471-ba56-7d242a8e65fa`
- Evaluation profile：`production_like_v1`
- 題數：`26`
- curation 時的自動對齊率：`0.346154`
- `OpenAI` review 核准數：`21`
- 最終 override 數：`25`

## Summary Metrics

| 階段 | nDCG@10 | Recall@10 | MRR@10 | Precision@10 | Doc Coverage@10 |
| --- | ---: | ---: | ---: | ---: | ---: |
| recall | 0.3127 | 0.5000 | 0.2483 | 0.0577 | 0.7308 |
| rerank | 0.7353 | 0.8462 | 0.7083 | 0.0885 | 0.9615 |
| assembled | 0.5288 | 0.6538 | 0.4968 | 0.0692 | 0.9615 |

## BGE Core Profiles

| Profile | Recall@10 | nDCG@10 | MRR@10 |
| --- | ---: | ---: | ---: |
| `production_like_v1` | 0.6538 | 0.5288 | 0.4968 |
| `generic_guarded_assembler_v2_bge` | 0.6538 | 0.5288 | 0.4968 |
| `generic_guarded_evidence_synopsis_v2_bge` | 0.6538 | 0.5264 | 0.4936 |
| `generic_guarded_evidence_synopsis_v3_bge` | 0.6538 | 0.5288 | 0.4968 |

## 備註

- 這不是完整 `UDA-QA` leaderboard，而是從官方 `UDA-Benchmark` sample artifact 收斂出的 pilot benchmark。
- source 範圍刻意限制在官方 repo 的 `extended_qa_info_bench` 與 `src_doc_files_example`。
- `JKHY_2015` 以抽出的 markdown (`JKHY_2015.md`) 形式 ingest，避免被目前 repo 的 upload size limit 擋下，同時保留同一組題目來源。
- 最終 `26` 題的來源結構為：
  - `9` 題 auto-matched
  - `21` 題由 `OpenAI API` review 核准
  - 在 LLM review 之外，再補 `4` 題 deterministic span override
- 在更新後的 `26` 題資料集上，`assembler_v2` 與 `generic_v1` 在 UDA nDCG@10 上與 baseline 持平，而 `generic_v1` 略低。
