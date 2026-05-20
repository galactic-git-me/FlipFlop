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

    done = len(unique_hits)
    pct = min(1.0, max(0.0, done / float(expected_terms)))
    width = 14
    filled = int(round(width * pct))
    bar = f"[cyan]{'█'*filled}[/cyan][dim]{'░'*(width-filled)}[/dim]"
    elapsed = age(last_ts)
    return f"{bar} {paint_time_tokens(elapsed)} [dim]({done}/{expected_terms})[/dim]"

url = "http://andromeda-ts:4311/api/schedule"
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
try:
    with urllib.request.urlopen("http://andromeda-ts:4311/api/search-telemetry/recent", timeout=4) as r2:
        telem_recent = json.load(r2)
    for item in telem_recent.get("items", []):
        src = str((item or {}).get("source") or "")
        if src and src not in latest_term_by_source:
            latest_term_by_source[src] = str((item or {}).get("term") or "—")

    with urllib.request.urlopen("http://andromeda-ts:4311/api/search-telemetry/by-source", timeout=4) as r3:
        telem_by_source = json.load(r3)
    telem_source_items = dict((telem_by_source or {}).get("items", {}))
except Exception:
    latest_term_by_source = latest_term_by_source or {}
    telem_source_items = {}

table = Table(title="Scheduler", expand=True)
table.add_column("Job", style="bold cyan")
table.add_column("Current Term Search", style="yellow")
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
        if jid == "cases":
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
    echo "API: http://andromeda-ts:4311/api/schedule"
    echo
    python3 - <<'PY'
import json
import urllib.request
from datetime import datetime, timezone

CASES_TOTAL_TERMS = 150
UPGRADE_PARTS_TOTAL_TERMS = 82

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

    done = len(unique_hits)
    pct = min(1.0, max(0.0, done / float(expected_terms)))
    width = 14
    filled = int(round(width * pct))
    bar = ("#" * filled) + ("-" * (width - filled))
    return f"{bar} {age(last_ts)} ({done}/{expected_terms})"

url = "http://andromeda-ts:4311/api/schedule"
try:
    with urllib.request.urlopen(url, timeout=4) as r:
        rows = json.load(r)
except Exception as e:
    print(f"schedule unavailable: {e}")
    rows = []

latest_term_by_source = {}
telem_source_items = {}
try:
    with urllib.request.urlopen("http://andromeda-ts:4311/api/search-telemetry/recent", timeout=4) as r2:
        telem_recent = json.load(r2)
    for item in telem_recent.get("items", []):
        src = str((item or {}).get("source") or "")
        if src and src not in latest_term_by_source:
            latest_term_by_source[src] = str((item or {}).get("term") or "—")

    with urllib.request.urlopen("http://andromeda-ts:4311/api/search-telemetry/by-source", timeout=4) as r3:
        telem_by_source = json.load(r3)
    telem_source_items = dict((telem_by_source or {}).get("items", {}))
except Exception:
    latest_term_by_source = latest_term_by_source or {}
    telem_source_items = {}

print(f"{'JOB':30} {'EN':3} {'CURRENT TERM SEARCH':28} {'LAST':28} STATUS")
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
        if jid == "cases":
            last = term_progress_cell(j.get("last_run_at"), telem_source_items, ["Cases:"], CASES_TOTAL_TERMS)
        elif jid == "upgrade_parts":
            last = term_progress_cell(j.get("last_run_at"), telem_source_items, ["UpgradeParts:"], UPGRADE_PARTS_TOTAL_TERMS)
        else:
            last = neutral_running_cell(j.get("last_run_at"))
    elif st == "skipped":
        last = ""
    else:
        last = completed_since(j.get("last_run_at"))

    print(f"{jid:30} {en:3} {term[:28]:28} {str(last)[:28]:28} {st}")
PY
    sleep 2
  done
fi

