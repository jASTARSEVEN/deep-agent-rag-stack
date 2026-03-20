#!/usr/bin/env bash
# 啟動 hybrid 開發模式。
# 目的：維持基礎設施、API 與 Web 由 Docker Compose 執行，同時讓 worker
# 直接在本機 Python 環境運行，以便在 macOS 上使用 MPS 或在本機直接控制
# Marker / PyTorch 裝置選擇。

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${REPO_ROOT}/.env"
COMPOSE_SCRIPT="${REPO_ROOT}/scripts/compose.sh"
LOCAL_MARKER_CACHE_DIR="${REPO_ROOT}/.marker-cache/models"
DEFAULT_WORKER_VENV_DIR="${REPO_ROOT}/.venv"
MARKER_WORKER_VENV_DIR="${REPO_ROOT}/.worker-venv"

has_marker_pdf() {
  local python_bin="$1"
  "${python_bin}" -c 'import importlib.util, sys; sys.exit(0 if importlib.util.find_spec("marker") else 1)' >/dev/null 2>&1
}

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
PDF_PARSER_PROVIDER="${PDF_PARSER_PROVIDER:-marker}"
MARKER_MODEL_CACHE_DIR="${MARKER_MODEL_CACHE_DIR:-${LOCAL_MARKER_CACHE_DIR}}"
TORCH_DEVICE="${TORCH_DEVICE:-mps}"
CELERY_LOGLEVEL="${CELERY_LOGLEVEL:-INFO}"
WORKER_VENV_DIR="${WORKER_VENV_DIR:-}"

if [[ -z "${WORKER_VENV_DIR}" ]]; then
  if [[ "${PDF_PARSER_PROVIDER}" == "marker" && -x "${MARKER_WORKER_VENV_DIR}/bin/python" && -x "${MARKER_WORKER_VENV_DIR}/bin/celery" ]] && has_marker_pdf "${MARKER_WORKER_VENV_DIR}/bin/python"; then
    WORKER_VENV_DIR="${MARKER_WORKER_VENV_DIR}"
  elif [[ "${PDF_PARSER_PROVIDER}" == "marker" && -x "${DEFAULT_WORKER_VENV_DIR}/bin/python" && -x "${DEFAULT_WORKER_VENV_DIR}/bin/celery" ]] && has_marker_pdf "${DEFAULT_WORKER_VENV_DIR}/bin/python"; then
    WORKER_VENV_DIR="${DEFAULT_WORKER_VENV_DIR}"
  else
    WORKER_VENV_DIR="${DEFAULT_WORKER_VENV_DIR}"
  fi
fi

VENV_PYTHON="${WORKER_VENV_DIR}/bin/python"
VENV_CELERY="${WORKER_VENV_DIR}/bin/celery"

if [[ ! -x "${VENV_PYTHON}" || ! -x "${VENV_CELERY}" ]]; then
  echo "找不到 worker virtualenv：${WORKER_VENV_DIR}。請先安裝本機 worker 依賴。" >&2
  echo "共享 workspace 可先執行 uv sync 建立 ${DEFAULT_WORKER_VENV_DIR}。" >&2
  echo "若要使用 PDF_PARSER_PROVIDER=marker，建議另外建立 ${MARKER_WORKER_VENV_DIR} 並安裝 marker-pdf。" >&2
  exit 1
fi

if [[ "${PDF_PARSER_PROVIDER}" == "marker" ]] && ! has_marker_pdf "${VENV_PYTHON}"; then
  echo "目前選擇的 worker virtualenv (${WORKER_VENV_DIR}) 沒有安裝 marker-pdf，無法使用 PDF_PARSER_PROVIDER=marker。" >&2
  echo "建議指令：" >&2
  echo "  uv venv ${MARKER_WORKER_VENV_DIR} --python 3.12" >&2
  echo "  uv pip install --python ${MARKER_WORKER_VENV_DIR}/bin/python -e '${REPO_ROOT}/apps/worker[dev]' 'marker-pdf>=1.9.2,<2.0.0'" >&2
  echo "或者改用 PDF_PARSER_PROVIDER=local / llamaparse。" >&2
  exit 1
fi

if [[ "${MARKER_MODEL_CACHE_DIR}" == /var/cache/* ]]; then
  echo "偵測到 container 專用 MARKER_MODEL_CACHE_DIR=${MARKER_MODEL_CACHE_DIR}，本機 hybrid worker 改用 ${LOCAL_MARKER_CACHE_DIR}。" >&2
  MARKER_MODEL_CACHE_DIR="${LOCAL_MARKER_CACHE_DIR}"
fi

mkdir -p "${MARKER_MODEL_CACHE_DIR}"

echo "啟動 Compose 服務（不含 container worker，會先自動執行 API migration）..."
"${COMPOSE_SCRIPT}" up -d supabase-db redis minio keycloak api-migrate keycloak api web --build

echo "以本機 worker 啟動 Celery..."
echo "  DATABASE_URL=postgresql://${POSTGRES_USER}:***@127.0.0.1:${POSTGRES_PORT}/${POSTGRES_DB}"
echo "  CELERY_BROKER_URL=redis://127.0.0.1:${REDIS_PORT}/0"
echo "  MINIO_ENDPOINT=http://127.0.0.1:${MINIO_PORT}"
echo "  PDF_PARSER_PROVIDER=${PDF_PARSER_PROVIDER}"
echo "  TORCH_DEVICE=${TORCH_DEVICE}"
echo "  MARKER_MODEL_CACHE_DIR=${MARKER_MODEL_CACHE_DIR}"
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
export MARKER_MODEL_CACHE_DIR="${MARKER_MODEL_CACHE_DIR}"
export TORCH_DEVICE="${TORCH_DEVICE}"

exec "${VENV_CELERY}" -A worker.celery_app.celery_app worker --loglevel="${CELERY_LOGLEVEL}" "$@"
