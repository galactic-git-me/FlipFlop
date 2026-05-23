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
FRONTEND_MODE="${FRONTEND_MODE:-dev}" # dev | prod
BACKEND_TZ="${BACKEND_TZ:-Europe/London}"
LAUNCH_DASHBOARD_WINDOW="${LAUNCH_DASHBOARD_WINDOW:-0}"
ATTACH_TMUX="${ATTACH_TMUX:-1}"
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
}

force_clear_frontend_port() {
  # Kill known Next.js launchers that may not yet show as LISTEN in lsof.
  pkill -f "next dev -p $FRONTEND_PORT" >/dev/null 2>&1 || true
  pkill -f "next start -p $FRONTEND_PORT" >/dev/null 2>&1 || true
  pkill -f "pc-flipper@0.1.0 dev" >/dev/null 2>&1 || true
  pkill -f "pc-flipper@0.1.0 start" >/dev/null 2>&1 || true
  sleep 0.3
  free_port "$FRONTEND_PORT"
}

start_frontend_with_retry() {
  local attempt=1
  local max_attempts=3
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

    return 0
  done

  echo "Frontend failed to bind port $FRONTEND_PORT after $max_attempts attempts."
  return 1
}

start_frontend_with_retry || exit 1

sleep 1

open_tmux_logs() {
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

table = Table(title="Scheduler", expand=True)
table.add_column("Job", style="bold cyan")
table.add_column("Search Terms", style="yellow")
table.add_column("Last", justify="right")
table.add_column("Status", style="magenta")

for j in rows:
    jid = str(j.get("id", ""))
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
    elif jid == "autonomous_cycle":
        term = "multi-source cycle"
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
        st = "[green]success[/green]"
    elif st_raw == "running":
        st = "[yellow]running[/yellow]"
    elif st_raw == "skipped":
        st = "[red]skipped[/red]"
    elif st_raw in {"failed", "error"}:
        st = f"[red]{st_raw}[/red]"
    elif st_raw in {"—", "", "None", "null"}:
        st = "[red]no data[/red]"
    else:
        st = st_raw

    table.add_row(jid, term, last, st)

console.clear()
console.print(Panel(table, border_style="bright_blue"))
PY
    sleep 2
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
    elif jid == "autonomous_cycle":
        term = "multi-source cycle"
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

    print(f"{jid:30} {term[:28]:28} {str(last)[:28]:28} {st}")
PY
    sleep 2
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
  printf "  \e]8;;http://$PUBLIC_HOST:$FRONTEND_PORT\ahttp://$PUBLIC_HOST:$FRONTEND_PORT\e]8;;\a\n"
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

total = int(stats.get("total_listings") or demand.get("total_listings") or 0)
gems = int(stats.get("gems_count") or demand.get("total_gems") or 0)
avg_profit = float(stats.get("avg_profit") or 0.0)
gem_rate = float(demand.get("gem_rate_pct") or 0.0)
running = bool(scan.get("running"))
done = int(scan.get("completed") or 0)
scan_total = int(scan.get("total") or 0)
live_found = int(scan.get("total_found") or 0)
live_gems = int(scan.get("total_gems") or 0)

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
print(f"  scan: {'running' if running else 'idle'}   progress: {done}/{scan_total}   found: {live_found}   live-gems: {live_gems}")
print(f"  next scan: [{bar}]  T-{remain_txt}")
PY
  sleep 2
done
EOF
  chmod +x "$title_pane_script"

  local terms_pane_script="$LOG_DIR/terms-pane-$BACKEND_PORT.sh"
  cat >"$terms_pane_script" <<EOF
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

base_url = "http://$PUBLIC_HOST:$BACKEND_PORT"
console = Console()

keywords = []
schedule_rows = []
items = []
try:
    with urllib.request.urlopen(f"{base_url}/api/config/search", timeout=4) as r:
        cfg = json.load(r) or {}
    keywords = [str(k).strip() for k in (cfg.get("keywords") or []) if str(k).strip()]

    with urllib.request.urlopen(f"{base_url}/api/schedule", timeout=4) as r:
        schedule_rows = json.load(r) or []

    with urllib.request.urlopen(f"{base_url}/api/search-telemetry/recent", timeout=4) as r:
        payload = json.load(r) or {}
    items = payload.get("items", []) or []
except Exception:
    keywords, schedule_rows, items = [], [], []

def prioritize_ebay_terms(seq):
    patterns = [
        "motherboard cpu combo",
        "motherboard bundle",
        "cpu motherboard bundle",
        "pc build",
        "pc base unit",
        "desktop pc",
        "pc tower",
        "gaming pc",
    ]
    required = ["AMD Ryzen 7 7800X3D", "Ryzen 9 7900", "Ryzen 9 7900X"]
    out, seen = [], set()
    for t in required:
        k = t.lower()
        if k not in seen:
            seen.add(k); out.append(t)
    for p in patterns:
        for t in seq:
            k = t.lower()
            if k in seen:
                continue
            if p in k:
                seen.add(k); out.append(t)
    for t in seq:
        k = t.lower()
        if k not in seen:
            seen.add(k); out.append(t)
    return out

keywords = prioritize_ebay_terms(keywords)

table = Table(title="Search Terms", expand=True)
table.add_column("Term", style="yellow")
table.add_column("Status")
table.add_column("When", justify="right")
table.add_column("Result", justify="right")

flip_job = next((j for j in schedule_rows if str((j or {}).get("id")) == "flip_opportunities"), {})
run_started = parse_iso((flip_job or {}).get("last_run_at"))
run_status = str((flip_job or {}).get("last_status") or "—")

term_state = {}  # term -> (status, ts, result)
for it in items:
    src = str((it or {}).get("source") or "")
    # Focus queue on flip-opportunity eBay terms.
    if src not in {"eBay UK", "eBay UK Auctions"}:
        continue
    term = str((it or {}).get("term") or "").strip()
    if not term:
        continue
    ts = parse_iso((it or {}).get("ts"))
    if run_started and ts and ts < run_started:
        continue
    err = str((it or {}).get("error") or "").strip()
    found = int((it or {}).get("found") or 0)
    new = int((it or {}).get("new") or 0)
    prev = term_state.get(term)
    # Prefer success over error for a term in same run.
    if err and prev and prev[0] == "done":
        continue
    st = "retry later" if err else "done"
    term_state[term] = (st, (it or {}).get("ts"), f"{found}/{new}")

if keywords:
    pending_terms = []
    for term in keywords:
        st = term_state.get(term)
        if st and st[0] == "done":
            continue
        pending_terms.append(term)
    for term in pending_terms[:36]:
        st = term_state.get(term)
        if st and st[0] == "done":
            status = "[green]done[/green]"
            when = age(st[1])
            result = st[2]
        elif st and st[0] == "retry later":
            status = "[red]retry later[/red]"
            when = age(st[1])
            result = st[2]
        else:
            status = "[yellow]pending[/yellow]" if run_status == "running" else "[cyan]waiting next run[/cyan]"
            when = "—"
            result = "—"
        table.add_row(
            term[:54],
            status,
            when,
            result,
        )
else:
    table.add_row("No search config keywords", "[red]no data[/red]", "—", "—")

console.clear()
console.print(Panel(table, border_style="green"))
PY
    sleep 2
  done
else
  while true; do
    clear
    echo "Search Terms"
    python3 - <<'PY'
import json
import urllib.request
from datetime import datetime, timezone

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

base_url = "http://$PUBLIC_HOST:$BACKEND_PORT"
keywords, schedule_rows, items = [], [], []
try:
    with urllib.request.urlopen(f"{base_url}/api/config/search", timeout=4) as r:
        cfg = json.load(r) or {}
    keywords = [str(k).strip() for k in (cfg.get("keywords") or []) if str(k).strip()]

    with urllib.request.urlopen(f"{base_url}/api/schedule", timeout=4) as r:
        schedule_rows = json.load(r) or []

    with urllib.request.urlopen(f"{base_url}/api/search-telemetry/recent", timeout=4) as r:
        payload = json.load(r) or {}
    items = payload.get("items", []) or []
except Exception:
    keywords, schedule_rows, items = [], [], []

def prioritize_ebay_terms(seq):
    patterns = [
        "motherboard cpu combo",
        "motherboard bundle",
        "cpu motherboard bundle",
        "pc build",
        "pc base unit",
        "desktop pc",
        "pc tower",
        "gaming pc",
    ]
    required = ["AMD Ryzen 7 7800X3D", "Ryzen 9 7900", "Ryzen 9 7900X"]
    out, seen = [], set()
    for t in required:
        k = t.lower()
        if k not in seen:
            seen.add(k); out.append(t)
    for p in patterns:
        for t in seq:
            k = t.lower()
            if k in seen:
                continue
            if p in k:
                seen.add(k); out.append(t)
    for t in seq:
        k = t.lower()
        if k not in seen:
            seen.add(k); out.append(t)
    return out

keywords = prioritize_ebay_terms(keywords)

flip_job = next((j for j in schedule_rows if str((j or {}).get("id")) == "flip_opportunities"), {})
run_started = parse_iso((flip_job or {}).get("last_run_at"))
run_status = str((flip_job or {}).get("last_status") or "—")

term_state = {}
for it in items:
    src = str((it or {}).get("source") or "")
    if src not in {"eBay UK", "eBay UK Auctions"}:
        continue
    term = str((it or {}).get("term") or "").strip()
    if not term:
        continue
    ts = parse_iso((it or {}).get("ts"))
    if run_started and ts and ts < run_started:
        continue
    err = str((it or {}).get("error") or "").strip()
    found = int((it or {}).get("found") or 0)
    new = int((it or {}).get("new") or 0)
    prev = term_state.get(term)
    if err and prev and prev[0] == "done":
        continue
    term_state[term] = ("retry later" if err else "done", (it or {}).get("ts"), f"{found}/{new}")

print(f"{'TERM':42} {'STATUS':16} {'WHEN':>10} {'RESULT':>9}")
print("-" * 84)
pending_terms = []
for term in keywords:
    st = term_state.get(term)
    if st and st[0] == "done":
        continue
    pending_terms.append(term)
for term in pending_terms[:36]:
    st = term_state.get(term)
    if st and st[0] == "done":
        status = "done"
        when = age(st[1])
        result = st[2]
    elif st and st[0] == "retry later":
        status = "retry later"
        when = age(st[1])
        result = st[2]
    else:
        status = "pending" if run_status == "running" else "waiting next"
        when = "—"
        result = "—"
    print(f"{term[:42]:42} {status:16} {when:>10} {result:>9}")
PY
    sleep 2
  done
fi
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
  # - Left: compact FlipFlop ASCII header, then frontend/backend logs
  # - Right: scheduler + search terms
  local left_top_pane right_top_pane left_bottom_pane left_bottom_bottom_pane right_bottom_pane
  left_top_pane="$(tmux new-session -d -P -F "#{pane_id}" -s "$TMUX_SESSION" "bash '$title_pane_script'")"
  right_top_pane="$(tmux split-window -h -P -F "#{pane_id}" -t "$left_top_pane" "bash '$scheduler_pane_script'")"
  # Keep title pane only as tall as needed for ASCII art.
  left_bottom_pane="$(tmux split-window -v -l 78% -P -F "#{pane_id}" -t "$left_top_pane" "bash '$frontend_tail_script'")"
  left_bottom_bottom_pane="$(tmux split-window -v -l 50% -P -F "#{pane_id}" -t "$left_bottom_pane" "bash '$backend_tail_script'")"
  # Give Search Terms 2 extra lines by taking them from Scheduler.
  right_h="$(tmux display-message -p -t "$right_top_pane" "#{pane_height}")"
  right_bottom_lines=$(( right_h / 2 + 2 ))
  right_bottom_pane="$(tmux split-window -v -l "$right_bottom_lines" -P -F "#{pane_id}" -t "$right_top_pane" "bash '$terms_pane_script'")"

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
