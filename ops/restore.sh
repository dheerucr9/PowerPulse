#!/usr/bin/env bash
# Solar Platform — Postgres restore
# Usage: ./ops/restore.sh [BACKUP_FILE|latest]
# Restores into a running db container. Stops api/worker during restore.
# Env: POSTGRES_USER POSTGRES_DB BACKUP_DIR

set -euo pipefail

: "${POSTGRES_USER:=solar}"
: "${POSTGRES_DB:=solar}"
: "${BACKUP_DIR:=}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
COMPOSE_FILE="${PROJECT_ROOT}/docker-compose.yml"
COMPOSE=(docker compose --project-directory "${PROJECT_ROOT}" -f "${COMPOSE_FILE}")

if [[ -z "${BACKUP_DIR}" ]]; then
  BACKUP_DIR="${PROJECT_ROOT}/backups"
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker CLI is required for restore operations." >&2
  exit 1
fi

if [[ ! -f "${COMPOSE_FILE}" ]]; then
  echo "ERROR: docker-compose.yml not found at ${COMPOSE_FILE}" >&2
  exit 1
fi

ARG="${1:-latest}"

# Find the backup file
if [[ "${ARG}" == "latest" ]]; then
  BACKUP_FILE=$(python3 -c 'import glob, os, sys; files=[]; [files.extend(glob.glob(p)) for p in sys.argv[1:]]; print(max(files, key=os.path.getmtime) if files else "")' "${BACKUP_DIR}/solar_${POSTGRES_DB}_*.dump" "${BACKUP_DIR}/solar_${POSTGRES_DB}_*.sql.gz")
  if [[ -z "${BACKUP_FILE}" ]]; then
    echo "ERROR: No backup files found in ${BACKUP_DIR}" >&2
    exit 1
  fi
elif [[ -f "${ARG}" ]]; then
  BACKUP_FILE="${ARG}"
else
  echo "ERROR: File not found: ${ARG}" >&2
  exit 1
fi

echo "Using backup: ${BACKUP_FILE}"

DB_RUNNING="$("${COMPOSE[@]}" ps --status running --services db 2>/dev/null || true)"
if [[ "${DB_RUNNING}" != "db" ]]; then
  echo "ERROR: db service is not running. Start it with: docker compose up -d db" >&2
  exit 1
fi

if ! "${COMPOSE[@]}" exec -T db pg_isready -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" >/dev/null 2>&1; then
  echo "ERROR: DB not reachable inside db container" >&2
  exit 1
fi

RUNNING_SERVICES=()
if [[ "$("${COMPOSE[@]}" ps --status running --services api 2>/dev/null || true)" == "api" ]]; then
  RUNNING_SERVICES+=(api)
fi
if [[ "$("${COMPOSE[@]}" ps --status running --services worker 2>/dev/null || true)" == "worker" ]]; then
  RUNNING_SERVICES+=(worker)
fi

if [[ "${#RUNNING_SERVICES[@]}" -gt 0 ]]; then
  echo "Stopping services: ${RUNNING_SERVICES[*]}"
  "${COMPOSE[@]}" stop "${RUNNING_SERVICES[@]}" >/dev/null
fi

RESTORE_OK=0

cleanup() {
  if [[ "${RESTORE_OK}" == "1" && "${#RUNNING_SERVICES[@]}" -gt 0 ]]; then
    echo "Restarting services: ${RUNNING_SERVICES[*]}"
    "${COMPOSE[@]}" start "${RUNNING_SERVICES[@]}" >/dev/null || true
  fi
}
trap cleanup EXIT

echo "Restoring ${POSTGRES_DB}..."
if ! "${COMPOSE[@]}" exec -T db dropdb --if-exists -U "${POSTGRES_USER}" "${POSTGRES_DB}"; then
  echo "ERROR: Failed to drop existing database '${POSTGRES_DB}'" >&2
  exit 1
fi

if ! "${COMPOSE[@]}" exec -T db createdb -U "${POSTGRES_USER}" "${POSTGRES_DB}"; then
  echo "ERROR: Failed to create database '${POSTGRES_DB}'" >&2
  exit 1
fi

if ! "${COMPOSE[@]}" exec -T db psql -v ON_ERROR_STOP=1 -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -c "CREATE EXTENSION IF NOT EXISTS timescaledb" >/dev/null; then
  echo "ERROR: Failed to initialize timescaledb extension in '${POSTGRES_DB}'" >&2
  exit 1
fi

if [[ "${BACKUP_FILE}" == *.dump ]]; then
  if ! "${COMPOSE[@]}" exec -T db pg_restore \
    --exit-on-error \
    --no-owner \
    --no-acl \
    -U "${POSTGRES_USER}" \
    -d "${POSTGRES_DB}" < "${BACKUP_FILE}"; then
    echo "ERROR: Restore failed for ${BACKUP_FILE}" >&2
    exit 1
  fi
elif [[ "${BACKUP_FILE}" == *.sql.gz ]]; then
  if ! gunzip -c "${BACKUP_FILE}" | "${COMPOSE[@]}" exec -T db psql \
    -v ON_ERROR_STOP=1 \
    -U "${POSTGRES_USER}" \
    -d "${POSTGRES_DB}"; then
    echo "ERROR: Restore failed for ${BACKUP_FILE}" >&2
    exit 1
  fi
else
  echo "ERROR: Unsupported backup format: ${BACKUP_FILE} (expected .dump or .sql.gz)" >&2
  exit 1
fi

if ! "${COMPOSE[@]}" run --rm --no-deps api alembic upgrade head >/dev/null; then
  echo "ERROR: Alembic migration reconcile failed after restore" >&2
  exit 1
fi

if ! "${COMPOSE[@]}" exec -T db psql -v ON_ERROR_STOP=1 -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -c "CREATE UNIQUE INDEX IF NOT EXISTS uq_site_power_samples_restore ON site_power_samples (site_id, ts)" >/dev/null; then
  echo "ERROR: Missing runtime uniqueness for site_power_samples (site_id, ts)" >&2
  exit 1
fi

if ! "${COMPOSE[@]}" exec -T db psql -v ON_ERROR_STOP=1 -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -c "CREATE UNIQUE INDEX IF NOT EXISTS uq_panel_power_samples_restore ON panel_power_samples (site_id, panel_id, ts)" >/dev/null; then
  echo "ERROR: Missing runtime uniqueness for panel_power_samples (site_id, panel_id, ts)" >&2
  exit 1
fi

RESTORE_OK=1
echo "Restore complete."
