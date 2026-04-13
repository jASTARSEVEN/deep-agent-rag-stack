# Summary / Compare Benchmark 補跑操作準則

## 文件目的

此文件用來固定 `summary/compare` 線的補跑方式、artifact 角色與引用規則，避免後續將 tuning suite、product gate 與臨時 aggregate 輸出混為同一套 baseline。

## 角色區分

### `summary-compare-real-curated-v1`

- 定位：`tuning / observability suite`
- 用途：作為 summary/compare prompt 或 runtime 調整時的 `before / after` 比較基準
- baseline 規則：目前一律採用 package-level consolidated baseline
- 正式採信 artifact：`artifacts/qmsum-query-summary-curated-pilot-v1-run.json`、`artifacts/multinews-multi-doc-summary-curated-pilot-v1-run.json`、`artifacts/lcsts-news-summary-curated-pilot-v1-run.json`、`artifacts/cnewsum-news-summary-curated-pilot-v1-run.json`、`artifacts/cocotrip-compare-curated-pilot-v1-run.json`、`artifacts/cocotrip-rerun-subset.json`
- 注意：新產生的 aggregate suite artifact 若未被文件明確升格，不得直接覆蓋 current baseline

### `phase8a-summary-compare-v1`

- 定位：唯一 `product gate`
- 用途：檢查 unified `Deep Agents` answer path 是否仍符合正式 checkpoint contract
- baseline 規則：在未補跑前，不宣稱 repo 已固定一份可追溯的 numeric checkpoint baseline
- 注意：它是 gate dataset，不是目前 tuning suite 的 current score 來源

## 何時需要補跑

只有在以下情況才建議補跑：

1. 準備開始新一輪 summary/compare prompt 或 runtime 調整
2. 需要重新驗證 `phase8a-summary-compare-v1` 是否仍符合 product gate
3. 需要確認真實部署路徑或 judge model 變動是否影響 summary/compare 輸出

若只是定稿 baseline 文件、同步 README 或更新分析敘事，則不應為了「看最新數字」而重跑。

## 執行前提

1. 從 repo root 執行指令。
2. 使用與 API runtime 相同的資料庫與設定來源。
3. 目標 area 內的 benchmark 文件都必須已進入 `ready`。
4. 執行者 `actor_sub` 必須對該 area 具備足夠權限。
5. 若有 judge model 覆寫需求，需明確記錄本次使用的 `--judge-model`。

## judge 執行模式

### `openai`

- 適用情境：已有 `OPENAI_API_KEY`，希望 runner 一次跑完 runtime 與 judge。
- 特性：CLI 直接產出正式 JSON / Markdown report，不需中繼 packet。

### `offline-export` + `offline-import`

- 適用情境：不想使用 `OPENAI_API_KEY`，改以 `Codex / ChatGPT Pro` 或人工方式完成 judge。
- 特性：先執行 runtime 並匯出 `judge packets`，之後再把回填的 `decision JSONL` 匯入產生正式 report。
- 契約：離線模式只能替換 judge 執行方式，不得更動題目、runtime answer、citations、baseline compare 與 product gate 判讀規則。

## 補跑順序

### 1. 先跑 tuning suite

先跑 `summary-compare-real-curated-v1`，取得新的 suite report，拿來和目前 canonical suite baseline 比較。

```bash
python -m app.scripts.run_summary_compare_benchmark \
  --area-id <AREA_ID> \
  --dataset-dir benchmarks/summary-compare-real-curated-v1 \
  --actor-sub <USER_SUB> \
  --judge-model <JUDGE_MODEL> \
  --output-path artifacts/summary-compare-real-curated-v1-rerun.json
```

參數說明：

- `--area-id`：已匯入 suite 文件的 target area
- `--dataset-dir`：固定使用 `benchmarks/summary-compare-real-curated-v1`
- `--actor-sub`：執行 benchmark 的使用者 `sub`
- `--judge-model`：選填；若不填則走系統預設 judge model
- `--output-path`：JSON report 輸出位置；CLI 也會同時寫出 markdown summary

### 2. 再跑 product gate checkpoint

若前一步是為了評估下一輪 runtime 調整是否值得進行，再補跑 `phase8a-summary-compare-v1`。

```bash
python -m app.scripts.run_summary_compare_checkpoint \
  --area-id <AREA_ID> \
  --dataset-dir benchmarks/phase8a-summary-compare-v1 \
  --actor-sub <USER_SUB> \
  --judge-model <JUDGE_MODEL> \
  --thinking-mode true \
  --output-path artifacts/phase8a-summary-compare-v1-rerun.json
```

補充說明：

- `--thinking-mode` 目前是相容性參數；正式 answer path 仍以 unified `Deep Agents` runtime 為準，不應把它當成新的 answer lane 開關
- checkpoint report 重點是 `passed`、`aggregate_metrics`、`gate_results`、`hard_blocker_failures`

## 離線 judge 操作

### 1. 匯出 judge packets

若要改由 `Codex / ChatGPT Pro` 或人工完成 judge，先跑 `offline-export`：

```bash
python -m app.scripts.run_summary_compare_benchmark \
  --area-id <AREA_ID> \
  --dataset-dir benchmarks/summary-compare-real-curated-v1 \
  --actor-sub <USER_SUB> \
  --judge-mode offline-export \
  --judge-model offline-codex \
  --judge-packets-path artifacts/summary-compare-real-curated-v1-judge-packets.jsonl \
  --output-path artifacts/unused-benchmark-report.json
```

```bash
python -m app.scripts.run_summary_compare_checkpoint \
  --area-id <AREA_ID> \
  --dataset-dir benchmarks/phase8a-summary-compare-v1 \
  --actor-sub <USER_SUB> \
  --judge-mode offline-export \
  --judge-model offline-codex \
  --judge-packets-path artifacts/phase8a-summary-compare-v1-judge-packets.jsonl \
  --output-path artifacts/unused-checkpoint-report.json
```

補充說明：

- `--output-path` 在 `offline-export` 模式下不會產生正式 report；CLI 只會輸出 packet 路徑與基本摘要
- `--judge-model` 在離線模式中是顯示標籤，不代表真的呼叫 API 模型
- packet JSONL 會保存 `system_prompt`、`user_prompt` 與 report 重建所需的 item context

### 2. 回填離線 decision JSONL

每一行 decision JSONL 至少要包含：

```json
{
  "packet_id": "compare-pkg:compare-1:pairwise",
  "model": "codex-pro",
  "result": {
    "verdict": "candidate",
    "rationale": "Candidate is stronger."
  }
}
```

checkpoint / rubric packet 的 `result` 需包含：

```json
{
  "scores": {
    "completeness": 4.5,
    "faithfulness_to_citations": 4.7,
    "structure_quality": 4.3,
    "compare_coverage": 4.2
  },
  "coverage_dimension_name": "section_focus_accuracy",
  "rationale": "Looks grounded.",
  "missing_points": []
}
```

### 3. 匯入離線結果並產生正式 report

```bash
python -m app.scripts.run_summary_compare_benchmark \
  --area-id <AREA_ID> \
  --dataset-dir benchmarks/summary-compare-real-curated-v1 \
  --actor-sub <USER_SUB> \
  --judge-mode offline-import \
  --judge-model offline-codex \
  --judge-packets-path artifacts/summary-compare-real-curated-v1-judge-packets.jsonl \
  --judge-results-path artifacts/summary-compare-real-curated-v1-judge-decisions.jsonl \
  --output-path artifacts/summary-compare-real-curated-v1-offline-report.json
```

```bash
python -m app.scripts.run_summary_compare_checkpoint \
  --area-id <AREA_ID> \
  --dataset-dir benchmarks/phase8a-summary-compare-v1 \
  --actor-sub <USER_SUB> \
  --judge-mode offline-import \
  --judge-model offline-codex \
  --judge-packets-path artifacts/phase8a-summary-compare-v1-judge-packets.jsonl \
  --judge-results-path artifacts/phase8a-summary-compare-v1-judge-decisions.jsonl \
  --output-path artifacts/phase8a-summary-compare-v1-offline-report.json
```

## 補跑後如何解讀 artifact

### suite rerun

優先比較：

- `summary_benchmark_score`
- `compare_benchmark_score`
- `per_dataset_scores`
- `task_family_scores`
- `baseline_compare`

判讀原則：

- 若只是新產生單一 aggregate suite artifact，預設仍是觀測輸出，不自動升格為 canonical baseline
- 若要升格，必須同步更新 `PROJECT_STATUS.md`、`ROADMAP.md`、README 與 benchmark 分析文件

### checkpoint rerun

優先比較：

- `passed`
- `gate_results`
- `hard_blocker_failures`
- `recommendations`
- `aggregate_metrics`

判讀原則：

- checkpoint 用來判斷正式 answer path 是否守住 contract，不取代 suite baseline
- 即使 checkpoint rerun 分數變動，也不代表 suite baseline 自動更新

## `Phase 8C` 啟動前必答問題

完成 suite 與 checkpoint rerun 後，至少要回答：

1. 缺口是否真的集中在 agentic evidence-seeking 可解的 coverage / faithfulness 問題？
2. 問題是否其實主要來自 compare answer quality、中文 summary 壓縮率或 judge / dataset contract？
3. latency 與 token 成本是否已讓多一步 loop 不划算？

只有在答案仍支持 loop 具備明確 ROI 時，才進入 `Phase 8C` 設計。

## 不可違反的規則

- 不得把 `summary-compare-real-curated-v1` 與 `phase8a-summary-compare-v1` 混成同一套 baseline
- 不得把未明確升格的 aggregate artifact 直接當作新的 canonical baseline
- 不得重新引入已移除的 enrichment schema、query-time merge lane 或查詢改寫 lane
- 即使未來啟動 `Phase 8C`，synopsis 也只能作為 planning hint，不得作為 citation 或最終回答證據
