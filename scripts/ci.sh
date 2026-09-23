#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

log() { printf '[flipflop-ci] %s\n' "$*"; }

log "Checking environment boundaries"
bash "$ROOT_DIR/scripts/validate-environments.sh"

log "Installing API dependencies"
python -m pip install --disable-pip-version-check -q \
  -r "$ROOT_DIR/flipflop-api/requirements.txt" \
  -r "$ROOT_DIR/flipflop-api/requirements-dev.txt"

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
