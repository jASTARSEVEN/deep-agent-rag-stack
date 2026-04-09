# Phase 8A 摘要 / 比較 Checkpoint

## 用途

這個 package 定義 `Phase 8A` 的固定 summary / compare checkpoint 資料集，用來驗證摘要與比較 runtime 是否達到正式過線條件。

它對應 `python -m app.scripts.run_summary_compare_checkpoint` 流程，重點覆蓋：

- 單文件整體摘要
- 章節聚焦摘要
- 多文件共同主題摘要
- 跨文件比較

## 使用方式

1. 先把 [`source_documents`](./source_documents) 內的檔案上傳到同一個 Knowledge Area。
2. 等待所有文件都進入 `ready`。
3. 用 checkpoint CLI 指向該 area 與本資料集目錄執行。

範例：

```bash
python -m app.scripts.run_summary_compare_checkpoint \
  --area-id <AREA_ID> \
  --dataset-dir benchmarks/phase8a-summary-compare-v1 \
  --actor-sub <USER_SUB> \
  --judge-model gpt-5-mini \
  --output-path artifacts/phase8a-summary-compare-report.json
```

## 資料集結構

- `manifest.json`：資料集 metadata
- `questions.jsonl`：固定 checkpoint 題目
- `source_documents/`：本機建立 benchmark area 時可直接使用的參考文件

`gold_span_refs` 採 quote-first contract，runner 會依 target area 內實際 `display_text` 對回 offsets。
