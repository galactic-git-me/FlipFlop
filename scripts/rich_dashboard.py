#!/usr/bin/env python3
from __future__ import annotations

import argparse
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

try:
    from rich import box
    from rich.console import Group
    from rich.layout import Layout
    from rich.live import Live
    from rich.panel import Panel
from rich.table import Table
except Exception as exc:  # pragma: no cover
    raise SystemExit(f"Rich is required. Install with pip install rich. Error: {exc}")


SCOPES = ["flip_opportunities", "upgrade_parts", "cases", "accessories"]
SCOPE_LABELS = {
    "flip_opportunities": "flip_opportunities",
    "upgrade_parts": "components",
    "cases": "cases",
    "accessories": "accessories",
}
VENDOR_GROUPS = {
    "eBay": ["eBay", "eBay UK", "eBay (Worldwide)", "eBay UK Auctions"],
    "FBMP": ["Facebook Marketplace"],
    "Others": [
        "Amazon",
        "Temu",
        "AliExpress",
        "Alibaba",
        "BargainHardware",
        "CherryTree Inc",
        "Gumtree",
        "BidSpotter",
        "Apex Auctions",
        "Wilsons Auctions",
        "i-bidder",
        "Preloved",
        "John Pye",
        "Manual Submission",
        "Manual Photo",
        "Merkandi",
        "Wholesale Clearance UK",
    ],
}


def _safe_get(client: httpx.Client, url: str) -> Any:
    try:
        r = client.get(url, timeout=4.0)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def _age(iso_ts: str | None) -> str:
    if not iso_ts:
        return "—"
    try:
        dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        secs = int((datetime.now(timezone.utc) - dt.astimezone(timezone.utc)).total_seconds())
        if secs < 0:
            secs = 0
        m, s = divmod(secs, 60)
        h, m = divmod(m, 60)
        if h > 0:
            return f"{h}h {m:02d}m"
        return f"{m:02d}m {s:02d}s"
    except Exception:
        return "—"


def _scope_vendor_sources(scope: str, vendor: str) -> list[str]:
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


def _cell_state(item: dict[str, Any] | None) -> tuple[str, int]:
    if not item:
        return ("blank", 0)
    err = str((item or {}).get("error") or "").strip().lower()
    found = int((item or {}).get("found") or 0)
    if err:
        if "retry" in err or "blocked" in err or "backoff" in err or "429" in err or "chromium_not_installed" in err:
            return ("retry", found)
        return ("error", found)
    if found > 0:
        return ("success", found)
    return ("zero", 0)


def _build_kpis(listing_stats: Any, demand_summary: Any, scan_status: Any) -> Panel:
    total_listings = int((listing_stats or {}).get("total_listings") or (demand_summary or {}).get("total_listings") or 0)
    total_gems = int((listing_stats or {}).get("gems_count") or (demand_summary or {}).get("total_gems") or 0)
    gem_rate = float((demand_summary or {}).get("gem_rate_pct") or 0.0)
    avg_profit = float((listing_stats or {}).get("avg_profit") or 0.0)
    running = bool((scan_status or {}).get("running"))
    done = int((scan_status or {}).get("completed") or 0)
    total = int((scan_status or {}).get("total") or 0)
    found = int((scan_status or {}).get("total_found") or 0)

    tbl = Table.grid(expand=True)
    for _ in range(5):
        tbl.add_column(justify="center")
    tbl.add_row(
        f"[bold]{total_listings}[/bold]\n[dim]listings[/dim]",
        f"[bold green]{total_gems}[/bold green]\n[dim]gems[/dim]",
        f"[bold yellow]{gem_rate:.1f}%[/bold yellow]\n[dim]gem-rate[/dim]",
        f"[bold cyan]£{avg_profit:.0f}[/bold cyan]\n[dim]avg-profit[/dim]",
        f"{'[green]running[/green]' if running else '[dim]idle[/dim]'}\n[dim]{done}/{total} found:{found}[/dim]",
    )
    return Panel(tbl, title="FlipFlop Live Stats", border_style="bright_blue")


def _build_schedule(schedule_rows: Any) -> Panel:
    tbl = Table(box=box.SIMPLE_HEAVY, expand=True)
    tbl.add_column("Job", style="bold cyan")
    tbl.add_column("Last")
    tbl.add_column("Next")
    tbl.add_column("Status")
    if isinstance(schedule_rows, list):
        for j in schedule_rows:
            jid = str((j or {}).get("id") or "")
            if not jid:
                continue
            status = str((j or {}).get("status") or "")
            status_label = "[green]success[/green]" if status == "success" else status or "—"
            tbl.add_row(jid, _age((j or {}).get("last_run_at")), _age((j or {}).get("next_run_at")), status_label)
    if tbl.row_count == 0:
        tbl.add_row("—", "—", "—", "—")
    return Panel(tbl, title="Scheduler", border_style="cyan")


def _build_terms(taxonomy_rows: list[dict[str, Any]], telem_items: dict[str, Any], enabled_sources: set[str]) -> Panel:
    by_scope: dict[str, list[dict[str, Any]]] = {s: [] for s in SCOPES}
    for row in taxonomy_rows:
        scope = str((row or {}).get("scope") or "").strip()
        term = str((row or {}).get("term") or "").strip()
        if scope not in by_scope or not term or not bool((row or {}).get("enabled", True)):
            continue
        srcs = [str(x).strip() for x in ((row or {}).get("source_names") or []) if str(x).strip()]
        by_scope[scope].append({"term": term, "source_names": srcs})

    latest: dict[tuple[str, str], dict[str, Any]] = {}
    for src, rows in (telem_items or {}).items():
        for r in rows or []:
            term = str((r or {}).get("term") or "").strip().lower()
            if term and (str(src), term) not in latest:
                latest[(str(src), term)] = r

    tbl = Table(expand=True, box=box.SIMPLE_HEAVY, show_lines=False)
    tbl.add_column("Catalogue", style="bold cyan", width=18, no_wrap=True)
    tbl.add_column("Search Term", style="yellow", width=34, overflow="fold")
    tbl.add_column("eBay", justify="center", width=10)
    tbl.add_column("FBMP", justify="center", width=10)
    tbl.add_column("Others", justify="center", width=10)

    def render_group(scope: str, rows: list[dict[str, Any]]) -> None:
        first = True
        for r in sorted(rows, key=lambda x: str(x.get("term", "")).lower())[:12]:
            term = str(r.get("term") or "").strip()
            allowed = set(r.get("source_names") or [])
            out = [SCOPE_LABELS[scope] if first else "", term]
            for group in ["eBay", "FBMP", "Others"]:
                members = VENDOR_GROUPS[group]
                seen_any = False
                state = "blank"
                total_found = 0
                for v in members:
                    if allowed and v not in allowed:
                        continue
                    # honor enabled sources as rough guard
                    if enabled_sources and v not in enabled_sources and v not in {"eBay", "Amazon"}:
                        pass
                    seen_any = True
                    for src in _scope_vendor_sources(scope, v):
                        st, found = _cell_state(latest.get((src, term.lower())))
                        total_found += max(0, found)
                        if st == "error":
                            state = "error"
                        elif st == "retry" and state != "error":
                            state = "retry"
                        elif st == "success" and state not in {"error", "retry"}:
                            state = "success"
                        elif st == "zero" and state == "blank":
                            state = "zero"
                if not seen_any:
                    out.append("")
                elif state == "error":
                    out.append("[red]✗[/red]")
                elif state == "retry":
                    out.append("[yellow]🚦[/yellow]")
                elif total_found > 0:
                    out.append(f"[green]✓{total_found}[/green]")
                else:
                    out.append("[dim]0[/dim]")
            tbl.add_row(*out)
            first = False
        tbl.add_section()

    for scope in SCOPES:
        render_group(scope, by_scope.get(scope, []))

    legend = "[green]✓count[/green]=scraped listings  [dim]0[/dim]=searched/none  [red]✗[/red]=error  [yellow]🚦[/yellow]=retry  blank=not run"
    return Panel(tbl, title="Search Terms by Catalogue x Vendor Groups", subtitle=legend, border_style="bright_blue")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:4311")
    ap.add_argument("--refresh", type=float, default=1.0)
    args = ap.parse_args()

    api = args.base_url.rstrip("/") + "/api"
    with httpx.Client(follow_redirects=True) as client:
        layout = Layout()
        layout.split_row(
            Layout(name="left", ratio=1),
            Layout(name="right", ratio=1),
        )
        layout["left"].split_column(
            Layout(name="kpis", size=7),
            Layout(name="sched"),
        )
        layout["right"].update(Panel("[dim]Loading search terms...[/dim]", border_style="bright_blue"))
        layout["kpis"].update(Panel("[dim]Loading KPIs...[/dim]", border_style="bright_blue"))
        layout["sched"].update(Panel("[dim]Loading scheduler...[/dim]", border_style="cyan"))

        with Live(layout, refresh_per_second=max(1, int(1 / max(args.refresh, 0.2))), screen=True):
            while True:
                try:
                    listing_stats = _safe_get(client, f"{api}/listings/stats")
                    demand_summary = _safe_get(client, f"{api}/demand/summary")
                    scan_status = _safe_get(client, f"{api}/swarms/scan/status")
                    schedule_rows = _safe_get(client, f"{api}/schedule") or []

                    taxonomy_payload = _safe_get(client, f"{api}/source-search-terms")
                    if isinstance(taxonomy_payload, dict):
                        taxonomy_rows = taxonomy_payload.get("items") or []
                    elif isinstance(taxonomy_payload, list):
                        taxonomy_rows = taxonomy_payload
                    else:
                        taxonomy_rows = []

                    telem = _safe_get(client, f"{api}/search-telemetry/by-source?limit=2500") or {}
                    telem_items = (telem or {}).get("items") if isinstance(telem, dict) else {}
                    if not isinstance(telem_items, dict):
                        telem_items = {}

                    health = _safe_get(client, f"{api}/sources/health") or {}
                    health_items = (health or {}).get("items") if isinstance(health, dict) else []
                    if not isinstance(health_items, list):
                        health_items = []
                    enabled = {
                        str((x or {}).get("name") or "")
                        for x in health_items
                        if bool((x or {}).get("enabled", False))
                    }

                    layout["kpis"].update(_build_kpis(listing_stats, demand_summary, scan_status))
                    layout["sched"].update(_build_schedule(schedule_rows))
                    layout["right"].update(_build_terms(taxonomy_rows, telem_items, enabled))
                except Exception as exc:
                    layout["kpis"].update(Panel("[red]Dashboard render error[/red]", border_style="red"))
                    layout["sched"].update(Panel(f"[red]{exc}[/red]", title="Error", border_style="red"))
                time.sleep(max(0.2, args.refresh))


if __name__ == "__main__":
    raise SystemExit(main())
