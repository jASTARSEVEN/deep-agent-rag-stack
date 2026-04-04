# QASPER Pilot 重現指南

## 目的

此文件說明如何在目前 repo 內重現 `qasper-curated-v1-pilot` 的建立與 benchmark 執行流程。  
重現目標是取得與 reference run 同型態、同 contract 的 retrieval benchmark 分數，而不是聲稱完整重現原始 `QASPER` 論文結果。

## 先備條件

- 已取得此 repo 與目前 benchmark package 內容
- Docker Compose stack 可正常啟動
- `OpenAI` 與 `Cohere` 金鑰可用
- 本機可連到：
  - `http://localhost/auth`
  - `http://localhost/api`
  - `postgresql://postgres:postgres@localhost:15432/deep_agent_rag`

## 本次 reference run 身分

- Area 名稱：`qasper-pilot`
- Area ID：`253f5f48-a0ce-4201-b966-04591501259c`
- Dataset 名稱：`qasper-curated-v1-pilot`
- Dataset ID：`db6d581c-2feb-5914-afb8-b4f1fa2092e2`
- Reference run ID：`6f1150df-1343-4905-a417-7334ea87c9d6`

## 步驟 1：啟動服務

在 repo 根目錄：

```bash
./scripts/compose.sh up --build
./scripts/compose.sh exec api python -m app.db.migration_runner
```

## 步驟 2：取得 QASPER 原始資料

下載官方 train/dev archive，並抽出 train split：

```bash
mkdir -p /tmp/qasper-pilot
cd /tmp/qasper-pilot

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

## 步驟 3：建立 pilot workspace

```bash
rm -rf /tmp/qasper-pilot-workspace

cd /Users/pin/Desktop/workspace/deep-agent-rag-stack/apps/api

PYTHONPATH=src python -m app.scripts.prepare_external_benchmark prepare-source \
  --dataset qasper \
  --input-path /tmp/qasper-pilot/qasper-train-v0.3.json \
  --workspace-dir /tmp/qasper-pilot-workspace \
  --limit-documents 8 \
  --limit-items 40

PYTHONPATH=src python -m app.scripts.prepare_external_benchmark filter-items \
  --workspace-dir /tmp/qasper-pilot-workspace
```

預期：

- `prepared_item_count = 40`
- `kept_item_count = 29`

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

建立 area：

```bash
curl -sS \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"qasper-pilot","description":"QASPER pilot benchmark"}' \
  http://localhost/api/areas
```

將回傳中的 `id` 記成 `AREA_ID`。

上傳產生出的 markdown 文件：

```bash
for f in /tmp/qasper-pilot-workspace/source_documents/*.md; do
  curl -sS \
    -H "Authorization: Bearer $TOKEN" \
    -F "file=@$f" \
    "http://localhost/api/areas/$AREA_ID/documents"
done
```

等到所有文件都進入 `ready`。

## 步驟 5：對齊 evidence

因為此 CLI 會直接連本機 PostgreSQL，請明確帶入 `DATABASE_URL`：

```bash
cd /Users/pin/Desktop/workspace/deep-agent-rag-stack/apps/api

DATABASE_URL='postgresql://postgres:postgres@localhost:15432/deep_agent_rag' \
PYTHONPATH=src python -m app.scripts.prepare_external_benchmark align-spans \
  --workspace-dir /tmp/qasper-pilot-workspace \
  --area-id "$AREA_ID"

DATABASE_URL='postgresql://postgres:postgres@localhost:15432/deep_agent_rag' \
PYTHONPATH=src python -m app.scripts.prepare_external_benchmark report \
  --workspace-dir /tmp/qasper-pilot-workspace
```

本次 reference run 的對齊結果為：

- `filtered_item_count = 29`
- `auto_matched = 27`
- `needs_review = 1`
- `rejected = 1`
- `auto_matched_ratio = 0.931034`

## 步驟 6：建立正式 snapshot

此 pilot 直接只採用 `auto_matched` 題目，不納入 `needs_review` 與 `rejected`。

```bash
PYTHONPATH=src python -m app.scripts.prepare_external_benchmark build-snapshot \
  --workspace-dir /tmp/qasper-pilot-workspace \
  --output-dir /Users/pin/Desktop/workspace/deep-agent-rag-stack/benchmarks/qasper-curated-v1-pilot \
  --benchmark-name qasper-curated-v1-pilot
```

預期：

- `question_count = 27`
- `span_count = 34`
- `document_count = 7`

## 步驟 7：匯入 snapshot

```bash
DATABASE_URL='postgresql://postgres:postgres@localhost:15432/deep_agent_rag' \
PYTHONPATH=src python -m app.scripts.import_benchmark_snapshot \
  --snapshot-dir /Users/pin/Desktop/workspace/deep-agent-rag-stack/benchmarks/qasper-curated-v1-pilot \
  --area-id "$AREA_ID" \
  --dataset-name qasper-curated-v1-pilot \
  --replace
```

預期 dataset id：

```text
db6d581c-2feb-5914-afb8-b4f1fa2092e2
```

## 步驟 8：執行 benchmark

正式 reference run：

```bash
CAROL_SUB="b907d381-84a3-4562-a367-3d4ab87f5190"

OPENAI_KEY=$(python - <<'PY'
from pathlib import Path
for line in Path('/Users/pin/Desktop/workspace/deep-agent-rag-stack/.env').read_text().splitlines():
    if line.startswith('OPENAI_API_KEY='):
        print(line.split('=', 1)[1])
        break
PY
)

COHERE_KEY=$(python - <<'PY'
from pathlib import Path
for line in Path('/Users/pin/Desktop/workspace/deep-agent-rag-stack/.env').read_text().splitlines():
    if line.startswith('COHERE_API_KEY='):
        print(line.split('=', 1)[1])
        break
PY
)

DATABASE_URL='postgresql://postgres:postgres@localhost:15432/deep_agent_rag' \
OPENAI_API_KEY="$OPENAI_KEY" \
COHERE_API_KEY="$COHERE_KEY" \
RERANK_PROVIDER=cohere \
PYTHONPATH=src python -m app.scripts.run_retrieval_eval run \
  --dataset-id db6d581c-2feb-5914-afb8-b4f1fa2092e2 \
  --top-k 10 \
  --evaluation-profile production_like_v1 \
  --actor-sub "$CAROL_SUB"
```

## Reference Metrics

| 階段 | nDCG@10 | Recall@10 | MRR@10 | Precision@10 | Doc Coverage@10 |
| --- | ---: | ---: | ---: | ---: | ---: |
| recall | 0.2920 | 0.5556 | 0.2062 | 0.0630 | 0.9630 |
| rerank | 0.4590 | 0.5556 | 0.4228 | 0.0593 | 0.9630 |
| assembled | 0.4489 | 0.5556 | 0.4105 | 0.0593 | 0.9630 |

## 已知限制

- 此 pilot 不是完整 `QASPER` benchmark，只是對齊到現有 contract 的小型可重現子集。
- `needs_review` 題目沒有納入最終 snapshot。
- `production_like_v1 + cohere` 可能會遇到 `HTTP 429` 並觸發 retry/backoff；只要最後 run 狀態為 `completed` 即屬正常重現範圍。
