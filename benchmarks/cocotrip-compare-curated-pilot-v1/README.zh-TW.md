# cocotrip-compare-curated-pilot-v1

## 用途

從 CoCoTrip 官方標註檔提取的 `10` 題 compare 真實資料 package。

## 資料來源與還原依據

- 上游資料集：CoCoSum 官方 repo 中的 CoCoTrip 標註資料。
- 上游檔案：`data/anno.json`。
- 抽取規則：保留 `test` split 原始順序，取前 `10` 筆。
- 每題都保存原始 test index，以及 `entity_a_id` / `entity_b_id`。
