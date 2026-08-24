from app.services.browser_pool import BACKGROUND_HEADED_ARGS, focus_page_for_human, managed_playwright
import asyncio
import os
import sys
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx

import structlog

log = structlog.get_logger(__name__)

_LOCK = asyncio.Lock()
_RUNNING = False
_LAST_RESULT = "never_run"
_LAST_MESSAGE = "Not run yet"
_LAST_RUN_AT: str | None = None

CHALLENGE_URLS = [
    "https://www.temu.com/",
]
_CHALLENGE_MARKERS = (
    "captcha", "verify you are human", "verification", "just a moment",
    "access denied", "bgn_verification", "challenge",
)


async def _has_human_challenge(page) -> bool:
    try:
        title = (await page.title() or "").lower()
        url = (page.url or "").lower()
        body = (await page.locator("body").inner_text(timeout=3000) or "").lower()[:20000]
        text = f"{title}\n{url}\n{body}"
        return any(marker in text for marker in _CHALLENGE_MARKERS)
    except Exception:
        return False


async def _wait_for_human_verification(page) -> None:
    """Keep a detected challenge open until solved, closed, or 30 minutes."""
    await focus_page_for_human(page)
    deadline = asyncio.get_running_loop().time() + max(
        300, int(os.getenv("HUMAN_VERIFICATION_MAX_WAIT_SECONDS", "1800"))
    )
    while not page.is_closed() and asyncio.get_running_loop().time() < deadline:
        await asyncio.sleep(5)
        if not await _has_human_challenge(page):
            log.info("runtime.preflight.antibot.challenge_resolved", url=page.url)
            return
    if not page.is_closed():
        log.warning("runtime.preflight.antibot.challenge_wait_expired", url=page.url)
_GATED_SOURCES = {
    "Temu",
}


def _interactive_mode() -> bool:
    enabled = os.getenv("SHOW_SCRAPER_BROWSER", "0").lower() in {"1", "true", "yes"}
    # DISPLAY/WAYLAND_DISPLAY are X11/Wayland-only — a native Windows desktop
    # session has neither set but still has a real GUI to pop a browser
    # window into, so treat win32 as always having a display.
    has_display = sys.platform == "win32" or bool(os.getenv("DISPLAY") or os.getenv("WAYLAND_DISPLAY"))
    has_cdp = bool((os.getenv("BROWSER_CDP_URL", "") or "").strip())
    return enabled and (has_display or has_cdp)


def should_defer_source_scrape(source_name: str) -> tuple[bool, str]:
    """Gate anti-bot/login sources until preflight has completed successfully."""
    src = (source_name or "").strip()
    if src not in _GATED_SOURCES:
        return False, ""
    enabled = os.getenv("ANTI_BOT_PREFLIGHT_ON_STARTUP", "1").lower() in {"1", "true", "yes"}
    if not enabled:
        return False, ""
    # If we're not in an interactive preflight-capable runtime, do not block sources.
    # They should still scrape headless/background and report real telemetry.
    if not _interactive_mode():
        return False, ""
    if _RUNNING:
        return True, "waiting_for_antibot_preflight"
    if _LAST_RESULT != "success":
        return True, "antibot_preflight_incomplete"
    return False, ""


def preflight_status() -> dict:
    cdp_url = (os.getenv("BROWSER_CDP_URL", "") or "").strip()
    cdp_host = ""
    if cdp_url:
        try:
            parsed = urlparse(cdp_url)
            cdp_host = parsed.netloc or parsed.path
        except Exception:
            cdp_host = ""
    return {
        "enabled": os.getenv("ANTI_BOT_PREFLIGHT_ON_STARTUP", "1").lower() in {"1", "true", "yes"},
        "show_scraper_browser": os.getenv("SHOW_SCRAPER_BROWSER", "0"),
        "has_display": sys.platform == "win32" or bool(os.getenv("DISPLAY") or os.getenv("WAYLAND_DISPLAY")),
        "interactive_mode": _interactive_mode(),
        "chromium_available": _chromium_available(),
        "running": _RUNNING,
        "last_result": _LAST_RESULT,
        "last_message": _LAST_MESSAGE,
        "last_run_at": _LAST_RUN_AT,
        "urls": CHALLENGE_URLS,
        "wait_seconds": max(30, int(os.getenv("ANTI_BOT_PREFLIGHT_WAIT_SECONDS", "120"))),
        "browser_cdp_url": cdp_url,
        "browser_cdp_host": cdp_host,
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
            if not _chromium_available():
                _LAST_RESULT = "skipped_no_chromium"
                _LAST_MESSAGE = "Chromium not installed for Playwright"
                log.warning("runtime.preflight.antibot.skipped_no_chromium")
                return


            wait_seconds = max(30, int(os.getenv("ANTI_BOT_PREFLIGHT_WAIT_SECONDS", "120")))
            log.info("runtime.preflight.antibot.start", pages=len(CHALLENGE_URLS), wait_seconds=wait_seconds)
            cdp_url = (os.getenv("BROWSER_CDP_URL", "") or "").strip()
            async with managed_playwright() as p:
                browser = None
                context = None
                try:
                    if cdp_url:
                        browser = await p.chromium.connect_over_cdp(cdp_url, timeout=15000)
                        if browser.contexts:
                            context = browser.contexts[0]
                        else:
                            context = await browser.new_context()
                        log.info("runtime.preflight.antibot.cdp_attached", cdp_url=cdp_url)
                    else:
                        browser = await p.chromium.launch(
                            headless=False,
                            args=["--no-sandbox", "--disable-dev-shm-usage", *BACKGROUND_HEADED_ARGS],
                        )
                        context = await browser.new_context()
                    for url in CHALLENGE_URLS:
                        try:
                            page = await context.new_page()
                            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                            log.info("runtime.preflight.antibot.page_opened", url=url)
                            await asyncio.sleep(3)
                            if await _has_human_challenge(page):
                                log.warning("runtime.preflight.antibot.challenge_detected", url=page.url)
                                await _wait_for_human_verification(page)
                        except Exception as page_exc:
                            log.warning("runtime.preflight.antibot.page_open_failed", url=url, error=str(page_exc))
                    # No challenge windows need foreground time. A small
                    # background settle preserves the original preflight.
                    await asyncio.sleep(min(wait_seconds, 10))
                    _LAST_RESULT = "success"
                    _LAST_MESSAGE = "Preflight browser session completed"
                finally:
                    if context is not None and not cdp_url:
                        await context.close()
                    if browser is not None and not cdp_url:
                        await browser.close()
            log.info("runtime.preflight.antibot.done")
        except Exception as exc:
            _LAST_RESULT = "failed"
            _LAST_MESSAGE = str(exc)[:300]
            log.warning("runtime.preflight.antibot.failed", error=str(exc))
        finally:
            _RUNNING = False


def _chromium_available() -> bool:
    try:
        from app.services.playwright_scraper import chromium_available
        return bool(chromium_available())
    except Exception:
        return False


def trigger_antibot_preflight() -> dict:
    if _RUNNING:
        return {"ok": True, "started": False, "reason": "already_running"}
    asyncio.create_task(run_antibot_preflight())
    return {"ok": True, "started": True}
