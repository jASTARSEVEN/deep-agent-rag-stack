# DRCD 100 重現指南

## 目的

此文件說明如何在目前 repo 內重現 `drcd-curated-v1-100` 的建立流程與 `production_like_v1` reference run。  
重現目標是取得與本 package 相同 contract、相同 profile 的 `100` 題 benchmark 分數，而不是重跑原始 `DRCD` leaderboard。

## 先備條件

- 已取得此 repo
- Docker Compose stack 可正常啟動
- 本機可連到：
  - `http://localhost/auth`
  - `http://localhost/api`
  - `postgresql://postgres:postgres@localhost:15432/deep_agent_rag`
- `OPENAI_API_KEY` 可用，供 queue-only `OpenAI` review；本次 reference package 雖然 queue 為空，仍保留同一條驗證步驟

補充：

- 所有 compose 操作都應透過 `./scripts/compose.sh`，不要直接呼叫裸 `docker compose`
- 若要做真正的回歸判讀，除了重跑 reference run 外，還應再跑 `compare_benchmark_runs`

## 本次 reference run 身分

- Area 名稱：`drcd-100`
- Area ID：`eb3d79be-220a-4658-9ecd-76ccaaf334f8`
- Dataset 名稱：`drcd-curated-v1-100`
- Dataset ID：`e82455ac-45fc-501e-a13d-333552c4a2ab`
- Reference run ID：`400921aa-3882-4504-8f3c-accf9054930e`

## 步驟 1：啟動服務

在 repo 根目錄：

```bash
./scripts/compose.sh up --build
./scripts/compose.sh exec api python -m app.db.migration_runner
```

## 步驟 2：建立 oversampled workspace

`DRCD` 這條流程不需要手動先下載 JSON；直接透過 `prepare_external_benchmark` 內建的 `hf://` 參照向 Hugging Face dataset-server 取 row。

```bash
rm -rf /tmp/drcd-100-workspace

cd /Users/pin/Desktop/workspace/deep-agent-rag-stack

PYTHONPATH=apps/api/src .venv/bin/python -m app.scripts.prepare_external_benchmark prepare-source \
  --dataset drcd \
  --input-path hf://voidful/DRCD/default/dev \
  --workspace-dir /tmp/drcd-100-workspace \
  --limit-documents 80 \
  --limit-items 400

PYTHONPATH=apps/api/src .venv/bin/python -m app.scripts.prepare_external_benchmark filter-items \
  --workspace-dir /tmp/drcd-100-workspace
```

預期：

- `document_count = 29`
- `prepared_item_count = 400`
- `kept_item_count = 400`

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
  -d '{"name":"drcd-100","description":"DRCD 100 benchmark"}' \
  http://localhost/api/areas
```

將回傳中的 `id` 記成 `AREA_ID`。

上傳 markdown 文件：

```bash
find /tmp/drcd-100-workspace/source_documents -type f -name "*.md" | sort | while read -r f; do
  curl -sS \
    -H "Authorization: Bearer $TOKEN" \
    -F "file=@$f" \
    "http://localhost/api/areas/$AREA_ID/documents"
done
```

若流程很久，建議在輪詢前重新取得一次 token，避免 `401 Unauthorized`：

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

等到所有文件都進入 `ready`。可用下列方式檢查：

```bash
curl -sS \
  -H "Authorization: Bearer $TOKEN" \
  "http://localhost/api/areas/$AREA_ID/documents" \
| python -c 'import sys, json; from collections import Counter; payload=json.load(sys.stdin); print(Counter(item["status"] for item in payload["items"]))'
```

## 步驟 4：對齊 evidence 與輸出報表

```bash
cd /Users/pin/Desktop/workspace/deep-agent-rag-stack

DATABASE_URL='postgresql://postgres:postgres@localhost:15432/deep_agent_rag' \
PYTHONPATH=apps/api/src .venv/bin/python -m app.scripts.prepare_external_benchmark align-spans \
  --workspace-dir /tmp/drcd-100-workspace \
  --area-id "$AREA_ID"

PYTHONPATH=apps/api/src .venv/bin/python -m app.scripts.prepare_external_benchmark report \
  --workspace-dir /tmp/drcd-100-workspace
```

本次 reference package 的 deterministic 對齊結果為：

- `filtered_item_count = 400`
- `auto_matched = 400`
- `needs_review = 0`
- `rejected = 0`

## 步驟 5：執行 queue-only `OpenAI` review

雖然這次 `alignment_review_queue` 為空，仍建議跑同一條 review 指令，確認 package 的 reproducible flow 維持一致。

```bash
DATABASE_URL='postgresql://postgres:postgres@localhost:15432/deep_agent_rag' \
OPENAI_API_KEY="$OPENAI_API_KEY" \
PYTHONPATH=apps/api/src .venv/bin/python -m app.scripts.review_external_benchmark_with_openai \
  --workspace-dir /tmp/drcd-100-workspace \
  --area-id "$AREA_ID" \
  --model gpt-5.4-mini \
  --replace \
  --review-source alignment_review_queue
```

本次 reference package 的 review 結果為：

- `review_item_count = 0`
- `approved_override_count = 0`

## 步驟 6：建立正式 snapshot

```bash
PYTHONPATH=apps/api/src .venv/bin/python -m app.scripts.prepare_external_benchmark build-snapshot \
  --workspace-dir /tmp/drcd-100-workspace \
  --output-dir /Users/pin/Desktop/workspace/deep-agent-rag-stack/benchmarks/drcd-curated-v1-100 \
  --benchmark-name drcd-curated-v1-100 \
  --target-question-count 100 \
  --reference-evaluation-profile production_like_v1
```

預期：

- `question_count = 100`
- `question_with_gold_span_count = 100`
- `span_count = 100`
- `document_count = 6`

## 步驟 7：匯入 snapshot

```bash
DATABASE_URL='postgresql://postgres:postgres@localhost:15432/deep_agent_rag' \
PYTHONPATH=apps/api/src .venv/bin/python -m app.scripts.import_benchmark_snapshot \
  --snapshot-dir /Users/pin/Desktop/workspace/deep-agent-rag-stack/benchmarks/drcd-curated-v1-100 \
  --area-id "$AREA_ID" \
  --dataset-name drcd-curated-v1-100 \
  --replace
```

預期 dataset id：

```text
e82455ac-45fc-501e-a13d-333552c4a2ab
```

## 步驟 8：執行 reference run

```bash
DATABASE_URL='postgresql://postgres:postgres@localhost:15432/deep_agent_rag' \
PYTHONPATH=apps/api/src .venv/bin/python -m app.scripts.run_retrieval_eval run \
  --dataset-id e82455ac-45fc-501e-a13d-333552c4a2ab \
  --top-k 10 \
  --evaluation-profile production_like_v1 \
  --actor-sub "$ACTOR_SUB" \
  > /tmp/drcd-100-run.json
```

建議順手取出 candidate run id：

```bash
RUN_ID=$(
  python - <<'PY' /tmp/drcd-100-run.json
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
  --reference-report /Users/pin/Desktop/workspace/deep-agent-rag-stack/benchmarks/drcd-curated-v1-100/reference_run_summary.json \
  --candidate-run-id "$RUN_ID" \
  --actor-sub "$ACTOR_SUB" \
  > /tmp/drcd-100-compare.json
```

建議至少檢查：

- `summary_metric_deltas.assembled.nDCG@k.delta`
- `summary_metric_deltas.assembled.Recall@k.delta`
- `per_query_diff.missing_in_candidate`
- `per_query_diff.matched_core_evidence_mismatch_count`

## Reference Metrics

| 階段 | nDCG@10 | Recall@10 | MRR@10 | Precision@10 | Doc Coverage@10 |
| --- | ---: | ---: | ---: | ---: | ---: |
| recall | 0.9543 | 0.9900 | 0.9420 | 0.0990 | 1.0000 |
| rerank | 0.8650 | 0.9700 | 0.8308 | 0.0970 | 1.0000 |
| assembled | 0.8650 | 0.9700 | 0.8308 | 0.0970 | 1.0000 |
