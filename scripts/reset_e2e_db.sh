#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
DEV_ENV_DIR="${WORKSPACE_ROOT}/servis_now_dev_env"
COMPOSE_FILE="${E2E_COMPOSE_FILE:-${DEV_ENV_DIR}/docker-compose.dev.yml}"
SEED_FILE="${E2E_SEED_FILE:-${DEV_ENV_DIR}/seed_test_data.sql}"
DB_SERVICE="${E2E_DB_SERVICE:-postgres}"
DB_USER="${E2E_DB_USER:-servis_dev}"
DB_NAME="${E2E_DB_NAME:-servis_dev_db}"
API_HEALTH_URL="${E2E_BASE_URL:-http://localhost:8000}/health"

if [[ ! -f "${COMPOSE_FILE}" ]]; then
  echo "Compose file not found: ${COMPOSE_FILE}" >&2
  exit 1
fi

if [[ ! -f "${SEED_FILE}" ]]; then
  echo "Seed file not found: ${SEED_FILE}" >&2
  exit 1
fi

docker compose -f "${COMPOSE_FILE}" up -d postgres redis backend
docker compose -f "${COMPOSE_FILE}" stop backend

docker compose -f "${COMPOSE_FILE}" exec -T "${DB_SERVICE}" psql -U "${DB_USER}" -d postgres -v ON_ERROR_STOP=1 <<SQL
DROP DATABASE IF EXISTS ${DB_NAME} WITH (FORCE);
CREATE DATABASE ${DB_NAME};
SQL

docker compose -f "${COMPOSE_FILE}" up -d backend

for _ in $(seq 1 30); do
  if curl --fail --silent "${API_HEALTH_URL}" >/dev/null; then
    break
  fi
  sleep 1
done

curl --fail --silent "${API_HEALTH_URL}" >/dev/null
docker compose -f "${COMPOSE_FILE}" exec -T "${DB_SERVICE}" psql -U "${DB_USER}" -d "${DB_NAME}" -v ON_ERROR_STOP=1 < "${SEED_FILE}"

echo "E2E database reset and seeded successfully."
