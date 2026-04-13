# multinews-multi-doc-summary-curated-pilot-v1

## 用途

從 Multi-News 官方 test set 提取的 `10` 題多文件摘要真實資料 package。

## 資料來源與還原依據

- 上游資料集：Multi-News 官方 test split。
- 上游檔案：資料集 repo 的 `data/test.src.cleaned` 與 `data/test.tgt`。
- 抽取規則：保留原始行順序，取前 `10` 筆。
- 每題都在 `source_record_index` 保存原始行號。
