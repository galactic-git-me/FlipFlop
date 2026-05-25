#!/usr/bin/env bash
set +e
while true; do
  python3 - <<'PY'
import json
import urllib.request
from pathlib import Path
from math import ceil
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

SCOPES = ["flip_opportunities", "upgrade_parts", "cases", "accessories"]
SCOPE_LABELS = {
    "flip_opportunities": "flip_opportunities",
    "upgrade_parts": "upgrade_parts",
    "cases": "cases",
    "accessories": "accessories",
}

base_url = "http://andromeda-ts:4311"
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

latest_term_state = {}
for src, rows in (telem_by_source or {}).items():
    for r in rows or []:
        term = str((r or {}).get("term") or "").strip().lower()
        if not term:
            continue
        key = (str(src), term)
        if key not in latest_term_state:
            latest_term_state[key] = r

cycle_state_path = Path("/home/mac/CODING/FlipFlop/pc-flipper-backend/data/term_cycle_state.json")
cycle_state = {}
try:
    if cycle_state_path.exists():
        cycle_state = json.loads(cycle_state_path.read_text(encoding="utf-8"))
except Exception:
    cycle_state = {}

def classify_cell(item):
    if not item:
        return ""
    err = str((item or {}).get("error") or "").strip().lower()
    found = int((item or {}).get("found") or 0)
    if err:
        if ("retry" in err) or ("blocked" in err) or ("backoff" in err) or ("429" in err):
            return "[yellow]🚦[/yellow]"
        return "[red]✗[/red]"
    return f"[green]✓{found}[/green]"

def scope_vendor_sources(scope: str, vendor: str) -> list[str]:
    if scope == "cases":
        return [f"Cases:{vendor}"]
    if scope == "accessories":
        return [f"Accessories:{vendor}"]
    if scope == "upgrade_parts":
        return [f"UpgradeParts:{vendor}"]
    return [vendor]

def scope_runs_progress(scope: str) -> str:
    terms = [str(r.get("term") or "").strip() for r in by_scope.get(scope, []) if str(r.get("term") or "").strip()]
    unique_terms = list(dict.fromkeys(terms))
    total_runs = max(1, int(ceil(len(unique_terms) / 5.0))) if unique_terms else 1
    rec = cycle_state.get(scope) if isinstance(cycle_state, dict) else None
    if not isinstance(rec, dict):
        return f"0/{total_runs}"
    batch_size = max(1, int(rec.get("batch_size") or 5))
    vendors = rec.get("vendors") or {}
    done = 0
    for _, vrec in vendors.items():
        cursor = max(0, int((vrec or {}).get("cursor") or 0))
        done = max(done, int(ceil(cursor / float(batch_size))))
    done = min(done, total_runs)
    return f"{done}/{total_runs}"

console = Console()
tbl = Table(expand=True, box=box.SIMPLE_HEAVY, show_lines=False, pad_edge=False)
all_vendors = sorted(set().union(*[vendors_by_scope[s] for s in SCOPES]))
tbl.add_column("Catalogue", style="bold cyan", no_wrap=True, width=16)
tbl.add_column("Run(5s)", justify="center", no_wrap=True, width=7)
tbl.add_column("Search Term", style="yellow", no_wrap=False, overflow="fold", width=28)
for v in all_vendors:
    lbl = v if len(v) <= 10 else v[:10]
    tbl.add_column(lbl, justify="center", no_wrap=True, width=5)

for scope in SCOPES:
    rows = by_scope.get(scope, [])
    if not rows:
        continue
    progress = scope_runs_progress(scope)
    term_rows = sorted(rows, key=lambda r: str(r.get("term") or "").lower())
    first = True
    for r in term_rows:
        term = str(r.get("term") or "").strip()
        allowed = set(r.get("source_names") or [])
        out = [SCOPE_LABELS[scope] if first else "", progress if first else "", term]
        for v in all_vendors:
            if allowed and v not in allowed:
                out.append("")
                continue
            candidates = scope_vendor_sources(scope, v)
            cell = ""
            for src in candidates:
                item = latest_term_state.get((src, term.lower()))
                cell = classify_cell(item)
                if cell:
                    break
            out.append(cell)
        tbl.add_row(*out)
        first = False
    tbl.add_section()

console.clear()
legend = "[green]✓N[/green]=success+items  [red]✗[/red]=error  [yellow]🚦[/yellow]=retry later  blank=not run"
console.print(Panel(tbl, title="Search Terms by Catalogue x Vendor", subtitle=legend, border_style="bright_blue"))
PY
  sleep 4
done
