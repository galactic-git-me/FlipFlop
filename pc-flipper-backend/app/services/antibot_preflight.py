import asyncio
import os
from datetime import datetime, timezone

import structlog

from app.services.playwright_scraper import chromium_available

log = structlog.get_logger(__name__)

_LOCK = asyncio.Lock()
_RUNNING = False
_LAST_RESULT = "never_run"
_LAST_MESSAGE = "Not run yet"
_LAST_RUN_AT: str | None = None

CHALLENGE_URLS = [
    "https://www.facebook.com/marketplace/",
    "https://www.temu.com/",
    "https://www.alibaba.com/",
    "https://www.aliexpress.com/",
    "https://www.gumtree.com/",
    "https://www.bargainhardware.co.uk/",
]


def _interactive_mode() -> bool:
    enabled = os.getenv("SHOW_SCRAPER_BROWSER", "0").lower() in {"1", "true", "yes"}
    has_display = bool(os.getenv("DISPLAY") or os.getenv("WAYLAND_DISPLAY"))
    return enabled and has_display


def preflight_status() -> dict:
    return {
        "enabled": os.getenv("ANTI_BOT_PREFLIGHT_ON_STARTUP", "1").lower() in {"1", "true", "yes"},
        "show_scraper_browser": os.getenv("SHOW_SCRAPER_BROWSER", "0"),
        "has_display": bool(os.getenv("DISPLAY") or os.getenv("WAYLAND_DISPLAY")),
        "interactive_mode": _interactive_mode(),
        "chromium_available": chromium_available(),
        "running": _RUNNING,
        "last_result": _LAST_RESULT,
        "last_message": _LAST_MESSAGE,
        "last_run_at": _LAST_RUN_AT,
        "urls": CHALLENGE_URLS,
        "wait_seconds": max(30, int(os.getenv("ANTI_BOT_PREFLIGHT_WAIT_SECONDS", "120"))),
    }


async def run_antibot_preflight() -> None:
    global _RUNNING, _LAST_RESULT, _LAST_MESSAGE, _LAST_RUN_AT
    if _RUNNING:
        return
    async with _LOCK:
        if _RUNNING:
            return
        _RUNNING = True
        _LAST_RUN_AT = datetime.now(timezone.utc).isoformat()
        try:
            enabled = os.getenv("ANTI_BOT_PREFLIGHT_ON_STARTUP", "1").lower() in {"1", "true", "yes"}
            if not enabled:
                _LAST_RESULT = "disabled"
                _LAST_MESSAGE = "Preflight disabled by env"
                log.info("runtime.preflight.antibot.disabled")
                return
            if not _interactive_mode():
                _LAST_RESULT = "skipped_no_gui"
                _LAST_MESSAGE = "No GUI display available in backend runtime"
                log.info(
                    "runtime.preflight.antibot.skipped_no_gui",
                    hint="Set SHOW_SCRAPER_BROWSER=1 and ensure DISPLAY/WAYLAND_DISPLAY is available",
                )
                return
            if not chromium_available():
                _LAST_RESULT = "skipped_no_chromium"
                _LAST_MESSAGE = "Chromium not installed for Playwright"
                log.warning("runtime.preflight.antibot.skipped_no_chromium")
                return

            from playwright.async_api import async_playwright

            wait_seconds = max(30, int(os.getenv("ANTI_BOT_PREFLIGHT_WAIT_SECONDS", "120")))
            log.info("runtime.preflight.antibot.start", pages=len(CHALLENGE_URLS), wait_seconds=wait_seconds)
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=False, args=["--no-sandbox", "--disable-dev-shm-usage"])
                context = await browser.new_context()
                try:
                    for url in CHALLENGE_URLS:
                        try:
                            page = await context.new_page()
                            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                            log.info("runtime.preflight.antibot.page_opened", url=url)
                        except Exception as page_exc:
                            log.warning("runtime.preflight.antibot.page_open_failed", url=url, error=str(page_exc))
                    await asyncio.sleep(wait_seconds)
                    _LAST_RESULT = "success"
                    _LAST_MESSAGE = "Preflight browser session completed"
                finally:
                    await context.close()
                    await browser.close()
            log.info("runtime.preflight.antibot.done")
        except Exception as exc:
            _LAST_RESULT = "failed"
            _LAST_MESSAGE = str(exc)[:300]
            log.warning("runtime.preflight.antibot.failed", error=str(exc))
        finally:
            _RUNNING = False


def trigger_antibot_preflight() -> dict:
    if _RUNNING:
        return {"ok": True, "started": False, "reason": "already_running"}
    asyncio.create_task(run_antibot_preflight())
    return {"ok": True, "started": True}

