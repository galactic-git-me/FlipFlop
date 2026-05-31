#!/usr/bin/env bash
set +e
while true; do
  python3 - <<'PY'
import json
import urllib.request
from datetime import datetime, timezone
import time
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

SCOPES = ["flip_opportunities", "upgrade_parts", "cases", "accessories"]
SCOPE_LABELS = {
    "flip_opportunities": "flip_opportunities",
    "upgrade_parts": "components",
    "cases": "cases",
    "accessories": "accessories",
}
VENDOR_ALIAS = {
    "eBay UK": "eUK",
    "eBay UK Auctions": "eAuc",
    "Facebook Marketplace": "FB",
    "BidSpotter": "BSp",
    "Amazon": "Amz",
    "Temu": "Tem",
    "AliExpress": "AliX",
    "Alibaba": "AliB",
    "BargainHardware": "BHW",
    "eBay": "eB",
    "eBay (Worldwide)": "eBW",
    "CherryTree Inc": "CTI",
}
VENDOR_GROUPS = {
    "eBay": ["eBay", "eBay UK", "eBay (Worldwide)", "eBay UK Auctions"],
    "Marketplaces": ["Amazon", "Temu", "AliExpress", "Alibaba", "BargainHardware", "CherryTree Inc", "Facebook Marketplace"],
    "Other": [
        "BidSpotter", "eBay UK Auctions", "Apex Auctions", "Wilsons Auctions", "i-bidder",
        "Gumtree", "Temu", "AliExpress", "Alibaba", "CherryTree Inc", "BargainHardware",
    ],
}
FLIP_SOURCE_PREFIXES = ["eBay UK Auctions", "Facebook Marketplace", "BidSpotter"]
FLIP_SOURCE_NAMES = {
    "eBay UK", "eBay UK Auctions", "BidSpotter", "Facebook Marketplace", "Gumtree",
    "Preloved", "Apex Auctions", "Wilsons Auctions", "i-bidder", "John Pye",
    "Amazon", "Alibaba", "AliExpress", "Temu", "BargainHardware", "CherryTree Inc",
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

cfg_keywords = []
try:
    with urllib.request.urlopen(f"{base_url}/api/config/search", timeout=4) as rcfg:
        cfg_keywords = [str(k).strip() for k in ((json.load(rcfg) or {}).get("keywords") or []) if str(k).strip()]
except Exception:
    cfg_keywords = []

enabled_source_names = set()
try:
    with urllib.request.urlopen(f"{base_url}/api/sources/health", timeout=4) as rsh:
        items = (json.load(rsh) or {}).get("items") or []
        for s in items:
            if bool((s or {}).get("enabled", False)):
                enabled_source_names.add(str((s or {}).get("name") or ""))
except Exception:
    enabled_source_names = set()

schedule_rows = []
try:
    with urllib.request.urlopen(f"{base_url}/api/schedule", timeout=4) as rs:
        schedule_rows = json.load(rs) or []
except Exception:
    schedule_rows = []

latest_term_state = {}
for src, rows in (telem_by_source or {}).items():
    for r in rows or []:
        term = str((r or {}).get("term") or "").strip().lower()
        if not term:
            continue
        key = (str(src), term)
        if key not in latest_term_state:
            latest_term_state[key] = r

def classify_cell(item):
    if not item:
        return ""
    err = str((item or {}).get("error") or "").strip().lower()
    found = int((item or {}).get("found") or 0)
    if err:
        if ("retry" in err) or ("blocked" in err) or ("backoff" in err) or ("429" in err):
            return "[yellow]🚦[/yellow]"
        return "[red]✗[/red]"
    if found > 0:
        return f"[green]✓{found}[/green]"
    return "[dim]0[/dim]"

def _cell_state(item):
    if not item:
        return ("blank", 0, 0)
    err = str((item or {}).get("error") or "").strip().lower()
    found = int((item or {}).get("found") or 0)
    saved = int((item or {}).get("new") or 0)
    if err:
        if "chromium_not_installed" in err:
            return ("retry", found, saved)
        if ("retry" in err) or ("blocked" in err) or ("backoff" in err) or ("429" in err):
            return ("retry", found, saved)
        return ("error", found, saved)
    if found > 0:
        return ("success", found, saved)
    return ("zero", 0, saved)

def scope_vendor_sources(scope: str, vendor: str) -> list[str]:
    aliases = {
        "eBay": ["eBay", "eBay UK", "eBay (Worldwide)", "eBay UK Auctions"],
        "Amazon": ["Amazon", "Amazon UK"],
    }
    names = aliases.get(vendor, [vendor])
    if scope == "cases":
        return [f"Cases:{n}" for n in names]
    if scope == "accessories":
        return [f"Accessories:{n}" for n in names]
    if scope == "upgrade_parts":
        return [f"UpgradeParts:{n}" for n in names]
    return names

def scope_runs_progress(scope: str) -> str:
    rows = by_scope.get(scope, []) or []
    if not rows:
        return "0/0 0%"

    expected = 0
    hit = 0
    for row in rows:
        term = str((row or {}).get("term") or "").strip().lower()
        if not term:
            continue
        allowed = [str(x).strip() for x in ((row or {}).get("source_names") or []) if str(x).strip()]
        for vendor in allowed:
            candidates = scope_vendor_sources(scope, vendor)
            base_enabled = False
            if vendor in {"eBay", "eBay UK", "eBay (Worldwide)", "eBay UK Auctions"}:
                base_enabled = ("eBay UK" in enabled_source_names) or ("eBay UK Auctions" in enabled_source_names)
            elif vendor in {"Amazon", "Amazon UK"}:
                base_enabled = "Amazon" in enabled_source_names
            else:
                base_enabled = vendor in enabled_source_names
            if not base_enabled:
                continue
            expected += 1
            if any((c, term) in latest_term_state for c in candidates):
                hit += 1

    expected = max(1, expected)
    pct = int(max(0.0, min(100.0, (100.0 * float(hit) / float(expected)))))
    return f"{hit}/{expected} {pct}%"

def active_term_rows(scope: str, rows: list[dict]) -> list[dict]:
    """Show recent active terms for each catalogue without cycle/cursor state."""
    if not rows:
        return []
    term_to_row = {}
    for r in rows:
        t = str((r or {}).get("term") or "").strip()
        if t and t not in term_to_row:
            term_to_row[t] = r

    prefixes = {
        "flip_opportunities": [""],
        "cases": ["Cases:"],
        "accessories": ["Accessories:"],
        "upgrade_parts": ["UpgradeParts:"],
    }.get(scope, [""])

    ranked = []
    seen = set()
    for src, items in (telem_by_source or {}).items():
        if prefixes != [""] and not any(str(src).startswith(p) for p in prefixes):
            continue
        for it in (items or []):
            term = str((it or {}).get("term") or "").strip()
            if not term or term in seen or term not in term_to_row:
                continue
            seen.add(term)
            ranked.append((str((it or {}).get("ts") or ""), term))

    ranked.sort(reverse=True)
    chosen = [term_to_row[t] for _, t in ranked[:12]]
    if chosen:
        return chosen
    return list(term_to_row.values())[:12]

console = Console()
tbl = Table(expand=True, box=box.SIMPLE_HEAVY, show_lines=False, pad_edge=False)
pane_w = max(80, int(getattr(console.size, "width", 120)))
tbl.add_column("Catalogue", style="bold cyan", no_wrap=True, width=16)
tbl.add_column("Run(5s)", justify="center", no_wrap=True, width=12)
tbl.add_column("Search Term", style="yellow", no_wrap=False, overflow="fold", width=28)
group_names = ["eBay", "Marketplaces", "Other"]
for g in group_names:
    tbl.add_column(g, justify="center", no_wrap=True, width=12)

for scope in SCOPES:
    rows = by_scope.get(scope, [])
    if not rows:
        continue
    progress = scope_runs_progress(scope)
    term_rows = sorted(active_term_rows(scope, rows), key=lambda r: str(r.get("term") or "").lower())
    first = True
    for r in term_rows:
        term = str(r.get("term") or "").strip()
        allowed = set(r.get("source_names") or [])
        out = [SCOPE_LABELS[scope] if first else "", progress if first else "", term]
        for group in group_names:
            members = VENDOR_GROUPS.get(group, [])
            seen_any = False
            status = "blank"
            total_found = 0
            total_saved = 0
            for v in members:
                if allowed and v not in allowed:
                    continue
                seen_any = True
                candidates = scope_vendor_sources(scope, v)
                for src in candidates:
                    item = latest_term_state.get((src, term.lower()))
                    st, found, saved = _cell_state(item)
                    total_found += max(0, int(found or 0))
                    total_saved += max(0, int(saved or 0))
                    if st == "error":
                        status = "error"
                    elif st == "retry" and status not in ("error",):
                        status = "retry"
                    elif st == "success" and status not in ("error", "retry"):
                        status = "success"
                    elif st == "zero" and status == "blank":
                        status = "zero"
            if not seen_any:
                out.append("")
            elif status == "error":
                out.append("[red]✗[/red]")
            elif status == "retry":
                out.append("[yellow]🚦[/yellow]")
            elif status == "success":
                if total_saved > 0 and total_saved != total_found:
                    out.append(f"[green]✓{total_found}/{total_saved}[/green]")
                else:
                    out.append(f"[green]✓{total_found}[/green]")
            else:
                out.append("[dim]0[/dim]")
        tbl.add_row(*out)
        first = False
    tbl.add_section()

console.clear()
legend = "[green]✓raw/saved[/green]=scraped/persisted  [dim]0[/dim]=searched/none  [red]✗[/red]=error  [yellow]🚦[/yellow]=retry later  blank=not run"
console.print(Panel(tbl, title="Search Terms by Catalogue x Vendor Groups", subtitle=legend, border_style="bright_blue"))
PY
  sleep "12"
done
