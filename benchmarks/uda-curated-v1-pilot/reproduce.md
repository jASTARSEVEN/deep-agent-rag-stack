# UDA Pilot 重現指南

## 目的

此文件說明如何在目前 repo 內重現 `uda-curated-v1-pilot` 的建立、`OpenAI API` review 與 benchmark 執行流程。  
重現目標是取得與 reference run 同型態、同 contract 的 retrieval benchmark 分數，而不是聲稱完整重現原始 `UDA-Benchmark` 論文的 answer-generation leaderboard。

## 先備條件

- 已取得此 repo 與目前 benchmark package 內容
- Docker Compose stack 可正常啟動
- 本機可連到：
  - `http://localhost/auth`
  - `http://localhost/api`
  - `postgresql://postgres:postgres@localhost:15432/deep_agent_rag`
- 本機可載入 `BAAI/bge-reranker-v2-m3`

## 本次 reference run 身分

- Area 名稱：`uda-pilot`
- Area ID：`58afaf23-423d-4526-b90d-43ea19711eaf`
- Dataset 名稱：`uda-curated-v1-pilot`
- Dataset ID：`3d779672-b561-5d64-aa76-035d37d4e0b4`
- Reference run ID：`593638b8-a3c7-4471-ba56-7d242a8e65fa`

## 步驟 1：啟動服務

在 repo 根目錄：

```bash
./scripts/compose.sh up --build
./scripts/compose.sh exec api python -m app.db.migration_runner
```

## 步驟 2：取得官方 UDA-Benchmark sample 資料

```bash
git clone --depth 1 https://github.com/qinchuanhui/UDA-Benchmark /tmp/UDA-Benchmark
```

此 pilot 只使用官方 repo 內已直接提供的小型 sample：

- `dataset/extended_qa_info_bench`
- `dataset/src_doc_files_example`

不下載完整 `UDA-QA` source documents。

## 步驟 3：建立 pilot rows 與 workspace

```bash
python - <<'PY'
import json
from pathlib import Path

base = Path('/tmp/UDA-Benchmark/dataset')
example = base / 'src_doc_files_example'
bench = base / 'extended_qa_info_bench'
output = Path('/tmp/uda_pilot_rows.jsonl')

from pypdf import PdfReader

jkhy_pdf = example / 'fin_docs' / 'JKHY_2015.pdf'
jkhy_md = Path('/tmp/JKHY_2015.md')
chunks = ['# JKHY_2015\n']
for page_index, page in enumerate(PdfReader(str(jkhy_pdf)).pages, start=1):
    text = (page.extract_text() or '').strip()
    if not text:
        continue
    chunks.append(f'\n## Page {page_index}\n\n{text}\n')
jkhy_md.write_text('\n'.join(chunks), encoding='utf-8')

bench_files = [
    ('paper_text', bench / 'bench_paper_text_qa.json'),
    ('paper_tab', bench / 'bench_paper_tab_qa.json'),
    ('fin', bench / 'bench_fin_qa.json'),
]

def flatten(value):
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        out = []
        for item in value:
            out.extend(flatten(item))
        return out
    if isinstance(value, dict):
        out = []
        for item in value.values():
            out.extend(flatten(item))
        return out
    return []

def pick_answer(answers):
    if isinstance(answers, dict):
        return (
            answers.get('short_answer')
            or answers.get('str_answer')
            or answers.get('long_answer')
            or ''
        )
    if isinstance(answers, list):
        for item in answers:
            if isinstance(item, dict) and item.get('type') == 'extractive' and item.get('answer'):
                return item['answer']
        for item in answers:
            if isinstance(item, dict) and item.get('answer'):
                return item['answer']
    return ''

rows = []
for subset, path in bench_files:
    payload = json.loads(path.read_text())
    for doc_name, entries in payload.items():
        source_file = allowed_docs.get(doc_name)
        if source_file is None or not source_file.exists():
            continue
        for entry in entries:
            evidence = []
            if subset in {'paper_text', 'paper_tab'}:
                for evidence_row in entry.get('evidence', []):
                    evidence.extend(
                        text.strip()
                        for text in flatten(evidence_row.get('highlighted_evidence', []))
                        if isinstance(text, str) and text.strip()
                    )
                    if not evidence:
                        evidence.extend(
                            text.strip()
                            for text in flatten(evidence_row.get('raw_evidence', []))
                            if isinstance(text, str) and text.strip()
                        )
            else:
                evidence.extend(
                    text.strip()
                    for text in flatten(entry.get('evidence', {}))
                    if isinstance(text, str) and text.strip()
                )
            answer_payload = entry.get('answers')
            answer_text = ''
            if isinstance(answer_payload, dict) and 'answer' in answer_payload:
                answer_value = answer_payload['answer']
                if isinstance(answer_value, list):
                    answer_text = ', '.join(str(part) for part in answer_value)
                else:
                    answer_text = str(answer_value)
            elif isinstance(answer_payload, list):
                for candidate in answer_payload:
                    if isinstance(candidate, dict) and candidate.get('type') == 'extractive' and candidate.get('answer'):
                        answer_text = candidate['answer']
                        break
                if not answer_text:
                    for candidate in answer_payload:
                        if isinstance(candidate, dict) and candidate.get('answer'):
                            answer_text = candidate['answer']
                            break

            if subset in {'fin', 'tat'} and not evidence:
                evidence.extend(str(part) for part in entry.get('facts', []) if str(part).strip())

            source_path = source_file
            if doc_name == 'JKHY_2015':
                source_path = jkhy_md

            rows.append(
                {
                    'document_id': doc_name,
                    'source_file': str(source_path),
                    'question': entry.get('question', ''),
                    'answer': answer_text,
                    'evidence': evidence[0] if evidence else '',
                }
            )

output.write_text('\n'.join(json.dumps(row, ensure_ascii=False) for row in rows) + '\n', encoding='utf-8')
print(output)
PY

rm -rf /tmp/uda-pilot-workspace

cd /Users/pin/Desktop/workspace/deep-agent-rag-stack/apps/api

PYTHONPATH=src python -m app.scripts.prepare_external_benchmark prepare-source \
  --dataset uda \
  --input-path /tmp/uda_pilot_rows.jsonl \
  --workspace-dir /tmp/uda-pilot-workspace

PYTHONPATH=src python -m app.scripts.prepare_external_benchmark filter-items \
  --workspace-dir /tmp/uda-pilot-workspace
```

預期：

- `prepared_item_count = 28`
- `kept_item_count = 26`
- 被排除的 `2` 題都是 `yes_no_answer`

## 步驟 4：建立 area 並上傳 sample PDFs

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
  -d '{"name":"uda-pilot","description":"UDA benchmark pilot based on official sample docs"}' \
  http://localhost/api/areas
```

將回傳中的 `id` 記成 `AREA_ID`。

上傳 sample documents：

```bash
for f in \
  /tmp/UDA-Benchmark/dataset/src_doc_files_example/paper_docs/1705.07830.pdf \
  /tmp/UDA-Benchmark/dataset/src_doc_files_example/paper_docs/1801.05147.pdf \
  /tmp/UDA-Benchmark/dataset/src_doc_files_example/paper_docs/1809.01202.pdf \
  /tmp/UDA-Benchmark/dataset/src_doc_files_example/paper_docs/1909.00754.pdf \
  /tmp/UDA-Benchmark/dataset/src_doc_files_example/paper_docs/1912.01214.pdf \
  /tmp/UDA-Benchmark/dataset/src_doc_files_example/paper_docs/2001.03131.pdf \
  /tmp/UDA-Benchmark/dataset/src_doc_files_example/fin_docs/GS_2016.pdf \
  /tmp/JKHY_2015.md
do
  curl -sS \
    -H "Authorization: Bearer $TOKEN" \
    -F "file=@$f" \
    "http://localhost/api/areas/$AREA_ID/documents"
done
```

等到這 `12` 份文件都進入 `ready`。

## 步驟 5：對齊 evidence 與執行 OpenAI review

```bash
cd /Users/pin/Desktop/workspace/deep-agent-rag-stack/apps/api

DATABASE_URL='postgresql://postgres:postgres@localhost:15432/deep_agent_rag' \
PYTHONPATH=src python -m app.scripts.prepare_external_benchmark align-spans \
  --workspace-dir /tmp/uda-pilot-workspace \
  --area-id "$AREA_ID"
```

本輪先跑 auto alignment，再接 `OpenAI API` review：

```bash
OPENAI_KEY=$(python - <<'PY'
from pathlib import Path
for line in Path('/Users/pin/Desktop/workspace/deep-agent-rag-stack/.env').read_text().splitlines():
    if line.startswith('OPENAI_API_KEY='):
        print(line.split('=', 1)[1])
        break
PY
)

DATABASE_URL='postgresql://postgres:postgres@localhost:15432/deep_agent_rag' \
OPENAI_API_KEY="$OPENAI_KEY" \
PYTHONPATH=src python -m app.scripts.review_external_benchmark_with_openai \
  --workspace-dir /tmp/uda-pilot-workspace \
  --area-id "$AREA_ID" \
  --model gpt-4.1-mini \
  --replace

PYTHONPATH=src python -m app.scripts.prepare_external_benchmark report \
  --workspace-dir /tmp/uda-pilot-workspace
```

本次 reference package 的 review 現況：

- `auto_matched = 9`
- `OpenAI review approvals = 21`
- 後續又補 `4` 題 deterministic span override
- 最終 `review_override_count = 25`

## 步驟 6：建立正式 snapshot

```bash
PYTHONPATH=src python -m app.scripts.prepare_external_benchmark build-snapshot \
  --workspace-dir /tmp/uda-pilot-workspace \
  --output-dir /tmp/uda-curated-v1-pilot \
  --benchmark-name uda-curated-v1-pilot
```

預期：

- `question_count = 26`
- `span_count = 38`
- `document_count = 12`

## 步驟 7：匯入 snapshot

```bash
DATABASE_URL='postgresql://postgres:postgres@localhost:15432/deep_agent_rag' \
PYTHONPATH=src python -m app.scripts.import_benchmark_snapshot \
  --snapshot-dir /tmp/uda-curated-v1-pilot \
  --area-id "$AREA_ID" \
  --dataset-name uda-curated-v1-pilot \
  --replace
```

預期 dataset id：

```text
3d779672-b561-5d64-aa76-035d37d4e0b4
```

## 步驟 8：執行 reference run

```bash
DATABASE_URL='postgresql://postgres:postgres@localhost:15432/deep_agent_rag' \
RERANK_PROVIDER=bge \
RERANK_MODEL='BAAI/bge-reranker-v2-m3' \
PYTHONPATH=src python -m app.scripts.run_retrieval_eval run \
  --dataset-id 3d779672-b561-5d64-aa76-035d37d4e0b4 \
  --top-k 10 \
  --evaluation-profile production_like_v1 \
  --actor-sub b907d381-84a3-4562-a367-3d4ab87f5190
```

## Reference Metrics

| 階段 | nDCG@10 | Recall@10 | MRR@10 | Precision@10 | Doc Coverage@10 |
| --- | ---: | ---: | ---: | ---: | ---: |
| recall | 0.3127 | 0.5000 | 0.2483 | 0.0577 | 0.7308 |
| rerank | 0.7353 | 0.8462 | 0.7083 | 0.0885 | 0.9615 |
| assembled | 0.5288 | 0.6538 | 0.4968 | 0.0692 | 0.9615 |

## BGE Core Profile 對照

若要對齊 `docs/retrieval-benchmark-strategy-analysis.md` 內的最新 UDA pilot 參考分數，請先以本 package 的 `reference_run_summary.json` 為準。  
`bge_core_profiles_summary.json` 會保存四條 current-head profile 的 assembled 指標對照。

## 已知限制

- 此 pilot 不是完整 `UDA-QA`，只是一組可被本 repo 實際 ingest、對齊與重跑的官方 sample 子集。
- `OpenAI API` review 是此版能把題數擴到 `26` 的核心步驟；若跳過這一步，只靠 auto alignment 會明顯不足。
- `production_like_v1` 在 current HEAD 已對齊主線 default，因此它的 config snapshot 會包含 `qasper_v3` evidence synopsis 設定。
