# Retrieval Benchmark Strategy Analysis（截至 2026-04-05）

## 文件目的

此文件現在只保留對後續 benchmark 治理最有用的五件事：

1. 目前 `production_like_v1` 的真實設定與最新分數。
2. 六個 benchmark package 在同一條 fresh rerun 下的 assembled 指標。
3. external `100Q` 各資料集基線的最新狀態。
4. `MS MARCO 100` 應如何解讀，不要把近天花板分數誤判成通用檢索已解完。
5. 下一輪 benchmark-driven 優化仍該把力氣放在哪裡。

## 2026-04-05 重跑範圍

本輪直接在目前 Compose-backed benchmark 環境中，對已載入且文件皆為 `ready` 的六個 dataset 重新執行 `production_like_v1`：

| Dataset | Run ID |
| --- | --- |
| `msmarco-curated-v1-100` | `5e9de20b-4781-4711-a69e-03157e61d68a` |
| `uda-curated-v1-pilot` | `e57393cc-c9a3-4ceb-a36c-7af416b6ba66` |
| `tw-insurance-rag-benchmark-v1` | `c8e2ab5a-e193-4147-ac0c-491fb06189c5` |
| `uda-curated-v1-100` | `821345d6-9a4d-48ea-8fb4-fb36f2af182e` |
| `qasper-curated-v1-pilot` | `a1885718-c3ee-4465-aca5-35354a80457d` |
| `qasper-curated-v1-100` | `6c4636ce-85da-456c-a8b3-059b4650b1ae` |

## `production_like_v1` 目前真實設定快照

這次六個 run 的 `config_snapshot` 完全一致，代表目前 current HEAD 下 `production_like_v1` 的實際 baseline 為：

- rerank provider：`easypinex-host`
- rerank model：`BAAI/bge-reranker-v2-m3`
- rerank top N：`30`
- rerank max chars per doc：`2000`
- evidence synopsis：`enabled=true`，variant=`generic_v1`
- query focus：`enabled=false`，variant=`generic_field_focus_v1`
- vector / FTS / max candidates：`30 / 30 / 30`
- assembler budget：`9 x 3000`
- assembler max children per parent：`7`

這一點很重要：

> 目前 `production_like_v1` 已固定為 `query_focus=false + 9x3000`。舊的 query-focus-on 數字只能視為歷史比較，不可再當成 current mainline baseline。

## 最新 assembled 指標

### 六個 dataset 的最新分數

| Dataset | Recall@10 | nDCG@10 | MRR@10 | Precision@10 | Doc Coverage@10 |
| --- | ---: | ---: | ---: | ---: | ---: |
| `msmarco-curated-v1-100` | `1.0000` | `0.9674` | `0.9550` | `0.1050` | `1.0000` |
| `uda-curated-v1-pilot` | `0.8462` | `0.7333` | `0.7051` | `0.0885` | `0.9615` |
| `tw-insurance-rag-benchmark-v1` | `0.8667` | `0.7254` | `0.6792` | `0.0867` | `1.0000` |
| `uda-curated-v1-100` | `0.8300` | `0.6818` | `0.6340` | `0.0830` | `1.0000` |
| `qasper-curated-v1-pilot` | `0.7778` | `0.5507` | `0.4844` | `0.0815` | `1.0000` |
| `qasper-curated-v1-100` | `0.5900` | `0.3797` | `0.3142` | `0.0640` | `0.8200` |

## 對目前基線的直接判讀

1. 目前由簡單到難的排序相當穩定：`MS MARCO 100 -> UDA pilot -> self -> UDA 100 -> QASPER pilot -> QASPER 100`。
2. `QASPER 100` 仍是目前最難的外部資料集；在 `query_focus=false` 的 current baseline 下，assembled `nDCG@10` 為 `0.3797`。
3. `UDA 100` 仍顯著比 `QASPER 100` 友善，assembled `nDCG@10=0.6818`、`MRR@10=0.6340`，顯示 same-document wiki 類 evidence 仍是 current mainline 相對穩定的區段。
4. `MS MARCO 100` 這次 assembled 幾乎接近天花板，但不能把它解讀成「通用 web retrieval 問題已解完」；它在此 repo 內的 contract 是每題一份 snippet-bundle 文件，壓力測試重心比較接近 query-to-passage matching 與 answer localization sanity check。
5. 因此，真正仍在拉低 external hard lane 的主要因子，依然是 `QASPER 100`。

## 建議保留的常規比較集合

| 類別 | 應保留項目 | 保留理由 |
| --- | --- | --- |
| current mainline baseline | `production_like_v1`（實際 snapshot：`generic_v1 + query_focus off + 9x3000`） | 這是目前真正會被拿來回歸檢查的 baseline，所有文件都應以它為準。 |
| self / pilot stability set | `uda-curated-v1-pilot`、`tw-insurance-rag-benchmark-v1`、`qasper-curated-v1-pilot` | 這組最適合檢查主線策略是否在既有自家 benchmark 上失穩。 |
| external pressure-test trio | `msmarco-curated-v1-100`、`uda-curated-v1-100`、`qasper-curated-v1-100` | 三者合併後可以同時觀察 snippet-bundle sanity check、same-document localization 與英文 semantic-gap。 |
| hard external lane | `qasper-curated-v1-100` | 若要找下一輪最高 ROI 的 hard case，仍應優先看這份。 |

## External `100Q` 最新摘要

### 最新 assembled 分數

| Dataset | Recall@10 | nDCG@10 | MRR@10 |
| --- | ---: | ---: | ---: |
| `msmarco-curated-v1-100` | `1.0000` | `0.9674` | `0.9550` |
| `uda-curated-v1-100` | `0.8300` | `0.6818` | `0.6340` |
| `qasper-curated-v1-100` | `0.5900` | `0.3797` | `0.3142` |

### 最新 miss 分布

| Dataset | miss 總數 | `recall_only` | `rerank_only` | `assembled_only` | query focus applied |
| --- | ---: | ---: | ---: | ---: | ---: |
| `MS MARCO 100` | `0` | `0` | `0` | `0` | `0` |
| `UDA 100` | `17` | `15` | `2` | `0` | `0` |
| `QASPER 100` | `41` | `38` | `1` | `2` | `0` |

### 這輪代表什麼

1. `QASPER 100` 仍是英文 generic evidence-field semantic gap 的主戰場，而且在 `query_focus=false` 之後仍以 `recall_only` 為最大宗。
2. `UDA 100` 仍以 same-document section / list / cast / release-date localization 為主。
3. `MS MARCO 100` 在目前 snippet-bundle contract 下沒有 assembled miss，因此它更像 sanity check，而不是下一輪 hard frontier。
4. 若要看逐題的 legacy 詳細 miss log，仍可參考 [`docs/external-100q-miss-analysis-2026-04-04.md`](./external-100q-miss-analysis-2026-04-04.md)，但那份文件只覆蓋舊的 `QASPER 100 + UDA 100` 組合；`MS MARCO 100` 本輪不需要另外寫 miss 清單。

## 歷史資料中仍值得保留的部分

仍值得保留的歷史訊號只有一條：

- `generic_guarded_query_focus_v1` 曾在舊一輪 pilot 比較中帶來正向 uplift，證明 query-side semantic-gap lane 的方向本身是合理的。

這條歷史資料現在的意義只剩下：

> query focus 類策略仍值得演進，但任何新 lane 都必須直接對目前這條 `generic_v1 + query_focus off + 9x3000` baseline 比較，不能再對已淘汰的舊 snapshot 做勝負判讀。

## 下一輪最高 ROI 假設

如果後續還要做 benchmark-driven 優化，最值得維持的主假設仍是：

> 在 current `production_like_v1` 之上，針對 `QASPER 100` 的 `recall_only` 英文 semantic-gap 再開一條更強的 generic lane，例如 `english_field_focus_v2`，優先補英文 `dataset / corpus / size / baseline / experiment / metric / annotation / pretraining source` 這批 high-ROI field intents。

這個方向仍符合產品邊界，因為它：

- 不引入新基礎設施
- 不放寬 `SQL gate`、`deny-by-default` 與 `ready-only` 這些安全邊界
- 主要處理目前 external `100Q` 真正仍有大量空間的 `QASPER 100` `recall_only` miss
