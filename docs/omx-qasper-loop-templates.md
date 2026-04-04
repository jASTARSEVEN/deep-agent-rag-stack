# OMX QASPER 受控五-Agent 模板

## 用途

此文件提供 effect-check / effect-opt / advice-agent / guard-agent / implement-agent 的固定輸出模板。  
若使用 `python -m app.scripts.run_qasper_omx_loop`，CLI 會自動產出同等結構的 JSON artifact；  
若人工審查或手動補跑，也應遵守相同欄位語意。

## Iteration Header

```text
Iteration: <iteration-id>
唯一主假設：rerank hit but assembled drop | evidence synopsis for fact windows
baseline profile：production_like_v1
candidate profile：qasper_guarded_assembler_v1 | qasper_guarded_assembler_v2 | qasper_guarded_evidence_synopsis_v1 | qasper_guarded_evidence_synopsis_v2
target metric：assembled Recall@10
target threshold：0.80
```

## effect-check

```text
角色：effect-check
責任：
1. 建立 QASPER baseline
2. 建立自家 benchmark baseline
3. 判定目前唯一主假設

必填輸出：
- baseline profile
- baseline metrics（QASPER / self）
- main hypothesis
- candidate profile ladder
- pass / fail / rollback rubric
```

## effect-opt

```text
角色：effect-opt
責任：
1. 只針對唯一主假設提出最小 proposal
2. 只允許 benchmark/profile-gated 變更

必填輸出：
- iteration
- main hypothesis
- profile name
- profile overrides
- expected improvement
- explicit non-goals
```

## advice-agent

```text
角色：advice-agent
責任：
1. 審查 effect-check 與 effect-opt
2. 強化 guardrails

必填輸出：
- support points
- risk points
- guardrails
```

## guard-agent

```text
角色：guard-agent
責任：
1. 驗證 candidate profile 是否仍在批准範圍
2. 明確做出 go / stop / rollback

必填輸出：
- decision
- reason
- approved
- allowed scope
- guardrails
```

## deterministic-gate

```text
角色：deterministic-gate
責任：
1. 先用 deterministic provider 跑 gate
2. 只有 Recall@10 達標才放行 live rerank

必填輸出：
- gate profile name
- gate run id
- gate metrics
- decision（pass / continue / rollback）
- reason
```

## implement-agent

```text
角色：implement-agent
責任：
1. 僅在 guard=go 後執行
2. 跑 candidate benchmark
3. 比較 candidate 與 baseline
4. 給出 continue / stop / rollback

必填輸出：
- candidate run ids（QASPER / self）
- candidate metrics（QASPER / self）
- delta summary（QASPER / self）
- guardrails passed（QASPER / self）
- decision
- reason
```

## rollback-rethink

```text
角色：effect-check（rollback rethink）
責任：
1. 在上一輪 rollback 後重新選擇單一主假設
2. 切到替代 lane

必填輸出：
- previous hypothesis
- next hypothesis
- remaining candidate profiles
- rethink reason
```

## Final Summary

```text
generated_at:
artifact_dir:
role_sequence:
main_hypothesis:
candidate_profiles:
final_decision:
final_reason:
best_result:
```
