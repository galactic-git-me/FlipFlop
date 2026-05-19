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
        dt = datetime.fromisoformat(ts.replace("Z","+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        secs = int((datetime.now(timezone.utc)-dt.astimezone(timezone.utc)).total_seconds())
        if secs < 0:
            return "due"
        m, s = divmod(secs, 60)
        h, m = divmod(m, 60)
        return f"{h}h{m:02d}m" if h else f"{m:02d}m{s:02d}s"
    except Exception:
        return "—"

url = "http://andromeda-ts:4311/api/schedule"
console = Console()
try:
    with urllib.request.urlopen(url, timeout=4) as r:
        rows = json.load(r)
except Exception as e:
    console.clear()
    console.print(Panel(f"[red]schedule unavailable[/red]: {e}", title="Scheduler", border_style="red"))
    rows = []

table = Table(title="Scheduler", expand=True)
table.add_column("Job", style="bold cyan")
table.add_column("En", justify="center")
table.add_column("Next", justify="right", style="yellow")
table.add_column("Last", justify="right", style="blue")
table.add_column("Status", style="magenta")

for j in rows:
    jid = str(j.get("id",""))
    en = "[green]yes[/green]" if j.get("enabled") else "[red]no[/red]"
    nxt = age(j.get("next_run_at"))
    last = age(j.get("last_run_at"))
    st_raw = str(j.get("last_status") or "—")
    if st_raw == "success":
        st = "[green]success[/green]"
    elif st_raw in {"running", "skipped"}:
        st = f"[yellow]{st_raw}[/yellow]"
    elif st_raw in {"failed", "error"}:
        st = f"[red]{st_raw}[/red]"
    else:
        st = st_raw
    table.add_row(jid, en, nxt, last, st)

console.clear()
console.print(Panel(table, border_style="bright_blue"))
PY
    sleep 2
  done
else
  while true; do
    clear
    echo "Scheduler"
    echo "API: http://andromeda-ts:4311/api/schedule"
    echo
    python3 - <<'PY'
import json
import urllib.request
from datetime import datetime, timezone

def age(ts):
    if not ts:
        return "—"
    try:
        dt = datetime.fromisoformat(ts.replace("Z","+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        secs = int((datetime.now(timezone.utc)-dt.astimezone(timezone.utc)).total_seconds())
        if secs < 0:
            return "due"
        m, s = divmod(secs, 60)
        h, m = divmod(m, 60)
        return f"{h}h{m:02d}m" if h else f"{m:02d}m{s:02d}s"
    except Exception:
        return "—"

url = "http://andromeda-ts:4311/api/schedule"
try:
    with urllib.request.urlopen(url, timeout=4) as r:
        rows = json.load(r)
except Exception as e:
    print(f"schedule unavailable: {e}")
    rows = []

print(f"{'JOB':30} {'EN':3} {'NEXT':10} {'LAST':10} STATUS")
print("-"*80)
for j in rows:
    jid = str(j.get("id",""))[:30]
    en = "yes" if j.get("enabled") else "no"
    nxt = age(j.get("next_run_at"))
    last = age(j.get("last_run_at"))
    st = str(j.get("last_status") or "—")
    print(f"{jid:30} {en:3} {nxt:10} {last:10} {st}")
PY
    sleep 2
  done
fi
