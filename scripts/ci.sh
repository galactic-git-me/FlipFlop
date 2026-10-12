#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

log() { printf '[flipflop-ci] %s\n' "$*"; }

log "Checking environment boundaries"
bash "$ROOT_DIR/scripts/validate-environments.sh"

require_test_database() {
  local variable_name="$1"
  local database_url="${!variable_name:-}"
  local database_name="${database_url##*/}"
  database_name="${database_name%%\?*}"
  if [[ ! "$database_url" =~ ^postgres(ql)?(\+asyncpg)?:// ]] || [[ ! "$database_name" =~ _test$ ]]; then
    log "Refusing database work: $variable_name must be a PostgreSQL URL whose database name ends in _test"
    exit 1
  fi
}

require_test_database DATABASE_URL
require_test_database SYNC_DATABASE_URL

log "Installing API dependencies"
python -m pip install --disable-pip-version-check -q \
  -r "$ROOT_DIR/flipflop-api/requirements.txt" \
  -r "$ROOT_DIR/flipflop-api/requirements-dev.txt"

log "Applying migrations to disposable test database"
(
  cd "$ROOT_DIR/flipflop-api"
  alembic upgrade head
)

log "Running API tests"
(
  cd "$ROOT_DIR/flipflop-api"
  python -m pytest -q
)

log "Building admin"
(
  cd "$ROOT_DIR/flipflop-admin"
  npm ci
  npm run build
)

log "Repository checks passed"
