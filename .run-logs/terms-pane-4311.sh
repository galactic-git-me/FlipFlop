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

base_url = "http://andromeda-ts:4311"
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
            # Remove successfully completed terms from queue.
            continue
        pending_terms.append(term)

    for term in pending_terms[:36]:
        st = term_state.get(term)
        if st and st[0] == "retry later":
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

base_url = "http://andromeda-ts:4311"
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
    if st and st[0] == "retry later":
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
