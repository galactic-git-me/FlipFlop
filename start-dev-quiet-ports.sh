#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$ROOT_DIR/pc-flipper"
BACKEND_DIR="$ROOT_DIR/pc-flipper-backend"
LOG_DIR="$ROOT_DIR/.run-logs"

# Quieter dev ports (override with env if needed)
FRONTEND_PORT="${FRONTEND_PORT:-4310}"
BACKEND_PORT="${BACKEND_PORT:-4311}"
FRONTEND_BIND_HOST="${FRONTEND_BIND_HOST:-0.0.0.0}"
BACKEND_BIND_HOST="${BACKEND_BIND_HOST:-0.0.0.0}"
PUBLIC_HOST="${PUBLIC_HOST:-andromeda-ts}"
TMUX_SESSION="${TMUX_SESSION:-flipflop-dev-logs}"
FRONTEND_MODE="${FRONTEND_MODE:-prod}" # prod | dev
BACKEND_TZ="${BACKEND_TZ:-Europe/London}"
DB_HOST="${DB_HOST:-127.0.0.1}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-pcflipper}"
DB_USER="${DB_USER:-flipper}"
DB_PASSWORD="${DB_PASSWORD:-flipper}"

mkdir -p "$LOG_DIR"

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1"
    exit 1
  fi
}

port_in_use() {
  local port="$1"
  lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1
}

port_pids() {
  local port="$1"
  lsof -t -nP -iTCP:"$port" -sTCP:LISTEN 2>/dev/null | sort -u
}

free_port() {
  local port="$1"
  if ! port_in_use "$port"; then
    return 0
  fi

  local pids
  pids="$(port_pids "$port" || true)"
  if [[ -z "$pids" ]]; then
    return 0
  fi

  echo "Port $port is in use. Stopping process(es): $pids"
  for pid in $pids; do
    kill "$pid" >/dev/null 2>&1 || true
  done

  sleep 1

  if port_in_use "$port"; then
    pids="$(port_pids "$port" || true)"
    if [[ -n "$pids" ]]; then
      echo "Port $port still busy. Force killing: $pids"
      for pid in $pids; do
        kill -9 "$pid" >/dev/null 2>&1 || true
      done
      sleep 1
    fi
  fi

  if port_in_use "$port"; then
    echo "Failed to free port $port automatically."
    exit 1
  fi
}

require_cmd npm
require_cmd lsof

if ! command -v python3 >/dev/null 2>&1 && ! command -v python >/dev/null 2>&1; then
  echo "Missing required command: python3 (or python)"
  exit 1
fi

free_port "$FRONTEND_PORT"
free_port "$BACKEND_PORT"

start_postgres() {
  if ! command -v docker >/dev/null 2>&1; then
    echo "Docker is required for local Postgres. Install Docker or set DATABASE_URL to an external Postgres."
    exit 1
  fi

  echo "Ensuring local Postgres container is running..."
  (
    cd "$BACKEND_DIR"
    docker compose up -d db >/dev/null
  )

  # Resolve DB container id for health/readiness checks
  local db_cid
  db_cid="$(cd "$BACKEND_DIR" && docker compose ps -q db)"
  if [[ -z "$db_cid" ]]; then
    echo "Could not resolve db container id from docker compose."
    exit 1
  fi

  # Wait for container health (or running) and pg_isready (up to ~90s)
  local attempts=90
  while (( attempts > 0 )); do
    local health status
    health="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$db_cid" 2>/dev/null || true)"
    status="$(docker inspect -f '{{.State.Status}}' "$db_cid" 2>/dev/null || true)"

    if [[ "$health" == "healthy" ]]; then
      return 0
    fi
    if [[ "$status" == "running" ]]; then
      if docker exec "$db_cid" pg_isready -U "$DB_USER" -d "$DB_NAME" >/dev/null 2>&1; then
        return 0
      fi
    fi

    sleep 1
    attempts=$((attempts-1))
  done

  echo "Postgres did not become ready (container status/health/pg_isready failed)."
  echo "Container: $db_cid"
  docker inspect -f 'status={{.State.Status}} health={{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$db_cid" || true
  docker logs --tail 80 "$db_cid" || true
  exit 1
}

start_postgres

PYTHON_BIN="python3"
if [[ -x "$BACKEND_DIR/.venv/bin/python" ]]; then
  PYTHON_BIN="$BACKEND_DIR/.venv/bin/python"
fi

UVICORN_BIN="uvicorn"
if [[ -x "$BACKEND_DIR/.venv/bin/uvicorn" ]]; then
  UVICORN_BIN="$BACKEND_DIR/.venv/bin/uvicorn"
fi

BACKEND_LOG="$LOG_DIR/backend-$BACKEND_PORT.log"
FRONTEND_LOG="$LOG_DIR/frontend-$FRONTEND_PORT.log"

if ! getent hosts "$PUBLIC_HOST" >/dev/null 2>&1; then
  echo "Warning: '$PUBLIC_HOST' does not resolve on this machine right now."
  echo "You can still run locally, but remote/Tailscale hostname links may fail."
fi

echo "Starting backend on http://$PUBLIC_HOST:$BACKEND_PORT ..."
(
  cd "$BACKEND_DIR"
  export DATABASE_URL="postgresql+asyncpg://$DB_USER:$DB_PASSWORD@$DB_HOST:$DB_PORT/$DB_NAME"
  export SYNC_DATABASE_URL="postgresql://$DB_USER:$DB_PASSWORD@$DB_HOST:$DB_PORT/$DB_NAME"
  TZ="$BACKEND_TZ" "$UVICORN_BIN" app.main:app --host "$BACKEND_BIND_HOST" --port "$BACKEND_PORT" --reload
) >"$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!

echo "Starting frontend on http://$PUBLIC_HOST:$FRONTEND_PORT ..."
(
  cd "$FRONTEND_DIR"
  if [[ "$FRONTEND_MODE" == "dev" ]]; then
    NEXT_PUBLIC_API_URL="http://$PUBLIC_HOST:$BACKEND_PORT/api" npm run dev -- -p "$FRONTEND_PORT" -H "$FRONTEND_BIND_HOST"
  else
    NEXT_PUBLIC_API_URL="http://$PUBLIC_HOST:$BACKEND_PORT/api" npm run build
    NEXT_PUBLIC_API_URL="http://$PUBLIC_HOST:$BACKEND_PORT/api" npm run start -- -p "$FRONTEND_PORT" -H "$FRONTEND_BIND_HOST"
  fi
) >"$FRONTEND_LOG" 2>&1 &
FRONTEND_PID=$!

sleep 1

open_tmux_logs() {
  if ! command -v tmux >/dev/null 2>&1; then
    echo "tmux not found; skipping split-log view. Install tmux to enable auto split panes."
    return 0
  fi

  if tmux has-session -t "$TMUX_SESSION" 2>/dev/null; then
    tmux kill-session -t "$TMUX_SESSION"
  fi

  tmux new-session -d -s "$TMUX_SESSION" "bash -lc 'echo Backend logs: $BACKEND_LOG; echo; tail -n 120 -f \"$BACKEND_LOG\"'"
  tmux split-window -h -t "$TMUX_SESSION" "bash -lc 'echo Frontend logs: $FRONTEND_LOG; echo; tail -n 120 -f \"$FRONTEND_LOG\"'"
  tmux select-layout -t "$TMUX_SESSION" even-horizontal

  echo
  echo "Opening tmux session '$TMUX_SESSION' with split panes (backend | frontend logs)."
  echo "Detach with Ctrl+b then d to return."
  if [[ -t 1 ]]; then
    tmux attach -t "$TMUX_SESSION" || true
  else
    echo "No interactive TTY detected; skipping auto-attach."
    echo "Attach manually with: tmux attach -t $TMUX_SESSION"
  fi
}

_cleaned_up=0
cleanup() {
  if [[ "$_cleaned_up" -eq 1 ]]; then
    return 0
  fi
  _cleaned_up=1
  echo
  echo "Stopping services..."
  kill "$FRONTEND_PID" >/dev/null 2>&1 || true
  kill "$BACKEND_PID" >/dev/null 2>&1 || true
  wait "$FRONTEND_PID" >/dev/null 2>&1 || true
  wait "$BACKEND_PID" >/dev/null 2>&1 || true
  if command -v tmux >/dev/null 2>&1 && tmux has-session -t "$TMUX_SESSION" 2>/dev/null; then
    tmux kill-session -t "$TMUX_SESSION" >/dev/null 2>&1 || true
  fi
}

trap cleanup INT TERM

echo
echo "Frontend: http://$PUBLIC_HOST:$FRONTEND_PORT"
echo "Backend : http://$PUBLIC_HOST:$BACKEND_PORT"
echo "API base: http://$PUBLIC_HOST:$BACKEND_PORT/api"
echo "Mode    : $FRONTEND_MODE"
echo
echo "Logs:"
echo "  $FRONTEND_LOG"
echo "  $BACKEND_LOG"
echo
echo "Press Ctrl+C to stop both."

open_tmux_logs

set +e
wait -n "$FRONTEND_PID" "$BACKEND_PID"
EXIT_CODE=$?
set -e

if [[ $EXIT_CODE -ne 0 ]]; then
  echo
  echo "One of the services exited unexpectedly."
  echo "Check logs:"
  echo "  $FRONTEND_LOG"
  echo "  $BACKEND_LOG"
fi

cleanup
