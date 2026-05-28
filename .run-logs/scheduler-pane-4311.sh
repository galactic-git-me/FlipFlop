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

base_url = "http://andromeda-ts:4311"
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
    sleep "15"
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

base_url = "http://andromeda-ts:4311"
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
    sleep "15"
  done
fi

