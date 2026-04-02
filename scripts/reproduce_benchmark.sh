#!/usr/bin/env bash
# 以既有 benchmark package 重建 evaluation dataset、執行 benchmark，並輸出 compare report。

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SNAPSHOT_DIR="${SNAPSHOT_DIR:-$ROOT_DIR/benchmarks/tw-insurance-rag-benchmark-v1}"
DATASET_NAME="${DATASET_NAME:-tw-insurance-rag-benchmark-v1}"
ACTOR_SUB="${ACTOR_SUB:-benchmark-reproducer}"
TOP_K="${TOP_K:-10}"
EVALUATION_PROFILE="${EVALUATION_PROFILE:-production_like_v1}"
REPORT_OUTPUT_PATH="${REPORT_OUTPUT_PATH:-$SNAPSHOT_DIR/reproduced_run_report.json}"
COMPARE_OUTPUT_PATH="${COMPARE_OUTPUT_PATH:-$SNAPSHOT_DIR/reproduced_compare_report.json}"

if [[ -z "${AREA_ID:-}" ]]; then
  echo "AREA_ID is required." >&2
  exit 1
fi

export PYTHONPATH="${PYTHONPATH:-$ROOT_DIR/apps/api/src}"

python -m app.scripts.import_benchmark_snapshot \
  --snapshot-dir "$SNAPSHOT_DIR" \
  --area-id "$AREA_ID" \
  --dataset-name "$DATASET_NAME" \
  --actor-sub "$ACTOR_SUB" \
  --replace

RUN_JSON="$(
  python -m app.scripts.run_retrieval_eval run \
    --dataset-id bb10c343-7d7c-4ae3-b78b-a513759867f2 \
    --top-k "$TOP_K" \
    --evaluation-profile "$EVALUATION_PROFILE" \
    --actor-sub "$ACTOR_SUB"
)"

printf '%s\n' "$RUN_JSON" > "$REPORT_OUTPUT_PATH"

RUN_ID="$(
  python - <<'PY' "$REPORT_OUTPUT_PATH"
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print(payload["run"]["id"])
PY
)"

python -m app.scripts.compare_benchmark_runs \
  --reference-report "$SNAPSHOT_DIR/reference_run_report.json" \
  --candidate-run-id "$RUN_ID" \
  --actor-sub "$ACTOR_SUB" \
  > "$COMPARE_OUTPUT_PATH"

printf 'Reproduced run report: %s\n' "$REPORT_OUTPUT_PATH"
printf 'Compare report: %s\n' "$COMPARE_OUTPUT_PATH"
