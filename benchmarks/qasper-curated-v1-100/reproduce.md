# QASPER 100 重現指南

## 目的

此文件說明如何在目前 repo 內重現 `qasper-curated-v1-100` 的建立流程與 `production_like_v1` reference run。  
重現目標是取得與本 package 相同 contract、相同 profile 的 `100` 題 benchmark 分數，而不是重跑原始 `QASPER` 論文 leaderboard。

## 先備條件

- 已取得此 repo
- Docker Compose stack 可正常啟動
- 本機可連到：
  - `http://localhost/auth`
  - `http://localhost/api`
  - `postgresql://postgres:postgres@localhost:15432/deep_agent_rag`
- `OPENAI_API_KEY` 可用，供 queue-only review 使用

補充：

- 所有 compose 操作都應透過 `./scripts/compose.sh`
- `QASPER 100` 的 `OpenAI` review 屬於 queue-only 補強流程，實際核准數可能會隨 provider 行為有些微波動；重跑時應保留 review log 與 compare artifact

## 本次 reference run 身分

- Area 名稱：`qasper-100`
- Area ID：`204b0f87-bbbd-4549-ae3b-8064e535b453`
- Dataset 名稱：`qasper-curated-v1-100`
- Dataset ID：`e836874e-5183-5f09-8241-eddb155adab1`
- Reference run ID：`6c4636ce-85da-456c-a8b3-059b4650b1ae`

## 步驟 1：啟動服務

在 repo 根目錄：

```bash
./scripts/compose.sh up --build
./scripts/compose.sh exec api python -m app.db.migration_runner
```

## 步驟 2：下載 QASPER 原始資料

```bash
mkdir -p /tmp/qasper-100
cd /tmp/qasper-100

python - <<'PY'
import tarfile
import urllib.request
from pathlib import Path

url = "https://qasper-dataset.s3.us-west-2.amazonaws.com/qasper-train-dev-v0.3.tgz"
archive = Path("qasper-train-dev-v0.3.tgz")
if not archive.exists():
    urllib.request.urlretrieve(url, archive)
with tarfile.open(archive) as tf:
    tf.extract("qasper-train-v0.3.json", path=".")
print(Path("qasper-train-v0.3.json").resolve())
PY
```

## 步驟 3：建立 oversampled workspace

```bash
rm -rf /tmp/qasper-100-workspace

cd /Users/pin/Desktop/workspace/deep-agent-rag-stack

PYTHONPATH=apps/api/src .venv/bin/python -m app.scripts.prepare_external_benchmark prepare-source \
  --dataset qasper \
  --input-path /tmp/qasper-100/qasper-train-v0.3.json \
  --workspace-dir /tmp/qasper-100-workspace \
  --limit-documents 50 \
  --limit-items 400

PYTHONPATH=apps/api/src .venv/bin/python -m app.scripts.prepare_external_benchmark filter-items \
  --workspace-dir /tmp/qasper-100-workspace
```

預期：

- `document_count = 50`
- `prepared_item_count = 196`
- `kept_item_count = 132`

## 步驟 4：建立 area 並上傳文件

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
  -d '{"name":"qasper-100","description":"QASPER 100 benchmark"}' \
  http://localhost/api/areas
```

將回傳中的 `id` 記成 `AREA_ID`。

上傳 markdown papers：

```bash
for f in /tmp/qasper-100-workspace/source_documents/*.md; do
  curl -sS \
    -H "Authorization: Bearer $TOKEN" \
    -F "file=@$f" \
    "http://localhost/api/areas/$AREA_ID/documents"
done
```

由於 QASPER 上傳與 ingest 時間不短，建議上傳完成後重新取一次 token，再開始輪詢：

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

## 步驟 5：對齊 evidence 與 queue-only review

```bash
cd /Users/pin/Desktop/workspace/deep-agent-rag-stack

DATABASE_URL='postgresql://postgres:postgres@localhost:15432/deep_agent_rag' \
PYTHONPATH=apps/api/src .venv/bin/python -m app.scripts.prepare_external_benchmark align-spans \
  --workspace-dir /tmp/qasper-100-workspace \
  --area-id "$AREA_ID"

DATABASE_URL='postgresql://postgres:postgres@localhost:15432/deep_agent_rag' \
PYTHONPATH=apps/api/src .venv/bin/python -m app.scripts.prepare_external_benchmark report \
  --workspace-dir /tmp/qasper-100-workspace
```

本次 reference package 的 deterministic 對齊結果為：

- `filtered_item_count = 132`
- `auto_matched = 122`
- `needs_review = 4`
- `rejected = 6`

只對 `alignment_review_queue` 跑 `OpenAI` review：

```bash
DATABASE_URL='postgresql://postgres:postgres@localhost:15432/deep_agent_rag' \
OPENAI_API_KEY="$OPENAI_API_KEY" \
PYTHONPATH=apps/api/src .venv/bin/python -m app.scripts.review_external_benchmark_with_openai \
  --workspace-dir /tmp/qasper-100-workspace \
  --area-id "$AREA_ID" \
  --model gpt-5-mini \
  --replace \
  --review-source alignment_review_queue
```

本次 reference package 的 queue-only review 結果為：

- `approved_override_count = 2`

若未來重跑結果與此值不同，建議保留以下檔案一起判讀：

- `alignment_review_queue.jsonl`
- `review_overrides.jsonl`
- `openai_review_log.jsonl`

## 步驟 6：建立正式 snapshot

```bash
PYTHONPATH=apps/api/src .venv/bin/python -m app.scripts.prepare_external_benchmark build-snapshot \
  --workspace-dir /tmp/qasper-100-workspace \
  --output-dir /Users/pin/Desktop/workspace/deep-agent-rag-stack/benchmarks/qasper-curated-v1-100 \
  --benchmark-name qasper-curated-v1-100 \
  --target-question-count 100 \
  --reference-evaluation-profile production_like_v1
```

預期：

- `question_count = 100`
- `question_with_gold_span_count = 100`
- `span_count = 164`
- `document_count = 42`

## 步驟 7：匯入 snapshot

```bash
DATABASE_URL='postgresql://postgres:postgres@localhost:15432/deep_agent_rag' \
PYTHONPATH=apps/api/src .venv/bin/python -m app.scripts.import_benchmark_snapshot \
  --snapshot-dir /Users/pin/Desktop/workspace/deep-agent-rag-stack/benchmarks/qasper-curated-v1-100 \
  --area-id "$AREA_ID" \
  --dataset-name qasper-curated-v1-100 \
  --replace
```

預期 dataset id：

```text
e836874e-5183-5f09-8241-eddb155adab1
```

## 步驟 8：執行 reference run

```bash
DATABASE_URL='postgresql://postgres:postgres@localhost:15432/deep_agent_rag' \
PYTHONPATH=apps/api/src .venv/bin/python -m app.scripts.run_retrieval_eval run \
  --dataset-id e836874e-5183-5f09-8241-eddb155adab1 \
  --top-k 10 \
  --evaluation-profile production_like_v1 \
  --actor-sub "$ACTOR_SUB" \
  > /tmp/qasper-100-run.json
```

建議順手取出 candidate run id：

```bash
RUN_ID=$(
  python - <<'PY' /tmp/qasper-100-run.json
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
  --reference-report /Users/pin/Desktop/workspace/deep-agent-rag-stack/benchmarks/qasper-curated-v1-100/reference_run_summary.json \
  --candidate-run-id "$RUN_ID" \
  --actor-sub "$ACTOR_SUB" \
  > /tmp/qasper-100-compare.json
```

建議至少檢查：

- `summary_metric_deltas.assembled.nDCG@k.delta`
- `summary_metric_deltas.assembled.Recall@k.delta`
- `per_query_diff.missing_in_candidate`
- `per_query_diff.matched_core_evidence_mismatch_count`

補充：

- 若 queue-only review 的核准數與 reference 不同，先確認 snapshot 的 `question_count / span_count / approved_override_count` 是否仍符合預期，再判讀 run 指標

## Reference Metrics

| 階段 | nDCG@10 | Recall@10 | MRR@10 | Precision@10 | Doc Coverage@10 |
| --- | ---: | ---: | ---: | ---: | ---: |
| recall | 0.1901 | 0.3600 | 0.1413 | 0.0390 | 0.7300 |
| rerank | 0.3533 | 0.5300 | 0.2983 | 0.0580 | 0.8300 |
| assembled | 0.3797 | 0.5900 | 0.3142 | 0.0640 | 0.8200 |
