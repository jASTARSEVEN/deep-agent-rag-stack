# Retrieval Benchmark Strategy Analysis（截至 2026-04-04）

## 文件目的

此文件現在只回答四件對後續優化最有用的事：

1. 目前正式 runtime 的最新分數是什麼。
2. current HEAD 下哪些策略值得持續保留在常規比較集合。
3. 已經測過哪些策略，它們各自證明了什麼。
4. 下一輪優先該打哪一類 miss，不該再回頭重試哪些低 ROI 方向。

閱讀順序也依此重新整理：

1. 先看正式 runtime。
2. 再看 apples-to-apples 的 BGE 對照。
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

## 目前建議保留的常規比較集合

這一節只保留仍對未來改善有決策價值的 lane。

| 類別 | Profile / 組合 | 為何保留 |
| --- | --- | --- |
| 正式 runtime baseline | `easypinex-host + BAAI/bge-reranker-v2-m3 + qasper_v3 + query-aware assembler anchor` | 代表目前最接近正式主線的實際分數，應作為後續 runtime 回歸基準。 |
| BGE apples-to-apples baseline | `production_like_v1` | 用來隔離 provider 差異，作為所有 current HEAD lane 的共同基線。 |
| 跨資料集平均 nDCG 最佳 lane | `qasper_guarded_assembler_v2_bge` | 目前仍是三資料集平均 `nDCG@10 uplift` 最佳的 current HEAD lane。 |
| QASPER ranking stress lane | `qasper_guarded_evidence_synopsis_v2_bge` | QASPER `nDCG@10` 最佳，適合觀察 ranking quality。 |
| QASPER recall stress lane | `qasper_guarded_evidence_synopsis_v3_bge` | QASPER `Recall@10` 最佳，適合觀察 recall ceiling 與 semantic-gap 類 miss。 |

不再保留為常規比較集合的 lane，不代表完全無價值，而是它們已不再是 current HEAD 上值得固定重跑的主集合。

---

## BGE apples-to-apples 參考

這一節保留，是因為它能隔離 hosted provider 差異，讓策略比較更乾淨。

### 本輪方法學

- 日期：`2026-04-04`
- rerank provider：`BAAI/bge-reranker-v2-m3`
- 資料集：
  - `QASPER`：`qasper-curated-v1-pilot`
  - `self`：`tw-insurance-rag-benchmark-v1`
  - `UDA`：`uda-curated-v1-pilot`
- artifact：
  - `QASPER + self`：`.omx/tmp/bge-core-profiles-latest.json`
  - `UDA`：`benchmarks/uda-curated-v1-pilot/bge_core_profiles_summary.json`
- 本輪已完成 BGE 重跑的 current HEAD profile：
  - `production_like_v1`
  - `qasper_guarded_assembler_v2_bge`
  - `qasper_guarded_evidence_synopsis_v2_bge`
  - `qasper_guarded_evidence_synopsis_v3_bge`

### 三資料集平均 nDCG@10 uplift 排名

| Profile | QASPER nDCG@10 | self nDCG@10 | UDA nDCG@10 | 三資料集平均 nDCG@10 | 相對 baseline 平均 uplift |
| --- | ---: | ---: | ---: | ---: | ---: |
| `production_like_v1` | `0.5201` | `0.7622` | `0.5288` | `0.6037` | `+0.0000` |
| `qasper_guarded_assembler_v2_bge` | `0.5558` | `0.7727` | `0.5288` | `0.6191` | `+0.0154` |
| `qasper_guarded_evidence_synopsis_v2_bge` | `0.5743` | `0.7254` | `0.5264` | `0.6087` | `+0.0050` |
| `qasper_guarded_evidence_synopsis_v3_bge` | `0.5661` | `0.7283` | `0.5288` | `0.6077` | `+0.0040` |

### 平均 Recall / MRR 補充

| Profile | 平均 Recall@10 | Recall uplift | 平均 MRR@10 | MRR uplift |
| --- | ---: | ---: | ---: | ---: |
| `production_like_v1` | `0.7525` | `+0.0000` | `0.5565` | `+0.0000` |
| `qasper_guarded_assembler_v2_bge` | `0.7883` | `+0.0358` | `0.5658` | `+0.0093` |
| `qasper_guarded_evidence_synopsis_v2_bge` | `0.7908` | `+0.0383` | `0.5519` | `-0.0046` |
| `qasper_guarded_evidence_synopsis_v3_bge` | `0.8031` | `+0.0506` | `0.5467` | `-0.0098` |

### BGE 對照的核心結論

1. 若主目標是三資料集平均 `nDCG@10 uplift`，最佳 lane 仍是 `qasper_guarded_assembler_v2_bge`。
2. `evidence synopsis` 系列仍有價值，但更像是 QASPER-leaning lane，而不是跨資料集平均品質最佳解。
3. `v3` 的平均 Recall uplift 最大，但沒有同步帶來平均 MRR uplift，因此不適合直接作為「整體最佳」結論。

---

## 已測策略整理

這一節保留「測過什麼」與「它證明了什麼」，避免後續優化再次回頭重試低 ROI 方向。

### current HEAD 仍可直接比較的 lane

| 方法 | 核心思想 | 最新可用數值 | 狀態 | 對未來改善的價值 |
| --- | --- | --- | --- | --- |
| `production_like_v1` | 主線 baseline | 三資料集平均 nDCG@10=`0.6037` | 已重跑 | 所有 current HEAD 策略比較的共同基線 |
| `assembler_v2` | rerank 已命中時，改善 assembled retention | 三資料集平均 nDCG uplift=`+0.0154` | 已重跑 | 目前平均 nDCG 目標下最值得保留的跨資料集 lane |
| `evidence_synopsis_v2` | 用 evidence-oriented phrasing 補強排序判別 | QASPER nDCG@10=`0.5743` | 已重跑 | 適合觀察 ranking quality 與 semantic-gap 類排序問題 |
| `evidence_synopsis_v3` | 在 v2 上補 alias / task / metric bridge | QASPER Recall@10=`0.8889` | 已重跑 | 適合觀察 recall ceiling，但不能單獨當平均品質最佳證據 |

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
4. 但若回到 current HEAD 的跨資料集平均 `nDCG@10 uplift`，目前最佳平衡點仍是 `assembler_v2`。

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

- 若主目標是隔離 provider 差異、比較 current HEAD 策略：
  - 以 `production_like_v1` 對照 `qasper_guarded_assembler_v2_bge`、`qasper_guarded_evidence_synopsis_v2_bge`、`qasper_guarded_evidence_synopsis_v3_bge`。
- 若主目標是看目前正式主線真實表現：
  - 以 `easypinex-host + BAAI/bge-reranker-v2-m3 + qasper_v3 + query-aware assembler anchor` 作為最新 baseline。
- 若主目標是跨資料集平均 `nDCG@10 uplift`：
  - 優先看 `qasper_guarded_assembler_v2_bge`。
- 若主目標是 QASPER recall ceiling：
  - 優先看 `qasper_guarded_evidence_synopsis_v3_bge`。
- 若主目標是 QASPER ranking quality：
  - 優先看 `qasper_guarded_evidence_synopsis_v2_bge`。

---

## 後續建議

### Primary

下一輪最值得的唯一主假設應是：

> 讓 `evidence synopsis / recall phrasing` 只在真正需要時介入，專注收斂 `recall_only` 與 `rerank_only` 的 semantic-gap miss。

可聚焦的方向：

- 讓 alias / task / metric / baseline-list 類 bridge 更 selective。
- 讓 bridge 補強只在真正需要的 query 類型生效。
- 在不破壞 `self` 的前提下，補強中文保險 query 與條款 phrasing 的 lexical / semantic 對齊。
- 讓長 numeric / tabular question 的 query wording 更容易撞到正確 evidence 類型。

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
