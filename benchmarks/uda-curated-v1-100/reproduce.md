# UDA 100 重現指南

## 目的

此文件說明如何在目前 repo 內重現 `uda-curated-v1-100` 的建立流程與 `production_like_v1` reference run。  
重現目標是取得與本 package 相同 contract、相同 profile 的 `100` 題 benchmark 分數，而不是重跑原始 `UDA-QA` leaderboard。

## 先備條件

- 已取得此 repo
- Docker Compose stack 可正常啟動
- 本機可連到：
  - `http://localhost/auth`
  - `http://localhost/api`
  - `postgresql://postgres:postgres@localhost:15432/deep_agent_rag`
- 本機可下載官方 `UDA-QA` source zip

## 本次 reference run 身分

- Area 名稱：`uda-100`
- Area ID：`2edabc25-1a54-43ab-b987-efd4e040114f`
- Dataset 名稱：`uda-curated-v1-100`
- Dataset ID：`3cca653e-ffd5-5ab8-8464-27aaac194bb4`
- Reference run ID：`821345d6-9a4d-48ea-8fb4-fb36f2af182e`

## 步驟 1：啟動服務

在 repo 根目錄：

```bash
./scripts/compose.sh up --build
./scripts/compose.sh exec api python -m app.db.migration_runner
```

## 步驟 2：取得官方 UDA bench 與 source docs

```bash
rm -rf /tmp/uda-100
mkdir -p /tmp/uda-100

git clone --depth 1 https://github.com/qinchuanhui/UDA-Benchmark /tmp/uda-100/UDA-Benchmark

curl -L --fail \
  'https://huggingface.co/datasets/qinchuanhui/UDA-QA/resolve/main/src_doc_files/wiki_nq_docs.zip?download=true' \
  -o /tmp/uda-100/wiki_nq_docs.zip

python -m zipfile -e /tmp/uda-100/wiki_nq_docs.zip /tmp/uda-100/wiki_nq_docs
```

## 步驟 3：建立 official full-source rows

```bash
cd /Users/pin/Desktop/workspace/deep-agent-rag-stack

PYTHONPATH=apps/api/src .venv/bin/python -m app.scripts.prepare_uda_full_source \
  --bench-root /tmp/uda-100/UDA-Benchmark/dataset \
  --source-doc-root /tmp/uda-100/wiki_nq_docs \
  --subsets nq \
  --output-path /tmp/uda-100/uda_nq_rows.jsonl
```

預期：

- `row_count = 379`

## 步驟 4：建立 oversampled workspace

```bash
PYTHONPATH=apps/api/src .venv/bin/python -m app.scripts.prepare_external_benchmark prepare-source \
  --dataset uda \
  --input-path /tmp/uda-100/uda_nq_rows.jsonl \
  --workspace-dir /tmp/uda-100-workspace

PYTHONPATH=apps/api/src .venv/bin/python -m app.scripts.prepare_external_benchmark filter-items \
  --workspace-dir /tmp/uda-100-workspace
```

預期：

- `document_count = 150`
- `prepared_item_count = 379`
- `kept_item_count = 263`

## 步驟 5：建立 area 並上傳文件

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
  -d '{"name":"uda-100","description":"UDA 100 benchmark"}' \
  http://localhost/api/areas
```

將回傳中的 `id` 記成 `AREA_ID`。

上傳全部 source docs：

```bash
for f in /tmp/uda-100-workspace/source_documents/*.pdf; do
  curl -sS \
    -H "Authorization: Bearer $TOKEN" \
    -F "file=@$f" \
    "http://localhost/api/areas/$AREA_ID/documents"
done
```

等到所有文件都進入 `ready`。

## 步驟 6：對齊 evidence

```bash
cd /Users/pin/Desktop/workspace/deep-agent-rag-stack

DATABASE_URL='postgresql://postgres:postgres@localhost:15432/deep_agent_rag' \
PYTHONPATH=apps/api/src .venv/bin/python -m app.scripts.prepare_external_benchmark align-spans \
  --workspace-dir /tmp/uda-100-workspace \
  --area-id "$AREA_ID"

DATABASE_URL='postgresql://postgres:postgres@localhost:15432/deep_agent_rag' \
PYTHONPATH=apps/api/src .venv/bin/python -m app.scripts.prepare_external_benchmark report \
  --workspace-dir /tmp/uda-100-workspace
```

本次 reference package 的 deterministic 對齊結果為：

- `auto_matched = 102`
- `needs_review = 0`
- `rejected = 161`

Reference package 本身只使用前 `100` 個 approved items，因此不需要再跑 LLM review。

## 步驟 7：建立正式 snapshot

```bash
PYTHONPATH=apps/api/src .venv/bin/python -m app.scripts.prepare_external_benchmark build-snapshot \
  --workspace-dir /tmp/uda-100-workspace \
  --output-dir /Users/pin/Desktop/workspace/deep-agent-rag-stack/benchmarks/uda-curated-v1-100 \
  --benchmark-name uda-curated-v1-100 \
  --target-question-count 100 \
  --reference-evaluation-profile production_like_v1
```

預期：

- `question_count = 100`
- `question_with_gold_span_count = 100`
- `span_count = 100`
- `document_count = 45`

## 步驟 8：匯入 snapshot

```bash
DATABASE_URL='postgresql://postgres:postgres@localhost:15432/deep_agent_rag' \
PYTHONPATH=apps/api/src .venv/bin/python -m app.scripts.import_benchmark_snapshot \
  --snapshot-dir /Users/pin/Desktop/workspace/deep-agent-rag-stack/benchmarks/uda-curated-v1-100 \
  --area-id "$AREA_ID" \
  --dataset-name uda-curated-v1-100 \
  --replace
```

預期 dataset id：

```text
3cca653e-ffd5-5ab8-8464-27aaac194bb4
```

## 步驟 9：執行 reference run

```bash
DATABASE_URL='postgresql://postgres:postgres@localhost:15432/deep_agent_rag' \
PYTHONPATH=apps/api/src .venv/bin/python -m app.scripts.run_retrieval_eval run \
  --dataset-id 3cca653e-ffd5-5ab8-8464-27aaac194bb4 \
  --top-k 10 \
  --evaluation-profile production_like_v1 \
  --actor-sub ea33183f-1e9f-458f-a405-bb365b8266c0
```

## Reference Metrics

| 階段 | nDCG@10 | Recall@10 | MRR@10 | Precision@10 | Doc Coverage@10 |
| --- | ---: | ---: | ---: | ---: | ---: |
| recall | 0.4544 | 0.6500 | 0.3956 | 0.0660 | 1.0000 |
| rerank | 0.6805 | 0.8200 | 0.6350 | 0.0820 | 1.0000 |
| assembled | 0.6818 | 0.8300 | 0.6340 | 0.0830 | 1.0000 |
