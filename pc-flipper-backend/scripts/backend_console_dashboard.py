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


def build_layout(base_url: str, schedule: Any, sources: Any, swarm_runs: Any, log_lines: list[str], log_file: str) -> Group:
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
    sources_tbl.add_column("Source", style="bold", no_wrap=True)
    sources_tbl.add_column("Enabled", no_wrap=True)
    sources_tbl.add_column("Found", no_wrap=True)
    sources_tbl.add_column("Last Scan", no_wrap=True)
    sources_tbl.add_column("Error", overflow="fold")

    if isinstance(sources, list):
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

    runs_tbl = Table(box=box.SIMPLE, expand=True)
    runs_tbl.add_column("Recent flip_opportunities runs", style="bold", no_wrap=True)
    runs_tbl.add_column("Status", no_wrap=True)
    runs_tbl.add_column("When", no_wrap=True)
    runs_tbl.add_column("Duration", no_wrap=True)
    runs_tbl.add_column("Message", overflow="fold")
    if isinstance(swarm_runs, list) and swarm_runs:
        for r in swarm_runs[:8]:
            st = str(r.get("status", ""))
            st_style = "green" if st == "success" else ("yellow" if st in {"running", "skipped"} else "red")
            msg = str(r.get("message", ""))
            runs_tbl.add_row(
                str(r.get("id", "—"))[-10:],
                f"[{st_style}]{st}[/{st_style}]",
                _age(r.get("started_at")),
                f"{r.get('duration_ms') or 0}ms",
                msg or "—",
            )
    else:
        runs_tbl.add_row("—", "—", "—", "—", "No run history yet")

    log_tbl = Table.grid(expand=True)
    log_tbl.add_column()
    if log_lines:
        for ln in log_lines[-20:]:
            log_tbl.add_row(_color_line(ln))
    else:
        log_tbl.add_row(Text("No log lines yet", style="dim"))

    middle = Table.grid(expand=True)
    middle.add_column(ratio=2)
    middle.add_column(ratio=3)
    middle.add_row(
        Panel(sources_tbl, title="Sources", border_style="magenta"),
        Panel(log_tbl, title=f"Live Logs · {log_file}", border_style="yellow"),
    )

    return Group(
        top,
        Panel(jobs_tbl, title="Scheduler", border_style="blue"),
        middle,
        Panel(runs_tbl, title="Recent Runs", border_style="green"),
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
                lines = tailer.poll()
                live.update(build_layout(args.base_url, schedule, sources, runs, lines, log_file))
                time.sleep(max(0.2, args.refresh))


if __name__ == "__main__":
    raise SystemExit(main())
