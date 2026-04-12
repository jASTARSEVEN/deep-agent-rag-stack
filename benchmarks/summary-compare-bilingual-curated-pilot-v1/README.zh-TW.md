# summary-compare-bilingual-curated-pilot-v1

## 用途

此 suite 收納新的雙語 summary/compare curated pilot packages，供 `CLI-first` benchmark lane 使用。

它的主要 benchmark 產出固定為：

- `summary_benchmark_score`
- `compare_benchmark_score`

## 內容

- `manifest.json`：suite manifest 與 package 清單
- 五個 curated pilot packages：
  - `qmsum-query-summary-curated-pilot-v1`
  - `multinews-multi-doc-summary-curated-pilot-v1`
  - `cocotrip-compare-curated-pilot-v1`
  - `drcd-query-summary-curated-pilot-v1`
  - `ttnews-multi-doc-summary-curated-pilot-v1`

## 執行方式

```bash
python -m app.scripts.run_summary_compare_benchmark \
  --area-id <AREA_ID> \
  --dataset-dir benchmarks/summary-compare-bilingual-curated-pilot-v1 \
  --actor-sub <USER_SUB> \
  --output-path artifacts/summary-compare-bilingual-curated-pilot-v1.json
```
