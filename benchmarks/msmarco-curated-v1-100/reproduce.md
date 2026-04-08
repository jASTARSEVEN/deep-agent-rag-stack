# MS MARCO 100 重現指南

## 目的

此文件說明如何在目前 repo 內重現 `msmarco-curated-v1-100` 的建立流程與 `production_like_v1` reference run。  
重現目標是取得與本 package 相同 contract、相同 profile 的 `100` 題 benchmark 分數，而不是重跑原始 `MS MARCO` leaderboard。

## 先備條件

- 已取得此 repo
- Docker Compose stack 可正常啟動
- 本機可連到：
  - `http://localhost/auth`
  - `http://localhost/api`
  - `postgresql://postgres:postgres@localhost:15432/deep_agent_rag`
- `OPENAI_API_KEY` 可用，供 review queue 補齊 gold spans

## 本次 reference run 身分

- Area 名稱：`msmarco-100`
- Area ID：`4a7a8c05-4aa2-403f-b101-d24ff28d1308`
- Dataset 名稱：`msmarco-curated-v1-100`
- Dataset ID：`4669417e-6276-54ae-89b3-95fcb7652096`
- Reference run ID：`5e9de20b-4781-4711-a69e-03157e61d68a`

## 步驟 1：啟動服務

在 repo 根目錄：

```bash
./scripts/compose.sh up --build
./scripts/compose.sh exec api python -m app.db.migration_runner
```

## 步驟 2：建立 oversampled workspace

`MS MARCO` 這條流程不需要手動先下載 parquet；直接透過 `prepare_external_benchmark` 內建的 `hf://` 參照向 Hugging Face dataset-server 取 row。

```bash
rm -rf /tmp/msmarco-100-workspace

cd /Users/pin/Desktop/workspace/deep-agent-rag-stack

PYTHONPATH=apps/api/src .venv/bin/python -m app.scripts.prepare_external_benchmark prepare-source \
  --dataset msmarco \
  --input-path hf://microsoft/ms_marco/v1.1/validation \
  --workspace-dir /tmp/msmarco-100-workspace \
  --limit-documents 180 \
  --limit-items 180

PYTHONPATH=apps/api/src .venv/bin/python -m app.scripts.prepare_external_benchmark filter-items \
  --workspace-dir /tmp/msmarco-100-workspace
```

預期：

- `prepared_item_count = 180`
- `kept_item_count = 154`
- drop reason 主要來自 `answer_too_long`、`yes_no_answer` 與少量 `layout_dependent`

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
  -d '{"name":"msmarco-100","description":"MS MARCO 100 benchmark"}' \
  http://localhost/api/areas
```

將回傳中的 `id` 記成 `AREA_ID`。

上傳 markdown snippet bundles：

```bash
find /tmp/msmarco-100-workspace/source_documents -type f -name "*.md" | sort | while read -r f; do
  curl -sS \
    -H "Authorization: Bearer $TOKEN" \
    -F "file=@$f" \
    "http://localhost/api/areas/$AREA_ID/documents"
done
```

等到所有文件都進入 `ready`。

## 步驟 4：對齊 evidence 與 review queue

```bash
cd /Users/pin/Desktop/workspace/deep-agent-rag-stack

DATABASE_URL='postgresql://postgres:postgres@localhost:15432/deep_agent_rag' \
PYTHONPATH=apps/api/src .venv/bin/python -m app.scripts.prepare_external_benchmark align-spans \
  --workspace-dir /tmp/msmarco-100-workspace \
  --area-id "$AREA_ID"

PYTHONPATH=apps/api/src .venv/bin/python -m app.scripts.prepare_external_benchmark report \
  --workspace-dir /tmp/msmarco-100-workspace
```

本次 reference package 的 deterministic 對齊結果為：

- `filtered_item_count = 154`
- `auto_matched = 103`
- `needs_review = 7`
- `rejected = 44`

## 步驟 5：對 review queue 跑 `OpenAI` review

`MS MARCO` 這條流程會先以答案字串對齊；若答案本身是 paraphrase 或多處可命中，才交給 `OpenAI` 從候選視窗回貼逐字 quote。

```bash
DATABASE_URL='postgresql://postgres:postgres@localhost:15432/deep_agent_rag' \
OPENAI_API_KEY="$OPENAI_API_KEY" \
PYTHONPATH=apps/api/src .venv/bin/python -m app.scripts.review_external_benchmark_with_openai \
  --workspace-dir /tmp/msmarco-100-workspace \
  --area-id "$AREA_ID" \
  --model gpt-5-mini \
  --replace \
  --review-source alignment_review_queue
```

本次 reference package 的 review 結果為：

- `review_item_count = 51`
- `approved_override_count = 47`
- `rejected_count = 4`

## 步驟 6：建立正式 snapshot

```bash
PYTHONPATH=apps/api/src .venv/bin/python -m app.scripts.prepare_external_benchmark build-snapshot \
  --workspace-dir /tmp/msmarco-100-workspace \
  --output-dir /Users/pin/Desktop/workspace/deep-agent-rag-stack/benchmarks/msmarco-curated-v1-100 \
  --benchmark-name msmarco-curated-v1-100 \
  --target-question-count 100 \
  --reference-evaluation-profile production_like_v1
```

預期：

- `question_count = 100`
- `question_with_gold_span_count = 100`
- `span_count = 114`
- `document_count = 100`

## 步驟 7：匯入 snapshot

```bash
DATABASE_URL='postgresql://postgres:postgres@localhost:15432/deep_agent_rag' \
PYTHONPATH=apps/api/src .venv/bin/python -m app.scripts.import_benchmark_snapshot \
  --snapshot-dir /Users/pin/Desktop/workspace/deep-agent-rag-stack/benchmarks/msmarco-curated-v1-100 \
  --area-id "$AREA_ID" \
  --dataset-name msmarco-curated-v1-100 \
  --replace
```

預期 dataset id：

```text
4669417e-6276-54ae-89b3-95fcb7652096
```

## 步驟 8：執行 reference run

```bash
DATABASE_URL='postgresql://postgres:postgres@localhost:15432/deep_agent_rag' \
PYTHONPATH=apps/api/src .venv/bin/python -m app.scripts.run_retrieval_eval run \
  --dataset-id 4669417e-6276-54ae-89b3-95fcb7652096 \
  --top-k 10 \
  --evaluation-profile production_like_v1 \
  --actor-sub ea33183f-1e9f-458f-a405-bb365b8266c0
```

## Reference Metrics

| 階段 | nDCG@10 | Recall@10 | MRR@10 | Precision@10 | Doc Coverage@10 |
| --- | ---: | ---: | ---: | ---: | ---: |
| recall | 0.7825 | 0.9900 | 0.7092 | 0.1110 | 1.0000 |
| rerank | 0.9674 | 1.0000 | 0.9550 | 0.1050 | 1.0000 |
| assembled | 0.9674 | 1.0000 | 0.9550 | 0.1050 | 1.0000 |
