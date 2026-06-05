#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import time
from collections import deque
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
    "Amazon": ["Amazon", "Amazon UK"],
    "Temu": ["Temu"],
    "Others": [
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


import subprocess
import threading


class LogTailer:
    def __init__(self, log_file: str, max_lines: int = 140, docker_container: str = ""):
        self.path = Path(log_file)
        self.max_lines = max_lines
        self.lines: deque[str] = deque(maxlen=max_lines)
        self._fh = None
        self._inode = None
        self._docker_proc: subprocess.Popen | None = None
        self._lock = threading.Lock()

        if docker_container:
            self._start_docker_tailer(docker_container)
        else:
            self._load_initial()

    def _start_docker_tailer(self, container: str) -> None:
        try:
            # Seed with recent history first
            result = subprocess.run(
                ["docker", "logs", "--tail", str(self.max_lines), container],
                capture_output=True, text=True, errors="replace",
            )
            for ln in (result.stdout + result.stderr).splitlines():
                self.lines.append(ln)
            # Then follow live
            self._docker_proc = subprocess.Popen(
                ["docker", "logs", "-f", "--tail", "0", container],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, errors="replace",
            )
            t = threading.Thread(target=self._docker_reader, daemon=True)
            t.start()
        except Exception:
            pass

    def _docker_reader(self) -> None:
        try:
            for ln in self._docker_proc.stdout:
                with self._lock:
                    self.lines.append(ln.rstrip("\n"))
        except Exception:
            pass

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
        if self._docker_proc is not None:
            return
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
        if self._docker_proc is not None:
            with self._lock:
                return list(self.lines)
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


def _build_backend_logs(lines: list[str], log_file: str, docker_container: str = "") -> Panel:
    tbl = Table.grid(expand=True)
    tbl.add_column()
    if not lines:
        tbl.add_row("[dim]Waiting for backend logs...[/dim]")
    else:
        for ln in lines[-120:]:
            low = ln.lower()
            style = "white"
            if "error" in low or "exception" in low or "failed" in low:
                style = "bold red"
            elif "warn" in low:
                style = "yellow"
            elif "/api/" in low:
                style = "cyan"
            elif "info" in low:
                style = "bright_blue"
            elif "debug" in low:
                style = "dim"
            safe_ln = re.sub(r"\x1b\[[0-9;]*m", "", ln)
            tbl.add_row(f"[{style}]{safe_ln}[/{style}]")
    title = f"Backend Logs: docker/{docker_container}" if docker_container else f"Backend Logs: {log_file}"
    return Panel(tbl, title=title, border_style="green")


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


_SCOPE_PREFIX = {
    "cases":        "Cases:",
    "accessories":  "Accessories:",
    "upgrade_parts":"UpgradeParts:",
}


def _scoped_src(scope: str, vendor: str) -> str:
    """Return the telemetry key for (scope, vendor), e.g. 'Cases:eBay UK'."""
    return _SCOPE_PREFIX.get(scope, "") + vendor


def _cell_state(item: dict[str, Any] | None) -> tuple[str, int]:
    if not item:
        return ("blank", 0)
    err = str((item or {}).get("error") or "").strip().lower()
    found = int((item or {}).get("found") or 0)
    if err:
        if any(k in err for k in ("retry", "blocked", "backoff", "429", "chromium_not_installed",
                                   "source_timeout", "captcha", "login_required")):
            return ("retry", found)
        return ("error", found)
    if found > 0:
        return ("success", found)
    return ("zero", 0)


_EBAY_CANONICAL = "eBay UK"
_EBAY_ALIASES   = {"eBay", "eBay UK", "eBay (Worldwide)", "eBay UK Auctions",
                   "eBay Auctions", "ebay", "ebay uk"}


def _normalise_vendor(name: str) -> str:
    """Merge ALL eBay variants (eBay UK, eBay UK Auctions, eBay (Worldwide), eBay…) into one column."""
    if name.lower().startswith("ebay") or name.lower() == "ebay":
        return _EBAY_CANONICAL
    return name


def _compute_top_vendors(telem_items: dict[str, Any], max_cols: int = 5) -> list[tuple[str, int]]:
    """
    Return (vendor_name, total_found) sorted by total_found DESC.
    - Strips scope prefixes (Cases:, Accessories:, UpgradeParts:)
    - Merges all eBay variants ("eBay", "eBay UK", "eBay (Worldwide)") into "eBay UK"
    """
    totals: dict[str, int] = {}
    for raw_src, rows in (telem_items or {}).items():
        src = re.sub(r"^(?:Cases|Accessories|UpgradeParts):", "", str(raw_src))
        src = _normalise_vendor(src)
        for r in (rows or []):
            found = int((r or {}).get("found") or 0)
            if found > 0:
                totals[src] = totals.get(src, 0) + found
    return sorted(totals.items(), key=lambda x: x[1], reverse=True)[:max_cols]


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
            status = str((j or {}).get("last_status") or (j or {}).get("status") or "")
            status_label = "[green]success[/green]" if status == "success" else status or "—"
            tbl.add_row(jid, _age((j or {}).get("last_run_at")), _age((j or {}).get("next_run_at")), status_label)
    if tbl.row_count == 0:
        tbl.add_row("—", "—", "—", "—")
    return Panel(tbl, title="Scheduler", border_style="cyan")


_SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
_spinner_tick = 0


def _build_terms(taxonomy_rows: list[dict[str, Any]], telem_items: dict[str, Any], enabled_sources: set[str], schedule_rows: list[Any] | None = None) -> Panel:
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

    # ── Dynamic vendor columns: top N sources by total listings found (DESC) ──
    top_vendors  = _compute_top_vendors(telem_items, max_cols=5)
    if not top_vendors:
        top_vendors = [("eBay UK", 0), ("Amazon", 0), ("Gumtree", 0), ("Facebook Marketplace", 0)]
    vendor_names = [v for v, _ in top_vendors]

    # ── Build table ───────────────────────────────────────────────────────────
    tbl = Table(expand=True, box=box.SIMPLE_HEAVY, show_lines=False)
    tbl.add_column("Catalogue",   style="bold cyan", width=16, no_wrap=True)
    tbl.add_column("Search Term", style="yellow",    width=28, overflow="fold")
    for vendor, total in top_vendors:
        label = (vendor[:9] + "…") if len(vendor) > 10 else vendor
        hdr   = (f"{label}\n[dim]Σ{total}[/dim]") if total else label
        tbl.add_column(hdr, justify="center", width=9, no_wrap=True)

    def _cell(scope: str, vendor: str, term: str) -> str:
        term_lower = term.lower()
        key = (_scoped_src(scope, vendor), term_lower)
        st, found = _cell_state(latest.get(key))
        # All eBay variants map to one canonical column — try all source name forms
        # so data from any eBay sub-source (auctions, worldwide, plain "eBay") shows up.
        if st == "blank" and vendor == _EBAY_CANONICAL:
            total_found_all = 0
            best_st = "blank"
            for alt in ("eBay UK", "eBay", "eBay (Worldwide)", "eBay UK Auctions",
                        "eBay Auctions", "eBay (UK)"):
                alt_st, alt_found = _cell_state(latest.get((_scoped_src(scope, alt), term_lower)))
                total_found_all += max(0, alt_found)
                if alt_st == "error":
                    best_st = "error"
                elif alt_st == "retry" and best_st != "error":
                    best_st = "retry"
                elif alt_st in ("success", "zero") and best_st == "blank":
                    best_st = alt_st
            if best_st != "blank":
                st, found = best_st, total_found_all
        if st == "error":   return "[red]✗[/red]"
        if st == "retry":   return "[yellow]~[/yellow]"
        if found > 0:       return f"[green]✓{found}[/green]"
        if st == "zero":    return "[dim]0[/dim]"
        return ""

    # Build scope → job status map from schedule_rows
    scope_status: dict[str, str] = {}
    for j in (schedule_rows or []):
        jid = str((j or {}).get("id") or "")
        st = str((j or {}).get("last_status") or "")
        if jid in SCOPES:
            scope_status[jid] = st

    def _scope_indicator(scope: str) -> str:
        global _spinner_tick
        st = scope_status.get(scope, "")
        if st == "running":
            frame = _SPINNER_FRAMES[_spinner_tick % len(_SPINNER_FRAMES)]
            return f"[yellow]{frame}[/yellow]"
        if st == "success":
            return "[green]✓[/green]"
        if st in ("failed", "error"):
            return "[red]✗[/red]"
        return ""

    def render_group(scope: str, rows: list[dict[str, Any]]) -> None:
        global _spinner_tick
        first = True
        indicator = _scope_indicator(scope)
        label = SCOPE_LABELS[scope]
        for r in sorted(rows, key=lambda x: str(x.get("term", "")).lower())[:14]:
            term  = str(r.get("term") or "").strip()
            cat   = f"{label}\n{indicator}" if first and indicator else (label if first else "")
            out   = [cat, term]
            out  += [_cell(scope, v, term) for v in vendor_names]
            tbl.add_row(*out)
            first = False
        tbl.add_section()
        _spinner_tick += 1

    for scope in SCOPES:
        render_group(scope, by_scope.get(scope, []))

    legend = (
        "[green]✓n[/green]=listings found  [dim]0[/dim]=ran/none  "
        "[red]✗[/red]=error  [yellow]~[/yellow]=retry/blocked  blank=not run  "
        "[dim]Σ[/dim]=total scraped"
    )
    return Panel(tbl, title="Search Terms × Vendors  [dim](sorted by yield ↓)[/dim]",
                 subtitle=legend, border_style="bright_blue")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:4311")
    ap.add_argument("--refresh", type=float, default=1.0)
    ap.add_argument("--log-file", default="", help="Backend log file path")
    ap.add_argument("--docker-container", default="", help="Stream logs from this Docker container instead of a file")
    args = ap.parse_args()

    api = args.base_url.rstrip("/") + "/api"
    default_log = str(Path(__file__).resolve().parents[1] / ".run-logs" / "backend-4311.log")
    log_file = args.log_file or default_log
    tailer = LogTailer(log_file=log_file, max_lines=140, docker_container=args.docker_container)
    with httpx.Client(follow_redirects=True) as client:
        layout = Layout()
        layout.split_row(
            Layout(name="left", ratio=1),
            Layout(name="right", ratio=1),
        )
        layout["left"].split_column(
            Layout(name="kpis", size=7),
            Layout(name="sched", size=14),
            Layout(name="logs"),
        )
        layout["right"].update(Panel("[dim]Loading search terms...[/dim]", border_style="bright_blue"))
        layout["kpis"].update(Panel("[dim]Loading KPIs...[/dim]", border_style="bright_blue"))
        layout["sched"].update(Panel("[dim]Loading scheduler...[/dim]", border_style="cyan"))
        layout["logs"].update(Panel("[dim]Loading backend logs...[/dim]", border_style="green"))

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
                    layout["right"].update(_build_terms(taxonomy_rows, telem_items, enabled, schedule_rows))
                    layout["logs"].update(_build_backend_logs(tailer.poll(), log_file, args.docker_container))
                except Exception as exc:
                    layout["kpis"].update(Panel("[red]Dashboard render error[/red]", border_style="red"))
                    layout["sched"].update(Panel(f"[red]{exc}[/red]", title="Error", border_style="red"))
                    layout["logs"].update(_build_backend_logs(tailer.poll(), log_file, args.docker_container))
                time.sleep(max(0.2, args.refresh))


if __name__ == "__main__":
    raise SystemExit(main())
