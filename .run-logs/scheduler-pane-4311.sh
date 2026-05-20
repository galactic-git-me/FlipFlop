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

def completed_since(last_ts):
    if not last_ts:
        return "—"
    a = age(last_ts)
    if a == "—":
        return "—"
    return f"completed {a} ago"

def _seconds_since(ts):
    if not ts:
        return 0
    try:
        dt = datetime.fromisoformat(ts.replace("Z","+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        secs = int((datetime.now(timezone.utc)-dt.astimezone(timezone.utc)).total_seconds())
        return max(0, secs)
    except Exception:
        return 0

def running_cell_text(last_ts):
    secs = _seconds_since(last_ts)
    width = 14
    phase = secs % (width + 1)
    filled = min(width, phase)
    bar = ("#"*filled) + ("-"*(width-filled))
    m, s = divmod(secs, 60)
    h, m = divmod(m, 60)
    elapsed = f"{h}h{m:02d}m{s:02d}s" if h else f"{m:02d}m{s:02d}s"
    return f"{bar} {elapsed}"

def _seconds_since(ts):
    if not ts:
        return 0
    try:
        dt = datetime.fromisoformat(ts.replace("Z","+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        secs = int((datetime.now(timezone.utc)-dt.astimezone(timezone.utc)).total_seconds())
        return max(0, secs)
    except Exception:
        return 0

def running_cell(last_ts):
    secs = _seconds_since(last_ts)
    width = 14
    phase = secs % (width + 1)
    filled = min(width, phase)
    bar = f"[cyan]{'█'*filled}[/cyan][dim]{'░'*(width-filled)}[/dim]"
    m, s = divmod(secs, 60)
    h, m = divmod(m, 60)
    elapsed = f"{h}h{m:02d}m{s:02d}s" if h else f"{m:02d}m{s:02d}s"
    return f"{bar} [white]{elapsed}[/white]"

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
table.add_column("Current Term Search", style="yellow")
table.add_column("Last", justify="right")
table.add_column("Status", style="magenta")

latest_term_by_source = {}
try:
    with urllib.request.urlopen("http://andromeda-ts:4311/api/search-telemetry/recent", timeout=4) as r2:
        telem = json.load(r2)
    for item in telem.get("items", []):
        src = str(item.get("source") or "")
        if src and src not in latest_term_by_source:
            latest_term_by_source[src] = str(item.get("term") or "—")
except Exception:
    pass

for j in rows:
    jid = str(j.get("id",""))
    en = "[green]yes[/green]" if j.get("enabled") else "[red]no[/red]"
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
        last = running_cell(j.get("last_run_at"))
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
    table.add_row(jid, en, term, last, st)

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

def completed_since(last_ts):
    if not last_ts:
        return "—"
    a = age(last_ts)
    if a == "—":
        return "—"
    return f"completed [white]{a}[/white] ago"

def _seconds_since(ts):
    if not ts:
        return 0
    try:
        dt = datetime.fromisoformat(ts.replace("Z","+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        secs = int((datetime.now(timezone.utc)-dt.astimezone(timezone.utc)).total_seconds())
        return max(0, secs)
    except Exception:
        return 0

def running_cell(last_ts):
    secs = _seconds_since(last_ts)
    width = 14
    phase = secs % (width + 1)
    filled = min(width, phase)
    bar = f"[cyan]{'█'*filled}[/cyan][dim]{'░'*(width-filled)}[/dim]"
    m, s = divmod(secs, 60)
    h, m = divmod(m, 60)
    elapsed = f"{h}h{m:02d}m{s:02d}s" if h else f"{m:02d}m{s:02d}s"
    return f"{bar} [white]{elapsed}[/white]"

url = "http://andromeda-ts:4311/api/schedule"
try:
    with urllib.request.urlopen(url, timeout=4) as r:
        rows = json.load(r)
except Exception as e:
    print(f"schedule unavailable: {e}")
    rows = []

print(f"{'JOB':30} {'EN':3} {'CURRENT TERM SEARCH':28} {'LAST':10} STATUS")
print("-"*80)
latest_term_by_source = {}
try:
    with urllib.request.urlopen("http://andromeda-ts:4311/api/search-telemetry/recent", timeout=4) as r2:
        telem = json.load(r2)
    for item in telem.get("items", []):
        src = str(item.get("source") or "")
        if src and src not in latest_term_by_source:
            latest_term_by_source[src] = str(item.get("term") or "—")
except Exception:
    pass
for j in rows:
    jid = str(j.get("id",""))[:30]
    en = "yes" if j.get("enabled") else "no"
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
        last = running_cell(j.get("last_run_at"))
    elif st == "skipped":
        last = ""
    else:
        last = completed_since(j.get("last_run_at"))
    print(f"{jid:30} {en:3} {term[:28]:28} {last:10} {st}")
PY
    sleep 2
  done
fi
