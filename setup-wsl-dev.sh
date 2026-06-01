#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/pc-flipper-backend"
FRONTEND_DIR="$ROOT_DIR/pc-flipper"
ROOT_ENV_LOCAL="$ROOT_DIR/.env.local"

START_AFTER_SETUP="${START_AFTER_SETUP:-1}"
if [[ "${1:-}" == "--no-start" ]]; then
  START_AFTER_SETUP="0"
fi

log() {
  printf "[setup] %s\n" "$*"
}

need_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    printf "Missing required command: %s\n" "$1" >&2
    exit 1
  fi
}

install_uv_if_missing() {
  if command -v uv >/dev/null 2>&1; then
    return 0
  fi
  log "uv not found, installing..."
  need_cmd curl
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
  if ! command -v uv >/dev/null 2>&1; then
    printf "uv install completed but uv is not on PATH. Add \$HOME/.local/bin to PATH.\n" >&2
    exit 1
  fi
}

ensure_env_shims() {
  if [[ -f "$ROOT_ENV_LOCAL" ]]; then
    log "Syncing .env shims for backend/frontend from root .env.local..."
    cp "$ROOT_ENV_LOCAL" "$BACKEND_DIR/.env"
    cp "$ROOT_ENV_LOCAL" "$FRONTEND_DIR/.env"
  else
    log "No root .env.local found; skipping .env shim copy."
  fi
}

setup_backend() {
  log "Setting up backend Python environment..."
  cd "$BACKEND_DIR"
  export UV_LINK_MODE=copy
  uv venv
  uv pip install -r requirements.txt
  log "Installing Playwright Chromium..."
  uv run playwright install chromium
}

setup_frontend() {
  log "Installing frontend dependencies..."
  cd "$FRONTEND_DIR"
  npm install --no-audit --no-fund
}

main() {
  need_cmd bash
  need_cmd npm
  install_uv_if_missing
  ensure_env_shims
  setup_backend
  setup_frontend
  cd "$ROOT_DIR"
  if [[ "$START_AFTER_SETUP" == "1" ]]; then
    log "Starting app..."
    ./start-dev-quiet-ports.sh
  else
    log "Setup complete. Start with: ./start-dev-quiet-ports.sh"
  fi
}

main "$@"
