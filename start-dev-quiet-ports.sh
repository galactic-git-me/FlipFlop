#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$ROOT_DIR/pc-flipper"
BACKEND_DIR="$ROOT_DIR/pc-flipper-backend"
LOG_DIR="$ROOT_DIR/.run-logs"
ROOT_ENV_LOCAL="$ROOT_DIR/.env.local"

# Quieter dev ports (override with env if needed)
FRONTEND_PORT="${FRONTEND_PORT:-4310}"
BACKEND_PORT="${BACKEND_PORT:-4311}"
FRONTEND_BIND_HOST="${FRONTEND_BIND_HOST:-0.0.0.0}"
BACKEND_BIND_HOST="${BACKEND_BIND_HOST:-0.0.0.0}"
PUBLIC_HOST="${PUBLIC_HOST:-andromeda-ts}"
TMUX_SESSION="${TMUX_SESSION:-flipflop-dev-logs}"
FRONTEND_MODE="${FRONTEND_MODE:-dev}" # dev | prod
FRONTEND_DEV_BUNDLER="${FRONTEND_DEV_BUNDLER:-webpack}" # webpack | turbo
BACKEND_TZ="${BACKEND_TZ:-Europe/London}"
LAUNCH_DASHBOARD_WINDOW="${LAUNCH_DASHBOARD_WINDOW:-0}"
# Always auto-attach to tmux dashboard for this workflow.
# (Only skipped automatically when no interactive TTY is available.)
ATTACH_TMUX="1"
ENABLE_TMUX_DASHBOARD="${ENABLE_TMUX_DASHBOARD:-1}"
ENABLE_NGROK="${ENABLE_NGROK:-1}"
NGROK_TUNNEL_PORT="${NGROK_TUNNEL_PORT:-$BACKEND_PORT}"
NGROK_API_PORT="${NGROK_API_PORT:-4048}"
NGROK_RESTART_DELAY_SECONDS="${NGROK_RESTART_DELAY_SECONDS:-2}"
DB_HOST="${DB_HOST:-127.0.0.1}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-pcflipper}"
DB_USER="${DB_USER:-flipper}"
DB_PASSWORD="${DB_PASSWORD:-flipper}"
FRONTEND_CONTAINER_PORT="${FRONTEND_CONTAINER_PORT:-3000}"
SCHEDULER_POLL_SECONDS="${SCHEDULER_POLL_SECONDS:-15}"
TERMS_POLL_SECONDS="${TERMS_POLL_SECONDS:-12}"
DEV_CLEAR_DATA_ON_START="${DEV_CLEAR_DATA_ON_START:-1}"
# Global startup mode override (dev|production). Defaults to dev.
STARTUP_MODE="${STARTUP_MODE:-dev}"
REMOTE_CHROME_AUTO_START="${REMOTE_CHROME_AUTO_START:-0}"
REMOTE_CHROME_SSH_USER="${REMOTE_CHROME_SSH_USER:-mclar}"
REMOTE_CHROME_HOST="${REMOTE_CHROME_HOST:-100.84.151.109}"
REMOTE_CHROME_DEBUG_PORT="${REMOTE_CHROME_DEBUG_PORT:-9222}"
REMOTE_CHROME_EXPOSE_PORT="${REMOTE_CHROME_EXPOSE_PORT:-9223}"

mkdir -p "$LOG_DIR"

# Single-instance guard: prevent competing startup controllers.
LOCK_FILE="$LOG_DIR/start-dev-quiet-ports.lock"
if command -v flock >/dev/null 2>&1; then
  exec 9>"$LOCK_FILE"
  if ! flock -n 9; then
    echo "Another start-dev-quiet-ports.sh instance is already running."
    echo "If this is stale, stop that process first and rerun."
    exit 1
  fi
  echo "$$" 1>&9
else
  # Fallback for environments without flock (e.g. Git Bash / some WSL setups).
  if [[ -f "$LOCK_FILE" ]]; then
    existing_pid="$(cat "$LOCK_FILE" 2>/dev/null || true)"
    if [[ -n "${existing_pid:-}" ]] && kill -0 "$existing_pid" >/dev/null 2>&1; then
      echo "Another start-dev-quiet-ports.sh instance is already running (pid $existing_pid)."
      echo "If this is stale, stop that process first and rerun."
      exit 1
    fi
  fi
  echo "$$" >"$LOCK_FILE"
fi

# Attempt to raise open-file limit to reduce Watchpack/EMFILE failures.
maybe_raise_nofile_limit() {
  local target="${NOFILE_TARGET:-65535}"
  local current
  current="$(ulimit -n 2>/dev/null || echo 0)"
  if [[ "$current" =~ ^[0-9]+$ ]] && (( current < target )); then
    ulimit -n "$target" >/dev/null 2>&1 || true
  fi
}

NGROK_SUPERVISOR_PID=""
NGROK_MONITOR_PID=""
NGROK_PUBLIC_URL=""
NGROK_LOG="$LOG_DIR/ngrok-$NGROK_TUNNEL_PORT.log"
NGROK_URL_FILE="$LOG_DIR/ngrok-$NGROK_TUNNEL_PORT.url"
BACKEND_ENV_LOCAL="$ROOT_ENV_LOCAL"
FRONTEND_PID=""
BACKEND_PID=""

COMPOSE_ENV_ARGS=()
if [[ -f "$ROOT_ENV_LOCAL" ]]; then
  COMPOSE_ENV_ARGS=(--env-file "$ROOT_ENV_LOCAL")
fi

DOCKER_COMPOSE_CMD=()
init_docker_compose_cmd() {
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    DOCKER_COMPOSE_CMD=(docker compose)
  elif command -v docker-compose >/dev/null 2>&1; then
    DOCKER_COMPOSE_CMD=(docker-compose)
    # docker-compose v1 can be inconsistent with --env-file in mixed environments.
    COMPOSE_ENV_ARGS=()
  else
    echo "Docker Compose is required (docker compose or docker-compose not found)."
    exit 1
  fi
}

compose() {
  "${DOCKER_COMPOSE_CMD[@]}" "${COMPOSE_ENV_ARGS[@]}" "$@"
}

start_ngrok_supervisor() {
  if [[ "$ENABLE_NGROK" != "1" ]]; then
    return 0
  fi
  if ! command -v ngrok >/dev/null 2>&1; then
    echo "ngrok not found; skipping tunnel auto-start."
    return 0
  fi

  # Ensure single ngrok instance for our chosen web API port.
  pkill -f "ngrok http $NGROK_TUNNEL_PORT.*127.0.0.1:$NGROK_API_PORT" >/dev/null 2>&1 || true
  : >"$NGROK_LOG"

  (
    while true; do
      ngrok http "$NGROK_TUNNEL_PORT" \
        --log=stdout \
        --web-addr="127.0.0.1:$NGROK_API_PORT" \
        >>"$NGROK_LOG" 2>&1 || true
      sleep "$NGROK_RESTART_DELAY_SECONDS"
    done
  ) &
  NGROK_SUPERVISOR_PID=$!
}

refresh_ngrok_url() {
  NGROK_PUBLIC_URL=""
  if [[ "$ENABLE_NGROK" != "1" ]]; then
    return 0
  fi
  if ! command -v curl >/dev/null 2>&1; then
    return 0
  fi

  local attempts=20
  while (( attempts > 0 )); do
    NGROK_PUBLIC_URL="$(
      curl -fsS "http://127.0.0.1:$NGROK_API_PORT/api/tunnels" 2>/dev/null \
        | "$PYTHON_BIN" -c "import sys,json; d=json.load(sys.stdin); ts=d.get('tunnels') or []; print((ts[0].get('public_url') if ts else '').strip())" 2>/dev/null || true
    )"
    if [[ -n "$NGROK_PUBLIC_URL" ]]; then
      printf "%s\n" "$NGROK_PUBLIC_URL" > "$NGROK_URL_FILE"
      break
    fi
    sleep 0.5
    attempts=$((attempts - 1))
  done

  if [[ -n "$NGROK_PUBLIC_URL" && -f "$BACKEND_ENV_LOCAL" ]]; then
    local endpoint="${NGROK_PUBLIC_URL%/}/api/ebay/marketplace-account-deletion"
    if grep -q '^EBAY_NOTIFICATION_ENDPOINT=' "$BACKEND_ENV_LOCAL"; then
      sed -i "s|^EBAY_NOTIFICATION_ENDPOINT=.*|EBAY_NOTIFICATION_ENDPOINT=$endpoint|" "$BACKEND_ENV_LOCAL"
    else
      printf "\nEBAY_NOTIFICATION_ENDPOINT=%s\n" "$endpoint" >> "$BACKEND_ENV_LOCAL"
    fi
  fi
}

start_ngrok_monitor() {
  if [[ "$ENABLE_NGROK" != "1" ]]; then
    return 0
  fi
  if ! command -v curl >/dev/null 2>&1; then
    return 0
  fi
  (
    local last_url=""
    local missed=0
    while true; do
      local cur_url=""
      cur_url="$(
        curl -fsS "http://127.0.0.1:$NGROK_API_PORT/api/tunnels" 2>/dev/null \
          | "$PYTHON_BIN" -c "import sys,json; d=json.load(sys.stdin); ts=d.get('tunnels') or []; print((ts[0].get('public_url') if ts else '').strip())" 2>/dev/null || true
      )"

      if [[ -n "$cur_url" ]]; then
        missed=0
        if [[ "$cur_url" != "$last_url" ]]; then
          last_url="$cur_url"
          printf "%s\n" "$cur_url" > "$NGROK_URL_FILE"
          NGROK_PUBLIC_URL="$cur_url"
          if [[ -f "$BACKEND_ENV_LOCAL" ]]; then
            local endpoint="${cur_url%/}/api/ebay/marketplace-account-deletion"
            if grep -q '^EBAY_NOTIFICATION_ENDPOINT=' "$BACKEND_ENV_LOCAL"; then
              sed -i "s|^EBAY_NOTIFICATION_ENDPOINT=.*|EBAY_NOTIFICATION_ENDPOINT=$endpoint|" "$BACKEND_ENV_LOCAL"
            else
              printf "\nEBAY_NOTIFICATION_ENDPOINT=%s\n" "$endpoint" >> "$BACKEND_ENV_LOCAL"
            fi
          fi
        fi
      else
        missed=$((missed + 1))
        if (( missed >= 6 )); then
          # Force a fresh ngrok child; supervisor loop will bring it back.
          pkill -f "ngrok http $NGROK_TUNNEL_PORT.*127.0.0.1:$NGROK_API_PORT" >/dev/null 2>&1 || true
          missed=0
        fi
      fi
      sleep 3
    done
  ) &
  NGROK_MONITOR_PID=$!
}

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
  lsof -t -nP -iTCP:"$port" -sTCP:LISTEN 2>/dev/null | sed '/^$/d' | sort -u
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

  local attempts=5
  while port_in_use "$port" && (( attempts > 0 )); do
    sleep 0.4
    attempts=$((attempts - 1))
  done

  if port_in_use "$port"; then
    pids="$(port_pids "$port" || true)"
    if [[ -n "$pids" ]]; then
      echo "Port $port still busy. Force killing: $pids"
      for pid in $pids; do
        kill -9 "$pid" >/dev/null 2>&1 || true
      done
      attempts=5
      while port_in_use "$port" && (( attempts > 0 )); do
        sleep 0.4
        attempts=$((attempts - 1))
      done
    fi
  fi

  if port_in_use "$port"; then
    echo "Failed to free port $port automatically."
    exit 1
  fi
}

require_cmd npm
require_cmd lsof
maybe_raise_nofile_limit
init_docker_compose_cmd

if ! command -v python3 >/dev/null 2>&1 && ! command -v python >/dev/null 2>&1; then
  echo "Missing required command: python3 (or python)"
  exit 1
fi

read_env_local_value() {
  local key="$1"
  local file="$2"
  if [[ ! -f "$file" ]]; then
    echo ""
    return 0
  fi
  grep -E "^[[:space:]]*${key}[[:space:]]*=" "$file" 2>/dev/null | tail -n1 | cut -d'=' -f2- | tr -d '"' | tr -d "'" | xargs || true
}

export_root_env_local() {
  if [[ ! -f "$ROOT_ENV_LOCAL" ]]; then
    return 0
  fi
  while IFS= read -r line || [[ -n "$line" ]]; do
    [[ -z "$line" ]] && continue
    [[ "$line" =~ ^[[:space:]]*# ]] && continue
    if [[ "$line" =~ ^[[:space:]]*([A-Za-z_][A-Za-z0-9_]*)[[:space:]]*=(.*)$ ]]; then
      local key="${BASH_REMATCH[1]}"
      local val="${BASH_REMATCH[2]}"
      val="${val%"${val##*[![:space:]]}"}"
      val="${val#"${val%%[![:space:]]*}"}"
      if [[ "$val" =~ ^\".*\"$ ]]; then
        val="${val:1:${#val}-2}"
      elif [[ "$val" =~ ^\'.*\'$ ]]; then
        val="${val:1:${#val}-2}"
      fi
      export "$key=$val"
    fi
  done < "$ROOT_ENV_LOCAL"
}

infer_startup_mode() {
  # Priority:
  # 1) explicit env STARTUP_MODE
  # 2) ROOT .env.local (APP_MODE/ENVIRONMENT/NODE_ENV)
  local explicit="${STARTUP_MODE:-}"
  local mode=""
  if [[ -n "$explicit" ]]; then
    mode="$explicit"
  fi
  if [[ -z "$mode" ]]; then
    mode="$(read_env_local_value "APP_MODE" "$ROOT_ENV_LOCAL")"
  fi
  if [[ -z "$mode" ]]; then
    mode="$(read_env_local_value "ENVIRONMENT" "$ROOT_ENV_LOCAL")"
  fi
  if [[ -z "$mode" ]]; then
    mode="$(read_env_local_value "NODE_ENV" "$ROOT_ENV_LOCAL")"
  fi
  mode="$(echo "${mode:-dev}" | tr '[:upper:]' '[:lower:]')"
  if [[ "$mode" == "prod" ]]; then
    mode="production"
  fi
  if [[ "$mode" != "production" ]]; then
    mode="dev"
  fi
  echo "$mode"
}

maybe_start_remote_chrome_debug() {
  if [[ "$REMOTE_CHROME_AUTO_START" != "1" ]]; then
    return 0
  fi
  if ! command -v ssh >/dev/null 2>&1; then
    echo "REMOTE_CHROME_AUTO_START=1 but ssh is not installed. Skipping remote Chrome launch."
    return 0
  fi

  local ssh_target="${REMOTE_CHROME_SSH_USER}@${REMOTE_CHROME_HOST}"
  echo "Starting remote Chrome debug on $ssh_target ..."
  if ! ssh -o ConnectTimeout=8 -o BatchMode=yes "$ssh_target" \
    "powershell -NoProfile -ExecutionPolicy Bypass -Command \"& { Stop-Process -Name chrome -Force -ErrorAction SilentlyContinue; Start-Process 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe' '--remote-debugging-port=${REMOTE_CHROME_DEBUG_PORT} --remote-debugging-address=127.0.0.1 --user-data-dir=\$env:TEMP\\flipflop-chrome'; Start-Sleep -Seconds 2; netsh interface portproxy delete v4tov4 listenaddress=0.0.0.0 listenport=${REMOTE_CHROME_EXPOSE_PORT} | Out-Null; netsh interface portproxy add v4tov4 listenaddress=0.0.0.0 listenport=${REMOTE_CHROME_EXPOSE_PORT} connectaddress=127.0.0.1 connectport=${REMOTE_CHROME_DEBUG_PORT} }\"" \
    >/dev/null 2>&1; then
    echo "Remote Chrome launch over SSH failed. Continuing startup."
    return 0
  fi

  local cdp_url="http://${REMOTE_CHROME_HOST}:${REMOTE_CHROME_EXPOSE_PORT}/json/version"
  if curl -fsS --max-time 5 "$cdp_url" >/dev/null 2>&1; then
    echo "Remote Chrome debug is reachable at $cdp_url"
  else
    echo "Remote Chrome launched but CDP probe failed at $cdp_url (continuing)."
  fi
}

START_MODE="$(infer_startup_mode)"
echo "Startup mode: $START_MODE"

start_postgres() {
  if ! command -v docker >/dev/null 2>&1; then
    echo "Docker is required for local Postgres. Install Docker or set DATABASE_URL to an external Postgres."
    exit 1
  fi

  echo "Ensuring local Postgres container is running..."
  (
    cd "$BACKEND_DIR"
    compose up -d db >/dev/null
  )

  # Resolve DB container id for health/readiness checks
  local db_cid
  db_cid="$(cd "$BACKEND_DIR" && compose ps -q db)"
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

clear_dev_data_first() {
  if [[ "$DEV_CLEAR_DATA_ON_START" != "1" ]]; then
    return 0
  fi
  echo "DEV mode: clearing local runtime data first..."
  if command -v docker >/dev/null 2>&1; then
    (cd "$BACKEND_DIR" && compose down -v --remove-orphans >/dev/null 2>&1 || true)
    # Frontend compose may require port vars; pass them explicitly.
    (
      cd "$FRONTEND_DIR" && \
      FRONTEND_PORT="$FRONTEND_PORT" FRONTEND_CONTAINER_PORT="$FRONTEND_CONTAINER_PORT" \
      compose down -v --remove-orphans >/dev/null 2>&1 || true
    )
    docker rm -f pc-flipper-web pc-flipper-backend-api-1 pc-flipper-backend-db-1 pc-flipper-backend-redis-1 >/dev/null 2>&1 || true
  fi
  rm -rf "$LOG_DIR"/* "$BACKEND_DIR/data"/*
  mkdir -p "$LOG_DIR" "$BACKEND_DIR/data"
  # Keep sqlite out of dev runs to avoid stale state confusion.
  rm -f "$BACKEND_DIR/pcflipper.db"
}

restart_project_containers_if_running() {
  if ! command -v docker >/dev/null 2>&1; then
    return 0
  fi

  local services=()
  while IFS= read -r svc; do
    [[ -n "$svc" ]] && services+=("$svc")
  done < <(cd "$BACKEND_DIR" && compose config --services 2>/dev/null || true)

  if [[ ${#services[@]} -eq 0 ]]; then
    return 0
  fi

  local running_services=()
  local svc cid status
  for svc in "${services[@]}"; do
    cid="$(cd "$BACKEND_DIR" && compose ps -q "$svc" 2>/dev/null || true)"
    if [[ -z "$cid" ]]; then
      continue
    fi
    status="$(docker inspect -f '{{.State.Status}}' "$cid" 2>/dev/null || true)"
    if [[ "$status" == "running" ]]; then
      running_services+=("$svc")
    fi
  done

  if [[ ${#running_services[@]} -gt 0 ]]; then
    echo "Detected running project containers. Restarting to avoid stale builds: ${running_services[*]}"
    (cd "$BACKEND_DIR" && compose restart "${running_services[@]}" >/dev/null)
  fi
}

project_tree_hash() {
  local dir="$1"
  if [[ ! -d "$dir" ]]; then
    echo ""
    return 0
  fi
  (
    cd "$dir"
    find . -type f \
      -not -path "./.git/*" \
      -not -path "./.venv/*" \
      -not -path "./node_modules/*" \
      -not -path "./.next/*" \
      -not -path "./dist/*" \
      -not -path "./build/*" \
      -print0 \
      | sort -z \
      | xargs -0 sha256sum 2>/dev/null \
      | sha256sum \
      | awk '{print $1}'
  )
}

compose_service_running() {
  local compose_dir="$1"
  local service="$2"
  local cid status
  cid="$(cd "$compose_dir" && compose ps -q "$service" 2>/dev/null || true)"
  if [[ -z "$cid" ]]; then
    return 1
  fi
  status="$(docker inspect -f '{{.State.Status}}' "$cid" 2>/dev/null || true)"
  [[ "$status" == "running" ]]
}

compose_service_buildable() {
  local compose_dir="$1"
  local dockerfile_rel="$2"
  [[ -n "$dockerfile_rel" && -f "$compose_dir/$dockerfile_rel" ]]
}

stop_docker_containers_binding_port() {
  local port="$1"
  if ! command -v docker >/dev/null 2>&1; then
    return 0
  fi

  local ids
  ids="$(
    docker ps --format '{{.ID}} {{.Ports}}' \
      | awk -v p=":${port}->" 'index($0,p){print $1}' \
      | tr '\n' ' '
  )"
  if [[ -n "${ids// }" ]]; then
    echo "Stopping container(s) already bound to host port $port: $ids"
    docker stop $ids >/dev/null 2>&1 || true
  fi
}

smart_refresh_project_containers() {
  if ! command -v docker >/dev/null 2>&1; then
    echo "Docker is required to rebuild project containers."
    exit 1
  fi

  local backend_hash_file="$LOG_DIR/backend-container-tree.sha"
  local frontend_hash_file="$LOG_DIR/frontend-container-tree.sha"
  local backend_prev_hash="" frontend_prev_hash=""
  [[ -f "$backend_hash_file" ]] && backend_prev_hash="$(cat "$backend_hash_file" 2>/dev/null || true)"
  [[ -f "$frontend_hash_file" ]] && frontend_prev_hash="$(cat "$frontend_hash_file" 2>/dev/null || true)"

  local backend_cur_hash frontend_cur_hash
  backend_cur_hash="$(project_tree_hash "$BACKEND_DIR")"
  frontend_cur_hash="$(project_tree_hash "$FRONTEND_DIR")"

  echo "Ensuring backend infra containers are up (db, redis)..."
  (cd "$BACKEND_DIR" && compose up -d db redis >/dev/null)

  local backend_api_buildable="0"
  if compose_service_buildable "$BACKEND_DIR" "Dockerfile"; then
    backend_api_buildable="1"
  fi

  if [[ "$backend_api_buildable" == "1" ]]; then
    stop_docker_containers_binding_port "$BACKEND_PORT"
    free_port "$BACKEND_PORT"
    if [[ -z "$backend_prev_hash" || "$backend_cur_hash" != "$backend_prev_hash" ]]; then
      echo "Backend code changed -> rebuilding api container..."
      (cd "$BACKEND_DIR" && compose up -d --build api >/dev/null)
    else
      if compose_service_running "$BACKEND_DIR" "api"; then
        echo "Backend code unchanged and api is running -> leaving backend container running."
      else
        echo "Backend api not running -> starting api container..."
        (cd "$BACKEND_DIR" && compose up -d api >/dev/null)
      fi
    fi
  else
    echo "Backend api Dockerfile missing -> skipping api container build/start (using local backend process)."
  fi

  local frontend_web_buildable="0"
  if compose_service_buildable "$FRONTEND_DIR" "Dockerfile"; then
    frontend_web_buildable="1"
  fi

  if [[ "$frontend_web_buildable" == "1" ]]; then
    # Avoid "address already in use" on host bind when stale containers/processes hold the port.
    stop_docker_containers_binding_port "$FRONTEND_PORT"
    free_port "$FRONTEND_PORT"
    if [[ -z "$frontend_prev_hash" || "$frontend_cur_hash" != "$frontend_prev_hash" ]]; then
      echo "Frontend code changed -> rebuilding web container..."
      (
          cd "$FRONTEND_DIR"
          FRONTEND_PORT="$FRONTEND_PORT" FRONTEND_CONTAINER_PORT="$FRONTEND_CONTAINER_PORT" \
          NEXT_PUBLIC_API_URL="http://$PUBLIC_HOST:$BACKEND_PORT/api" \
          compose up -d --build web >/dev/null
      )
    else
      if compose_service_running "$FRONTEND_DIR" "web"; then
        echo "Frontend code unchanged -> restarting web container..."
        (
          cd "$FRONTEND_DIR"
          FRONTEND_PORT="$FRONTEND_PORT" FRONTEND_CONTAINER_PORT="$FRONTEND_CONTAINER_PORT" \
          NEXT_PUBLIC_API_URL="http://$PUBLIC_HOST:$BACKEND_PORT/api" \
            compose restart web >/dev/null
        )
      else
        echo "Frontend web not running -> starting web container..."
        (
          cd "$FRONTEND_DIR"
          FRONTEND_PORT="$FRONTEND_PORT" FRONTEND_CONTAINER_PORT="$FRONTEND_CONTAINER_PORT" \
          NEXT_PUBLIC_API_URL="http://$PUBLIC_HOST:$BACKEND_PORT/api" \
            compose up -d web >/dev/null
        )
      fi
    fi
  else
    echo "Frontend web Dockerfile missing -> skipping web container build/start (using local frontend process)."
  fi

  printf "%s\n" "$backend_cur_hash" > "$backend_hash_file"
  printf "%s\n" "$frontend_cur_hash" > "$frontend_hash_file"
}

if [[ "$START_MODE" == "production" ]]; then
  echo "Mode summary: PRODUCTION (Docker app containers enabled)"
  echo "App runtime: api/web in Docker"
  echo "Infra runtime: db/redis in Docker"
  smart_refresh_project_containers
  echo "Production mode: using Docker app containers (api/web)."
  echo "Skipping local uvicorn/npm process launch."
  echo "Backend container port is defined by compose (default 8001->8000)."
  echo "Frontend container port is defined by compose (\$FRONTEND_PORT->\$FRONTEND_CONTAINER_PORT)."
  exit 0
fi

echo "Mode summary: DEV (hot reload enabled)"
echo "App runtime: local uvicorn + local next dev (NO api/web Docker containers)"
echo "Infra runtime: db/redis in Docker"
export_root_env_local
maybe_start_remote_chrome_debug
if [[ "${SHOW_SCRAPER_BROWSER:-0}" =~ ^(1|true|yes)$ ]]; then
  if [[ -z "${DISPLAY:-}" && -z "${WAYLAND_DISPLAY:-}" ]]; then
    echo "SHOW_SCRAPER_BROWSER=1 is set, but no GUI display is available (DISPLAY/WAYLAND_DISPLAY missing)."
    echo "Interactive login/captcha windows cannot be shown in this session."
    echo "Run this script from your desktop terminal session (with DISPLAY set) to get Facebook login windows."
  else
    echo "Interactive scraper browser mode enabled; login/captcha windows will be shown when needed."
  fi
fi

clear_dev_data_first

free_port "$FRONTEND_PORT"
free_port "$BACKEND_PORT"
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
# Reset logs each startup so panes show current run clearly.
: >"$BACKEND_LOG"
: >"$FRONTEND_LOG"

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

# Re-check frontend port immediately before launch to avoid race/EADDRINUSE.
free_port "$FRONTEND_PORT"

echo "Starting frontend on http://$PUBLIC_HOST:$FRONTEND_PORT ..."
start_frontend() {
  local dev_flag="--turbopack"
  if [[ "$FRONTEND_DEV_BUNDLER" == "webpack" ]]; then
    dev_flag="--webpack"
  fi
  (
    cd "$FRONTEND_DIR"
    # Guard against EMFILE from recursive file watching in larger repos.
    export WATCHPACK_POLLING="${WATCHPACK_POLLING:-true}"
    export WATCHPACK_POLLING_INTERVAL="${WATCHPACK_POLLING_INTERVAL:-1000}"
    export CHOKIDAR_USEPOLLING="${CHOKIDAR_USEPOLLING:-1}"
    export CHOKIDAR_INTERVAL="${CHOKIDAR_INTERVAL:-1000}"
    echo "============================================================"
    echo "Frontend URL: http://$PUBLIC_HOST:$FRONTEND_PORT"
    echo "Tailscale URL: $PUBLIC_HOST:$FRONTEND_PORT"
    echo "============================================================"
    if [[ "$FRONTEND_MODE" == "dev" ]]; then
      echo "Tailscale URL (live): $PUBLIC_HOST:$FRONTEND_PORT"
      exec env NEXT_PUBLIC_API_URL="http://$PUBLIC_HOST:$BACKEND_PORT/api" \
        npm run dev -- "$dev_flag" -p "$FRONTEND_PORT" -H "$FRONTEND_BIND_HOST"
    else
      NEXT_PUBLIC_API_URL="http://$PUBLIC_HOST:$BACKEND_PORT/api" npm run build
      echo "Tailscale URL (live): $PUBLIC_HOST:$FRONTEND_PORT"
      exec env NEXT_PUBLIC_API_URL="http://$PUBLIC_HOST:$BACKEND_PORT/api" \
        npm run start -- -p "$FRONTEND_PORT" -H "$FRONTEND_BIND_HOST"
    fi
  ) >"$FRONTEND_LOG" 2>&1 &
  FRONTEND_PID=$!
}

force_clear_frontend_port() {
  # Kill known Next.js launchers that may not yet show as LISTEN in lsof.
  pkill -f "next dev -p $FRONTEND_PORT" >/dev/null 2>&1 || true
  pkill -f "next start -p $FRONTEND_PORT" >/dev/null 2>&1 || true
  pkill -f "node .*next dev .* -p $FRONTEND_PORT" >/dev/null 2>&1 || true
  pkill -f "node .*next start .* -p $FRONTEND_PORT" >/dev/null 2>&1 || true
  pkill -f "$FRONTEND_DIR/node_modules/.bin/next dev .* -p $FRONTEND_PORT" >/dev/null 2>&1 || true
  pkill -f "$FRONTEND_DIR/node_modules/.bin/next start .* -p $FRONTEND_PORT" >/dev/null 2>&1 || true
  pkill -f "pc-flipper@0.1.0 dev" >/dev/null 2>&1 || true
  pkill -f "pc-flipper@0.1.0 start" >/dev/null 2>&1 || true
  sleep 0.3
  free_port "$FRONTEND_PORT"
}

start_frontend_with_retry() {
  local attempt=1
  local max_attempts=3
  local emfile_fallback_used=0
  while (( attempt <= max_attempts )); do
    force_clear_frontend_port
    : >"$FRONTEND_LOG"
    start_frontend
    sleep 1

    if grep -q "EADDRINUSE" "$FRONTEND_LOG" 2>/dev/null; then
      echo "Frontend attempt $attempt/$max_attempts hit EADDRINUSE on $FRONTEND_PORT; retrying..."
      kill "$FRONTEND_PID" >/dev/null 2>&1 || true
      wait "$FRONTEND_PID" >/dev/null 2>&1 || true
      attempt=$((attempt + 1))
      continue
    fi
    if grep -q "EMFILE\\|Watchpack Error (watcher)\\|TurbopackInternalError\\|Too many open files (os error 24)" "$FRONTEND_LOG" 2>/dev/null; then
      echo "Frontend attempt $attempt/$max_attempts hit EMFILE watcher exhaustion."
      kill "$FRONTEND_PID" >/dev/null 2>&1 || true
      wait "$FRONTEND_PID" >/dev/null 2>&1 || true

      if (( emfile_fallback_used == 0 )); then
        echo "Switching frontend to production mode fallback for stability."
        FRONTEND_MODE="prod"
        emfile_fallback_used=1
      fi
      attempt=$((attempt + 1))
      continue
    fi

    return 0
  done

  echo "Frontend failed to bind port $FRONTEND_PORT after $max_attempts attempts."
  return 1
}

start_frontend_with_retry || exit 1

sleep 1
start_ngrok_supervisor
refresh_ngrok_url
start_ngrok_monitor

open_tmux_logs() {
  if [[ "$ENABLE_TMUX_DASHBOARD" != "1" ]]; then
    return 0
  fi
  if ! command -v tmux >/dev/null 2>&1; then
    echo "tmux not found; skipping split-log view. Install tmux to enable auto split panes."
    return 0
  fi

  if tmux has-session -t "$TMUX_SESSION" 2>/dev/null; then
    tmux kill-session -t "$TMUX_SESSION"
  fi

  local scheduler_pane_script="$LOG_DIR/scheduler-pane-$BACKEND_PORT.sh"
  cat >"$scheduler_pane_script" <<EOF
#!/usr/bin/env bash
set +e
if python3 -c "from rich.console import Console" >/dev/null 2>&1; then
  while true; do
    python3 - <<'PY'
import json
import urllib.request
from datetime import datetime, timezone
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

CASES_TOTAL_TERMS = 150
UPGRADE_PARTS_TOTAL_TERMS = 82
FLIP_SOURCE_PREFIXES = ["eBay UK Auctions", "Facebook Marketplace", "BidSpotter"]
FLIP_SOURCE_NAMES = {"eBay UK Auctions", "Facebook Marketplace", "BidSpotter"}

def age(ts):
    if not ts:
        return "—"
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        secs = int((datetime.now(timezone.utc) - dt.astimezone(timezone.utc)).total_seconds())
        secs = max(0, secs)
        m, s = divmod(secs, 60)
        h, m = divmod(m, 60)
        return f"{h}h{m:02d}m{s:02d}s" if h else f"{m:02d}m{s:02d}s"
    except Exception:
        return "—"

def paint_time_tokens(s):
    out = ""
    i = 0
    while i < len(s):
        ch = s[i]
        if ch.isdigit():
            j = i
            while j < len(s) and (s[j].isdigit() or s[j] in {"h", "m", "s", ":"}):
                j += 1
            out += f"[white]{s[i:j]}[/white]"
            i = j
        else:
            out += f"[blue]{ch}[/blue]"
            i += 1
    return out

def completed_since(last_ts):
    if not last_ts:
        return "—"
    a = age(last_ts)
    if a == "—":
        return "—"
    return paint_time_tokens(f"done {a} ago")

def _parse_iso(ts):
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None

def _seconds_since(ts):
    dt = _parse_iso(ts)
    if not dt:
        return 0
    return max(0, int((datetime.now(timezone.utc) - dt).total_seconds()))

def neutral_running_cell(last_ts):
    elapsed = age(last_ts)
    if elapsed == "—":
        return "—"
    return paint_time_tokens(elapsed)

def term_progress_cell(last_ts, source_items, source_prefixes, expected_terms):
    started = _parse_iso(last_ts)
    if not started or expected_terms <= 0:
        return neutral_running_cell(last_ts)

    unique_hits = set()
    for src, rows in (source_items or {}).items():
        src_s = str(src)
        if not any(src_s.startswith(pref) for pref in source_prefixes):
            continue
        for it in rows or []:
            ts = _parse_iso((it or {}).get("ts"))
            if not ts or ts < started:
                continue
            term = str((it or {}).get("term") or "").strip().lower()
            if not term:
                continue
            unique_hits.add((src_s, term))

    # Clamp to expected_terms so retries/duplicates never show > total.
    done = min(len(unique_hits), int(expected_terms))
    pct = min(1.0, max(0.0, done / float(expected_terms)))
    width = 14
    filled = int(round(width * pct))
    bar = f"[cyan]{'█'*filled}[/cyan][dim]{'░'*(width-filled)}[/dim]"
    elapsed = age(last_ts)
    return f"{bar} {paint_time_tokens(elapsed)} [dim]({done}/{expected_terms})[/dim]"

def expected_flip_terms(base_url):
    keywords = []
    enabled_sources = set()
    try:
        with urllib.request.urlopen(f"{base_url}/api/config/search", timeout=4) as r_cfg:
            cfg = json.load(r_cfg) or {}
        keywords = cfg.get("keywords") or []
    except Exception:
        keywords = []

    try:
        with urllib.request.urlopen(f"{base_url}/api/sources", timeout=4) as r_src:
            sources = json.load(r_src) or []
        for src in sources:
            if not src or not src.get("enabled"):
                continue
            name = str(src.get("name") or "")
            if name in FLIP_SOURCE_NAMES:
                enabled_sources.add(name)
    except Exception:
        enabled_sources = set()

    kw_count = max(1, len([k for k in keywords if str(k).strip()]))
    src_count = len(enabled_sources) if enabled_sources else len(FLIP_SOURCE_NAMES)
    return max(1, kw_count * src_count)

base_url = "http://$PUBLIC_HOST:$BACKEND_PORT"
url = f"{base_url}/api/schedule"
console = Console()
try:
    with urllib.request.urlopen(url, timeout=4) as r:
        rows = json.load(r)
except Exception as e:
    console.clear()
    console.print(Panel(f"[red]schedule unavailable[/red]: {e}", title="Scheduler", border_style="red"))
    rows = []

latest_term_by_source = {}
telem_source_items = {}
flip_expected_terms = expected_flip_terms(base_url)
try:
    with urllib.request.urlopen(f"{base_url}/api/search-telemetry/recent", timeout=4) as r2:
        telem_recent = json.load(r2)
    for item in telem_recent.get("items", []):
        src = str((item or {}).get("source") or "")
        if src and src not in latest_term_by_source:
            latest_term_by_source[src] = str((item or {}).get("term") or "—")

    with urllib.request.urlopen(f"{base_url}/api/search-telemetry/by-source", timeout=4) as r3:
        telem_by_source = json.load(r3)
    telem_source_items = dict((telem_by_source or {}).get("items", {}))
except Exception:
    latest_term_by_source = latest_term_by_source or {}
    telem_source_items = {}

sources_health = []
try:
    with urllib.request.urlopen(f"{base_url}/api/sources/health", timeout=4) as rs:
        sh = json.load(rs) or {}
    sources_health = sh.get("items", []) or []
except Exception:
    sources_health = []

flip_source_names = {
    "eBay UK", "eBay UK Auctions", "BidSpotter", "Facebook Marketplace", "Gumtree",
    "Preloved", "Apex Auctions", "Wilsons Auctions", "i-bidder", "John Pye",
    "Amazon", "Alibaba", "AliExpress", "Temu", "BargainHardware", "CherryTree Inc",
}
flip_found_total = 0
flip_error_count = 0
flip_cooldown_count = 0
for s in sources_health:
    name = str((s or {}).get("name") or "")
    if name not in flip_source_names:
        continue
    if not bool((s or {}).get("enabled", False)):
        continue
    flip_found_total += int((s or {}).get("listings_found_last_run") or 0)
    if str((s or {}).get("last_error") or "").strip():
        flip_error_count += 1
    if str((s or {}).get("cooldown_until") or "").strip():
        flip_cooldown_count += 1

table = Table(title="Scheduler", expand=True)
table.add_column("Job", style="bold cyan")
table.add_column("Search Terms", style="yellow")
table.add_column("Last", justify="right")
table.add_column("Status", style="magenta")

for j in rows:
    jid = str(j.get("id", ""))
    if "_cycle" in jid:
        continue
    if jid == "flip_opportunities":
        term = latest_term_by_source.get("eBay UK Auctions") or latest_term_by_source.get("Facebook Marketplace") or latest_term_by_source.get("BidSpotter") or "—"
    elif jid == "upgrade_parts":
        term = latest_term_by_source.get("UpgradeParts:eBay") or latest_term_by_source.get("UpgradeParts:Amazon") or latest_term_by_source.get("UpgradeParts:AliExpress") or "—"
    elif jid == "cases":
        term = latest_term_by_source.get("Cases:eBay") or latest_term_by_source.get("Cases:Amazon") or latest_term_by_source.get("Cases:Temu") or latest_term_by_source.get("Cases:AliExpress") or "—"
    elif jid == "accessories":
        term = latest_term_by_source.get("Accessories:eBay") or latest_term_by_source.get("Accessories:Amazon") or latest_term_by_source.get("Accessories:Temu") or latest_term_by_source.get("Accessories:AliExpress") or "—"
    elif jid == "external_demand":
        term = "demand signals"
    elif jid == "autonomous":
        term = "multi-source run"
    else:
        term = "—"

    st_raw = str(j.get("last_status") or "—")
    if st_raw == "running":
        if jid == "flip_opportunities":
            last = term_progress_cell(j.get("last_run_at"), telem_source_items, FLIP_SOURCE_PREFIXES, flip_expected_terms)
        elif jid == "cases":
            last = term_progress_cell(j.get("last_run_at"), telem_source_items, ["Cases:"], CASES_TOTAL_TERMS)
        elif jid == "upgrade_parts":
            last = term_progress_cell(j.get("last_run_at"), telem_source_items, ["UpgradeParts:"], UPGRADE_PARTS_TOTAL_TERMS)
        else:
            last = neutral_running_cell(j.get("last_run_at"))
    elif st_raw == "skipped":
        last = ""
    else:
        last = completed_since(j.get("last_run_at"))

    if st_raw == "success":
        if jid == "flip_opportunities":
            if flip_found_total <= 0 and flip_error_count > 0:
                st = "[red]error[/red]"
            elif flip_found_total <= 0:
                st = "[red]ran 0[/red]"
            else:
                st = "[green]success[/green]"
        else:
            st = "[green]success[/green]"
    elif st_raw == "running":
        st = "[yellow]running[/yellow]"
    elif st_raw == "skipped":
        st = "[yellow]waiting for next main run[/yellow]"
    elif st_raw in {"failed", "error"}:
        st = f"[red]{st_raw}[/red]"
    elif st_raw in {"—", "", "None", "null"}:
        if jid == "flip_opportunities" and flip_cooldown_count > 0 and flip_found_total <= 0:
            st = "[yellow]cooldown[/yellow]"
        else:
            st = "[yellow]waiting for next main run[/yellow]"
    else:
        st = st_raw

    jid_disp = "components" if jid == "upgrade_parts" else jid
    table.add_row(jid_disp, term, last, st)

console.clear()
console.print(Panel(table, border_style="bright_blue"))
PY
    sleep "$SCHEDULER_POLL_SECONDS"
  done
else
  while true; do
    clear
    echo "Scheduler"
    echo "API: http://$PUBLIC_HOST:$BACKEND_PORT/api/schedule"
    echo
    python3 - <<'PY'
import json
import urllib.request
from datetime import datetime, timezone

CASES_TOTAL_TERMS = 150
UPGRADE_PARTS_TOTAL_TERMS = 82
FLIP_SOURCE_PREFIXES = ["eBay UK Auctions", "Facebook Marketplace", "BidSpotter"]
FLIP_SOURCE_NAMES = {"eBay UK Auctions", "Facebook Marketplace", "BidSpotter"}

def age(ts):
    if not ts:
        return "—"
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        secs = int((datetime.now(timezone.utc) - dt.astimezone(timezone.utc)).total_seconds())
        secs = max(0, secs)
        m, s = divmod(secs, 60)
        h, m = divmod(m, 60)
        return f"{h}h{m:02d}m{s:02d}s" if h else f"{m:02d}m{s:02d}s"
    except Exception:
        return "—"

def completed_since(last_ts):
    if not last_ts:
        return "—"
    a = age(last_ts)
    if a == "—":
        return "—"
    return f"done {a} ago"

def _parse_iso(ts):
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None

def neutral_running_cell(last_ts):
    return age(last_ts)

def term_progress_cell(last_ts, source_items, source_prefixes, expected_terms):
    started = _parse_iso(last_ts)
    if not started or expected_terms <= 0:
        return neutral_running_cell(last_ts)

    unique_hits = set()
    for src, rows in (source_items or {}).items():
        src_s = str(src)
        if not any(src_s.startswith(pref) for pref in source_prefixes):
            continue
        for it in rows or []:
            ts = _parse_iso((it or {}).get("ts"))
            if not ts or ts < started:
                continue
            term = str((it or {}).get("term") or "").strip().lower()
            if not term:
                continue
            unique_hits.add((src_s, term))

    # Clamp to expected_terms so retries/duplicates never show > total.
    done = min(len(unique_hits), int(expected_terms))
    pct = min(1.0, max(0.0, done / float(expected_terms)))
    width = 14
    filled = int(round(width * pct))
    bar = ("#" * filled) + ("-" * (width - filled))
    return f"{bar} {age(last_ts)} ({done}/{expected_terms})"

def expected_flip_terms(base_url):
    keywords = []
    enabled_sources = set()
    try:
        with urllib.request.urlopen(f"{base_url}/api/config/search", timeout=4) as r_cfg:
            cfg = json.load(r_cfg) or {}
        keywords = cfg.get("keywords") or []
    except Exception:
        keywords = []

    try:
        with urllib.request.urlopen(f"{base_url}/api/sources", timeout=4) as r_src:
            sources = json.load(r_src) or []
        for src in sources:
            if not src or not src.get("enabled"):
                continue
            name = str(src.get("name") or "")
            if name in FLIP_SOURCE_NAMES:
                enabled_sources.add(name)
    except Exception:
        enabled_sources = set()

    kw_count = max(1, len([k for k in keywords if str(k).strip()]))
    src_count = len(enabled_sources) if enabled_sources else len(FLIP_SOURCE_NAMES)
    return max(1, kw_count * src_count)

base_url = "http://$PUBLIC_HOST:$BACKEND_PORT"
url = f"{base_url}/api/schedule"
try:
    with urllib.request.urlopen(url, timeout=4) as r:
        rows = json.load(r)
except Exception as e:
    print(f"schedule unavailable: {e}")
    rows = []

latest_term_by_source = {}
telem_source_items = {}
flip_expected_terms = expected_flip_terms(base_url)
try:
    with urllib.request.urlopen(f"{base_url}/api/search-telemetry/recent", timeout=4) as r2:
        telem_recent = json.load(r2)
    for item in telem_recent.get("items", []):
        src = str((item or {}).get("source") or "")
        if src and src not in latest_term_by_source:
            latest_term_by_source[src] = str((item or {}).get("term") or "—")

    with urllib.request.urlopen(f"{base_url}/api/search-telemetry/by-source", timeout=4) as r3:
        telem_by_source = json.load(r3)
    telem_source_items = dict((telem_by_source or {}).get("items", {}))
except Exception:
    latest_term_by_source = latest_term_by_source or {}
    telem_source_items = {}

print(f"{'JOB':30} {'CURRENT TERM SEARCH':28} {'LAST':28} STATUS")
print("-" * 115)
for j in rows:
    jid = str(j.get("id", ""))[:30]
    if "_cycle" in jid:
        continue

    if jid == "flip_opportunities":
        term = latest_term_by_source.get("eBay UK Auctions") or latest_term_by_source.get("Facebook Marketplace") or latest_term_by_source.get("BidSpotter") or "—"
    elif jid == "upgrade_parts":
        term = latest_term_by_source.get("UpgradeParts:eBay") or latest_term_by_source.get("UpgradeParts:Amazon") or latest_term_by_source.get("UpgradeParts:AliExpress") or "—"
    elif jid == "cases":
        term = latest_term_by_source.get("Cases:eBay") or latest_term_by_source.get("Cases:Amazon") or latest_term_by_source.get("Cases:Temu") or latest_term_by_source.get("Cases:AliExpress") or "—"
    elif jid == "accessories":
        term = latest_term_by_source.get("Accessories:eBay") or latest_term_by_source.get("Accessories:Amazon") or latest_term_by_source.get("Accessories:Temu") or latest_term_by_source.get("Accessories:AliExpress") or "—"
    elif jid == "external_demand":
        term = "demand signals"
    elif jid == "autonomous":
        term = "multi-source run"
    else:
        term = "—"

    st = str(j.get("last_status") or "—")
    if st == "running":
        if jid == "flip_opportunities":
            last = term_progress_cell(j.get("last_run_at"), telem_source_items, FLIP_SOURCE_PREFIXES, flip_expected_terms)
        elif jid == "cases":
            last = term_progress_cell(j.get("last_run_at"), telem_source_items, ["Cases:"], CASES_TOTAL_TERMS)
        elif jid == "upgrade_parts":
            last = term_progress_cell(j.get("last_run_at"), telem_source_items, ["UpgradeParts:"], UPGRADE_PARTS_TOTAL_TERMS)
        else:
            last = neutral_running_cell(j.get("last_run_at"))
    elif st == "skipped":
        last = ""
    else:
        last = completed_since(j.get("last_run_at"))

    if st == "success" and jid == "flip_opportunities":
        if flip_found_total <= 0 and flip_error_count > 0:
            st_disp = "error"
        elif flip_found_total <= 0:
            st_disp = "ran 0"
        else:
            st_disp = "success"
    elif st == "skipped":
        st_disp = "waiting for next main run"
    elif st in {"—", "", "None", "null"}:
        if jid == "flip_opportunities" and flip_cooldown_count > 0 and flip_found_total <= 0:
            st_disp = "cooldown"
        else:
            st_disp = "waiting for next main run"
    else:
        st_disp = st

    jid_disp = "components" if jid == "upgrade_parts" else jid
    print(f"{jid_disp:30} {term[:28]:28} {str(last)[:28]:28} {st_disp}")
PY
    sleep "$SCHEDULER_POLL_SECONDS"
  done
fi

EOF
  chmod +x "$scheduler_pane_script"

  local title_pane_script="$LOG_DIR/title-pane.sh"
  cat >"$title_pane_script" <<EOF
#!/usr/bin/env bash
set +e
while true; do
  clear
  cat <<ASCII

  ███████╗██╗     ██╗██████╗ ███████╗██╗      ██████╗ ██████╗
  ██╔════╝██║     ██║██╔══██╗██╔════╝██║     ██╔═══██╗██╔══██╗
  █████╗  ██║     ██║██████╔╝█████╗  ██║     ██║   ██║██████╔╝
  ██╔══╝  ██║     ██║██╔═══╝ ██╔══╝  ██║     ██║   ██║██╔═══╝
  ██║     ███████╗██║██║     ██║     ███████╗╚██████╔╝██║
  ╚═╝     ╚══════╝╚═╝╚═╝     ╚═╝     ╚══════╝ ╚═════╝ ╚═╝

ASCII
  python3 - <<'PY'
import json
import urllib.request
from datetime import datetime, timezone

base = "http://$PUBLIC_HOST:$BACKEND_PORT/api"

def get(path):
    try:
        with urllib.request.urlopen(base + path, timeout=3) as r:
            return json.load(r)
    except Exception:
        return {}

stats = get("/listings/stats") or {}
demand = get("/demand/summary") or {}
scan = get("/swarms/scan/status") or {}
schedule = get("/schedule") or []
taxonomy = get("/source-search-terms") or {}
telem = get("/search-telemetry/by-source?limit=2500") or {}
sources_health = get("/sources/health") or {}

total = int(stats.get("total_listings") or demand.get("total_listings") or 0)
gems = int(stats.get("gems_count") or demand.get("total_gems") or 0)
avg_profit = float(stats.get("avg_profit") or 0.0)
gem_rate = (float(gems) / float(total) * 100.0) if total > 0 else 0.0
running = bool(scan.get("running"))
live_found = int(scan.get("total_found") or 0)
live_gems = int(scan.get("total_gems") or 0)

def normalize_source_name(name: str) -> str:
    n = str(name or "").strip().lower()
    if n in {"ebay", "ebay uk", "ebay (worldwide)"}:
        return "eBay UK"
    if n in {"ebay uk auctions", "ebay auctions"}:
        return "eBay UK Auctions"
    if n in {"amazon", "amazon uk"}:
        return "Amazon"
    if n in {"facebook", "facebook marketplace"}:
        return "Facebook Marketplace"
    if n == "bargainhardware":
        return "BargainHardware"
    return str(name or "").strip()

def telemetry_source_candidates(scope: str, vendor: str) -> list[str]:
    aliases = {
        "eBay": ["eBay UK", "eBay UK Auctions"],
        "Amazon": ["Amazon"],
    }
    names = aliases.get(vendor, [normalize_source_name(vendor)])
    if scope == "cases":
        return [f"Cases:{n}" for n in names]
    if scope == "accessories":
        return [f"Accessories:{n}" for n in names]
    if scope == "upgrade_parts":
        return [f"UpgradeParts:{n}" for n in names]
    return names

def vendor_enabled(vendor: str) -> bool:
    aliases = {
        "eBay": ["eBay UK", "eBay UK Auctions"],
        "Amazon": ["Amazon"],
    }
    options = aliases.get(vendor, [normalize_source_name(vendor)])
    return any(normalize_source_name(o) in enabled_sources for o in options)

enabled_sources = set()
for s in (sources_health.get("items") or []):
    if bool((s or {}).get("enabled", False)):
        enabled_sources.add(normalize_source_name((s or {}).get("name")))

latest = {}
for src, rows in ((telem.get("items") or {}) or {}).items():
    src_n = str(src or "")
    for r in (rows or []):
        t = str((r or {}).get("term") or "").strip().lower()
        if t and (src_n, t) not in latest:
            latest[(src_n, t)] = True

term_items = taxonomy.get("items") or []
term_expected = 0
term_done = 0
for row in term_items:
    if not bool((row or {}).get("enabled", True)):
        continue
    scope = str((row or {}).get("scope") or "").strip()
    term = str((row or {}).get("term") or "").strip().lower()
    if not scope or not term:
        continue
    srcs = [str(x).strip() for x in ((row or {}).get("source_names") or []) if str(x).strip()]
    for vendor in srcs:
        candidates = telemetry_source_candidates(scope, vendor)
        if not vendor_enabled(vendor):
            continue
        term_expected += 1
        if any((cand, term) in latest for cand in candidates):
            term_done += 1

def parse_iso(ts):
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None

flip = next((j for j in schedule if str((j or {}).get("id")) == "flip_opportunities"), {})
last_dt = parse_iso((flip or {}).get("last_run_at"))
next_dt = parse_iso((flip or {}).get("next_run_at"))
now = datetime.now(timezone.utc)
bar = "—"
remain_txt = "—"
if last_dt and next_dt and next_dt > last_dt:
    total = max(1, int((next_dt - last_dt).total_seconds()))
    elapsed = int((now - last_dt).total_seconds())
    elapsed = max(0, min(elapsed, total))
    remain = max(0, int((next_dt - now).total_seconds()))
    pct = elapsed / float(total)
    width = 28
    filled = int(round(width * pct))
    bar = "█" * filled + "░" * (width - filled)
    rm, rs = divmod(remain, 60)
    rh, rm = divmod(rm, 60)
    remain_txt = f"{rh:02d}:{rm:02d}:{rs:02d}"

print("")
print(f"  listings: {total}   gems: {gems}   gem-rate: {gem_rate:.1f}%   avg-profit: £{avg_profit:.0f}")
print(f"  scan: {'running' if running else 'idle'}   progress: {term_done}/{term_expected}   found: {live_found}   live-gems: {live_gems}")
print(f"  next scan: [{bar}]  T-{remain_txt}")
PY
  sleep 8
done
EOF
  chmod +x "$title_pane_script"

  local terms_pane_script="$LOG_DIR/terms-pane-$BACKEND_PORT.sh"
  cat >"$terms_pane_script" <<EOF
#!/usr/bin/env bash
set +e
while true; do
  python3 - <<'PY'
import json
import urllib.request
from datetime import datetime, timezone
import time
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

SCOPES = ["flip_opportunities", "upgrade_parts", "cases", "accessories"]
SCOPE_LABELS = {
    "flip_opportunities": "flip_opportunities",
    "upgrade_parts": "components",
    "cases": "cases",
    "accessories": "accessories",
}
VENDOR_ALIAS = {
    "eBay UK": "eUK",
    "eBay UK Auctions": "eAuc",
    "Facebook Marketplace": "FB",
    "BidSpotter": "BSp",
    "Amazon": "Amz",
    "Temu": "Tem",
    "AliExpress": "AliX",
    "Alibaba": "AliB",
    "BargainHardware": "BHW",
    "eBay": "eB",
    "eBay (Worldwide)": "eBW",
    "CherryTree Inc": "CTI",
}
VENDOR_GROUPS = {
    "eBay": ["eBay", "eBay UK", "eBay (Worldwide)", "eBay UK Auctions"],
    "FBMP": ["Facebook Marketplace"],
    "Others": [
        "Amazon", "Temu", "AliExpress", "Alibaba", "BargainHardware", "CherryTree Inc",
        "Gumtree", "BidSpotter", "Apex Auctions", "Wilsons Auctions", "i-bidder",
        "Preloved", "John Pye", "Manual Submission", "Manual Photo", "Merkandi",
        "Wholesale Clearance UK",
    ],
}
FLIP_SOURCE_PREFIXES = ["eBay UK Auctions", "Facebook Marketplace", "BidSpotter"]
FLIP_SOURCE_NAMES = {
    "eBay UK", "eBay UK Auctions", "BidSpotter", "Facebook Marketplace", "Gumtree",
    "Preloved", "Apex Auctions", "Wilsons Auctions", "i-bidder", "John Pye",
    "Amazon", "Alibaba", "AliExpress", "Temu", "BargainHardware", "CherryTree Inc",
}

base_url = "http://$PUBLIC_HOST:$BACKEND_PORT"
taxonomy_rows = []
try:
    with urllib.request.urlopen(f"{base_url}/api/source-search-terms", timeout=4) as r2:
        t_payload = json.load(r2) or {}
    taxonomy_rows = t_payload.get("items", []) or []
except Exception:
    taxonomy_rows = []

if not taxonomy_rows:
    console = Console()
    console.clear()
    console.print(Panel("[dim]No search terms available[/dim]", title="Search Terms by Catalogue x Vendor", border_style="bright_blue"))
    raise SystemExit(0)

by_scope = {s: [] for s in SCOPES}
vendors_by_scope = {s: set() for s in SCOPES}
for row in taxonomy_rows:
    scope = str((row or {}).get("scope") or "").strip()
    term = str((row or {}).get("term") or "").strip()
    if scope not in by_scope or not term or not bool((row or {}).get("enabled", True)):
        continue
    srcs = [str(x).strip() for x in ((row or {}).get("source_names") or []) if str(x).strip()]
    by_scope[scope].append({
        "term": term,
        "source_names": srcs,
    })
    for s in srcs:
        vendors_by_scope[scope].add(s)

telem_by_source = {}
try:
    with urllib.request.urlopen(f"{base_url}/api/search-telemetry/by-source?limit=2500", timeout=4) as rt:
        telem_by_source = (json.load(rt) or {}).get("items", {}) or {}
except Exception:
    telem_by_source = {}

cfg_keywords = []
try:
    with urllib.request.urlopen(f"{base_url}/api/config/search", timeout=4) as rcfg:
        cfg_keywords = [str(k).strip() for k in ((json.load(rcfg) or {}).get("keywords") or []) if str(k).strip()]
except Exception:
    cfg_keywords = []

enabled_source_names = set()
try:
    with urllib.request.urlopen(f"{base_url}/api/sources/health", timeout=4) as rsh:
        items = (json.load(rsh) or {}).get("items") or []
        for s in items:
            if bool((s or {}).get("enabled", False)):
                enabled_source_names.add(str((s or {}).get("name") or ""))
except Exception:
    enabled_source_names = set()

schedule_rows = []
try:
    with urllib.request.urlopen(f"{base_url}/api/schedule", timeout=4) as rs:
        schedule_rows = json.load(rs) or []
except Exception:
    schedule_rows = []

latest_term_state = {}
for src, rows in (telem_by_source or {}).items():
    for r in rows or []:
        term = str((r or {}).get("term") or "").strip().lower()
        if not term:
            continue
        key = (str(src), term)
        if key not in latest_term_state:
            latest_term_state[key] = r

def classify_cell(item):
    if not item:
        return ""
    err = str((item or {}).get("error") or "").strip().lower()
    found = int((item or {}).get("found") or 0)
    if err:
        if ("retry" in err) or ("blocked" in err) or ("backoff" in err) or ("429" in err):
            return "[yellow]🚦[/yellow]"
        return "[red]✗[/red]"
    if found > 0:
        return f"[green]✓{found}[/green]"
    return "[dim]0[/dim]"

def _cell_state(item):
    if not item:
        return ("blank", 0, 0)
    err = str((item or {}).get("error") or "").strip().lower()
    found = int((item or {}).get("found") or 0)
    saved = int((item or {}).get("new") or 0)
    if err:
        if "chromium_not_installed" in err:
            return ("retry", found, saved)
        if ("retry" in err) or ("blocked" in err) or ("backoff" in err) or ("429" in err):
            return ("retry", found, saved)
        return ("error", found, saved)
    if found > 0:
        return ("success", found, saved)
    return ("zero", 0, saved)

def scope_vendor_sources(scope: str, vendor: str) -> list[str]:
    aliases = {
        "eBay": ["eBay", "eBay UK", "eBay (Worldwide)", "eBay UK Auctions"],
        "Amazon": ["Amazon", "Amazon UK"],
    }
    names = aliases.get(vendor, [vendor])
    if scope == "cases":
        return [f"Cases:{n}" for n in names]
    if scope == "accessories":
        return [f"Accessories:{n}" for n in names]
    if scope == "upgrade_parts":
        return [f"UpgradeParts:{n}" for n in names]
    return names

def scope_runs_progress(scope: str) -> str:
    rows = by_scope.get(scope, []) or []
    if not rows:
        return "0/0 0%"

    expected = 0
    hit = 0
    for row in rows:
        term = str((row or {}).get("term") or "").strip().lower()
        if not term:
            continue
        allowed = [str(x).strip() for x in ((row or {}).get("source_names") or []) if str(x).strip()]
        for vendor in allowed:
            candidates = scope_vendor_sources(scope, vendor)
            base_enabled = False
            if vendor in {"eBay", "eBay UK", "eBay (Worldwide)", "eBay UK Auctions"}:
                base_enabled = ("eBay UK" in enabled_source_names) or ("eBay UK Auctions" in enabled_source_names)
            elif vendor in {"Amazon", "Amazon UK"}:
                base_enabled = "Amazon" in enabled_source_names
            else:
                base_enabled = vendor in enabled_source_names
            if not base_enabled:
                continue
            expected += 1
            if any((c, term) in latest_term_state for c in candidates):
                hit += 1

    expected = max(1, expected)
    pct = int(max(0.0, min(100.0, (100.0 * float(hit) / float(expected)))))
    return f"{hit}/{expected} {pct}%"

def active_term_rows(scope: str, rows: list[dict]) -> list[dict]:
    """Show recent active terms for each catalogue without cycle/cursor state."""
    if not rows:
        return []
    term_to_row = {}
    for r in rows:
        t = str((r or {}).get("term") or "").strip()
        if t and t not in term_to_row:
            term_to_row[t] = r

    prefixes = {
        "flip_opportunities": [""],
        "cases": ["Cases:"],
        "accessories": ["Accessories:"],
        "upgrade_parts": ["UpgradeParts:"],
    }.get(scope, [""])

    ranked = []
    seen = set()
    for src, items in (telem_by_source or {}).items():
        if prefixes != [""] and not any(str(src).startswith(p) for p in prefixes):
            continue
        for it in (items or []):
            term = str((it or {}).get("term") or "").strip()
            if not term or term in seen or term not in term_to_row:
                continue
            seen.add(term)
            ranked.append((str((it or {}).get("ts") or ""), term))

    ranked.sort(reverse=True)
    chosen = [term_to_row[t] for _, t in ranked[:12]]
    if chosen:
        return chosen
    return list(term_to_row.values())[:12]

console = Console()
tbl = Table(expand=True, box=box.SIMPLE_HEAVY, show_lines=False, pad_edge=False)
pane_w = max(80, int(getattr(console.size, "width", 120)))
tbl.add_column("Catalogue", style="bold cyan", no_wrap=True, width=16)
tbl.add_column("Run(5s)", justify="center", no_wrap=True, width=12)
tbl.add_column("Search Term", style="yellow", no_wrap=False, overflow="fold", width=28)
group_names = ["eBay", "FBMP", "Others"]
for g in group_names:
    tbl.add_column(g, justify="center", no_wrap=True, width=12)

for scope in SCOPES:
    rows = by_scope.get(scope, [])
    if not rows:
        continue
    progress = scope_runs_progress(scope)
    term_rows = sorted(active_term_rows(scope, rows), key=lambda r: str(r.get("term") or "").lower())
    first = True
    for r in term_rows:
        term = str(r.get("term") or "").strip()
        allowed = set(r.get("source_names") or [])
        out = [SCOPE_LABELS[scope] if first else "", progress if first else "", term]
        for group in group_names:
            members = VENDOR_GROUPS.get(group, [])
            seen_any = False
            status = "blank"
            total_found = 0
            for v in members:
                if allowed and v not in allowed:
                    continue
                seen_any = True
                candidates = scope_vendor_sources(scope, v)
                for src in candidates:
                    item = latest_term_state.get((src, term.lower()))
                    st, found, saved = _cell_state(item)
                    total_found += max(0, int(found or 0))
                    if st == "error":
                        status = "error"
                    elif st == "retry" and status not in ("error",):
                        status = "retry"
                    elif st == "success" and status not in ("error", "retry"):
                        status = "success"
                    elif st == "zero" and status == "blank":
                        status = "zero"
            if not seen_any:
                out.append("")
            elif status == "error":
                out.append("[red]✗[/red]")
            elif status == "retry":
                out.append("[yellow]🚦[/yellow]")
            elif total_found > 0:
                out.append(f"[green]✓{total_found}[/green]")
            else:
                out.append("[dim]0[/dim]")
        tbl.add_row(*out)
        first = False
    tbl.add_section()

console.clear()
legend = "[green]✓count[/green]=scraped listings  [dim]0[/dim]=searched/none  [red]✗[/red]=error  [yellow]🚦[/yellow]=retry later  blank=not run"
console.print(Panel(tbl, title="Search Terms by Catalogue x Vendor Groups", subtitle=legend, border_style="bright_blue"))
PY
  sleep "$TERMS_POLL_SECONDS"
done
EOF
  chmod +x "$terms_pane_script"

  local backend_tail_script="$LOG_DIR/backend-tail-$BACKEND_PORT.sh"
  cat >"$backend_tail_script" <<EOF
#!/usr/bin/env bash
set +e
if python3 -c "from rich.console import Console" >/dev/null 2>&1; then
  python3 "$ROOT_DIR/scripts/rich_tail.py" --title "Backend Logs" --file "$BACKEND_LOG" --lines 180
else
  echo "Backend logs: $BACKEND_LOG"
  echo
  tail -n 240 -f "$BACKEND_LOG" | sed -u \
    -e 's/\(ERROR\|Error\|error\|FAILED\|failed\)/\x1b[31m&\x1b[0m/g' \
    -e 's/\(WARN\|Warn\|warn\)/\x1b[33m&\x1b[0m/g' \
    -e 's/\(INFO\|Info\|info\)/\x1b[36m&\x1b[0m/g'
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

  # Layout:
  # - Left: compact FlipFlop ASCII header, then scheduler + backend logs
  # - Right: search terms only (full right column height)
  local left_top_pane right_top_pane left_bottom_pane left_bottom_bottom_pane
  left_top_pane="$(tmux new-session -d -P -F "#{pane_id}" -s "$TMUX_SESSION" "bash '$title_pane_script'")"
  right_top_pane="$(tmux split-window -h -P -F "#{pane_id}" -t "$left_top_pane" "bash '$terms_pane_script'")"
  # Keep title pane only as tall as needed for ASCII art.
  left_bottom_pane="$(tmux split-window -v -l 82% -P -F "#{pane_id}" -t "$left_top_pane" "bash '$scheduler_pane_script'")"
  # Give scheduler extra vertical room by shrinking backend log height.
  left_bottom_bottom_pane="$(tmux split-window -v -l 36% -P -F "#{pane_id}" -t "$left_bottom_pane" "bash '$backend_tail_script'")"

  tmux select-window -t "$TMUX_SESSION":0

  echo
  echo "Opening tmux session '$TMUX_SESSION' with 4-pane quadrant layout."
  echo "Detach with Ctrl+b then d to return."
  if [[ "$ATTACH_TMUX" == "1" && -t 1 ]]; then
    tmux attach -t "$TMUX_SESSION" || true
  else
    echo "Skipping auto-attach."
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
  if [[ -n "${FRONTEND_PID:-}" ]]; then
    kill "$FRONTEND_PID" >/dev/null 2>&1 || true
    wait "$FRONTEND_PID" >/dev/null 2>&1 || true
  fi
  if [[ -n "${BACKEND_PID:-}" ]]; then
    kill "$BACKEND_PID" >/dev/null 2>&1 || true
    wait "$BACKEND_PID" >/dev/null 2>&1 || true
  fi
  if [[ -n "${NGROK_MONITOR_PID:-}" ]]; then
    kill "$NGROK_MONITOR_PID" >/dev/null 2>&1 || true
    wait "$NGROK_MONITOR_PID" >/dev/null 2>&1 || true
  fi
  if [[ -n "${NGROK_SUPERVISOR_PID:-}" ]]; then
    kill "$NGROK_SUPERVISOR_PID" >/dev/null 2>&1 || true
    wait "$NGROK_SUPERVISOR_PID" >/dev/null 2>&1 || true
  fi
  pkill -f "ngrok http $NGROK_TUNNEL_PORT.*127.0.0.1:$NGROK_API_PORT" >/dev/null 2>&1 || true
  if command -v tmux >/dev/null 2>&1 && tmux has-session -t "$TMUX_SESSION" 2>/dev/null; then
    tmux kill-session -t "$TMUX_SESSION" >/dev/null 2>&1 || true
  fi
}

trap cleanup EXIT INT TERM

echo
echo "Frontend: http://$PUBLIC_HOST:$FRONTEND_PORT"
echo "Backend : http://$PUBLIC_HOST:$BACKEND_PORT"
echo "API base: http://$PUBLIC_HOST:$BACKEND_PORT/api"
echo "Tailscale URL: $PUBLIC_HOST:$FRONTEND_PORT"
if [[ "$ENABLE_NGROK" == "1" ]]; then
  if [[ -n "$NGROK_PUBLIC_URL" ]]; then
    echo "ngrok   : $NGROK_PUBLIC_URL"
    echo "eBay CB : ${NGROK_PUBLIC_URL%/}/api/ebay/marketplace-account-deletion"
  else
    echo "ngrok   : starting (monitoring on 127.0.0.1:$NGROK_API_PORT)"
  fi
fi
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
