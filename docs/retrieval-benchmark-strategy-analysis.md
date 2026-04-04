# Retrieval Benchmark Strategy Analysis（截至 2026-04-04）

## 文件目的

此文件現在只回答四件對後續優化最有用的事：

1. 目前正式 runtime 的最新分數是什麼。
2. current HEAD 下哪些策略值得持續保留在常規比較集合。
3. 已經測過哪些策略，它們各自證明了什麼。
4. 下一輪優先該打哪一類 miss，不該再回頭重試哪些低 ROI 方向。

閱讀順序也依此重新整理：

1. 先看正式 runtime。
2. 再看目前保留的常規比較集合。
3. 最後看歷史策略與診斷結論。

## Benchmark 改善策略

後續 benchmark-driven 改善，正式採以下策略：

1. 先以目前主線設定實際跑分，建立 `before` baseline。
2. 每一輪只允許一個主假設與最小、可審查改動。
3. 改動後必須重新跑分，比較 `before / after`。
4. 若分數沒有達標，或相對目前最佳結果反而下降：
   - 只保留分析文件更新
   - 其餘程式與設定改動一律回退
   - 再重新分析最新 miss 題目與目前查到的 chunks
5. 若分數有提升：
   - 保留改動
   - 仍要重新分析最新 miss 題目與目前查到的 chunks
   - 再決定下一輪最有價值的主假設

這個策略的核心不是「連續調參直到分數上升」，而是：

> **每一輪都要先用真實 benchmark 驗證，再以最新 miss/chunk 診斷來決定下一輪，而不是靠猜測連續疊規則。**

---

## 2026-04-04 實測更新：`query_focus_v1`

這一輪不是只看離線 artifact，而是實際做了以下重建與驗證：

1. 以 `Docker Compose` 重建資料庫與 runtime stack。
2. 依各 benchmark package / reproduce 文件重新建立三個 area 與對應 source documents。
3. 等待文件正式進入 `ready` 後，再匯入三個 snapshot：
   - `tw-insurance-rag-benchmark-v1`
   - `qasper-curated-v1-pilot`
   - `uda-curated-v1-pilot`
4. 以目前程式碼在重建後的資料庫上，直接比較：
   - `qasper_guarded_evidence_synopsis_v3`
   - `qasper_guarded_query_focus_v1`

### 驗證結果摘要

| Dataset | `v3` Recall@10 | `query_focus_v1` Recall@10 | Recall uplift | `v3` nDCG@10 | `query_focus_v1` nDCG@10 | nDCG uplift | `v3` MRR@10 | `query_focus_v1` MRR@10 | MRR uplift |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `tw-insurance-rag-benchmark-v1` | `0.8667` | `0.8667` | `+0.0000` | `0.7283` | `0.7481` | `+0.0197` | `0.6825` | `0.7083` | `+0.0258` |
| `QASPER` | `0.8148` | `0.8148` | `+0.0000` | `0.5353` | `0.5353` | `+0.0000` | `0.4467` | `0.4467` | `+0.0000` |
| `UDA` | `0.8462` | `0.8846` | `+0.0385` | `0.7357` | `0.7742` | `+0.0385` | `0.7083` | `0.7468` | `+0.0385` |
| 三資料集平均 | `0.8425` | `0.8554` | `+0.0128` | `0.6664` | `0.6858` | `+0.0194` | `0.6125` | `0.6339` | `+0.0214` |

### 這輪真正證明了什麼

1. `query_focus_v1` 在重建後的真實資料庫上沒有造成 regression。
2. `self` 的提升不是靠擴池，而是 query-side intent/slot 對齊把既有 evidence 排得更前面。
3. `UDA` 的提升直接命中原本最代表性的 comparison 題：
   - `Does this approach perform better in the multi-domain or single-domain setting?`
4. `QASPER` 持平，代表目前這組 bilingual core intent 規則沒有破壞英文 general retrieval，但也尚未打開新的 QASPER uplift。

### self dataset 實際改善題

`query_focus_v1` 在 `tw-insurance-rag-benchmark-v1` 上實際推前了 3 題：

- `投保臻滿億2變額萬能壽險會有身分限制嗎?`
  - `rank 2 -> 1`
  - planner intent：`eligibility_identity`
- `保利美美元利率變動型終身壽險其累計最高投保金額為何?`
  - `rank 7 -> 6`
  - planner intent：`amount_max`
- `被保險人-基本資料變更需有誰簽章及應備文件為何`
  - `rank 4 -> 2`
  - planner intent：`eligibility_identity`

### 對 lane 決策的直接意義

- `query_focus_v1` 已通過這一輪 benchmark governance，可保留程式碼，不需回退。
- 它的角色不是取代 `evidence_synopsis_v3`，而是作為其上層的 query-side semantic-gap 補強。
- assembled budget sweep 已顯示：
  - `9 x 3000 = 27000` 是主線 sweet spot：相對 `10 x 3500 = 35000` 少 `8000` 字元，三資料集平均 `Recall@10 / nDCG@10 / MRR@10` 全持平。
  - `6 x 3000 = 18000` 雖然更省，但平均 `Recall@10` 下降約 `0.037`，不適合作為主線。
- 因此主線切到 `9 x 3000`，並另外保留 `qasper_guarded_query_focus_budget_6x3000` 作為成本優先 profile。

---

## 正式 runtime 更新：`easypinex-host + BAAI/bge-reranker-v2-m3`

這一節放在最前面，因為它代表目前主線最接近正式環境的實跑結果。

### 2026-04-04 實跑前置修正

在正式 runtime 路徑上，先確認了兩個關鍵前提：

1. `Easypinex-host /v1/rerank` 可用，但先前 `10s` timeout 太短。
   - 最小 probe 首次成功回應約需 `28.96s`。
   - 若維持 `10s`，benchmark 會大量走 fail-open fallback，無法代表 hosted rerank 真實能力。
2. `easypinex-host` 的 `RERANK_MODEL` 必須使用真實 model 名稱。
   - 本輪正式對齊為 `BAAI/bge-reranker-v2-m3`。
   - `bge-rerank` 這類 alias 不再視為正式可用值。

本節所有 hosted 分數均來自以下設定：

- `RERANK_PROVIDER=easypinex-host`
- `RERANK_MODEL=BAAI/bge-reranker-v2-m3`
- `EASYPINEX_HOST_RERANK_TIMEOUT_SECONDS=60`
- `RETRIEVAL_EVIDENCE_SYNOPSIS_VARIANT=qasper_v3`
- 主線已套用 `query-aware assembler anchor`

### 正式 runtime：最新主線分數

| Dataset | before（hosted baseline） | after（目前主線） | uplift |
| --- | ---: | ---: | ---: |
| `QASPER` nDCG@10 | `0.5661` | `0.5846` | `+0.0185` |
| `tw-insurance-rag-benchmark-v1` nDCG@10 | `0.7283` | `0.7283` | `+0.0000` |
| `UDA` nDCG@10 | `0.5288` | `0.7353` | `+0.2065` |
| 三資料集平均 nDCG@10 | `0.6077` | `0.6827` | `+0.0750` |

### 正式 runtime：平均 Recall / MRR 補充

| 指標 | before（hosted baseline） | after（目前主線） | uplift |
| --- | ---: | ---: | ---: |
| 平均 Recall@10 | `0.8031` | `0.8672` | `+0.0641` |
| 平均 MRR@10 | `0.5467` | `0.6255` | `+0.0787` |

### 正式 runtime：目前最重要的判讀

1. 本輪最明顯的收益來自 assembler retention，而不是再加深 recall pool。
2. `UDA` 的大幅提升證明先前有大量題目其實是 `rerank hit`，但 assembler 沒保住正確 child。
3. `self` 維持 `0.7283`，表示這輪 assembler 修正沒有在中文保險資料集上引入明顯副作用。
4. `QASPER` 雖然穩定上升到 `0.5846`，但剩餘 gap 已更多落在 `semantic gap / rerank discrimination`，而不是純 assembler retention。

### 正式 runtime：miss 分布更新

| Dataset | assembled miss 總數 | `recall_only` | `rerank_only` | `assembled_only` |
| --- | ---: | ---: | ---: | ---: |
| `QASPER` | `3` | `1` | `1` | `1` |
| `tw-insurance-rag-benchmark-v1` | `4` | `3` | `1` | `0` |
| `UDA` | `4` | `3` | `0` | `1` |

### 正式 runtime：對下一輪的直接意義

- 目前主戰場已從 assembler 擴窗，轉回 `recall_only` 與 `rerank_only`。
- 下一輪若要繼續開 lane，主假設應該是「讓 recall / rerank 更理解 query 想找的證據型別」，而不是再把 assembler window 當主策略。

---

## 2026-04-04 External 100Q Baseline

這一節固定記錄「排除 self」之後，目前兩份外部 `100` 題 package 在正式 profile 下的最新分數。

正式基線規則：

- dataset 固定為：
  - `qasper-curated-v1-100`
  - `uda-curated-v1-100`
- evaluation profile 固定為 `qasper_guarded_query_focus_v1`
- `self` dataset 不納入這一節，也不納入 macro average

### External 100Q Metrics

| Dataset | Evaluation Profile | Question Count | Recall@10 | nDCG@10 | MRR@10 | Precision@10 | Doc Coverage@10 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `qasper-curated-v1-100` | `qasper_guarded_query_focus_v1` | `100` | `0.5900` | `0.3812` | `0.3153` | `0.0640` | `0.8100` |
| `uda-curated-v1-100` | `qasper_guarded_query_focus_v1` | `100` | `0.8300` | `0.6816` | `0.6336` | `0.0830` | `1.0000` |
| `External macro average (self excluded)` | `qasper_guarded_query_focus_v1` | `100 + 100` | `0.7100` | `0.5314` | `0.4745` | `0.0735` | `0.9050` |

### External 100Q 判讀

1. `QASPER 100` 仍然明顯比 `UDA 100` 難，assembled `nDCG@10` 只有 `0.3812`，表示 query-to-evidence semantic gap 仍是主要瓶頸。
2. `UDA 100` 在同一 profile 下 assembled `Recall@10=0.8300`、`nDCG@10=0.6816`，代表官方 `nq` full-source 子集對目前主線更友善，且 rerank/assembler 能穩定把 evidence 留住。
3. 這一節不與 pilot package 做 uplift 比較，因為 `27/26` 題 pilot 與 `100` 題版不是同一 benchmark population，直接比 uplift 會誤導。

---

## 目前建議保留的常規比較集合

這一節只保留仍對未來改善有決策價值的 lane。

| 類別 | Profile / 組合 | 為何保留 |
| --- | --- | --- |
| 正式 runtime baseline | `easypinex-host + BAAI/bge-reranker-v2-m3 + qasper_v3 + query-aware assembler anchor` | 代表目前最接近正式主線的實際分數，應作為後續 runtime 回歸基準。 |
| 主線前一版 baseline | `qasper_guarded_evidence_synopsis_v3` | 用來直接比較 query-side 對齊是否帶來實質 uplift。 |
| Query-side semantic-gap lane | `qasper_guarded_query_focus_v1` | 已在 compose 重建後的真實資料庫上驗證：self / UDA 提升、QASPER 持平，適合作為下一輪 query-side 對齊基線。 |

不再保留為常規比較集合的 lane，不代表完全無價值，而是它們已不再是 current HEAD 上值得固定重跑的主集合。

---

## 已測策略整理

這一節保留「測過什麼」與「它證明了什麼」，避免後續優化再次回頭重試低 ROI 方向。

### current HEAD 仍可直接比較的 lane

| 方法 | 核心思想 | 最新可用數值 | 狀態 | 對未來改善的價值 |
| --- | --- | --- | --- | --- |
| `evidence_synopsis_v3` | `query_focus_v1` 前一版主線 | 三資料集平均 `Recall@10=0.8425`、`nDCG@10=0.6664`、`MRR@10=0.6125` | 已重跑 | 作為 query-side 對齊前的直接比較基線 |
| `query_focus_v1` | 以 intent/slot planner 補 query-side evidence 對齊 | 三資料集平均 `Recall@10 uplift=+0.0128`、`nDCG@10 uplift=+0.0194`、`MRR@10 uplift=+0.0214` | 已實測 | 適合觀察中文 table-field 與英文 comparison/count 類 semantic-gap 問題 |

### 歷史測過、但不建議作為常規主集合的策略

| 方法 | 核心思想 | 歷史訊號 | 目前狀態 | 保留原因 |
| --- | --- | --- | --- | --- |
| depth lane | 加深召回池 | 歷史最佳 Recall@10=`0.4074` | 未納入本輪 BGE 長跑批 | 用來提醒「問題不只是池子太淺」 |
| coverage lane | 在固定 output budget 下擴大 pre-assembly coverage | 歷史最佳 Recall@10=`0.3704` | 未納入本輪 BGE 長跑批 | 用來提醒 coverage 擴張雜訊高、ROI 低 |
| fact-heavy child refinement + assembler v2 | 對 Dataset / Setup / Metrics 類 child 做 evidence-centric refinement | 歷史最佳 Recall@10=`0.7407` | retired lane | 保留作為 evidence density 高 ROI 的證據 |
| heading-aware recall | 用 heading lexical hit 補強召回 | 歷史最佳 Recall@10=`0.5185` | retired lane | 保留作為「有訊號但非主要瓶頸」的參考 |
| parent-first lexical recall | 先 parent lexical hit，再回填 child | 歷史最佳 Recall@10=`0.4444` | retired lane | 保留作為失敗樣式，避免回頭重做 |
| parent-group retrieval | child RRF 後先聚合 parent 再選 | 歷史最佳 Recall@10=`0.6296` | retired lane | 保留作為曾有效但不如 assembler_v2 的中間解 |
| RPC parent-content backfill | 在 `match_chunks` 內直接做 parent-content FTS 回填 | 歷史最佳 Recall@10=`0.4815` | retired lane | 保留作為 DB 層粗粒度回填效果不佳的證據 |

### 歷史策略的整體判讀

1. `depth / coverage / parent-first / RPC backfill` 已足夠證明不是優先方向。
2. `assembler lane` 是第一個明顯有效的高 ROI lane。
3. `fact-heavy child refinement` 到 `evidence synopsis` 系列，其實都在指向同一個結論：
   - 高 ROI 的槓桿在 evidence density 與 query-to-evidence phrasing 對齊。
4. 在目前 hosted 主線已與 `BAAI/bge-reranker-v2-m3` 對齊的前提下，額外保留 BGE apples-to-apples 對照已無決策必要。

---

## 歷史 artifact 中仍值得保留的診斷結論

詳細逐題 miss 清單已移除，因為它對日後重讀的資訊密度不高；但以下診斷結論仍值得保留。

### `evidence_synopsis_v2` 階段留下的訊號

在先前 deterministic artifact 中，`v2` 剩餘 miss 呈現三種仍有價值的型別：

| miss 類型 | 代表問題 | 保留原因 |
| --- | --- | --- |
| `recall_only` | query framing 與 evidence framing 不一致 | 說明主戰場是 semantic gap，而不是單純沒把池子開大 |
| `rerank_only` | evidence 有進池，但排序判別不夠穩 | 說明 query-aware phrasing 仍值得做得更精準、更 selective |
| `assembled_only` | rerank 已命中，但長 parent 內保留策略失敗 | 說明 assembler 修正要聚焦 retention，而不是無限制擴窗 |

這一階段最重要的歷史結論只有兩句：

1. assembler-only miss 已被壓到很小。
2. hardest cases 多半卡在 query-to-evidence semantic gap。

### `evidence_synopsis_v3_gate` 留下的訊號

`v3` 的唯一主假設是補三種 bridge：

- dataset alias bridge
- task framing bridge
- metric-aspect bridge

它證明了：

1. 這些 bridge 的確能推高 QASPER Recall。
2. 但「Recall 提升」不等於「ranking quality 同步提升」。
3. 若 bridge 介入得太重，容易變成 QASPER-leaning，而非跨資料集穩定增益。

因此 `v3` 仍應保留，但定位應是：

- recall stress lane
- semantic-gap 診斷 lane

而不是直接當成正式主線策略本身。

---

## 三資料集綜合決策

- 若主目標是看目前正式主線真實表現：
  - 以 `easypinex-host + BAAI/bge-reranker-v2-m3 + qasper_v3 + query-aware assembler anchor` 作為最新 baseline。
- 若主目標是看 query-side semantic-gap 對齊是否成立：
  - 直接比較 `qasper_guarded_evidence_synopsis_v3` 與 `qasper_guarded_query_focus_v1`。
- 若主目標是跨資料集平均 uplift：
  - 目前優先看 `query_focus_v1` 在重建後真實資料庫上的三資料集平均 uplift。

---

## 後續建議

### Primary

下一輪最值得的唯一主假設已不再是「要不要做 query-side 對齊」，而是：

> 在保留 `query_focus_v1` 的前提下，擴充下一批高 ROI intents / field aliases，專注收斂剩餘的 `recall_only` 與 `rerank_only` semantic-gap miss。

可聚焦方向：

- 補強 zh-TW table-field query 的 alias 與 target-field vocabulary。
- 擴充英文除 `count_total / comparison_axis` 之外的下一個高 ROI intent。
- 保持高信心 gating，避免把 query rewrite 擴成 generic prompt engineering。

### Secondary

只在主戰場處理完後，才值得開小型 secondary lane 處理剩餘 assembler 題，例如：

- `QASPER`：`How many reviews in total (both generated and true) do they evaluate on Amazon Mechanical Turk?`
- `UDA`：`Does this approach perform better in the multi-domain or single-domain setting?`

這些題目較像局部 retention 問題，而不是目前最主要的 miss 類型。

### 目前不建議優先重做的方向

- 再加深 recall pool
- 再擴大 coverage lane
- 再回去做 generic fact alignment score 微調
- 再做粗粒度 parent lexical / RPC backfill
- 再把 assembler window 當主要策略擴張

原因很一致：

> 現在主問題已不再是 assembler 保不住 evidence，  
> 而是 recall / rerank 還不夠理解 query 想找的證據型別，  
> 導致正確 evidence 不是沒進池，就是沒被穩定排到前面。
