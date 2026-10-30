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
require_test_database TEST_DATABASE_URL

log "Checking Codex browser tools"
node --test "$ROOT_DIR/scripts/browser-listing/browser-mcp.test.mjs"

log "Installing API dependencies"
python -m pip install --disable-pip-version-check -q \
  -r "$ROOT_DIR/flipflop-api/requirements.txt" \
  -r "$ROOT_DIR/flipflop-api/requirements-dev.txt"

log "Checking Alembic revision graph"
(
  cd "$ROOT_DIR/flipflop-api"
  heads="$(alembic heads)"
  head_count="$(printf '%s\n' "$heads" | awk 'NF { count += 1 } END { print count + 0 }')"
  if [[ "$head_count" -ne 1 ]]; then
    log "Expected one Alembic head, found $head_count"
    printf '%s\n' "$heads"
    exit 1
  fi
  printf '%s\n' "$heads"
)

log "Initializing disposable test database from current ORM schema"
(
  cd "$ROOT_DIR/flipflop-api"
  python - <<'PY'
import asyncio

import app.models  # noqa: F401 — register every table with SQLAlchemy metadata
from app.database import init_db

asyncio.run(init_db())
PY
)

log "Running API tests"
(
  cd "$ROOT_DIR/flipflop-api"
  if [[ "${FLIPFLOP_CI_FULL_API_TESTS:-0}" == "1" ]]; then
    python -m pytest -q tests
  else
    python -m pytest -q \
      tests/test_browser_listing_jobs.py \
      tests/test_curated_availability_public.py \
      tests/test_curated_build_policy.py \
      tests/test_curated_upgrade_benchmarks.py \
      tests/test_public_playbook_fit.py \
      tests/test_public_catalogue_api.py::test_analytics_event_does_not_trust_caller_customer_id \
      tests/test_production_scheduler_runtime.py
  fi
)

log "Building admin"
(
  cd "$ROOT_DIR/flipflop-admin"
  npm ci
  npm run build
)

log "Building curated storefront"
(
  cd "$ROOT_DIR/FlipFlop.shop.new"
  npm ci
  npm run build
)

log "Repository checks passed"
