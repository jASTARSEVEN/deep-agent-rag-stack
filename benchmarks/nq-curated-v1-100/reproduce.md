# NQ 100 重現指南

## 目的

此文件說明如何在目前 repo 內重現 `nq-curated-v1-100` 的建立流程與 `production_like_v1` reference run。  
重現目標是取得與本 package 相同 contract、相同 profile 的 `100` 題 benchmark 分數，而不是重跑原始 `Natural Questions` leaderboard。

## 先備條件

- 已取得此 repo
- Docker Compose stack 可正常啟動
- 本機可連到：
  - `http://localhost/auth`
  - `http://localhost/api`
  - `postgresql://postgres:postgres@localhost:15432/deep_agent_rag`
- 若 future rerun 的 `alignment_review_queue` 非空，需提供可用的 `OPENAI_API_KEY`

補充：

- 所有 compose 操作都應透過 `./scripts/compose.sh`
- `NQ 100` 文件量大，若只用單一 worker，等待 `ready` 可能非常久；建議先把 worker scale 到 `4`

## 本次 reference run 身分

- Area 名稱：`nq-100`
- Area ID：`9d89e5b3-3a31-43d6-9441-8d1de9dd6e0b`
- Dataset 名稱：`nq-curated-v1-100`
- Dataset ID：`c1fef25a-7f8a-59d0-8974-f44ace477600`
- Reference run ID：`3e07bb70-7068-483c-81d0-35ad43092dfb`

## 步驟 1：啟動服務

在 repo 根目錄：

```bash
./scripts/compose.sh up --build
./scripts/compose.sh exec api python -m app.db.migration_runner
./scripts/compose.sh up -d --scale worker=4 worker
```

## 步驟 2：建立 oversampled workspace

`Natural Questions` 這條流程不需要手動先下載 parquet；直接透過 `prepare_external_benchmark` 內建的 `hf://` 參照向 Hugging Face dataset-server 取 row。

```bash
rm -rf /tmp/nq-100-workspace

cd /Users/pin/Desktop/workspace/deep-agent-rag-stack

PYTHONPATH=apps/api/src .venv/bin/python -m app.scripts.prepare_external_benchmark prepare-source \
  --dataset nq \
  --input-path hf://google-research-datasets/natural_questions/default/validation \
  --workspace-dir /tmp/nq-100-workspace \
  --limit-items 260

PYTHONPATH=apps/api/src .venv/bin/python -m app.scripts.prepare_external_benchmark filter-items \
  --workspace-dir /tmp/nq-100-workspace
```

預期：

- `prepared_item_count = 260`
- `kept_item_count = 250`
- drop reason 主要來自 `evidence_too_long` 與 `layout_dependent`

## 步驟 3：建立 area 並上傳文件

先取得 `carol` token：

```bash
TOKEN=$(
  curl -sS -X POST "http://localhost/auth/realms/deep-agent-dev/protocol/openid-connect/token" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "client_id=deep-agent-web" \
    -d "grant_type=password" \
    -d "username=carol" \
    -d "password=carol123" \
  | python -c 'import sys, json; print(json.load(sys.stdin)["access_token"])'
)
```

再取得本次建立 area / run benchmark 所使用的 `actor-sub`：

```bash
ACTOR_SUB=$(
  curl -sS \
    -H "Authorization: Bearer $TOKEN" \
    http://localhost/api/auth/context \
  | python -c 'import sys, json; print(json.load(sys.stdin)["sub"])'
)
```

建立 area：

```bash
curl -sS \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"nq-100","description":"Natural Questions 100 benchmark"}' \
  http://localhost/api/areas
```

將回傳中的 `id` 記成 `AREA_ID`。

上傳 markdown documents：

```bash
for f in /tmp/nq-100-workspace/source_documents/*.md; do
  curl -sS \
    -H "Authorization: Bearer $TOKEN" \
    -F "file=@$f" \
    "http://localhost/api/areas/$AREA_ID/documents"
done
```

由於此流程很長，建議上傳完成後重新取一次 token，再開始輪詢：

```bash
TOKEN=$(
  curl -sS -X POST "http://localhost/auth/realms/deep-agent-dev/protocol/openid-connect/token" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "client_id=deep-agent-web" \
    -d "grant_type=password" \
    -d "username=carol" \
    -d "password=carol123" \
  | python -c 'import sys, json; print(json.load(sys.stdin)["access_token"])'
)
```

等到所有文件都進入 `ready`。建議用下列方式查看整體狀態：

```bash
curl -sS \
  -H "Authorization: Bearer $TOKEN" \
  "http://localhost/api/areas/$AREA_ID/documents" \
| python -c 'import sys, json; from collections import Counter; payload=json.load(sys.stdin); print(Counter(item["status"] for item in payload["items"]))'
```

## 步驟 4：對齊 evidence

```bash
cd /Users/pin/Desktop/workspace/deep-agent-rag-stack

DATABASE_URL='postgresql://postgres:postgres@localhost:15432/deep_agent_rag' \
PYTHONPATH=apps/api/src .venv/bin/python -m app.scripts.prepare_external_benchmark align-spans \
  --workspace-dir /tmp/nq-100-workspace \
  --area-id "$AREA_ID"

DATABASE_URL='postgresql://postgres:postgres@localhost:15432/deep_agent_rag' \
PYTHONPATH=apps/api/src .venv/bin/python -m app.scripts.prepare_external_benchmark report \
  --workspace-dir /tmp/nq-100-workspace
```

本次 reference package 的 deterministic 對齊結果為：

- `filtered_item_count = 250`
- `auto_matched = 250`
- `needs_review = 0`
- `rejected = 0`

## 步驟 5：只有 queue 非空時才跑 `OpenAI` review

這次 reference package 不需要這一步，因為 `needs_review = 0`。  
若未來 rerun 產生非空 `alignment_review_queue`，則只對 queue 跑 `OpenAI` review：

```bash
DATABASE_URL='postgresql://postgres:postgres@localhost:15432/deep_agent_rag' \
OPENAI_API_KEY="$OPENAI_API_KEY" \
PYTHONPATH=apps/api/src .venv/bin/python -m app.scripts.review_external_benchmark_with_openai \
  --workspace-dir /tmp/nq-100-workspace \
  --area-id "$AREA_ID" \
  --model gpt-5.4-mini \
  --replace \
  --review-source alignment_review_queue
```

## 步驟 6：建立正式 snapshot

```bash
PYTHONPATH=apps/api/src .venv/bin/python -m app.scripts.prepare_external_benchmark build-snapshot \
  --workspace-dir /tmp/nq-100-workspace \
  --output-dir /Users/pin/Desktop/workspace/deep-agent-rag-stack/benchmarks/nq-curated-v1-100 \
  --benchmark-name nq-curated-v1-100 \
  --target-question-count 100 \
  --reference-evaluation-profile production_like_v1
```

預期：

- `question_count = 100`
- `question_with_gold_span_count = 100`
- `span_count = 100`
- `document_count = 100`

## 步驟 7：匯入 snapshot

```bash
DATABASE_URL='postgresql://postgres:postgres@localhost:15432/deep_agent_rag' \
PYTHONPATH=apps/api/src .venv/bin/python -m app.scripts.import_benchmark_snapshot \
  --snapshot-dir /Users/pin/Desktop/workspace/deep-agent-rag-stack/benchmarks/nq-curated-v1-100 \
  --area-id "$AREA_ID" \
  --dataset-name nq-curated-v1-100 \
  --replace
```

預期 dataset id：

```text
c1fef25a-7f8a-59d0-8974-f44ace477600
```

## 步驟 8：執行 reference run

```bash
DATABASE_URL='postgresql://postgres:postgres@localhost:15432/deep_agent_rag' \
PYTHONPATH=apps/api/src .venv/bin/python -m app.scripts.run_retrieval_eval run \
  --dataset-id c1fef25a-7f8a-59d0-8974-f44ace477600 \
  --top-k 10 \
  --evaluation-profile production_like_v1 \
  --actor-sub "$ACTOR_SUB" \
  > /tmp/nq-100-run.json
```

建議順手取出 candidate run id：

```bash
RUN_ID=$(
  python - <<'PY' /tmp/nq-100-run.json
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print(payload["run"]["id"])
PY
)
```

## 步驟 9：比對 reference run 與本次 rerun

```bash
DATABASE_URL='postgresql://postgres:postgres@localhost:15432/deep_agent_rag' \
PYTHONPATH=apps/api/src .venv/bin/python -m app.scripts.compare_benchmark_runs \
  --reference-report /Users/pin/Desktop/workspace/deep-agent-rag-stack/benchmarks/nq-curated-v1-100/reference_run_summary.json \
  --candidate-run-id "$RUN_ID" \
  --actor-sub "$ACTOR_SUB" \
  > /tmp/nq-100-compare.json
```

建議至少檢查：

- `summary_metric_deltas.assembled.nDCG@k.delta`
- `summary_metric_deltas.assembled.Recall@k.delta`
- `per_query_diff.missing_in_candidate`
- `per_query_diff.matched_core_evidence_mismatch_count`

補充：

- 若 `run_retrieval_eval` 在剛匯入完 snapshot 後遇到暫時性資料庫錯誤，先確認 area 內所有文件都已穩定 `ready`，再重跑一次 benchmark
- 若仍有外部 provider timeout，可先保留已完成的 `prepare / align / snapshot / import` artifact，再獨立重跑 benchmark 與 compare

## Reference Metrics

| 階段 | nDCG@10 | Recall@10 | MRR@10 | Precision@10 | Doc Coverage@10 |
| --- | ---: | ---: | ---: | ---: | ---: |
| recall | 0.5019 | 0.8100 | 0.4166 | 0.1110 | 0.9700 |
| rerank | 0.9569 | 0.9700 | 0.9525 | 0.0970 | 1.0000 |
| assembled | 0.7443 | 0.7500 | 0.7425 | 0.0750 | 1.0000 |
