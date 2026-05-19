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
  if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
    return 0
  fi
  if command -v ss >/dev/null 2>&1; then
    ss -ltn "( sport = :$port )" 2>/dev/null | tail -n +2 | grep -q .
    return $?
  fi
  return 1
}

port_pids() {
  local port="$1"
  {
    lsof -t -nP -iTCP:"$port" -sTCP:LISTEN 2>/dev/null || true
    if command -v fuser >/dev/null 2>&1; then
      fuser -n tcp "$port" 2>/dev/null || true
    fi
  } | tr ' ' '\n' | sed '/^$/d' | sort -u
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
  echo "============================================================"
  echo "Frontend URL: http://$PUBLIC_HOST:$FRONTEND_PORT"
  echo "Tailscale URL: $PUBLIC_HOST:$FRONTEND_PORT"
  echo "============================================================"
  if [[ "$FRONTEND_MODE" == "dev" ]]; then
    NEXT_PUBLIC_API_URL="http://$PUBLIC_HOST:$BACKEND_PORT/api" npm run dev -- -p "$FRONTEND_PORT" -H "$FRONTEND_BIND_HOST" &
    _frontend_child=$!
    echo "Tailscale URL (live): $PUBLIC_HOST:$FRONTEND_PORT"
    wait "$_frontend_child"
  else
    NEXT_PUBLIC_API_URL="http://$PUBLIC_HOST:$BACKEND_PORT/api" npm run build
    NEXT_PUBLIC_API_URL="http://$PUBLIC_HOST:$BACKEND_PORT/api" npm run start -- -p "$FRONTEND_PORT" -H "$FRONTEND_BIND_HOST" &
    _frontend_child=$!
    echo "Tailscale URL (live): $PUBLIC_HOST:$FRONTEND_PORT"
    wait "$_frontend_child"
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

  local backend_pane_script="$LOG_DIR/backend-pane-$BACKEND_PORT.sh"
  cat >"$backend_pane_script" <<EOF
#!/usr/bin/env bash
set +e
echo "Backend dashboard (Rich): http://$PUBLIC_HOST:$BACKEND_PORT"
echo "API base: http://$PUBLIC_HOST:$BACKEND_PORT/api"
echo "Backend log file: $BACKEND_LOG"
echo
if [[ -x "$BACKEND_DIR/.venv/bin/python" ]] && "$BACKEND_DIR/.venv/bin/python" -c "from rich.console import Console" >/dev/null 2>&1; then
  "$BACKEND_DIR/.venv/bin/python" "$BACKEND_DIR/scripts/backend_console_dashboard.py" --base-url "http://$PUBLIC_HOST:$BACKEND_PORT"
else
  python3 "$BACKEND_DIR/scripts/backend_console_dashboard.py" --base-url "http://$PUBLIC_HOST:$BACKEND_PORT"
fi
code=\$?
echo
echo "[warn] Rich backend dashboard exited (status: \$code). Falling back to backend logs..."
echo
tail -n 240 -f "$BACKEND_LOG"
EOF
  chmod +x "$backend_pane_script"

  local backend_tail_script="$LOG_DIR/backend-tail-$BACKEND_PORT.sh"
  cat >"$backend_tail_script" <<EOF
#!/usr/bin/env bash
set +e
if python3 -c "from rich.console import Console" >/dev/null 2>&1; then
  python3 "$ROOT_DIR/scripts/rich_tail.py" --title "Backend Logs" --file "$BACKEND_LOG" --lines 180
else
  echo "Backend logs: $BACKEND_LOG"
  echo
  tail -n 240 -f "$BACKEND_LOG"
fi
EOF
  chmod +x "$backend_tail_script"

  local frontend_tail_script="$LOG_DIR/frontend-tail-$FRONTEND_PORT.sh"
  cat >"$frontend_tail_script" <<EOF
#!/usr/bin/env bash
set +e
if python3 -c "from rich.console import Console" >/dev/null 2>&1; then
  python3 "$ROOT_DIR/scripts/rich_tail.py" --title "Frontend Logs" --file "$FRONTEND_LOG" --lines 180
else
  echo "Frontend logs: $FRONTEND_LOG"
  echo
  tail -n 240 -f "$FRONTEND_LOG"
fi
EOF
  chmod +x "$frontend_tail_script"

  local alerts_tail_script="$LOG_DIR/alerts-tail-$BACKEND_PORT.sh"
  cat >"$alerts_tail_script" <<EOF
#!/usr/bin/env bash
set +e
echo "Alerts / Errors (backend + frontend)"
echo "Backend : $BACKEND_LOG"
echo "Frontend: $FRONTEND_LOG"
echo
touch "$BACKEND_LOG" "$FRONTEND_LOG"
tail -n 120 -f "$BACKEND_LOG" "$FRONTEND_LOG" | grep --line-buffered -Ei "error|warn|failed|exception|traceback|critical|429|403"
EOF
  chmod +x "$alerts_tail_script"

  tmux new-session -d -s "$TMUX_SESSION" "bash '$backend_pane_script'"
  tmux split-window -h -t "$TMUX_SESSION":0.0 "bash '$backend_tail_script'"
  tmux split-window -v -t "$TMUX_SESSION":0.0 "bash '$frontend_tail_script'"
  tmux split-window -v -t "$TMUX_SESSION":0.1 "bash '$alerts_tail_script'"
  tmux select-layout -t "$TMUX_SESSION":0 tiled

  echo
  echo "Opening tmux session '$TMUX_SESSION' with 4-pane quadrant layout."
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
echo "Tailscale URL: $PUBLIC_HOST:$FRONTEND_PORT"
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
else
  # A clean exit from wait -n still means one child ended, so print a quick hint.
  if ! kill -0 "$FRONTEND_PID" >/dev/null 2>&1; then
    echo
    echo "Frontend process exited. Check: $FRONTEND_LOG"
  fi
  if ! kill -0 "$BACKEND_PID" >/dev/null 2>&1; then
    echo
    echo "Backend process exited. Check: $BACKEND_LOG"
  fi
fi

cleanup
