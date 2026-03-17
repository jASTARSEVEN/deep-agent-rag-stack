#!/usr/bin/env bash
# 專案固定的 Docker Compose 入口。
# 目的：無論從哪個工作目錄呼叫，都強制使用 repo 根目錄 `.env`
# 與 `infra/docker-compose.yml`，避免遺漏 `--env-file` 時讓 API key
# 或其他環境變數在 container 內變成空值。

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${REPO_ROOT}/.env"
COMPOSE_FILE="${REPO_ROOT}/infra/docker-compose.yml"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "找不到 ${ENV_FILE}，請先建立根目錄 .env。" >&2
  exit 1
fi

exec docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" "$@"
