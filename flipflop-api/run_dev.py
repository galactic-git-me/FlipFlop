"""
Dev launcher for Windows.

uvicorn's --reload flag forces WindowsSelectorEventLoopPolicy on Windows
(needed for its subprocess-based file watcher), which breaks Playwright's
browser subprocess creation.  We therefore run WITHOUT reload and instead
use watchfiles directly to restart the whole process when source files change.
This preserves Proactor event loop → Playwright works.
"""
import sys
import asyncio

if sys.platform == "win32":
    # Windows consoles default stdout/stderr to the system codepage (cp1252),
    # not UTF-8. eBay listing titles routinely contain emoji (sellers add
    # fire/star icons etc.) — the moment any log line prints one of those
    # characters, cp1252 can't encode it and raises UnicodeEncodeError,
    # which crashes whatever request triggered that log line (e.g. an entire
    # /api/gem-radar/scans submission, discarding every listing in it).
    # Reconfiguring to UTF-8 here, before anything else can log, fixes this
    # for the whole process instead of needing every log call site to guard
    # against it individually.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    # Suppress the spurious [WinError 10054] "connection forcibly closed"
    # errors that ProactorEventLoop raises in cleanup callbacks when remote
    # hosts (scraped sites) abruptly drop connections.  These are harmless
    # but flood stderr and can destabilise the event loop under high load.
    import asyncio.proactor_events as _pe
    _orig_lost = _pe._ProactorBasePipeTransport._call_connection_lost
    def _patched_lost(self, exc):
        try:
            _orig_lost(self, exc)
        except (ConnectionResetError, OSError):
            pass
    _pe._ProactorBasePipeTransport._call_connection_lost = _patched_lost

import argparse
import uvicorn

ap = argparse.ArgumentParser()
ap.add_argument("--port", type=int, default=4311)
ap.add_argument("--host", default="0.0.0.0")
args = ap.parse_args()

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=False,   # reload=True forces SelectorEventLoop on Windows → breaks Playwright
    )
