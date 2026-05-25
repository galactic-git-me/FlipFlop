#!/usr/bin/env bash
set +e
while true; do
  python3 - <<'PY'
import json
import urllib.request
from pathlib import Path
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
    console.print(Panel("[dim]No search terms available[/dim]", title="Current 5 Terms per Catalogue", border_style="bright_blue"))
    raise SystemExit(0)

by_scope = {s: [] for s in SCOPES}
for row in taxonomy_rows:
    scope = str((row or {}).get("scope") or "").strip()
    term = str((row or {}).get("term") or "").strip()
    if scope not in by_scope or not term or not bool((row or {}).get("enabled", True)):
        continue
    by_scope[scope].append({
        "term": term,
        "source_names": [str(x).strip() for x in ((row or {}).get("source_names") or []) if str(x).strip()],
    })

cycle_state_path = Path("/home/mac/CODING/FlipFlop/pc-flipper-backend/data/term_cycle_state.json")
cycle_state = {}
try:
    if cycle_state_path.exists():
        cycle_state = json.loads(cycle_state_path.read_text(encoding="utf-8"))
except Exception:
    cycle_state = {}

def current_terms_for_scope(scope: str) -> tuple[str, list[str]]:
    rows = by_scope.get(scope, [])
    terms_by_vendor: dict[str, list[str]] = {}
    for r in rows:
        term = r["term"]
        srcs = r["source_names"]
        if not srcs:
            terms_by_vendor.setdefault("all", []).append(term)
        else:
            for s in srcs:
                terms_by_vendor.setdefault(s, []).append(term)
    for v in list(terms_by_vendor.keys()):
        terms_by_vendor[v] = list(dict.fromkeys(terms_by_vendor[v]))
    rec = cycle_state.get(scope) if isinstance(cycle_state, dict) else None
    if not isinstance(rec, dict):
        return ("idle", [])
    active = bool(rec.get("active"))
    batch_size = max(1, int(rec.get("batch_size") or 5))
    vendors = rec.get("vendors") or {}
    cur: list[str] = []
    seen: set[str] = set()
    for vendor, vrec in vendors.items():
        cursor = max(0, int((vrec or {}).get("cursor") or 0))
        terms = terms_by_vendor.get(vendor, terms_by_vendor.get("all", []))
        start = max(0, cursor - batch_size)
        for t in terms[start:cursor]:
            if t not in seen:
                seen.add(t)
                cur.append(t)
    if not cur and active:
        for terms in terms_by_vendor.values():
            for t in terms[:batch_size]:
                if t not in seen:
                    seen.add(t)
                    cur.append(t)
    return ("running" if active else "idle", cur[:5])

console = Console()
tbl = Table(expand=True, box=box.SIMPLE_HEAVY, show_lines=False, pad_edge=False)
tbl.add_column("Catalogue", style="bold cyan", no_wrap=True, width=20)
tbl.add_column("Status", justify="center", no_wrap=True, width=9)
tbl.add_column("Current 5 Terms", style="yellow", no_wrap=False, overflow="fold")
for scope in SCOPES:
    status, terms = current_terms_for_scope(scope)
    st = "[green]running[/green]" if status == "running" else "[dim]idle[/dim]"
    txt = ", ".join(terms) if terms else "[dim]-[/dim]"
    tbl.add_row(SCOPE_LABELS[scope], st, txt)

console.clear()
console.print(Panel(tbl, title="Current 5 Terms per Catalogue", border_style="bright_blue"))
PY
  sleep 4
done
