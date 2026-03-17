<!-- Phase 6 retrieval boundary decision note. -->

# Phase 6 檢索邊界決策

## 決策摘要

Phase 6 不將最終 `RRF` 與排名政策永久下沉到資料庫 RPC。

正式邊界改為：
- `DB / RPC`：負責 SQL gate 所需過濾、vector recall、PGroonga FTS recall，以及回傳最小 ranking inputs。
- `Python`：負責 `RRF`、未來 ranking policy、rerank、assembler 與 trace。

## 決策原因

未來預期會加入多種排名規則，例如：
- business rules
- source priors
- document-level penalties
- freshness
- section boosts

這些規則具有下列特性：
- 變動頻率高
- 需要較強的可測試性
- 需要明確 trace 與 debug 能力
- 常會依產品策略快速調整

若將最終排名邏輯固定在 SQL/RPC：
- 測試與除錯成本較高
- SQLite / 離線 fallback 較難維持
- 後續規則演進會持續推高 SQL 複雜度
- retrieval policy 會過度耦合到 Postgres extension 細節

## 目前實作

- `match_chunks` RPC 只回傳受保護候選與 `vector_rank` / `fts_rank`。
- `retrieve_area_candidates()` 在 Python 層做 `RRF`。
- `_apply_ranking_policy()` 作為未來擴充 business rules 的接點，本輪先維持 pass-through。
- rerank 與 assembler 仍維持在 Python 層。

## 後續原則

- 凡是「靠近資料、很吃索引、穩定不常改」的檢索責任，優先放 DB。
- 凡是「產品規則、常調整、需要 trace」的排序責任，優先放 Python。
- 若未來新增 ranking rules，不應為了下沉規則而破壞 deny-by-default、same-404、ready-only 的既有邊界。
