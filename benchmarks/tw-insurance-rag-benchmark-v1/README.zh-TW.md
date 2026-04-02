# tw-insurance-rag-benchmark-v1

此目錄是本 repo 對外提供的 benchmark package，目的是讓外部讀者可以檢查 benchmark 輸入、重建 evaluation dataset，並重新執行 retrieval benchmark，而不是只看根目錄 README 中的 summary metrics。

[English README](README.md)

## Purpose

此 benchmark package 用於支援第三方重現本專案的 retrieval evaluation 結果，並審查：

- benchmark 使用了哪些文件與題目
- gold spans 如何對回文件內容
- 單題結果是否與 summary metrics 一致
- 在相同設定下是否能近似重跑

## 內容

- `manifest.json`：snapshot 身分、commit、migration 版本、來源文件校驗值與 reference run 資訊
- `source_documents/`：正式打包的 benchmark 原始文件
- `parser_artifacts/`：從物件儲存複製出的 parser 階段 artifact
- `parser_artifacts_manifest.jsonl`：parser artifact 清單與 checksum
- `documents.jsonl`：benchmark 文件中繼資料
- `document_display_text.jsonl`：用來驗證 offset 的完整 `display_text` snapshot
- `document_chunks.jsonl`：用來檢查 chunking 結果的 parent/child chunk snapshot
- `questions.jsonl`：evaluation 題目
- `gold_spans.jsonl`：對齊 `display_text` offsets 的證據 spans
- `per_query.jsonl`：reference run 的逐題結果
- `runs.jsonl`：匯出的 run 摘要
- `reference_run_report.json`：reference run 的完整報表
- `dataset_card.md`：資料範圍、欄位說明與限制
- `reproduce.md`：重現流程

## How to Reproduce

1. 啟動專案 stack 並完成 migration。
2. 上傳四份 benchmark 原始文件，並等待文件進入 `ready`。
3. 執行一鍵重現腳本：
   - `AREA_ID=<target-area-id> ./scripts/reproduce_benchmark.sh`
4. 檢查輸出結果：
   - `benchmarks/tw-insurance-rag-benchmark-v1/reproduced_run_report.json`
   - `benchmarks/tw-insurance-rag-benchmark-v1/reproduced_compare_report.json`
5. 若需要手動控制每一步，請改看 `reproduce.md`。

## Public Release Notes

目前此 package 已直接包含四份原始 PDF/XLSX 於 `source_documents/`，也包含 `parser_artifacts/` 供外部審查 parser 階段輸出。

## Troubleshooting

- 若匯入失敗且顯示缺少文件，請確認目標 area 內已存在四份 benchmark 文件，且都處於 `ready`。
- 若 span offset 對不起來，請先確認來源文件與 `manifest.json` 記錄的版本、parser 路徑是否一致。
- 若重跑後 metrics 有偏差，先看 `per_query.jsonl`；parser、rerank model 或 chunking 調整通常會先影響少數題目。
