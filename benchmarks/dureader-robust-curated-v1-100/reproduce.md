# DuReader-robust 100 重現指南

## 目的

此文件說明如何在目前 repo 內重現 `dureader-robust-curated-v1-100` 的建立流程與 `production_like_v1` reference run。  
重現目標是取得與本 package 相同 contract、相同 profile 的 `100` 題 benchmark 分數，而不是重跑原始 `DuReader-robust` leaderboard。

## 先備條件

- 已取得此 repo
- Docker Compose stack 可正常啟動
- 本機可連到：
  - `http://localhost/auth`
  - `http://localhost/api`
  - `postgresql://postgres:postgres@localhost:15432/deep_agent_rag`
- 若 future rerun 的 `alignment_review_queue` 非空，需提供可用的 `OPENAI_API_KEY`

## 本次 reference run 身分

- Area 名稱：`dureader-robust-100`
- Area ID：`d9cd72a9-5684-47cc-ae17-088606160377`
- Dataset 名稱：`dureader-robust-curated-v1-100`
- Dataset ID：`f4a91b45-64fa-5cd7-b815-9a454888bf9c`
- Reference run ID：`6befc441-39ba-4580-9d9c-f5d795158f1b`

## 步驟 1：啟動服務

在 repo 根目錄：

```bash
./scripts/compose.sh up --build
./scripts/compose.sh exec api python -m app.db.migration_runner
```

## 步驟 2：下載官方資料並建立 oversampled workspace

```bash
rm -rf /tmp/dureader-robust-download /tmp/dureader-robust-100-workspace
mkdir -p /tmp/dureader-robust-download

cd /tmp/dureader-robust-download
curl -L --fail -o dureader_robust-data.tar.gz \
  https://bj.bcebos.com/paddlenlp/datasets/dureader_robust-data.tar.gz
tar -xzf dureader_robust-data.tar.gz dureader_robust-data/dev.json

cd /Users/pin/Desktop/workspace/deep-agent-rag-stack

PYTHONPATH=apps/api/src .venv/bin/python -m app.scripts.prepare_external_benchmark prepare-source \
  --dataset dureader \
  --input-path /tmp/dureader-robust-download/dureader_robust-data/dev.json \
  --workspace-dir /tmp/dureader-robust-100-workspace \
  --limit-documents 220 \
  --limit-items 220

PYTHONPATH=apps/api/src .venv/bin/python -m app.scripts.prepare_external_benchmark filter-items \
  --workspace-dir /tmp/dureader-robust-100-workspace
```

預期：

- `prepared_item_count = 220`
- `kept_item_count = 220`
- drop reason 為空，全部 `kept`

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

建立 area：

```bash
curl -sS \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"dureader-robust-100","description":"DuReader-robust 100 benchmark"}' \
  http://localhost/api/areas
```

將回傳中的 `id` 記成 `AREA_ID`。

上傳 markdown paragraph documents：

```bash
find /tmp/dureader-robust-100-workspace/source_documents -type f -name "*.md" | sort | while read -r f; do
  curl -sS \
    -H "Authorization: Bearer $TOKEN" \
    -F "file=@$f" \
    "http://localhost/api/areas/$AREA_ID/documents"
done
```

等到所有文件都進入 `ready`。

## 步驟 4：對齊 evidence

```bash
cd /Users/pin/Desktop/workspace/deep-agent-rag-stack

DATABASE_URL='postgresql://postgres:postgres@localhost:15432/deep_agent_rag' \
PYTHONPATH=apps/api/src .venv/bin/python -m app.scripts.prepare_external_benchmark align-spans \
  --workspace-dir /tmp/dureader-robust-100-workspace \
  --area-id "$AREA_ID"

PYTHONPATH=apps/api/src .venv/bin/python -m app.scripts.prepare_external_benchmark report \
  --workspace-dir /tmp/dureader-robust-100-workspace
```

本次 reference package 的 deterministic 對齊結果為：

- `filtered_item_count = 220`
- `auto_matched = 220`
- `needs_review = 0`
- `rejected = 0`

## 步驟 5：只有 queue 非空時才跑 `OpenAI` review

這次 reference package 不需要這一步，因為 `needs_review = 0`。  
若未來 rerun 產生非空 `alignment_review_queue`，則只對 queue 跑 `OpenAI` review：

```bash
DATABASE_URL='postgresql://postgres:postgres@localhost:15432/deep_agent_rag' \
OPENAI_API_KEY="$OPENAI_API_KEY" \
PYTHONPATH=apps/api/src .venv/bin/python -m app.scripts.review_external_benchmark_with_openai \
  --workspace-dir /tmp/dureader-robust-100-workspace \
  --area-id "$AREA_ID" \
  --model gpt-4.1-mini \
  --replace \
  --review-source alignment_review_queue
```

## 步驟 6：建立正式 snapshot

```bash
PYTHONPATH=apps/api/src .venv/bin/python -m app.scripts.prepare_external_benchmark build-snapshot \
  --workspace-dir /tmp/dureader-robust-100-workspace \
  --output-dir /Users/pin/Desktop/workspace/deep-agent-rag-stack/benchmarks/dureader-robust-curated-v1-100 \
  --benchmark-name dureader-robust-curated-v1-100 \
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
  --snapshot-dir /Users/pin/Desktop/workspace/deep-agent-rag-stack/benchmarks/dureader-robust-curated-v1-100 \
  --area-id "$AREA_ID" \
  --dataset-name dureader-robust-curated-v1-100 \
  --replace
```

預期 dataset id：

```text
f4a91b45-64fa-5cd7-b815-9a454888bf9c
```

## 步驟 8：執行 reference run

```bash
DATABASE_URL='postgresql://postgres:postgres@localhost:15432/deep_agent_rag' \
PYTHONPATH=apps/api/src .venv/bin/python -m app.scripts.run_retrieval_eval run \
  --dataset-id f4a91b45-64fa-5cd7-b815-9a454888bf9c \
  --top-k 10 \
  --evaluation-profile production_like_v1 \
  --actor-sub ea33183f-1e9f-458f-a405-bb365b8266c0
```

## Reference Metrics

| 階段 | nDCG@10 | Recall@10 | MRR@10 | Precision@10 | Doc Coverage@10 |
| --- | ---: | ---: | ---: | ---: | ---: |
| recall | `0.8867` | `0.9800` | `0.8566` | `0.0990` | `0.9800` |
| rerank | `0.9677` | `1.0000` | `0.9570` | `0.1000` | `1.0000` |
| assembled | `0.9677` | `1.0000` | `0.9570` | `0.1000` | `1.0000` |
