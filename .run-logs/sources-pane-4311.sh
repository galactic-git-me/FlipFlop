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
rows = []
try:
    with urllib.request.urlopen(f"{base_url}/api/sources/", timeout=4) as r:
        rows = json.load(r) or []
except Exception:
    rows = []

table = Table(title="Sources", expand=True)
table.add_column("Source", style="bold cyan")
table.add_column("Status")
table.add_column("Found", justify="right")
table.add_column("Last Scan", justify="right")
table.add_column("Error")

if rows:
    for s in rows[:20]:
        st = "enabled" if s.get("enabled") else "disabled"
        st = "[green]enabled[/green]" if s.get("enabled") else "[red]disabled[/red]"
        err = str(s.get("last_error") or "—")
        table.add_row(
            str(s.get("name") or "—"),
            st,
            str(s.get("listings_found_total") or s.get("listings_found") or 0),
            age(s.get("last_scraped_at")),
            err,
        )
else:
    table.add_row("—", "[red]unavailable[/red]", "—", "—", "No source data")

console.clear()
console.print(Panel(table, border_style="magenta"))
PY
    sleep 2
  done
else
  while true; do
    clear
    echo "Sources"
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
rows = []
try:
    with urllib.request.urlopen(f"{base_url}/api/sources/", timeout=4) as r:
        rows = json.load(r) or []
except Exception:
    rows = []

print(f"{'SOURCE':32} {'STATUS':10} {'FOUND':>6} {'LAST':>10} ERROR")
print("-" * 96)
for s in rows[:20]:
    name = str(s.get("name") or "—")[:32]
    st = "enabled" if s.get("enabled") else "disabled"
    found = str(s.get("listings_found_total") or s.get("listings_found") or 0)
    last = age(s.get("last_scraped_at"))
    err = str(s.get("last_error") or "—")
    print(f"{name:32} {st:10} {found:>6} {last:>10} {err}")
PY
    sleep 2
  done
fi
