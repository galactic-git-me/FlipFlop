#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$ROOT_DIR/.run-logs"
PID_FILE="$ROOT_DIR/.start-dev-daemon.pid"
OUT_LOG="$ROOT_DIR/.start-dev-daemon.log"

mkdir -p "$LOG_DIR"

controller_pids() {
  pgrep -f 'bash ./start-dev-quiet-ports.sh' || true
}

is_running() {
  [[ -f "$PID_FILE" ]] || return 1
  local pid
  pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  [[ -n "${pid:-}" ]] || return 1
  kill -0 "$pid" 2>/dev/null
}

cmd_start() {
  # If startup controller already exists, adopt it and don't launch another.
  local existing
  existing="$(controller_pids | head -n1 || true)"
  if [[ -n "${existing:-}" ]]; then
    echo "$existing" > "$PID_FILE"
    echo "Startup controller already running (pid $existing)."
    echo "Log: $OUT_LOG"
    return 0
  fi

  if is_running; then
    echo "Daemon already running (pid $(cat "$PID_FILE"))."
    return 0
  fi

  cd "$ROOT_DIR"
  # Run startup script detached from this shell so child services survive.
  nohup env ENABLE_TMUX_DASHBOARD="${ENABLE_TMUX_DASHBOARD:-1}" ATTACH_TMUX="${ATTACH_TMUX:-0}" bash ./start-dev-quiet-ports.sh >> "$OUT_LOG" 2>&1 < /dev/null &
  local pid=$!
  echo "$pid" > "$PID_FILE"
  sleep 1
  if kill -0 "$pid" 2>/dev/null; then
    echo "Daemon started (pid $pid)."
    echo "Log: $OUT_LOG"
  else
    echo "Daemon failed to start. Check: $OUT_LOG"
    rm -f "$PID_FILE"
    return 1
  fi
}

cmd_stop() {
  if ! is_running; then
    echo "Daemon not running."
    rm -f "$PID_FILE"
    return 0
  fi
  local pid
  pid="$(cat "$PID_FILE")"
  echo "Stopping daemon pid $pid ..."
  kill "$pid" >/dev/null 2>&1 || true
  sleep 2
  if kill -0 "$pid" 2>/dev/null; then
    echo "Force stopping daemon pid $pid ..."
    kill -9 "$pid" >/dev/null 2>&1 || true
  fi
  rm -f "$PID_FILE"

  # Best-effort cleanup of child app processes from this project.
  pkill -f 'next dev --webpack -p 4310 -H 0.0.0.0' >/dev/null 2>&1 || true
  pkill -f 'uvicorn app.main:app --host 0.0.0.0 --port 4311 --reload' >/dev/null 2>&1 || true
  pkill -f 'start-dev-quiet-ports.sh' >/dev/null 2>&1 || true

  echo "Stopped."
}

cmd_status() {
  if is_running; then
    local pid
    pid="$(cat "$PID_FILE")"
    echo "Daemon running (pid $pid)."
  else
    # Clean up stale pid file if process no longer exists.
    rm -f "$PID_FILE"
    echo "Daemon not running."
  fi

  local controllers
  controllers="$(controller_pids | tr '\n' ' ' | xargs || true)"
  if [[ -n "${controllers:-}" ]]; then
    echo "Controller PIDs: $controllers"
  else
    echo "Controller PIDs: none"
  fi
  echo "Relevant processes:"
  pgrep -af 'start-dev-quiet-ports.sh|next dev --webpack -p 4310 -H 0.0.0.0|uvicorn app.main:app --host 0.0.0.0 --port 4311 --reload' || true
}

cmd_logs() {
  touch "$OUT_LOG"
  tail -n 120 -f "$OUT_LOG"
}

case "${1:-start}" in
  start) cmd_start ;;
  stop) cmd_stop ;;
  restart) cmd_stop; cmd_start ;;
  status) cmd_status ;;
  logs) cmd_logs ;;
  *)
    echo "Usage: $0 {start|stop|restart|status|logs}"
    exit 2
    ;;
esac
