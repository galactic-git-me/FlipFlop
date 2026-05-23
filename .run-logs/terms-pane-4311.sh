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

base_url = "http://andromeda-ts:4311"
console = Console()
items = []
try:
    with urllib.request.urlopen(f"{base_url}/api/search-telemetry/recent", timeout=4) as r:
        payload = json.load(r) or {}
    items = payload.get("items", []) or []
except Exception:
    items = []

table = Table(title="Search Terms", expand=True)
table.add_column("Source", style="bold cyan")
table.add_column("Term", style="yellow")
table.add_column("Found/New", justify="right")
table.add_column("When", justify="right")
table.add_column("Status")

if items:
    for it in items[:24]:
        err = str((it or {}).get("error") or "")
        status = "[red]error[/red]" if err else "[green]ok[/green]"
        table.add_row(
            str((it or {}).get("source") or "—"),
            str((it or {}).get("term") or "—")[:54],
            f"{int((it or {}).get('found') or 0)}/{int((it or {}).get('new') or 0)}",
            age((it or {}).get("ts")),
            status,
        )
else:
    table.add_row("—", "No telemetry yet", "—", "—", "—")

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

base_url = "http://andromeda-ts:4311"
items = []
try:
    with urllib.request.urlopen(f"{base_url}/api/search-telemetry/recent", timeout=4) as r:
        payload = json.load(r) or {}
    items = payload.get("items", []) or []
except Exception:
    items = []

print(f"{'SOURCE':30} {'TERM':42} {'F/N':>7} {'WHEN':>10} STATUS")
print("-" * 102)
for it in items[:24]:
    src = str((it or {}).get("source") or "—")[:30]
    term = str((it or {}).get("term") or "—")[:42]
    fn = f"{int((it or {}).get('found') or 0)}/{int((it or {}).get('new') or 0)}"
    when = age((it or {}).get("ts"))
    status = "error" if (it or {}).get("error") else "ok"
    print(f"{src:30} {term:42} {fn:>7} {when:>10} {status}")
PY
    sleep 2
  done
fi
