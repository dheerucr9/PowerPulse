#!/usr/bin/env bash
# Solar Platform — Postgres backup
# Usage: ./ops/backup.sh [BACKUP_DIR]
# Env: POSTGRES_USER POSTGRES_DB BACKUP_DIR BACKUP_RETENTION_DAYS

set -euo pipefail

: "${POSTGRES_USER:=solar}"
: "${POSTGRES_DB:=solar}"
: "${BACKUP_RETENTION_DAYS:=7}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
COMPOSE_FILE="${PROJECT_ROOT}/docker-compose.yml"
COMPOSE=(docker compose --project-directory "${PROJECT_ROOT}" -f "${COMPOSE_FILE}")

BACKUP_DIR="${1:-${BACKUP_DIR:-${PROJECT_ROOT}/backups}}"

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker CLI is required for backup operations." >&2
  exit 1
fi

if [[ ! -f "${COMPOSE_FILE}" ]]; then
  echo "ERROR: docker-compose.yml not found at ${COMPOSE_FILE}" >&2
  exit 1
fi

if [[ ! -d "${BACKUP_DIR}" ]]; then
  echo "ERROR: BACKUP_DIR '${BACKUP_DIR}' does not exist. Create it first:" >&2
  echo "  mkdir -p ${BACKUP_DIR}" >&2
  exit 1
fi

if [[ ! -w "${BACKUP_DIR}" ]]; then
  echo "ERROR: BACKUP_DIR '${BACKUP_DIR}' is not writable." >&2
  exit 1
fi

DB_RUNNING="$("${COMPOSE[@]}" ps --status running --services db 2>/dev/null || true)"
if [[ "${DB_RUNNING}" != "db" ]]; then
  echo "ERROR: db service is not running. Start it with: docker compose up -d db" >&2
  exit 1
fi

if ! "${COMPOSE[@]}" exec -T db pg_isready -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" >/dev/null 2>&1; then
  echo "ERROR: Cannot reach Postgres inside db container. Is db healthy?" >&2
  exit 1
fi

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/solar_${POSTGRES_DB}_${TIMESTAMP}.dump"
LOCK_FILE="${BACKUP_DIR}/.backup_in_progress"

if [[ -f "${LOCK_FILE}" ]]; then
  echo "ERROR: Another backup in progress (${LOCK_FILE} exists)." >&2
  exit 1
fi

trap 'rm -f "${LOCK_FILE}"' EXIT
touch "${LOCK_FILE}"

echo "Backup: ${POSTGRES_DB} -> ${BACKUP_FILE}"

if ! "${COMPOSE[@]}" exec -T db pg_dump \
  -U "${POSTGRES_USER}" \
  -d "${POSTGRES_DB}" \
  --format=custom \
  --no-owner \
  --no-acl \
  2>/dev/null > "${BACKUP_FILE}"; then
  echo "ERROR: Backup failed while dumping database '${POSTGRES_DB}'." >&2
  rm -f "${BACKUP_FILE}"
  exit 1
fi

ARCHIVE_SIZE=$(wc -c < "${BACKUP_FILE}")
if [[ "${ARCHIVE_SIZE}" -lt 1024 ]]; then
  echo "ERROR: Backup file suspiciously small (${ARCHIVE_SIZE} bytes). Removing." >&2
  rm -f "${BACKUP_FILE}"
  exit 1
fi

echo "Done: ${BACKUP_FILE} ($(numfmt --to=iec "${ARCHIVE_SIZE}" 2>/dev/null || echo "${ARCHIVE_SIZE} bytes"))"

CUTOFF=$(date -d "${BACKUP_RETENTION_DAYS} days ago" +%Y%m%d_%H%M%S 2>/dev/null || date -v-${BACKUP_RETENTION_DAYS}d +%Y%m%d_%H%M%S)
for f in "${BACKUP_DIR}"/solar_${POSTGRES_DB}_*.sql.gz; do
  [[ -e "${f}" ]] || continue
  FTS="${f##*/solar_${POSTGRES_DB}_}"
  FTS="${FTS%.sql.gz}"
  if [[ "${FTS}" < "${CUTOFF}" ]]; then
    rm -f "${f}"
    echo "  Removed: ${f}"
  fi
done
for f in "${BACKUP_DIR}"/solar_${POSTGRES_DB}_*.dump; do
  [[ -e "${f}" ]] || continue
  FTS="${f##*/solar_${POSTGRES_DB}_}"
  FTS="${FTS%.dump}"
  if [[ "${FTS}" < "${CUTOFF}" ]]; then
    rm -f "${f}"
    echo "  Removed: ${f}"
  fi
done
