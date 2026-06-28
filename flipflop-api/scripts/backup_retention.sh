#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DB_PATH="${ROOT_DIR}/pcflipper.db"
BACKUP_DIR="${ROOT_DIR}/backups"
RETENTION_DAYS="${RETENTION_DAYS:-14}"

mkdir -p "${BACKUP_DIR}"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="${BACKUP_DIR}/pcflipper-${TS}.db"

if [[ -f "${DB_PATH}" ]]; then
  cp "${DB_PATH}" "${OUT}"
  gzip -f "${OUT}"
  echo "backup_created=${OUT}.gz"
else
  echo "db_not_found=${DB_PATH}"
fi

find "${BACKUP_DIR}" -type f -name 'pcflipper-*.db.gz' -mtime +"${RETENTION_DAYS}" -print -delete
