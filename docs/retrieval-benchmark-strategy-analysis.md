# Retrieval Benchmark Strategy Analysis（截至 2026-04-05）

## 文件目的

此文件現在只保留對後續 benchmark 治理最有用的四件事：

1. 目前 `production_like_v1` 的真實設定與最新分數。
2. 每個 benchmark package 在最新重跑下的 assembled 指標。
3. external `100Q` 的最新基線與 miss 主戰場。
4. 哪些歷史資料仍值得保留，哪些舊敘述應停止當成 current mainline。

## 2026-04-05 重跑範圍

本輪沒有再宣稱 fresh rebuild，而是直接在目前 Compose-backed benchmark 環境中，對已載入且文件皆為 `ready` 的五個 dataset 重新執行 `production_like_v1`：

| Dataset | Run ID |
| --- | --- |
| `tw-insurance-rag-benchmark-v1` | `a5cc80a1-fab0-4184-94da-02bbac6eb428` |
| `qasper-curated-v1-pilot` | `c7bd9111-ce84-4fda-b799-826e70173db2` |
| `uda-curated-v1-pilot` | `d137f59b-a372-4c6a-bcc2-ba9e1e226cd2` |
| `qasper-curated-v1-100` | `653032cb-9694-4878-915a-d73ebddd006d` |
| `uda-curated-v1-100` | `986c130d-6ccf-45b8-a47f-a07e15753ec0` |

## `production_like_v1` 目前真實設定快照

這次五個 run 的 `config_snapshot` 完全一致，代表目前 current HEAD 下 `production_like_v1` 的實際 baseline 為：

- rerank provider：`easypinex-host`
- rerank model：`BAAI/bge-reranker-v2-m3`
- rerank top N：`30`
- rerank max chars per doc：`2000`
- evidence synopsis：`enabled=true`，variant=`qasper_v3`
- query focus：`enabled=false`
- vector / FTS / max candidates：`30 / 30 / 30`
- assembler budget：`10 x 3600`
- assembler max children per parent：`7`

這一點很重要：

> 目前 `production_like_v1` 已不等於先前文件中記錄的 `generic_field_focus_v1 + 9x3000`。舊敘述可以保留作歷史策略訊號，但不能再當成 current mainline baseline。

## 最新 assembled 指標

### 五個 dataset 的最新分數

| Dataset | Recall@10 | nDCG@10 | MRR@10 | Precision@10 | Doc Coverage@10 |
| --- | ---: | ---: | ---: | ---: | ---: |
| `tw-insurance-rag-benchmark-v1` | `0.8667` | `0.7283` | `0.6825` | `0.0867` | `1.0000` |
| `qasper-curated-v1-pilot` | `0.8148` | `0.5353` | `0.4467` | `0.0852` | `1.0000` |
| `uda-curated-v1-pilot` | `0.8462` | `0.7357` | `0.7083` | `0.0885` | `0.9615` |
| `qasper-curated-v1-100` | `0.6200` | `0.3903` | `0.3183` | `0.0680` | `0.8300` |
| `uda-curated-v1-100` | `0.8600` | `0.6972` | `0.6447` | `0.0860` | `1.0000` |

### 分組平均

| Group | Recall@10 | nDCG@10 | MRR@10 | Precision@10 | Doc Coverage@10 |
| --- | ---: | ---: | ---: | ---: | ---: |
| `pilot trio` | `0.8425` | `0.6664` | `0.6125` | `0.0868` | `0.9872` |
| `external 100Q (self excluded)` | `0.7400` | `0.5437` | `0.4815` | `0.0770` | `0.9150` |
| `all five datasets` | `0.8015` | `0.6174` | `0.5601` | `0.0829` | `0.9583` |

## 對目前基線的直接判讀

1. `pilot trio` 的平均分數剛好落在先前 `generic_guarded_evidence_synopsis_v3` 的數字上：
   - `Recall@10=0.8425`
   - `nDCG@10=0.6664`
   - `MRR@10=0.6125`
   這代表目前 `production_like_v1` 的實際行為，比較接近舊的 `evidence_synopsis_v3` 主線，而不是先前文件記錄的 `generic_guarded_query_focus_v1`。
2. `external 100Q` 相對 2026-04-04 文件中的 assembled 基線有小幅上升：
   - `qasper-curated-v1-100`：`Recall@10 +0.0300`、`nDCG@10 +0.0091`、`MRR@10 +0.0030`
   - `uda-curated-v1-100`：`Recall@10 +0.0300`、`nDCG@10 +0.0156`、`MRR@10 +0.0111`
   - `external macro average`：`Recall@10 +0.0300`、`nDCG@10 +0.0123`、`MRR@10 +0.0070`
3. `QASPER 100` 仍明顯是最難的 dataset；即使本輪外部基線略升，assembled `nDCG@10` 仍只有 `0.3903`。
4. `UDA 100` 仍顯著比 `QASPER 100` 友善，assembled `nDCG@10=0.6972`、`MRR@10=0.6447`，表示 current mainline 對 same-document wiki 類 evidence 仍相對穩定。

## 建議保留的常規比較集合

這一節只保留當下仍有決策價值的 lane 與基線。

| 類別 | 應保留項目 | 保留理由 |
| --- | --- | --- |
| current mainline baseline | `production_like_v1`（實際 snapshot：`qasper_v3 + query_focus off + 10x3600`） | 這是目前真正會被拿來回歸檢查的 baseline，所有文件都應以它為準。 |
| explicit query-focus comparison lane | `generic_guarded_query_focus_v1` | 2026-04-04 的歷史結果仍顯示它在 `pilot trio` 曾帶來 `nDCG@10 +0.0194` uplift；若未來要再做 query-side semantic-gap 驗證，應以它作為顯式 lane，而不是把它誤寫成 current production baseline。 |
| external pressure-test baseline | `qasper-curated-v1-100`、`uda-curated-v1-100` 與 `external 100Q average` | 這兩份 package 比 pilot 更能顯示英文 semantic-gap 與 same-document localization 的主戰場。 |

## External `100Q` 最新摘要

### 最新 assembled 分數

| Dataset | Recall@10 | nDCG@10 | MRR@10 |
| --- | ---: | ---: | ---: |
| `qasper-curated-v1-100` | `0.6200` | `0.3903` | `0.3183` |
| `uda-curated-v1-100` | `0.8600` | `0.6972` | `0.6447` |
| `external macro average (self excluded)` | `0.7400` | `0.5437` | `0.4815` |

### 最新 miss 分布

| Dataset | miss 總數 | `recall_only` | `rerank_only` | `assembled_only` |
| --- | ---: | ---: | ---: | ---: |
| `QASPER 100` | `38` | `35` | `2` | `1` |
| `UDA 100` | `14` | `12` | `2` | `0` |

### 這輪代表什麼

1. `QASPER 100` 的主問題仍是英文 generic evidence-field semantic gap。
2. `UDA 100` 的主問題仍是 same-document section / list / cast / season / release-date localization。
3. 目前 `production_like_v1` 根本沒有啟用 query focus，因此 external `100Q` 這輪的 planner coverage 是 `0 / 100` 與 `0 / 100`。
4. 因此，若接下來要驗證 `english_field_focus_v2`，必須把它當成新的 guarded lane 明確比較，不能再假設它已內建在 `production_like_v1` 裡。

詳細逐題 miss 與批次歸類，請看 [`docs/external-100q-miss-analysis-2026-04-04.md`](./external-100q-miss-analysis-2026-04-04.md)。

## 歷史資料中仍值得保留的部分

舊文件中的大部分 `generic_field_focus_v1` 主線敘述已移除，但以下一條歷史訊號仍值得保留：

- `2026-04-04` 的 `generic_guarded_query_focus_v1` 相對 `generic_guarded_evidence_synopsis_v3`，在 `pilot trio` 上曾帶來：
  - `Recall@10 +0.0128`
  - `nDCG@10 +0.0194`
  - `MRR@10 +0.0214`

這組數字的意義現在只剩下：

> query-side semantic-gap lane 曾被證明有用，值得在未來重新以顯式 guarded lane 驗證；但它不再代表目前 `production_like_v1` 的真實 baseline。

## 下一輪最高 ROI 假設

如果後續還要做 benchmark-driven 優化，最值得維持的主假設仍是：

> 在 current `production_like_v1` 之上，重新開一條顯式 guarded lane 驗證 `english_field_focus_v2`，優先補英文 `dataset / corpus / size / baseline / experiment / metric / annotation / pretraining source` 這批 high-ROI field intents。

這個方向仍符合產品邊界，因為它：

- 不引入新基礎設施
- 不放寬 `SQL gate`、`deny-by-default` 與 `ready-only` 這些安全邊界
- 主要處理 external `100Q` 仍最集中的 `recall_only` / `rerank_only` semantic-gap miss
