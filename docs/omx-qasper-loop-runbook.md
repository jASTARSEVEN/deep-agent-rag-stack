# OMX QASPER 受控五-Agent 循環 Runbook

## 目的

此文件定義本 repo 內執行 QASPER benchmark-driven optimization 的正式受控 lane。  
本 lane 的目標不是讓 agent 無限制連續調參，而是把每一輪固定收斂為：

1. `effect-check`
2. `effect-opt`
3. `advice-agent`
4. `guard-agent`
5. `implement-agent`
6. 回到 `effect-check`

並且強制滿足下列條件：

- 每輪只允許一個主假設
- `guard-agent` 必須在 `implement-agent` 前明確做出 `go / stop / rollback`
- 不可修改 production runtime defaults
- 不可修改 chunking、query normalization、rerank 結構
- 不可修改 benchmark gold spans 或 alignment artifacts
- 成功標準改為 weighted multi-benchmark objective：
  - 自家 benchmark `tw-insurance-rag-benchmark-v1` 權重 `0.6`
  - `QASPER` 權重 `0.4`
  - 以 weighted assembled 指標作為主決策基準

## 主假設選擇規則

`effect-check` 會先跑 baseline；目前正式自動化 lane 僅批准以下主假設：

1. `fact_lookup_evidence_retention`
   - 條件：`assembled Recall@10 < 0.8`
   - assembler lane：`qasper_guarded_assembler_v1 -> qasper_guarded_assembler_v2`
   - evidence synopsis lane：`qasper_guarded_evidence_synopsis_v1 -> qasper_guarded_evidence_synopsis_v2`

若 weighted baseline `Recall@10 >= 0.8`，則直接 `stop`。

## 允許與禁止範圍

允許的受控實驗面：

- `rerank_top_n`
- `assembler_max_contexts`
- `assembler_max_chars_per_context`
- `assembler_max_children_per_parent`
- `retrieval_evidence_synopsis_enabled`

禁止混入：

- chunking 調整
- query normalization
- production default 的 rerank text / rerank structure 改寫
- benchmark snapshot / gold span / alignment artifact 修改
- production default 變更

## 自動執行入口

本 repo 已提供 CLI：

```bash
cd /Users/pin/Desktop/workspace/deep-agent-rag-stack

DATABASE_URL='postgresql://postgres:postgres@localhost:15432/deep_agent_rag' \
PYTHONPATH=apps/api/src python -m app.scripts.run_qasper_omx_loop \
  --qasper-actor-sub <principal-sub> \
  --self-actor-sub <principal-sub> \
  --output-dir /Users/pin/Desktop/workspace/deep-agent-rag-stack/.omx/runs/qasper-loop/latest
```

此 CLI 會自動：

1. 載入 QASPER reference run 與自家 benchmark reference report
2. 產出 `effect-check`
3. 依唯一主假設建立 `effect-opt`
4. 產出 `advice-agent`
5. 先由 `guard-agent` 決定是否可進入 candidate run
6. 先跑 `deterministic-gate`；會同時執行 `QASPER + self benchmark` 的 gate run，並以 weighted `Recall@10` 判斷；若 weighted `Recall@10 <= 0.8`，直接跳過 live rerank
7. 只有 `deterministic-gate=pass` 才執行 live rerank candidate benchmark 作為 `implement-agent`
8. 比較 candidate 與 baseline
9. 由 `implement-agent` 產出 `continue / stop / rollback` 決策
10. 若 `rollback`，先產生 `rollback-rethink` artifact，切到替代主假設 lane 再開新一輪
11. 若 weighted `Recall@10 < 0.8` 且 weighted guardrails 未破壞，進入同 lane 的下一個受控 profile

目前保留的替代 lane 順序為：

```text
assembler -> evidence-synopsis
```

預設 artifact 會寫到：

```text
.omx/runs/qasper-omx-loop/<run-id>/
```

## 主要 artifact

每次 loop 至少會輸出：

- `baseline-qasper-run-report.json`
- `baseline-self-run-report.json`
- `effect-check.json`
- `iteration-01/effect-opt.json`
- `iteration-01/advice-agent.json`
- `iteration-01/guard-agent.json`
- `iteration-01/deterministic-gate.json`
- `iteration-01/candidate-qasper-run-report.json`
- `iteration-01/candidate-self-run-report.json`
- `iteration-01/qasper-compare-report.json`
- `iteration-01/self-compare-report.json`
- `iteration-01/implement-agent.json`
- `iteration-01/rollback-rethink.json`（僅在 rollback 且仍有替代策略時）
- `final-summary.json`

## Continue / Stop / Rollback Gate

### Continue

- weighted `assembled Recall@10` 有提升
- weighted `assembled nDCG@10 / MRR@10 / Precision@10 / Doc Coverage@10` 不退化
- weighted `assembled Recall@10` 仍低於 `0.8`
- 尚有下一個受控 profile 可用

### Stop

- weighted baseline 已達 `Recall@10 >= 0.8`
- 或 weighted candidate 已達 `Recall@10 >= 0.8`
- 或已用盡既定 profile ladder

### Rollback

- weighted `assembled Recall@10` 未提升
- 或 weighted `assembled nDCG@10 / MRR@10 / Precision@10 / Doc Coverage@10` 任一退化
- profile 覆寫超出 guardrail
- profile 覆寫包含未批准 knobs

補充：
- `rollback` 不再代表整個 autopilot 立即結束。
- 若仍存在未嘗試的替代主假設 lane，系統會自動重想策略並進入下一輪。

## 與產品邊界的關係

- 此 loop 只作用於 evaluation profile，不可污染 production defaults。
- 所有 benchmark rerun 都必須沿用正式 pipeline：
  `SQL gate -> vector recall -> FTS recall -> RRF -> rerank -> assembler`
- `QASPER` 仍只是外部壓力測試；但目前 loop 會用 `self=0.6 / qasper=0.4` 的 weighted objective 同時評估兩者。
