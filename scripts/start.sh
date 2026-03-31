#!/usr/bin/env bash
# 啟動 hybrid 開發模式。
# 目的：維持基礎設施、API 與 Web 由 Docker Compose 執行，同時讓 worker
# 直接在本機 Python 環境運行，並使用 OpenDataLoader + Java 路徑。

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${REPO_ROOT}/.env"
COMPOSE_SCRIPT="${REPO_ROOT}/scripts/compose.sh"
PROJECT_VENV_DIR="${REPO_ROOT}/.venv"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "找不到 ${ENV_FILE}，請先建立根目錄 .env。" >&2
  exit 1
fi

if [[ ! -x "${COMPOSE_SCRIPT}" ]]; then
  echo "找不到 ${COMPOSE_SCRIPT}，無法啟動 Compose 服務。" >&2
  exit 1
fi

set -a
source "${ENV_FILE}"
set +a

POSTGRES_DB="${POSTGRES_DB:-deep_agent_rag}"
POSTGRES_USER="${POSTGRES_USER:-app}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-app}"
POSTGRES_PORT="${POSTGRES_PORT:-15432}"
REDIS_PORT="${REDIS_PORT:-16379}"
MINIO_ROOT_USER="${MINIO_ROOT_USER:-minio}"
MINIO_ROOT_PASSWORD="${MINIO_ROOT_PASSWORD:-minio123}"
MINIO_PORT="${MINIO_PORT:-19000}"
MINIO_BUCKET="${MINIO_BUCKET:-documents}"
PDF_PARSER_PROVIDER="${PDF_PARSER_PROVIDER:-opendataloader}"
TORCH_DEVICE="${TORCH_DEVICE:-mps}"
CELERY_LOGLEVEL="${CELERY_LOGLEVEL:-INFO}"
WORKER_VENV_DIR="${PROJECT_VENV_DIR}"

VENV_PYTHON="${WORKER_VENV_DIR}/bin/python"
VENV_CELERY="${WORKER_VENV_DIR}/bin/celery"

if [[ ! -x "${VENV_PYTHON}" || ! -x "${VENV_CELERY}" ]]; then
  echo "找不到專案虛擬環境：${WORKER_VENV_DIR}。worker 與主專案固定共用同一個 .venv。" >&2
  echo "請先在 repo 根目錄執行 uv sync 建立 ${PROJECT_VENV_DIR}。" >&2
  exit 1
fi

if [[ "${PDF_PARSER_PROVIDER}" == "opendataloader" ]] && ! command -v java >/dev/null 2>&1; then
  echo "偵測到 PDF_PARSER_PROVIDER=opendataloader，但本機找不到 java。請先安裝 Java 11+。" >&2
  exit 1
fi

if [[ "${PDF_PARSER_PROVIDER}" == "opendataloader" ]]; then
  if ! "${VENV_PYTHON}" - <<'PY' >/dev/null 2>&1
import opendataloader_pdf
PY
  then
    echo "偵測到 PDF_PARSER_PROVIDER=opendataloader，但 ${WORKER_VENV_DIR} 尚未安裝 opendataloader-pdf。" >&2
    echo "請先在 repo 根目錄執行 uv sync，或至少執行 uv pip install opendataloader-pdf。" >&2
    exit 1
  fi
fi

echo "啟動 Compose 服務（不含 container worker，會先自動執行 API migration）..."
"${COMPOSE_SCRIPT}" up -d supabase-db redis minio keycloak api-migrate keycloak api web caddy --build

echo "以本機 worker 啟動 Celery..."
echo "  DATABASE_URL=postgresql://${POSTGRES_USER}:***@127.0.0.1:${POSTGRES_PORT}/${POSTGRES_DB}"
echo "  CELERY_BROKER_URL=redis://127.0.0.1:${REDIS_PORT}/0"
echo "  MINIO_ENDPOINT=http://127.0.0.1:${MINIO_PORT}"
echo "  PDF_PARSER_PROVIDER=${PDF_PARSER_PROVIDER}"
echo "  TORCH_DEVICE=${TORCH_DEVICE}"
echo "  WORKER_VENV_DIR=${WORKER_VENV_DIR}"

cd "${REPO_ROOT}"

export PYTHONPATH="${REPO_ROOT}/apps/worker/src:${PYTHONPATH:-}"
export DATABASE_URL="postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@127.0.0.1:${POSTGRES_PORT}/${POSTGRES_DB}"
export CELERY_BROKER_URL="redis://127.0.0.1:${REDIS_PORT}/0"
export CELERY_RESULT_BACKEND="redis://127.0.0.1:${REDIS_PORT}/1"
export STORAGE_BACKEND="${STORAGE_BACKEND:-minio}"
export MINIO_ENDPOINT="http://127.0.0.1:${MINIO_PORT}"
export MINIO_ACCESS_KEY="${MINIO_ACCESS_KEY:-${MINIO_ROOT_USER}}"
export MINIO_SECRET_KEY="${MINIO_SECRET_KEY:-${MINIO_ROOT_PASSWORD}}"
export MINIO_BUCKET="${MINIO_BUCKET}"
export PDF_PARSER_PROVIDER="${PDF_PARSER_PROVIDER}"
export TORCH_DEVICE="${TORCH_DEVICE}"

exec "${VENV_CELERY}" -A worker.celery_app.celery_app worker --loglevel="${CELERY_LOGLEVEL}" "$@"
