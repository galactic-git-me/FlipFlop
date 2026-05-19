#!/usr/bin/env python3
"""
Rich backend dashboard for FlipFlop.

Usage:
  python scripts/backend_console_dashboard.py --base-url http://andromeda-ts:4311
"""
from __future__ import annotations

import argparse
import time
from datetime import datetime, timezone
from typing import Any

import httpx

try:
    from rich import box
    from rich.console import Group
    from rich.live import Live
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
except Exception as exc:  # pragma: no cover
    raise SystemExit(
        "Rich is required for backend dashboard. Install with: pip install rich\n"
        f"Import error: {exc}"
    )


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


def build_layout(base_url: str, schedule: Any, sources: Any, swarm_runs: Any) -> Group:
    title = Text(f"FlipFlop Backend Console  |  {base_url}", style="bold cyan")
    subtitle = Text(datetime.now().strftime("Updated %Y-%m-%d %H:%M:%S"), style="dim")

    top = Table.grid(expand=True)
    top.add_column()
    top.add_row(Panel(Group(title, subtitle), border_style="cyan", box=box.ROUNDED))

    jobs_tbl = Table(box=box.SIMPLE_HEAVY, expand=True)
    jobs_tbl.add_column("Job", style="bold")
    jobs_tbl.add_column("Status")
    jobs_tbl.add_column("Next")
    jobs_tbl.add_column("Last")

    if isinstance(schedule, list):
        for job in schedule:
            jid = str(job.get("id", ""))
            if jid not in {"flip_opportunities", "upgrade_parts", "external_demand", "autonomous_cycle"}:
                continue
            enabled = bool(job.get("enabled", False))
            status = "[green]enabled[/green]" if enabled else "[red]paused[/red]"
            jobs_tbl.add_row(
                jid,
                status,
                _age(job.get("next_run_at")),
                _age(job.get("last_run_at")),
            )
    else:
        jobs_tbl.add_row("schedule", "[red]unavailable[/red]", "—", "—")

    sources_tbl = Table(box=box.SIMPLE, expand=True)
    sources_tbl.add_column("Source", style="bold")
    sources_tbl.add_column("Enabled")
    sources_tbl.add_column("Found")
    sources_tbl.add_column("Last Scan")
    sources_tbl.add_column("Error")

    if isinstance(sources, list):
        for src in sources[:8]:
            err = src.get("last_error") or ""
            if len(err) > 36:
                err = err[:33] + "..."
            sources_tbl.add_row(
                str(src.get("name", "—")),
                "yes" if src.get("enabled") else "no",
                str(src.get("listings_found_total") or src.get("listings_found") or 0),
                _age(src.get("last_scraped_at")),
                err or "—",
            )
    else:
        sources_tbl.add_row("sources", "—", "—", "—", "unavailable")

    runs_tbl = Table(box=box.SIMPLE, expand=True)
    runs_tbl.add_column("Recent flip_opportunities runs", style="bold")
    runs_tbl.add_column("Status")
    runs_tbl.add_column("When")
    runs_tbl.add_column("Duration")
    runs_tbl.add_column("Message")
    if isinstance(swarm_runs, list) and swarm_runs:
        for r in swarm_runs[:8]:
            st = str(r.get("status", ""))
            st_style = "green" if st == "success" else ("yellow" if st in {"running", "skipped"} else "red")
            msg = str(r.get("message", ""))
            if len(msg) > 48:
                msg = msg[:45] + "..."
            runs_tbl.add_row(
                str(r.get("id", "—"))[-10:],
                f"[{st_style}]{st}[/{st_style}]",
                _age(r.get("started_at")),
                f"{r.get('duration_ms') or 0}ms",
                msg or "—",
            )
    else:
        runs_tbl.add_row("—", "—", "—", "—", "No run history yet")

    middle = Table.grid(expand=True)
    middle.add_column(ratio=1)
    middle.add_column(ratio=2)
    middle.add_row(
        Panel(jobs_tbl, title="Scheduler", border_style="blue"),
        Panel(sources_tbl, title="Sources", border_style="magenta"),
    )

    bottom = Panel(runs_tbl, title="Recent Runs", border_style="green")

    return Group(top, middle, bottom)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--base-url", default="http://127.0.0.1:4311", help="Backend base URL without /api")
    p.add_argument("--refresh", type=float, default=1.0, help="Refresh seconds")
    args = p.parse_args()

    api = args.base_url.rstrip("/") + "/api"

    with httpx.Client() as client:
        with Live(refresh_per_second=max(1, int(1 / max(args.refresh, 0.2))), screen=True) as live:
            while True:
                schedule = _safe_get(client, f"{api}/schedule")
                sources = _safe_get(client, f"{api}/sources")
                runs = _safe_get(client, f"{api}/schedule/flip_opportunities/runs")
                live.update(build_layout(args.base_url, schedule, sources, runs))
                time.sleep(max(0.2, args.refresh))


if __name__ == "__main__":
    raise SystemExit(main())

