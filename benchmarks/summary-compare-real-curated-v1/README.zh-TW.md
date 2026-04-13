# summary-compare-real-curated-v1

此 suite 只包含從真實外部資料集提取的 packages。

每個 package 都會記錄上游來源、split、row index 與原始 example id，方便外部獨立重建。

這條 suite 目前定位為 summary/compare 的 tuning 與 observability lane。

它不是 product gate；唯一的 product gate 仍是 `phase8a-summary-compare-v1`。

目前 baseline 的引用規則如下：

- 一律使用 package-level consolidated baseline 作為 current suite baseline
- 後續若產生新的 aggregate artifact，除非文件明確升格，否則只能視為觀測輸出，不能直接覆蓋這條 baseline
