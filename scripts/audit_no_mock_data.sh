#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-.}"
cd "$ROOT"

PATTERN='sample_partner_feed|data/sample_|example\\.com/listings'

EXCLUDES=(
  "-g" "!**/tests/**"
  "-g" "!**/test/**"
  "-g" "!**/__pycache__/**"
  "-g" "!**/*.md"
  "-g" "!**/node_modules/**"
  "-g" "!**/.venv/**"
)

set +e
rg -n -S "$PATTERN" pc-flipper pc-flipper-backend "${EXCLUDES[@]}"
STATUS=$?
set -e

if [[ $STATUS -eq 0 ]]; then
  echo "\nAudit failed: mock/sample/dummy feed markers found in non-test code."
  exit 1
fi

if [[ $STATUS -eq 1 ]]; then
  echo "Audit passed: no mock/sample/dummy feed markers in non-test code."
  exit 0
fi

exit $STATUS
