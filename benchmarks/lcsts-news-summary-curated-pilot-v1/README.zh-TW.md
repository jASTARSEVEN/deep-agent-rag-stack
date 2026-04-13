# lcsts-news-summary-curated-pilot-v1

## 用途

從 LCSTS 官方 test split 提取的 `10` 題中文新聞摘要真實資料 package。

## 資料來源與還原依據

- 上游資料集：LCSTS 官方 test split。
- 上游來源：Hugging Face `suolyer/lcsts`。
- 抽取規則：取 test split 前 `10` 筆，並移除 `input` 欄位共用的 instruction 前綴。
- 每題都保存 test split 的零起算 row index 作為穩定鍵，原始 LCSTS `id` 則保留在 `source_mapping.original_id`。
