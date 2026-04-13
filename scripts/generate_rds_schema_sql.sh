#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

OUTPUT_FILE="${1:-${SCRIPT_DIR}/rds_schema_latest.sql}"
CONTAINER_NAME="${SCHEMA_EXPORT_CONTAINER_NAME:-servisnow_schema_export_pg}"
PG_IMAGE="${SCHEMA_EXPORT_PG_IMAGE:-postgres:16-alpine}"
PG_HOST_PORT="${SCHEMA_EXPORT_PG_HOST_PORT:-}"
PG_USER="${SCHEMA_EXPORT_PG_USER:-schema_user}"
PG_PASSWORD="${SCHEMA_EXPORT_PG_PASSWORD:-schema_pass}"
PG_DB="${SCHEMA_EXPORT_PG_DB:-servisnow_schema_meta}"
ALEMBIC_HEAD="${SCHEMA_EXPORT_ALEMBIC_HEAD:-q1r2s3t4u5v6}"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required" >&2
  exit 1
fi

if [[ ! -x "${APP_DIR}/venv/bin/python" ]]; then
  echo "Missing virtualenv python at ${APP_DIR}/venv/bin/python" >&2
  exit 1
fi

cleanup() {
  docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true

PORT_ARGS=(-p "127.0.0.1::5432")
if [[ -n "${PG_HOST_PORT}" ]]; then
  PORT_ARGS=(-p "${PG_HOST_PORT}:5432")
fi

docker run -d \
  --name "${CONTAINER_NAME}" \
  -e POSTGRES_USER="${PG_USER}" \
  -e POSTGRES_PASSWORD="${PG_PASSWORD}" \
  -e POSTGRES_DB="${PG_DB}" \
  "${PORT_ARGS[@]}" \
  "${PG_IMAGE}" >/dev/null

if [[ -z "${PG_HOST_PORT}" ]]; then
  PG_HOST_PORT="$(docker port "${CONTAINER_NAME}" 5432/tcp | tail -n 1 | awk -F: '{print $NF}')"
fi

for _ in $(seq 1 30); do
  if docker exec "${CONTAINER_NAME}" pg_isready -U "${PG_USER}" -d "${PG_DB}" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

docker exec "${CONTAINER_NAME}" pg_isready -U "${PG_USER}" -d "${PG_DB}" >/dev/null

(
  cd "${APP_DIR}"
  env \
    ENVIRONMENT=production \
    SECRET_KEY=temp-secret \
    REFRESH_SECRET_KEY=temp-refresh \
    FIRST_SUPERUSER=admin@example.com \
    FIRST_SUPERUSER_PASSWORD=temp-password \
    POSTGRES_USER="${PG_USER}" \
    POSTGRES_PASSWORD="${PG_PASSWORD}" \
    POSTGRES_SERVER=127.0.0.1 \
    POSTGRES_PORT="${PG_HOST_PORT}" \
    POSTGRES_DB="${PG_DB}" \
    REDIS_HOST=localhost \
    REDIS_PORT=6379 \
    venv/bin/python - <<'PY'
import asyncio
from app.database.database import engine, Base
from app.database import models  # noqa: F401


async def main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


asyncio.run(main())
PY
)

docker exec -i "${CONTAINER_NAME}" psql -U "${PG_USER}" -d "${PG_DB}" -v ON_ERROR_STOP=1 <<SQL
CREATE INDEX IF NOT EXISTS ix_organizations_type ON organizations (type);
CREATE INDEX IF NOT EXISTS ix_organizations_name ON organizations (name);
CREATE INDEX IF NOT EXISTS ix_contracts_school_org_id ON school_company_contracts (school_org_id);
CREATE INDEX IF NOT EXISTS ix_contracts_company_org_id ON school_company_contracts (company_org_id);
CREATE INDEX IF NOT EXISTS ix_contracts_is_active ON school_company_contracts (is_active);
CREATE UNIQUE INDEX IF NOT EXISTS ix_absences_student_date ON absences (student_id, absence_date);
CREATE INDEX IF NOT EXISTS ix_bus_locations_bus_id_timestamp ON bus_locations (bus_id, timestamp);
CREATE INDEX IF NOT EXISTS ix_bus_locations_timestamp ON bus_locations (timestamp);
CREATE INDEX IF NOT EXISTS ix_attendance_logs_student_id_log_time ON attendance_logs (student_id, log_time);
CREATE INDEX IF NOT EXISTS ix_attendance_logs_bus_id ON attendance_logs (bus_id);
CREATE INDEX IF NOT EXISTS ix_notifications_recipient_id_created_at ON notifications (recipient_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_notifications_recipient_unread ON notifications (recipient_id, is_read) WHERE is_read = false;
CREATE INDEX IF NOT EXISTS ix_parent_student_relations_parent_id ON parent_student_relations (parent_id);
CREATE INDEX IF NOT EXISTS ix_parent_student_relations_student_id ON parent_student_relations (student_id);
CREATE INDEX IF NOT EXISTS ix_student_bus_assignments_student_id ON student_bus_assignments (student_id);
CREATE INDEX IF NOT EXISTS ix_student_bus_assignments_bus_id ON student_bus_assignments (bus_id);
CREATE INDEX IF NOT EXISTS ix_buses_school_id ON buses (school_id);
CREATE INDEX IF NOT EXISTS ix_users_id_organization_id ON users (id, organization_id);
CREATE TABLE IF NOT EXISTS alembic_version (
  version_num VARCHAR(32) NOT NULL PRIMARY KEY
);
DELETE FROM alembic_version;
INSERT INTO alembic_version (version_num) VALUES ('${ALEMBIC_HEAD}');
SQL

docker exec "${CONTAINER_NAME}" pg_dump -s --no-owner --no-privileges -U "${PG_USER}" -d "${PG_DB}" > "${OUTPUT_FILE}"

cat <<SQL >> "${OUTPUT_FILE}"

--
-- Name: alembic_version bootstrap row; Type: DATA; Schema: public; Owner: -
--

INSERT INTO public.alembic_version (version_num) VALUES ('${ALEMBIC_HEAD}');
SQL

echo "Schema SQL exported to ${OUTPUT_FILE}"
