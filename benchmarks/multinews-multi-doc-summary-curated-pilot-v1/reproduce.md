# Reproduce

## English

1. Download `data/test.src.cleaned` and `data/test.tgt` from the official Multi-News dataset repository.
2. Read the first 10 aligned rows in original order.
3. Split each source row on `|||||` to reconstruct the individual source documents.
4. Use `source_record_index` to verify the exact original source-summary pair.

## 繁體中文

1. 從官方 Multi-News 資料集 repo 下載 `data/test.src.cleaned` 與 `data/test.tgt`。
2. 按原始順序讀取前 `10` 筆對齊資料。
3. 用 `|||||` 分隔符把每筆 source row 還原成多份來源文件。
4. 透過 `source_record_index` 回查原始 source-summary 配對。
