"""
Global Playwright browser pool — single semaphore enforced across the whole app.

ALL code that spawns a headless browser MUST use managed_playwright() instead
of async_playwright() directly.  Without this, every scraper, swarm, and tool
launches its own browser in parallel — headless_shell.exe accumulates without
bound and the machine grinds to a halt.

Usage (drop-in for async_playwright):

    from app.services.browser_pool import managed_playwright

    async with managed_playwright() as p:
        browser = await p.chromium.launch(headless=True, ...)
        ...
        await browser.close()
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

import structlog

log = structlog.get_logger(__name__)

# Hard cap — ONE browser process alive at a time across the entire app.
# Chromium spawns ~3-7 headless_shell.exe sub-processes per browser instance,
# so cap=1 means ≤7 headless_shell.exe at any moment regardless of how many
# scrapers are running concurrently.
#
# Scrapers queue up and run serially.  On a dev machine this is safe and still
# fast enough (a full hourly scan completes in ~20-30 min serialised).
#
# Raise to 2 only when:
#   • You have 16+ GB RAM free
#   • You are certain only ONE backend process is running
MAX_CONCURRENT_BROWSERS: int = 1

# Lazily created so it binds to the correct running event loop.
_sem: asyncio.Semaphore | None = None


def _get_sem() -> asyncio.Semaphore:
    global _sem
    if _sem is None:
        _sem = asyncio.Semaphore(MAX_CONCURRENT_BROWSERS)
    return _sem


@asynccontextmanager
async def managed_playwright(engine: str = "playwright"):
    """
    Context manager that acquires a browser slot, runs async_playwright(),
    then releases the slot on exit — even if an exception is raised.

    engine="patchright" swaps in the patchright fork (same API, patched to
    remove CDP automation signals) for sites with Cloudflare bot-management
    that fingerprints and blocks vanilla Playwright — e.g. Overclockers.

    Example:
        async with managed_playwright() as p:
            browser, context = await _launch_browser(p)
            ...
    """
    if engine == "patchright":
        from patchright.async_api import async_playwright
    else:
        from playwright.async_api import async_playwright

    sem = _get_sem()
    async with sem:
        log.debug("browser_pool.acquired", cap=MAX_CONCURRENT_BROWSERS, engine=engine)
        try:
            async with async_playwright() as p:
                yield p
        finally:
            log.debug("browser_pool.released")
