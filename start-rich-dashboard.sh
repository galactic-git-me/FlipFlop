#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/pc-flipper-backend"
BACKEND_PORT="${BACKEND_PORT:-4311}"
BASE_URL="${BASE_URL:-http://127.0.0.1:$BACKEND_PORT}"

if [[ -x "$BACKEND_DIR/.venv/bin/python" ]]; then
  PY_BIN="$BACKEND_DIR/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PY_BIN="python3"
else
  echo "Python not found. Install python3 or create backend venv first."
  exit 1
fi

exec "$PY_BIN" "$ROOT_DIR/scripts/rich_dashboard.py" --base-url "$BASE_URL"

