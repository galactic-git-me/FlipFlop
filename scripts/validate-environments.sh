#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fail() { printf '[environment-check] ERROR: %s\n' "$*" >&2; exit 1; }

test -f "$ROOT_DIR/docker-compose.dev.yml" || fail "missing DEV compose file"
test -f "$ROOT_DIR/deploy/andromeda-api.compose.yml" || fail "missing PROD compose file"

# These are deployment invariants, not secret-value checks. They prevent the
# old mode-switching and accidental cross-environment wiring from returning.
grep -q 'ENVIRONMENT: development' "$ROOT_DIR/docker-compose.dev.yml" \
  || fail "DEV compose must declare development environment"
grep -q 'FLIPFLOP_RUNTIME_ENV: live' "$ROOT_DIR/deploy/andromeda-api.compose.yml" \
  || fail "PROD compose must declare live runtime environment"
grep -q 'EBAY_LISTING_ENVIRONMENT: production' "$ROOT_DIR/deploy/andromeda-api.compose.yml" \
  || fail "PROD listing environment must be production"

if grep -nE 'flipflop-production|pcflipper|EBAY_LISTING_ENVIRONMENT: production' "$ROOT_DIR/docker-compose.dev.yml"; then
  fail "DEV compose contains production-only wiring"
fi

if grep -nE 'localhost:4312|localhost:4313' "$ROOT_DIR/deploy/andromeda-api.compose.yml"; then
  fail "PROD compose contains local UI URLs"
fi

printf '[environment-check] OK\n'
