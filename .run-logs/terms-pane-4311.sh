#!/usr/bin/env bash
set +e
while true; do
  python3 - <<'PY'
import json
import urllib.request
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

VENDOR_ALIASES = {
    "eBay UK Auctions": "eBayAuc",
    "eBay UK": "eBay",
    "Facebook Marketplace": "FB",
    "BidSpotter": "BidSp",
    "Amazon": "Amz",
    "AliExpress": "AliX",
    "Alibaba": "AliB",
    "Temu": "Temu",
    "Gumtree": "Gum",
    "Preloved": "Prev",
    "BargainHardware": "BHW",
    "John Pye": "JP",
    "i-bidder": "iBid",
    "Apex Auctions": "Apex",
    "Wilsons Auctions": "Wilsons",
}

def alias_vendor(name: str) -> str:
    s = str(name or "").strip()
    return VENDOR_ALIASES.get(s, s[:7] if len(s) > 7 else s)

def classify_status(item):
    err = str((item or {}).get("error") or "").strip().lower()
    found = int((item or {}).get("found") or 0)
    new = int((item or {}).get("new") or 0)
    if err:
        if "retry" in err or "blocked" in err:
            return "retry"
        return "error"
    if found > 0 or new > 0:
        return "success"
    return "no_data"

base_url = "http://andromeda-ts:4311"
cfg_keywords, taxonomy_rows, by_source = [], [], {}
try:
    with urllib.request.urlopen(f"{base_url}/api/config/search", timeout=4) as r:
        cfg = json.load(r) or {}
    cfg_keywords = [str(k).strip() for k in (cfg.get("keywords") or []) if str(k).strip()]
    with urllib.request.urlopen(f"{base_url}/api/source-search-terms", timeout=4) as r2:
        t_payload = json.load(r2) or {}
    taxonomy_rows = t_payload.get("items", []) or []
    with urllib.request.urlopen(f"{base_url}/api/search-telemetry/by-source?limit=2500", timeout=4) as r3:
        s_payload = json.load(r3) or {}
    by_source = s_payload.get("items", {}) or {}
except Exception:
    cfg_keywords, taxonomy_rows, by_source = [], [], {}

term_info = {}
for t in cfg_keywords:
    k = t.lower()
    if k not in term_info:
        term_info[k] = {"term": t, "vendors": set()}
for row in taxonomy_rows:
    term = str((row or {}).get("term") or "").strip()
    if not term:
        continue
    if not bool((row or {}).get("enabled", True)):
        continue
    k = term.lower()
    if k not in term_info:
        term_info[k] = {"term": term, "vendors": set()}
    srcs = (row or {}).get("source_names") or []
    for src in srcs:
        s = str(src).strip()
        if s:
            term_info[k]["vendors"].add(s)

matrix = {}
vendors = set()
for source, rows in by_source.items():
    src = str(source or "").strip()
    if not src:
        continue
    vendors.add(src)
    for it in rows or []:
        term = str((it or {}).get("term") or "").strip()
        if not term:
            continue
        key = (term.lower(), src)
        if key in matrix:
            continue
        matrix[key] = it
        if term.lower() not in term_info:
            term_info[term.lower()] = {"term": term, "vendors": set()}
        term_info[term.lower()]["vendors"].add(src)

if not term_info:
    console = Console()
    console.clear()
    console.print(Panel("[dim]No search terms available[/dim]", title="Search Terms by Vendor", border_style="bright_blue"))
    raise SystemExit(0)

term_keys = sorted(term_info.keys(), key=lambda x: term_info[x]["term"].lower())
vendors = sorted(vendors)
if not vendors:
    vendor_pool = set()
    for item in term_info.values():
        vendor_pool.update(item["vendors"])
    vendors = sorted(vendor_pool)

console = Console()
pane_width = max(70, int(getattr(console.size, "width", 120)))
term_col_w = 30
status_col_w = 4
max_vendor_cols = max(1, min(len(vendors), (pane_width - term_col_w - 6) // status_col_w))
vendors = vendors[:max_vendor_cols]

tbl = Table(expand=True, box=box.SIMPLE_HEAVY, show_lines=False, pad_edge=False)
tbl.add_column("Search Term", style="bold cyan", no_wrap=False, overflow="fold", width=term_col_w)
for v in vendors:
    tbl.add_column(alias_vendor(v), justify="center", no_wrap=True, width=status_col_w)

def render_cell(term_key: str, vendor: str) -> str:
    allowed = term_info[term_key]["vendors"]
    if allowed and vendor not in allowed:
        return ""
    item = matrix.get((term_key, vendor))
    if not item:
        return ""
    st = classify_status(item)
    found = int((item or {}).get("found") or 0)
    if st == "success":
        return f"[green]{min(found,99):>2}[/green]"
    if st == "retry":
        return "[yellow] ![/yellow]"
    if st == "error":
        return "[red] x[/red]"
    return "[dim] .[/dim]"

for k in term_keys:
    term = term_info[k]["term"]
    row = [term] + [render_cell(k, v) for v in vendors]
    tbl.add_row(*row)

console.clear()
legend = "[green]NN[/green]=success count  [yellow]![/yellow]=retry  [red]x[/red]=fail  [dim].[/dim]=0  blank=not searched"
console.print(Panel(tbl, title="Search Terms x Vendor", subtitle=legend, border_style="bright_blue"))
PY
  sleep 4
done
