# cnewsum-news-summary-curated-pilot-v1

## 用途

從 CNewSum processed test split 提取的 `10` 題中文新聞摘要真實資料 package。

## 資料來源與還原依據

- 上游資料集：CNewSum processed test split。
- 上游來源：Hugging Face `ethanhao2077/cnewsum-processed`。
- 抽取規則：從 `data/test-00000-of-00001.parquet` 取前 `10` 筆。
- 每題都保存原始資料集 `id`、零起算 row index 與 processed `label`。
