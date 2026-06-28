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
from collections import deque
from pathlib import Path
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


class LogTailer:
    def __init__(self, log_file: str, max_lines: int = 20):
        self.path = Path(log_file)
        self.max_lines = max_lines
        self.lines: deque[str] = deque(maxlen=max_lines)
        self._fh = None
        self._inode = None
        self._load_initial()

    def _load_initial(self) -> None:
        try:
            if not self.path.exists():
                return
            with self.path.open("r", encoding="utf-8", errors="replace") as f:
                for ln in f.readlines()[-self.max_lines:]:
                    self.lines.append(ln.rstrip("\n"))
        except Exception:
            pass

    def _ensure_open(self) -> None:
        try:
            if not self.path.exists():
                return
            st = self.path.stat()
            inode = (st.st_dev, st.st_ino)
            if self._fh is None or self._inode != inode:
                if self._fh:
                    self._fh.close()
                self._fh = self.path.open("r", encoding="utf-8", errors="replace")
                self._fh.seek(0, 2)
                self._inode = inode
        except Exception:
            self._fh = None
            self._inode = None

    def poll(self) -> list[str]:
        self._ensure_open()
        if not self._fh:
            return list(self.lines)
        try:
            while True:
                ln = self._fh.readline()
                if not ln:
                    break
                self.lines.append(ln.rstrip("\n"))
        except Exception:
            pass
        return list(self.lines)


def _color_line(line: str) -> Text:
    t = Text(line)
    lower = line.lower()
    if "[error" in lower or " error " in lower:
        t.stylize("bold red")
    elif "[warning" in lower or " warning " in lower:
        t.stylize("yellow")
    elif "[info" in lower or " info " in lower:
        t.stylize("cyan")
    elif "[debug" in lower or " debug " in lower:
        t.stylize("dim")
    return t


def build_layout(
    base_url: str,
    schedule: Any,
    sources: Any,
    swarm_runs: Any,
    demand_runs: Any,
    upgrade_runs: Any,
    autonomous_runs: Any,
    search_recent: Any,
    listing_stats: Any,
    demand_summary: Any,
    scan_status: Any,
    log_lines: list[str],
    log_file: str,
) -> Group:
    kpi_tbl = Table.grid(expand=True)
    kpi_tbl.add_column(justify="center")
    kpi_tbl.add_column(justify="center")
    kpi_tbl.add_column(justify="center")
    kpi_tbl.add_column(justify="center")
    kpi_tbl.add_column(justify="center")

    listing_runs_count = len(swarm_runs) if isinstance(swarm_runs, list) else 0
    demand_runs_count = len(demand_runs) if isinstance(demand_runs, list) else 0
    total_listings = int((listing_stats or {}).get("total_listings") or (demand_summary or {}).get("total_listings") or 0)
    total_gems = int((listing_stats or {}).get("gems_count") or (demand_summary or {}).get("total_gems") or 0)
    gem_rate = float((demand_summary or {}).get("gem_rate_pct") or 0.0)
    avg_profit = float((listing_stats or {}).get("avg_profit") or 0.0)
    live_running = bool((scan_status or {}).get("running"))
    live_total = int((scan_status or {}).get("total") or 0)
    live_done = int((scan_status or {}).get("completed") or 0)
    live_found = int((scan_status or {}).get("total_found") or 0)
    live_gems = int((scan_status or {}).get("total_gems") or 0)

    kpi_tbl.add_row(
        f"[bold cyan]{listing_runs_count}[/bold cyan]\n[dim]listing runs[/dim]",
        f"[bold magenta]{demand_runs_count}[/bold magenta]\n[dim]demand runs[/dim]",
        f"[bold green]{total_gems}[/bold green] / [bold]{total_listings}[/bold]\n[dim]gems vs listings[/dim]",
        f"[bold yellow]{gem_rate:.1f}%[/bold yellow]\n[dim]gem rate[/dim]",
        f"[bold blue]£{avg_profit:.0f}[/bold blue]\n[dim]avg profit[/dim]",
    )
    if live_running:
        kpi_tbl.add_row(
            f"[bold bright_cyan]{live_done}/{live_total}[/bold bright_cyan]\n[dim]scan progress[/dim]",
            f"[bold bright_green]{live_found}[/bold bright_green]\n[dim]live found[/dim]",
            f"[bold bright_yellow]{live_gems}[/bold bright_yellow]\n[dim]live gems[/dim]",
            f"[green]running[/green]\n[dim]scan state[/dim]",
            f"[dim]{', '.join((scan_status or {}).get('current_sites') or []) or '—'}[/dim]\n[dim]active sources[/dim]",
        )

    top = Table.grid(expand=True)
    top.add_column()
    top.add_row(Panel(kpi_tbl, title="Live Stats", border_style="bright_blue"))

    jobs_tbl = Table(box=box.SIMPLE_HEAVY, expand=True)
    jobs_tbl.add_column("Job", style="bold")
    jobs_tbl.add_column("Processed")
    jobs_tbl.add_column("OK / Err")
    jobs_tbl.add_column("Last")
    jobs_tbl.add_column("Next")

    runs_by_job: dict[str, list[dict[str, Any]]] = {
        "flip_opportunities": swarm_runs if isinstance(swarm_runs, list) else [],
        "external_demand": demand_runs if isinstance(demand_runs, list) else [],
        "upgrade_parts": upgrade_runs if isinstance(upgrade_runs, list) else [],
        "autonomous_cycle": autonomous_runs if isinstance(autonomous_runs, list) else [],
    }

    def _run_metrics(job_id: str) -> tuple[str, str]:
        rows = runs_by_job.get(job_id, [])
        processed = len(rows)
        ok = sum(1 for r in rows if str(r.get("status", "")).lower() == "success")
        err = sum(1 for r in rows if str(r.get("status", "")).lower() in {"error", "failed"})
        return str(processed), f"[green]{ok}[/green] / [red]{err}[/red]"

    if isinstance(schedule, list):
        for job in schedule:
            jid = str(job.get("id", ""))
            if jid not in {"flip_opportunities", "upgrade_parts", "external_demand", "autonomous_cycle"}:
                continue
            processed, ok_err = _run_metrics(jid)
            jobs_tbl.add_row(
                jid,
                processed,
                ok_err,
                _age(job.get("last_run_at")),
                _age(job.get("next_run_at")),
            )
    else:
        jobs_tbl.add_row("schedule", "—", "[red]unavailable[/red]", "—", "—")

    sources_tbl = Table(box=box.SIMPLE, expand=True)
    sources_tbl.add_column("Source", style="bold", no_wrap=True)
    sources_tbl.add_column("Enabled", no_wrap=True)
    sources_tbl.add_column("Found", no_wrap=True)
    sources_tbl.add_column("Last Scan", no_wrap=True)
    sources_tbl.add_column("Error", overflow="fold")

    if live_running and isinstance(scan_status, dict) and isinstance(scan_status.get("sites"), list):
        for src in scan_status.get("sites", [])[:10]:
            st = str(src.get("status") or "—")
            st_label = {
                "pending": "[dim]pending[/dim]",
                "scanning": "[cyan]scanning[/cyan]",
                "done": "[green]done[/green]",
                "error": "[red]error[/red]",
            }.get(st, st)
            sources_tbl.add_row(
                str(src.get("name", "—")),
                st_label,
                str(src.get("found") or 0),
                "live",
                str(src.get("error") or "—"),
            )
    elif isinstance(sources, list):
        for src in sources[:8]:
            err = src.get("last_error") or ""
            sources_tbl.add_row(
                str(src.get("name", "—")),
                "yes" if src.get("enabled") else "no",
                str(src.get("listings_found_total") or src.get("listings_found") or 0),
                _age(src.get("last_scraped_at")),
                err or "—",
            )
    else:
        sources_tbl.add_row("sources", "—", "—", "—", "unavailable")

    terms_tbl = Table(box=box.SIMPLE, expand=True)
    terms_tbl.add_column("Source", style="bold", no_wrap=True)
    terms_tbl.add_column("Current Term Search", overflow="fold")
    terms_tbl.add_column("Found/New", no_wrap=True)
    terms_tbl.add_column("When", no_wrap=True)
    terms_tbl.add_column("Status", no_wrap=True)

    if isinstance(search_recent, dict) and isinstance(search_recent.get("items"), list):
        latest_by_source: dict[str, dict[str, Any]] = {}
        for row in search_recent.get("items", []):
            src = str(row.get("source") or "—")
            if src not in latest_by_source:
                latest_by_source[src] = row
        for src, row in list(latest_by_source.items())[:12]:
            term = str(row.get("term") or "—")
            found = int(row.get("found") or 0)
            new = int(row.get("new") or 0)
            err = row.get("error")
            status = "[red]error[/red]" if err else "[green]ok[/green]"
            terms_tbl.add_row(
                src,
                term,
                f"{found}/{new}",
                _age(row.get("ts")),
                status,
            )
    else:
        terms_tbl.add_row("—", "No telemetry yet", "—", "—", "—")

    middle = Table.grid(expand=True)
    middle.add_column()
    middle.add_row(Panel(sources_tbl, title="Sources", border_style="magenta"))

    return Group(
        top,
        middle,
        Panel(terms_tbl, title="Live Term Search", border_style="green"),
    )


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--base-url", default="http://127.0.0.1:4311", help="Backend base URL without /api")
    p.add_argument("--refresh", type=float, default=1.0, help="Refresh seconds")
    p.add_argument("--log-file", default="", help="Path to backend log file to tail")
    args = p.parse_args()

    api = args.base_url.rstrip("/") + "/api"
    log_file = args.log_file or str((Path(__file__).resolve().parents[2] / ".run-logs" / "backend-4311.log"))
    tailer = LogTailer(log_file=log_file, max_lines=24)

    with httpx.Client(follow_redirects=True) as client:
        with Live(refresh_per_second=max(1, int(1 / max(args.refresh, 0.2))), screen=True) as live:
            while True:
                schedule = _safe_get(client, f"{api}/schedule")
                sources = _safe_get(client, f"{api}/sources/")
                runs = _safe_get(client, f"{api}/schedule/flip_opportunities/runs")
                demand_runs = _safe_get(client, f"{api}/schedule/external_demand/runs")
                upgrade_runs = _safe_get(client, f"{api}/schedule/upgrade_parts/runs")
                autonomous_runs = _safe_get(client, f"{api}/schedule/autonomous_cycle/runs")
                search_recent = _safe_get(client, f"{api}/search-telemetry/recent")
                listing_stats = _safe_get(client, f"{api}/listings/stats")
                demand_summary = _safe_get(client, f"{api}/demand/summary")
                scan_status = _safe_get(client, f"{api}/swarms/scan/status")
                lines = tailer.poll()
                live.update(
                    build_layout(
                        args.base_url,
                        schedule,
                        sources,
                        runs,
                        demand_runs,
                        upgrade_runs,
                        autonomous_runs,
                        search_recent,
                        listing_stats,
                        demand_summary,
                        scan_status,
                        lines,
                        log_file,
                    )
                )
                time.sleep(max(0.2, args.refresh))


if __name__ == "__main__":
    raise SystemExit(main())
