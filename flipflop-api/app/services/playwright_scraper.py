from app.services.browser_pool import BACKGROUND_HEADED_ARGS, managed_playwright
"""
Playwright-based scrapers for sites that require a real browser:
  - Gumtree  (JS SPA, no login needed)
  - Facebook Marketplace (JS SPA, works without login for ~20 items;
    works fully with saved login cookies)
  - Apex Auctions (Gatsby + BidJS SPA, UK IT/electronics liquidation)

REQUIREMENT — run once after pip install:
    playwright install chromium

Cookie setup for Facebook:
  1. Log into facebook.com in Chrome/Firefox
  2. Install "Cookie Editor" browser extension
  3. Export cookies as JSON → save to  pc-flipper-backend/fb_cookies.json
  The scraper loads that file automatically on each run.
"""

import asyncio
import json
import os
import re
import random
import time
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

import structlog
from app.services.search_telemetry import record_term_result
from app.services.proxy import playwright_proxy_config
from app.config import get_settings
from app.services.antibot_preflight import should_defer_source_scrape

log = structlog.get_logger(__name__)
_LOG_THROTTLE_TS: dict[str, float] = {}
_PLAYWRIGHT_MISSING_WARNED = False
_CHROMIUM_AVAILABLE: bool | None = None
# Hard cap on simultaneous live Playwright browser processes.
# Each browser = one headless_shell.exe.
#
# IMPORTANT: This semaphore lives in-process.  If multiple backend instances
# are running simultaneously (e.g. after an unclean restart), each has its
# own semaphore — so 2 instances × 2 cap = 4 real browsers.  Always ensure
# only ONE backend process is running (start-dev-windows.ps1 handles this).
#
# Set to 1: fully serialise browser usage.  Scrapers queue up rather than
# running in parallel.  Slower, but safe on a dev machine with limited RAM.
# Raise to 2 once you have ≥ 16 GB RAM free and only one backend instance.
_MAX_CONCURRENT_BROWSERS = 1
_BROWSER_LIFETIME_SEM = asyncio.Semaphore(_MAX_CONCURRENT_BROWSERS)

# Max seconds any single browser session may run before it is force-closed.
# Prevents a hung scraper from holding the semaphore slot indefinitely.
_BROWSER_SESSION_TIMEOUT = 120  # 2 minutes

# Legacy name kept so existing _launch_browser usages don't error.
# It now guards only the actual chromium.launch() call (serialised).
_PLAYWRIGHT_LAUNCH_SEM = asyncio.Semaphore(1)
_FACEBOOK_SCRAPE_SEM  = asyncio.Semaphore(1)


def _log_info_throttled(event: str, window_seconds: float = 30.0, **kwargs) -> None:
    """Emit repetitive info logs at most once per window per unique key."""
    key = f"{event}|{kwargs.get('term','')}|{kwargs.get('status','')}|{kwargs.get('mode','')}"
    now = time.monotonic()
    last = _LOG_THROTTLE_TS.get(key, 0.0)
    if now - last < window_seconds:
        return
    _LOG_THROTTLE_TS[key] = now
    log.info(event, **kwargs)


def _interactive_scraper_mode() -> bool:
    enabled = os.getenv("SHOW_SCRAPER_BROWSER", "0").lower() in {"1", "true", "yes"}
    has_display = bool(os.getenv("DISPLAY") or os.getenv("WAYLAND_DISPLAY"))
    return enabled and has_display


def _log_playwright_missing_once(error: str | None = None) -> None:
    """Avoid spamming the same missing-Chromium guidance across parallel scrapers."""
    global _PLAYWRIGHT_MISSING_WARNED
    if _PLAYWRIGHT_MISSING_WARNED:
        return
    _PLAYWRIGHT_MISSING_WARNED = True
    log.warning(
        "playwright.chromium_not_installed",
        error=error or "",
        fix="Run this command once: playwright install chromium",
    )


def _is_missing_chromium_error(message: str) -> bool:
    msg = (message or "").lower()
    return (
        "executable doesn't exist" in msg
        or ("browser_type.launch" in msg and "executable" in msg and "playwright install" in msg)
        or ("failed to launch" in msg and "chromium" in msg and "playwright install" in msg)
    )


def chromium_available() -> bool:
    """
    Fast preflight to avoid repeated launch crashes when Chromium is missing.
    Cached for process lifetime.
    """
    global _CHROMIUM_AVAILABLE
    if _CHROMIUM_AVAILABLE is not None:
        return _CHROMIUM_AVAILABLE
    try:
        # Async-safe preflight: avoid Playwright Sync API usage inside running asyncio loop.
        # Probe the browser cache directly (default Playwright install location).
        browsers_root = os.getenv("PLAYWRIGHT_BROWSERS_PATH", "").strip()
        candidates: list[Path] = []
        if browsers_root:
            candidates.append(Path(browsers_root).expanduser())
        candidates.append(Path.home() / ".cache" / "ms-playwright")
        # Windows: AppData/Local/ms-playwright
        local_app_data = os.getenv("LOCALAPPDATA", "")
        if local_app_data:
            candidates.append(Path(local_app_data) / "ms-playwright")

        executable_hits: list[Path] = []
        for root in candidates:
            if not root.exists():
                continue
            for d in root.glob("chromium-*"):
                for rel in ("chrome-linux/chrome", "chrome-win/chrome.exe", "chrome-mac/Chromium.app/Contents/MacOS/Chromium"):
                    exe = d / rel
                    if exe.exists():
                        executable_hits.append(exe)

        ok = len(executable_hits) > 0
        if not ok:
            _log_playwright_missing_once("chromium executable not found in Playwright cache")
        _CHROMIUM_AVAILABLE = ok
        return ok
    except Exception as exc:
        _log_playwright_missing_once(str(exc))
        _CHROMIUM_AVAILABLE = False
        return False

# Path to optional Facebook session cookies
FB_COOKIES_PATH = Path(__file__).parent.parent.parent / "fb_cookies.json"
FB_PROFILE_DIR = Path(__file__).parent.parent.parent / ".fb-profile"

# Stealth args that suppress automation signals
_STEALTH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-extensions",
    "--disable-infobars",
    "--window-size=1366,768",
    "--lang=en-GB",
    # Disable Chrome telemetry / metrics reporting — these write GBs of data
    # into BrowserMetrics/ and DeferredBrowserMetrics/ inside the profile dir.
    "--metrics-recording-only",
    "--disable-background-networking",
    "--disable-sync",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-component-update",
    "--disable-domain-reliability",
    "--disable-features=OptimizationHints,MediaRouter,Translate",
]

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# Suppress navigator.webdriver flag
_STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3]});
Object.defineProperty(navigator, 'languages', {get: () => ['en-GB','en']});
"""


@dataclass
class RawListing:
    external_id: str
    title: str
    price: float
    url: str
    location: Optional[str]
    condition: Optional[str]
    description: str
    image_urls: list[str] = field(default_factory=list)
    source_name: str = ""
    listing_type: str = "classified"   # Playwright sources are always classifieds
    listing_ends_at: Optional[datetime] = None


def _parse_price(text: str) -> float:
    m = re.search(r"[\d,]+\.?\d*", str(text).replace(",", ""))
    return float(m.group(0)) if m else 0.0


def _is_mini_pc(title: str) -> bool:
    """Return True if the listing is a mini PC / NUC (skip — not flippable)."""
    _EXCLUDE = {
        "mini pc", "mini-pc", "mini computer", "mini desktop",
        "intel nuc", " nuc ", "nuc pc", "stick pc", "pc stick",
        "beelink", "minisforum", "gmktec", "trigkey", "geekom",
        "acemagic", "asus nuc", "compute stick", "tiny pc",
        "nano pc", "pico pc", "mele quieter",
    }
    t = title.lower()
    return any(kw in t for kw in _EXCLUDE)


# Keywords that must appear in a title for it to be considered a PC listing.
# Preloved's JS SPA ignores category path filtering so we enforce it ourselves.
_PC_KEYWORDS = {
    "pc", "computer", "desktop", "tower", "gaming",
    "i3", "i5", "i7", "i9", "ryzen", "xeon",
    "elitedesk", "optiplex", "thinkcentre", "thinkstation",
    "z240", "z440", "z640", "prodesk", "probook",
    "nvidia", "radeon", "rtx", "gtx", "rx 5", "rx 6", "rx 7",
    "workstation",
}

def _is_pc_listing(title: str) -> bool:
    """Return True if the title plausibly refers to a desktop PC listing."""
    t = title.lower()
    return any(kw in t for kw in _PC_KEYWORDS)


# ── Shared browser context factory ──────────────────────────────────────────

async def _make_context(
    playwright,
    cookies: list | None = None,
    *,
    force_persistent_profile: bool = False,
):
    settings = get_settings()
    cdp_url = str(getattr(settings, "browser_cdp_url", "") or "").strip()
    if cdp_url:
        try:
            browser = await playwright.chromium.connect_over_cdp(cdp_url)
            log.info("playwright.cdp_attached", cdp_url=cdp_url)
            if browser.contexts:
                context = browser.contexts[0]
            else:
                context = await browser.new_context(
                    user_agent=_USER_AGENT,
                    viewport={"width": 1366, "height": 768},
                    locale="en-GB",
                    timezone_id="Europe/London",
                    java_script_enabled=True,
                )
            try:
                await context.add_init_script(_STEALTH_JS)
            except Exception:
                pass
            if cookies:
                try:
                    await context.add_cookies(cookies)
                except Exception as exc:
                    log.warning("playwright.cookies.add_failed", error=str(exc))
            # Return browser=None so downstream cleanup only closes page/context,
            # not the externally owned Chrome session.
            return None, context
        except Exception as exc:
            log.warning("playwright.cdp_connect_failed_fallback_launch", error=str(exc), cdp_url=cdp_url)

    interactive = _interactive_scraper_mode()
    headless = os.getenv("FB_HEADLESS", "1").lower() not in {"0", "false", "no"}
    if interactive:
        headless = False
    # If no display is available (e.g. inside Docker), force headless regardless of FB_HEADLESS.
    # This prevents Chrome from crashing with "Missing X server or $DISPLAY" when FB_HEADLESS=0
    # is set but no GUI environment exists.
    if not headless and not (os.getenv("DISPLAY") or os.getenv("WAYLAND_DISPLAY")):
        headless = True
        log.debug("playwright.headless_forced_no_display",
                  reason="FB_HEADLESS=0 but no DISPLAY/WAYLAND_DISPLAY found — forcing headless")
    # Keep headless by default in server environments; explicit FB_HEADLESS=0 can opt into headed mode.
    use_persistent_profile = os.getenv("FB_USE_PROFILE", "0").lower() in {"1", "true", "yes"}
    use_persistent_profile = use_persistent_profile or force_persistent_profile

    if use_persistent_profile:
        FB_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        try:
            async with _PLAYWRIGHT_LAUNCH_SEM:
                context = await playwright.chromium.launch_persistent_context(
                    user_data_dir=str(FB_PROFILE_DIR),
                    headless=headless,
                    args=[*_STEALTH_ARGS, *([] if headless else BACKGROUND_HEADED_ARGS)],
                    proxy=playwright_proxy_config(),
                    user_agent=_USER_AGENT,
                    viewport={"width": 1366, "height": 768},
                    locale="en-GB",
                    timezone_id="Europe/London",
                    java_script_enabled=True,
                )
        except Exception as exc:
            if headless:
                raise
            log.warning("playwright.fb_headed_launch_failed_fallback_headless", error=str(exc))
            async with _PLAYWRIGHT_LAUNCH_SEM:
                context = await playwright.chromium.launch_persistent_context(
                    user_data_dir=str(FB_PROFILE_DIR),
                    headless=True,
                    args=_STEALTH_ARGS,
                    proxy=playwright_proxy_config(),
                    user_agent=_USER_AGENT,
                    viewport={"width": 1366, "height": 768},
                    locale="en-GB",
                    timezone_id="Europe/London",
                    java_script_enabled=True,
                )
        await context.add_init_script(_STEALTH_JS)
        if cookies:
            try:
                await context.add_cookies(cookies)
            except Exception as exc:
                log.warning("playwright.cookies.add_failed", error=str(exc))
        return None, context

    try:
        async with _PLAYWRIGHT_LAUNCH_SEM:
            browser = await playwright.chromium.launch(
                headless=headless,
                args=[*_STEALTH_ARGS, *([] if headless else BACKGROUND_HEADED_ARGS)],
                proxy=playwright_proxy_config(),
            )
    except Exception as exc:
        if headless:
            raise
        log.warning("playwright.headed_launch_failed_fallback_headless", error=str(exc))
        async with _PLAYWRIGHT_LAUNCH_SEM:
            browser = await playwright.chromium.launch(
                headless=True,
                args=_STEALTH_ARGS,
                proxy=playwright_proxy_config(),
            )
    context = await browser.new_context(
        user_agent=_USER_AGENT,
        viewport={"width": 1366, "height": 768},
        locale="en-GB",
        timezone_id="Europe/London",
        java_script_enabled=True,
    )
    await context.add_init_script(_STEALTH_JS)
    if cookies:
        await context.add_cookies(cookies)
    return browser, context


async def _launch_browser(playwright):
    """
    Wraps browser launch with a clear error message if chromium isn't installed.
    Returns (browser, context) or raises.
    """
    try:
        return await _make_context(playwright)
    except Exception as exc:
        msg = str(exc)
        if _is_missing_chromium_error(msg):
            _log_playwright_missing_once(msg)
        raise


async def _best_effort_click_any(
    page,
    selectors: list[str],
    *,
    log_key: str,
    click_timeout_ms: int = 1200,
) -> bool:
    """
    Try to click the first visible selector without generating timeout-noise logs.
    Returns True when a click was performed.
    """
    for selector in selectors:
        try:
            el = await page.query_selector(selector)
            if not el:
                continue
            if not await el.is_visible():
                continue
            await el.click(timeout=click_timeout_ms)
            log.info(log_key, selector=selector)
            return True
        except Exception:
            continue
    return False


# ── Gumtree ─────────────────────────────────────────────────────────────────

async def scrape_gumtree_playwright(
    search_terms: list[str],
    min_price: float,
    max_price: float,
) -> list[RawListing]:
    """
    Render Gumtree search results with a real headless browser.
    No login required — Gumtree shows all ads publicly.

    REQUIREMENT: playwright install chromium
    """
    results: list[RawListing] = []
    seen: set[str] = set()

    async with managed_playwright() as p:
        try:
            browser, context = await _launch_browser(p)
        except Exception:
            return []

        page = await context.new_page()

        timeout_errors = 0
        for term in search_terms[:6]:  # cap terms — each takes ~5s
            if timeout_errors >= 2:
                record_term_result(term=term, found=0, new=0, error="source_timeout_backoff", source_name="Gumtree")
                continue
            try:
                term_added = 0
                url = (
                    "https://www.gumtree.com/for-sale"
                    f"?q={term.replace(' ', '+')}"
                    f"&max_price={int(max_price)}"
                    f"&min_price={int(min_price)}"
                    "&sort=date"
                    "&distance=nationwide"
                )
                log.info("gumtree.playwright.fetch", url=url)
                # Fail fast on slow/blocked sessions so one source doesn't stall startup cycles.
                await page.goto(url, wait_until="domcontentloaded", timeout=14000)

                # Accept cookie banner if present (increased timeout for slow page loads)
                try:
                    await page.click(
                        "button:has-text('Accept'), button:has-text('I Accept'), "
                        "[data-testid='cookie-accept'], #gdpr-banner-accept, "
                        "button[class*='accept'], button[class*='Accept']",
                        timeout=8000,
                    )
                    await asyncio.sleep(0.5)
                except Exception as exc:
                    log.debug("gumtree.cookie_click_skipped", term=term, error=str(exc))

                # Wait for listing cards to appear
                try:
                    await page.wait_for_selector(
                        "article.listing-maxi, .listing-maxi, "
                        "[data-q='search-result'], li.natural",
                        timeout=10000,
                    )
                except Exception:
                    # Log page title to help diagnose bot detection
                    title_text = await page.title()
                    log.warning(
                        "gumtree.playwright.no_listings",
                        term=term,
                        page_title=title_text,
                    )
                    record_term_result(term=term, found=0, new=0, source_name="Gumtree")
                    continue

                await asyncio.sleep(random.uniform(0.5, 1.5))

                # Extract all listings from the page
                cards = await page.query_selector_all(
                    "article.listing-maxi, article.listing-thumbnail, "
                    "[data-q='search-result'], li.natural"
                )
                log.info("gumtree.playwright.cards", term=term, count=len(cards))

                for card in cards:
                    try:
                        title_el = await card.query_selector(
                            "[data-q='tile-title'], [data-q='listing-title'], .listing-title, h2, h3"
                        )
                        price_el = await card.query_selector(
                            "[data-q='tile-price'], [data-q='listing-price'], .listing-price strong, "
                            ".listing-price, [class*='price']"
                        )
                        link_el = await card.query_selector(
                            "a[data-q='search-result-anchor'], a[href*='/ad/'], a[href*='/p/'], a[href]"
                        )
                        img_el = await card.query_selector("img")
                        loc_el = await card.query_selector(
                            "[data-q='tile-location'], [data-q='listing-location'], .listing-location, [class*='location']"
                        )

                        if not title_el or not link_el:
                            continue

                        title = (await title_el.inner_text()).strip()
                        if not title or len(title) < 5 or _is_mini_pc(title):
                            continue

                        href = await link_el.get_attribute("href") or ""
                        if not href.startswith("http"):
                            href = "https://www.gumtree.com" + href

                        external_id = "gumtree_" + href.rstrip("/").split("/")[-1].split("?")[0]
                        if external_id in seen:
                            continue
                        seen.add(external_id)

                        price_text = (await price_el.inner_text()).strip() if price_el else "0"
                        price = _parse_price(price_text)
                        if price <= 0:
                            # Gumtree card markup shifts often; fallback to full card text parse.
                            try:
                                price = _parse_price((await card.inner_text()).strip())
                            except Exception:
                                price = 0.0
                        if price <= 0:
                            price = max(1.0, float(min_price))

                        image_url = await img_el.get_attribute("src") or "" if img_el else ""
                        location = (await loc_el.inner_text()).strip() if loc_el else None

                        results.append(RawListing(
                            external_id=external_id,
                            title=title,
                            price=price,
                            url=href,
                            location=location,
                            condition="used",
                            description="",
                            image_urls=[image_url] if image_url else [],
                            source_name="Gumtree",
                        ))
                        term_added += 1
                    except Exception:
                        continue
                record_term_result(term=term, found=term_added, new=term_added, source_name="Gumtree")

            except Exception as exc:
                log.error("gumtree.playwright.error", term=term, error=str(exc))
                msg = str(exc).lower()
                if "timed_out" in msg or "timeout" in msg:
                    timeout_errors += 1
                continue

        if browser is not None:
            await browser.close()
        else:
            await context.close()

    log.info("gumtree.playwright.done", total=len(results))
    return results


# ── Facebook Marketplace ─────────────────────────────────────────────────────

async def scrape_facebook_playwright(
    search_terms: list[str],
    min_price: float,
    max_price: float,
) -> list[RawListing]:
    """
    Render Facebook Marketplace with a real headless browser.

    Without cookies:  FB shows ~20 local listings before asking to log in.
    With cookies:     Full access to all listings in the configured area.

    To set up cookies:
      1. Log in to facebook.com in Chrome
      2. Install "Cookie Editor" extension → export as JSON
      3. Save to:  pc-flipper-backend/fb_cookies.json
    """
    # Default: when CDP is configured, prefer live browser session state and do NOT
    # inject file cookies (stale cookie files can force an unexpected logout wall).
    # Override: FB_FORCE_COOKIE_FILE=1 forces fb_cookies.json mode for troubleshooting.
    settings = get_settings()
    cdp_url = str(getattr(settings, "browser_cdp_url", "") or "").strip()
    force_cookie_file = os.getenv("FB_FORCE_COOKIE_FILE", "0").lower() in {"1", "true", "yes"}
    use_live_cdp_session = bool(cdp_url) and not force_cookie_file

    cookies = None if use_live_cdp_session else _load_fb_cookies()
    if use_live_cdp_session:
        log.info("facebook.playwright.using_live_cdp_session", cdp_url=cdp_url)
    elif force_cookie_file:
        log.info("facebook.playwright.using_cookie_file_override")
    elif cookies:
        log.info("facebook.playwright.cookies_loaded", count=len(cookies))
    else:
        log.info("facebook.playwright.no_cookies", hint="Save fb_cookies.json for full access")

    results: list[RawListing] = []
    seen: set[str] = set()
    login_required = asyncio.Event()
    term_concurrency = max(1, min(4, int(getattr(settings, "max_concurrent_scrapers", 3) or 3)))

    async with _FACEBOOK_SCRAPE_SEM:
        async with managed_playwright() as p:
            try:
                browser, context = await _make_context(
                    p,
                    cookies,
                    force_persistent_profile=False,
                )
            except Exception as exc:
                msg = str(exc)
                if _is_missing_chromium_error(msg):
                    log.error("playwright.chromium_not_installed", fix="Run: playwright install chromium")
                else:
                    log.error("facebook.playwright.launch_failed", error=msg[:500])
                return []

            sem = asyncio.Semaphore(term_concurrency)

            async def _fetch_term(term: str) -> tuple[str, list[RawListing], str | None]:
                if login_required.is_set():
                    return term, [], "login_required"
                async with sem:
                    page = await context.new_page()
                    term_results: list[RawListing] = []
                    try:
                        url = (
                            "https://www.facebook.com/marketplace/london/search/"
                            f"?query={term.replace(' ', '%20')}"
                            f"&minPrice={int(min_price)}"
                            f"&maxPrice={int(max_price)}"
                            "&exact=false"
                        )
                        log.info("facebook.playwright.fetch", url=url)
                        await page.goto(url, wait_until="domcontentloaded", timeout=16000)
                        if "/login/" in (page.url or ""):
                            login_required.set()
                            return term, [], "login_required"

                        cookie_clicked = await _best_effort_click_any(
                            page,
                            [
                                "button:has-text('Allow all cookies')",
                                "button:has-text('Accept all')",
                                "[data-testid='cookie-policy-manage-dialog-accept-button']",
                                "div[aria-label='Close']",
                            ],
                            log_key="facebook.cookie_banner_clicked",
                        )
                        if cookie_clicked:
                            await asyncio.sleep(0.4)

                        login_wall = await page.query_selector("input[name='email'], form[data-testid='royal_login_form']")
                        if login_wall:
                            if _interactive_scraper_mode():
                                log.warning("facebook.playwright.manual_login_required", term=term, wait_seconds=180)
                                for _ in range(18):
                                    await asyncio.sleep(10)
                                    login_wall = await page.query_selector("input[name='email'], form[data-testid='royal_login_form']")
                                    if not login_wall:
                                        break
                            if login_wall:
                                login_required.set()
                                log.warning("facebook.playwright.login_required", hint="Save fb_cookies.json — see playwright_scraper.py instructions")
                                return term, [], "login_required"

                        try:
                            await page.wait_for_selector(
                                "[data-testid='marketplace_feed_item'], [aria-label='Marketplace item'], div[class*='x3ct3a4']",
                                timeout=10000,
                            )
                        except Exception as exc:
                            log.debug("facebook.results_wait_timeout", term=term, error=str(exc))

                        await asyncio.sleep(random.uniform(1.0, 2.0))
                        await page.evaluate("window.scrollBy(0, 800)")
                        await asyncio.sleep(1.0)

                        items = await page.query_selector_all(
                            "[data-testid='marketplace_feed_item'], [aria-label='Marketplace item'], a[href*='/marketplace/item/']"
                        )
                        log.info("facebook.playwright.items", term=term, count=len(items))

                        if not items:
                            try:
                                page_title = await page.title()
                            except Exception:
                                page_title = ""
                            link_count = len(await page.query_selector_all("a[href*='/marketplace/item/']"))
                            log.warning(
                                "facebook.playwright.no_cards",
                                term=term,
                                title=page_title,
                                current_url=page.url,
                                item_links=link_count,
                            )
                            items = await page.query_selector_all("a[href*='/marketplace/item/']")

                        for item in items:
                            try:
                                link_el = item if await item.get_attribute("href") else await item.query_selector("a[href*='/marketplace/item/']")
                                if not link_el:
                                    continue
                                href = await link_el.get_attribute("href") or ""
                                if not href.startswith("http"):
                                    href = "https://www.facebook.com" + href
                                m = re.search(r"/item/(\d+)", href)
                                if not m:
                                    continue
                                external_id = f"fb_{m.group(1)}"

                                spans = await item.query_selector_all("span")
                                texts = [(await s.inner_text()).strip() for s in spans if (await s.inner_text()).strip()]

                                price = 0.0
                                title = ""
                                for t in texts:
                                    if "£" in t and not price:
                                        price = _parse_price(t)
                                    elif len(t) > 8 and not title and "£" not in t:
                                        title = t
                                if not title or price <= 0 or _is_mini_pc(title):
                                    continue

                                img_el = await item.query_selector("img")
                                image_url = await img_el.get_attribute("src") or "" if img_el else ""
                                term_results.append(
                                    RawListing(
                                        external_id=external_id,
                                        title=title,
                                        price=price,
                                        url=href,
                                        location=None,
                                        condition="used",
                                        description="",
                                        image_urls=[image_url] if image_url else [],
                                        source_name="Facebook Marketplace",
                                    )
                                )
                            except Exception:
                                continue
                        return term, term_results, None
                    except Exception as exc:
                        log.error("facebook.playwright.error", term=term, error=str(exc))
                        return term, [], str(exc)
                    finally:
                        await page.close()

            timeout_errors = 0
            for term in search_terms[:20]:
                if timeout_errors >= 2:
                    record_term_result(
                        term=term,
                        found=0,
                        new=0,
                        error="source_timeout_backoff",
                        source_name="Facebook Marketplace",
                    )
                    continue
                term, term_items, err = await _fetch_term(term)
                if err == "login_required":
                    record_term_result(term=term, found=0, new=0, error="login_required", source_name="Facebook Marketplace")
                    continue
                if err:
                    record_term_result(term=term, error=err, source_name="Facebook Marketplace")
                    err_l = str(err).lower()
                    if "timed_out" in err_l or "timeout" in err_l:
                        timeout_errors += 1
                    continue

                term_new = 0
                for row in term_items:
                    if row.external_id in seen:
                        continue
                    seen.add(row.external_id)
                    results.append(row)
                    term_new += 1

                record_term_result(term=term, found=term_new, new=term_new, source_name="Facebook Marketplace")

            if browser is not None:
                await browser.close()
            else:
                await context.close()

    log.info("facebook.playwright.done", total=len(results))
    return results


# ── Preloved ─────────────────────────────────────────────────────────────────

async def scrape_preloved_playwright(
    search_terms: list[str],
    min_price: float,
    max_price: float,
) -> list[RawListing]:
    """
    Preloved.co.uk — despite appearing to be a classic PHP site, the search
    results page is JavaScript-rendered (SPA). Requires a real browser.
    No login needed.

    REQUIREMENT: playwright install chromium
    """
    results: list[RawListing] = []
    seen: set[str] = set()

    async with managed_playwright() as p:
        try:
            browser, context = await _launch_browser(p)
        except Exception:
            return []

        # Navigate to Preloved once to establish session cookies.
        # We use context.request for subsequent API calls — it automatically
        # carries all cookies set during page navigation.
        page = await context.new_page()
        await page.goto(
            "https://www.preloved.co.uk/classifieds/computers/all/uk",
            wait_until="domcontentloaded",
            timeout=25000,
        )
        # Accept cookie banner if present
        try:
            await page.click(
                "button:has-text('Accept'), button:has-text('OK'), "
                "[class*='cookie'] button, #cookie-accept",
                timeout=3000,
            )
        except Exception as exc:
            log.debug("preloved.cookie_click_skipped", error=str(exc))
        await asyncio.sleep(1)

        for term in search_terms[:8]:
            try:
                log.info("preloved.playwright.fetch", term=term)

                # Preloved's HTML SPA ignores ?q= on initial page load and
                # renders featured items. Call the internal JSON API directly
                # via context.request so session cookies are included.
                api_url = (
                    "https://www.preloved.co.uk/account/api/classifieds"
                    f"?q={term.replace(' ', '+')}"
                    "&section=computers"
                    f"&price_min={int(min_price)}"
                    f"&price_max={int(max_price)}"
                    "&per_page=40"
                    "&sort=date_desc"
                )
                resp = await context.request.get(
                    api_url,
                    headers={
                        "Accept": "application/json, text/plain, */*",
                        "Referer": "https://www.preloved.co.uk/classifieds/computers/all/uk",
                        "X-Requested-With": "XMLHttpRequest",
                    },
                )
                if not resp.ok:
                    if resp.status in (403, 404):
                        _log_info_throttled("preloved.playwright.no_data", status=resp.status, term=term)
                    else:
                        log.warning("preloved.playwright.api_error", status=resp.status, term=term)
                    raw_listings = []
                else:
                    data = await resp.json()
                    items = (
                        data.get("adverts")
                        or data.get("classifieds")
                        or data.get("listings")
                        or data.get("items")
                        or data.get("results")
                        or (data if isinstance(data, list) else [])
                    )
                    def _extract(item: dict) -> dict:
                        price_raw = item.get("price") or item.get("amount")
                        if isinstance(price_raw, dict):
                            price = str(price_raw.get("value") or price_raw.get("amount") or "")
                        else:
                            price = str(price_raw or "")

                        loc_raw = item.get("location") or item.get("area") or ""
                        location = loc_raw.get("display", "") if isinstance(loc_raw, dict) else loc_raw

                        images = item.get("images") or []
                        if images and isinstance(images[0], dict):
                            img_src = images[0].get("url") or images[0].get("src") or ""
                        elif images:
                            img_src = images[0]
                        else:
                            img_src = item.get("image") or item.get("thumbnail") or ""

                        return {
                            "href": item.get("url") or item.get("link") or f"/adverts/show/{item.get('id','')}",
                            "title": item.get("title") or item.get("name") or "",
                            "price": price,
                            "imgSrc": img_src,
                            "location": location,
                            "id": str(item.get("id") or ""),
                        }
                    raw_listings = [_extract(item) for item in items]

                log.info("preloved.playwright.raw", term=term, count=len(raw_listings))

                for item in raw_listings:
                    try:
                        href = item.get("href", "")
                        if not href:
                            continue
                        if not href.startswith("http"):
                            href = "https://www.preloved.co.uk" + href

                        title = item.get("title", "").strip()
                        if not title or len(title) < 5:
                            continue
                        if _is_mini_pc(title) or not _is_pc_listing(title):
                            continue

                        # Prefer the API-provided id field; fall back to URL parse
                        api_id = item.get("id", "")
                        if api_id:
                            numeric_id = api_id
                        else:
                            parts = href.rstrip("/").split("/")
                            numeric_id = next(
                                (p for p in reversed(parts) if p.isdigit()), None
                            ) or parts[-1]
                        external_id = "preloved_" + numeric_id
                        if external_id in seen:
                            continue
                        seen.add(external_id)

                        price_str = item.get("price", "")
                        try:
                            price = float(str(price_str).replace(",", ""))
                        except (ValueError, TypeError):
                            price = 0.0
                        if price <= 0:
                            continue

                        image_url = item.get("imgSrc", "")
                        location = item.get("location") or None

                        results.append(RawListing(
                            external_id=external_id,
                            title=title,
                            price=price,
                            url=href,
                            location=location,
                            condition="used",
                            description="",
                            image_urls=[image_url] if image_url else [],
                            source_name="Preloved",
                        ))
                    except Exception:
                        continue

                log.info("preloved.playwright.term_done", term=term, running_total=len(results))
                await asyncio.sleep(random.uniform(1.5, 2.5))

            except Exception as exc:
                log.error("preloved.playwright.error", term=term, error=str(exc))
                continue

        await browser.close()

    log.info("preloved.playwright.done", total=len(results))
    return results


# ── Apex Auctions ─────────────────────────────────────────────────────────────

_APEX_IT_KW = {
    "pc", "computer", "desktop", "tower", "workstation", "server",
    "laptop", "notebook", "monitor", "gpu", "graphics", "nvidia", "amd",
    "radeon", "rtx", "gtx", "rx ", "i3", "i5", "i7", "i9", "xeon", "ryzen",
    "optiplex", "elitedesk", "thinkcentre", "prodesk", "thinkstation",
    "ssd", "ram", "memory", "cpu", "processor",
    "it equipment", "it lot", "computer equipment", "tech", "electronics",
}


async def scrape_apex_playwright(
    search_terms: list[str],
    min_price: float,
    max_price: float,
) -> list[RawListing]:
    """
    Apex Auctions — UK IT/electronics liquidation via BidJS SPA.
    Uses Playwright to render the page, intercepts BidJS REST API responses
    to extract lot data without needing to manage session cookies manually.
    """
    results: list[RawListing] = []
    seen: set[str] = set()
    intercepted: list[dict] = []

    async with managed_playwright() as p:
        try:
            browser, context = await _launch_browser(p)
        except Exception:
            return []

        # Intercept BidJS API responses to extract lot data
        async def on_response(response):
            url = response.url
            if "bidjs.com" in url and "/api/" in url and response.status == 200:
                ct = response.headers.get("content-type", "")
                if "json" in ct:
                    try:
                        body = await response.json()
                        intercepted.append({"url": url, "data": body})
                    except Exception as exc:
                        log.debug("apex.intercept_json_parse_failed", url=url, error=str(exc))

        context.on("response", on_response)
        page = await context.new_page()

        try:
            # Load the main auction list — BidJS will make API calls on load
            await page.goto(
                "https://www.apexauctions.co.uk/auction/",
                wait_until="networkidle",
                timeout=40000,
            )
            await asyncio.sleep(4)

            # Accept cookies if present
            try:
                await page.click(
                    "button:has-text('Accept'), button:has-text('accept cookies')",
                    timeout=3000,
                )
                await asyncio.sleep(1)
            except Exception as exc:
                log.debug("apex.cookie_click_skipped", error=str(exc))

            # Filter to UK auctions using the country dropdown
            try:
                await page.select_option("#countryFilter", "United Kingdom")
                await asyncio.sleep(2)
            except Exception as exc:
                log.debug("apex.country_filter_skipped", error=str(exc))

            # Collect UK auction links (click-based navigation works; hash eval causes SPA errors)
            auction_items = await page.query_selector_all(".upcoming-auctions-item")
            log.info("apex.playwright.auction_items", count=len(auction_items))

            # Gather all auction links first, then navigate one by one
            auction_links: list[str] = []
            for el in auction_items:
                link = await el.query_selector("a[href*='auction']")
                if link:
                    href = await link.get_attribute("href") or ""
                    if href and href not in auction_links:
                        auction_links.append(href)

            log.info("apex.playwright.uk_auctions", count=len(auction_links))

            # Navigate into each auction via click to let the SPA route properly
            # Check all UK auctions — there's no category/title info exposed on the
            # listing grid itself, so we can't pre-filter to IT-only auctions before
            # visiting each one. Sampling only the first few risks missing the IT
            # auctions entirely (observed: 0/6 were IT-related in one run).
            for auction_href in auction_links[:16]:
                try:
                    # Go back to list and re-click to avoid SPA routing errors
                    await page.goto(
                        "https://www.apexauctions.co.uk/auction/",
                        wait_until="domcontentloaded",
                        timeout=20000,
                    )
                    await asyncio.sleep(2)
                    await page.select_option("#countryFilter", "United Kingdom")
                    await asyncio.sleep(1)

                    link_el = await page.query_selector(f"a[href='{auction_href}']")
                    if not link_el:
                        continue
                    await link_el.click()
                    await asyncio.sleep(5)

                    # BidJS renders lots as ".lot.timed-listing" panel cards
                    # (NOT plain <li> — earlier selectors matched pagination controls instead).
                    lot_els = await page.query_selector_all(
                        ".lot.timed-listing, [class*='timed-listing']"
                    )
                    log.info("apex.playwright.lots", href=auction_href, count=len(lot_els))

                    for lot_el in lot_els:
                        try:
                            title_el = await lot_el.query_selector(".lot__info--title a, .lot__info--title, h3, h2, h4, .lot-title, .title, a[title]")
                            title = ""
                            if title_el:
                                title = (await title_el.inner_text()).strip()
                            if not title:
                                # Fall back to link text
                                a_el = await lot_el.query_selector("a[href]")
                                if a_el:
                                    title = (await a_el.inner_text()).strip()
                            if not title or len(title) < 5:
                                continue
                            t = title.lower()
                            if not any(kw in t for kw in _APEX_IT_KW):
                                continue
                            if _is_mini_pc(title):
                                continue

                            link_el = await lot_el.query_selector(".lot__info--title a, a[href]")
                            href_val = await link_el.get_attribute("href") if link_el else ""
                            if href_val and not href_val.startswith("http"):
                                href_val = "https://www.apexauctions.co.uk/auction/" + href_val.lstrip("/")

                            price_el = await lot_el.query_selector(
                                ".lot__info--current-bid, "
                                "[class*='price'], [class*='bid'], [class*='estimate'], [class*='amount'], "
                                ".timed-lot__bid, .current-bid, .lot-price"
                            )
                            price_text = (await price_el.inner_text()).strip() if price_el else ""
                            price = _parse_price(price_text)
                            if max_price > 0 and price > max_price:
                                continue

                            img_el = await lot_el.query_selector("img")
                            img_url = ""
                            if img_el:
                                img_url = await img_el.get_attribute("src") or await img_el.get_attribute("data-src") or ""

                            import re as _re
                            m = _re.search(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", href_val)
                            lot_id = m.group(1) if m else (href_val.rstrip("/").split("/")[-1] if href_val else title[:20])
                            external_id = f"apex_{lot_id}"
                            if external_id in seen:
                                continue
                            seen.add(external_id)

                            results.append(RawListing(
                                external_id=external_id,
                                title=title,
                                price=price,
                                url=href_val or f"https://www.apexauctions.co.uk/auction/{auction_href}",
                                location="UK",
                                condition="used",
                                description="",
                                image_urls=[img_url] if img_url else [],
                                source_name="Apex Auctions",
                                listing_type="auction",
                            ))
                        except Exception:
                            continue

                except Exception as exc:
                    log.warning("apex.playwright.auction_error", href=auction_href, error=str(exc))
                    continue

        except Exception as exc:
            log.error("apex.playwright.error", error=str(exc))
        finally:
            await browser.close()

    # Also parse any intercepted BidJS API responses for extra coverage
    for intercepted_call in intercepted:
        try:
            data = intercepted_call.get("data", {})
            models = data.get("models", {})
            # BidJS lots come in various model shapes
            for key in ("LotModel", "AuctionLotModel", "lots", "listings"):
                lots = models.get(key, [])
                if isinstance(lots, list):
                    for lot in lots:
                        title = lot.get("lotTitle") or lot.get("title") or lot.get("name") or ""
                        t = title.lower()
                        if not title or not any(kw in t for kw in _APEX_IT_KW):
                            continue
                        price = lot.get("currentBid") or lot.get("estimateFrom") or lot.get("startingBid") or 0
                        if isinstance(price, str):
                            price = _parse_price(price)
                        lot_uuid = lot.get("uuid") or lot.get("lotUuid") or ""
                        external_id = f"apex_api_{lot_uuid or title[:20]}"
                        if external_id in seen:
                            continue
                        seen.add(external_id)
                        url = (
                            f"https://www.apexauctions.co.uk/auction/#!/"
                            f"auctions/{lot.get('auctionUuid','')}/listings/{lot_uuid}"
                            if lot_uuid else "https://www.apexauctions.co.uk/auction/"
                        )
                        results.append(RawListing(
                            external_id=external_id,
                            title=title,
                            price=float(price),
                            url=url,
                            location=lot.get("locationName") or "UK",
                            condition="used",
                            description=lot.get("description") or "",
                            image_urls=[],
                            source_name="Apex Auctions",
                            listing_type="auction",
                        ))
        except Exception:
            continue

    log.info("apex.playwright.done", total=len(results))
    return results


# ── Shared auction-search Playwright helper ───────────────────────────────────

# "PC" preceded by a number means "pieces" in UK auction lot listings
# (e.g. "350 PC LINEA", "21 PC KITS SETS") — not a personal computer.
_PC_AS_PIECE_COUNT = re.compile(r"\b\d+\s*[xX]?\s*pc\b", re.IGNORECASE)


def _matches_auction_pc_keyword(title_lower: str, keywords: set[str]) -> bool:
    if _PC_AS_PIECE_COUNT.search(title_lower) and not any(
        kw in title_lower for kw in keywords if kw != "pc"
    ):
        return False
    return any(kw in title_lower for kw in keywords)


_AUCTION_PC_KW = {
    "pc", "computer", "desktop", "tower", "workstation", "server",
    "i3", "i5", "i7", "i9", "ryzen", "xeon", "amd", "intel",
    "optiplex", "elitedesk", "thinkcentre", "prodesk", "thinkstation",
    "nvidia", "radeon", "rtx", "gtx", "gpu", "graphics",
    "z240", "z440", "z640",
    # component and chassis lanes
    "motherboard", "mainboard", "cpu", "processor", "ram", "ddr4", "ddr5",
    "ssd", "nvme", "psu", "power supply", "case", "chassis", "mid tower", "atx",
    "lot", "job lot", "joblot",
}

_AUCTION_SEARCH_TERMS = [
    "desktop pc",
    "gaming pc",
    "computer tower",
    "pc build",
    "HP EliteDesk",
    "Dell OptiPlex",
    "workstation",
    "Lenovo ThinkCentre",
    "gaming computer",
    "motherboard",
    "cpu bundle",
    "graphics card",
    "ddr4 ram",
    "nvme ssd",
    "pc case",
]


async def _scrape_auction_site(
    p,
    site_name: str,
    search_url_fn,
    lot_selectors: list[str],
    title_selectors: list[str],
    price_selectors: list[str],
    link_selectors: list[str],
    search_terms: list[str],
    min_price: float,
    max_price: float,
    wait_selector: str | None = None,
    base_url: str = "",
    required_href_tokens: list[str] | None = None,
    enforce_pc_keywords: bool = True,
    strict_price_cap: bool = True,
) -> list[RawListing]:
    """
    Generic Playwright scraper for auction lot search pages.
    Each site provides selector lists; this handles browser lifecycle, scrolling,
    dedup, and PC keyword filtering.
    """
    results: list[RawListing] = []
    seen: set[str] = set()

    try:
        browser, context = await _launch_browser(p)
    except Exception:
        return []

    page = await context.new_page()

    for term in search_terms:
        try:
            url = search_url_fn(term, min_price, max_price)
            log.info(f"{site_name}.playwright.fetch", url=url)
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)

            # Dismiss cookie/consent banners
            for btn in [
                "button:has-text('Accept all')",
                "button:has-text('Accept All')",
                "button:has-text('Accept cookies')",
                "button:has-text('Accept')",
                "button:has-text('OK')",
                "button:has-text('I agree')",
                "[id*='cookie'] button",
                "[class*='cookie-accept']",
                "#onetrust-accept-btn-handler",
                ".cc-allow",
            ]:
                try:
                    await page.click(btn, timeout=2000)
                    await asyncio.sleep(0.3)
                    break
                except Exception as exc:
                    log.debug("generic_playwright.cookie_click_skipped", site=site_name, selector=btn, error=str(exc))

            if wait_selector:
                try:
                    await page.wait_for_selector(wait_selector, timeout=12000)
                except Exception:
                    _log_info_throttled(f"{site_name}.playwright.no_results", term=term, mode="fallback_parse")

            await asyncio.sleep(random.uniform(1.0, 2.0))
            await page.evaluate("window.scrollBy(0, 600)")
            await asyncio.sleep(0.8)

            # Try lot selectors in priority order
            cards = []
            for sel in lot_selectors:
                cards = await page.query_selector_all(sel)
                if cards:
                    break

            # Fallback: treat matching anchors as cards when site card selectors drift.
            if not cards:
                fallback_cards = []
                for sel in link_selectors:
                    anchors = await page.query_selector_all(sel)
                    if anchors:
                        fallback_cards = anchors
                        break
                cards = fallback_cards

            log.info(f"{site_name}.playwright.cards", term=term, count=len(cards))
            kept = 0
            skipped_no_title = 0
            skipped_keyword = 0
            skipped_no_href = 0
            skipped_href_filter = 0

            for card in cards:
                try:
                    # Title
                    title = ""
                    for sel in title_selectors:
                        el = await card.query_selector(sel)
                        if el:
                            title = (await el.inner_text()).strip()
                            if title:
                                break
                    if not title:
                        # Anchor-style fallback cards (from link_selectors) often only expose
                        # title/aria-label attributes rather than visible text.
                        title = (
                            (await card.get_attribute("title"))
                            or (await card.get_attribute("aria-label"))
                            or ""
                        ).strip()
                    if not title or len(title) < 5:
                        # Fall back to card text when title nodes are noisy/missing.
                        try:
                            card_text = (await card.inner_text()).strip()
                        except Exception:
                            card_text = ""
                        if card_text and len(card_text) >= 5:
                            title = card_text.split("\n")[0].strip()[:200]
                        else:
                            skipped_no_title += 1
                            continue
                    t = title.lower()
                    if enforce_pc_keywords and not _matches_auction_pc_keyword(t, _AUCTION_PC_KW):
                        skipped_keyword += 1
                        continue
                    if _is_mini_pc(title):
                        continue

                    # URL
                    href = (await card.get_attribute("href") or "").strip()
                    for sel in link_selectors:
                        if href:
                            break
                        el = await card.query_selector(sel)
                        if el:
                            href = await el.get_attribute("href") or ""
                            if href:
                                break
                    if not href:
                        skipped_no_href += 1
                        continue
                    if not href.startswith("http"):
                        href = base_url + href
                    if required_href_tokens and not any(tok in href for tok in required_href_tokens):
                        skipped_href_filter += 1
                        continue

                    slug = href.rstrip("/").split("/")[-1].split("?")[0]
                    external_id = f"{site_name.lower().replace(' ', '_')}_{slug}"
                    if external_id in seen:
                        continue
                    seen.add(external_id)

                    # Price
                    price = 0.0
                    for sel in price_selectors:
                        el = await card.query_selector(sel)
                        if el:
                            price = _parse_price((await el.inner_text()).strip())
                            if price > 0:
                                break

                    if strict_price_cap and max_price > 0 and price > max_price:
                        continue

                    img_el = await card.query_selector("img")
                    img_url = ""
                    if img_el:
                        img_url = await img_el.get_attribute("src") or await img_el.get_attribute("data-src") or ""

                    results.append(RawListing(
                        external_id=external_id,
                        title=title,
                        price=price if price >= min_price else min_price,
                        url=href,
                        location="UK",
                        condition="used",
                        description="",
                        image_urls=[img_url] if img_url else [],
                        source_name=site_name,
                        listing_type="auction",
                    ))
                    kept += 1
                except Exception:
                    continue

            log.info(
                f"{site_name}.playwright.term_summary",
                term=term,
                cards=len(cards),
                kept=kept,
                skipped_no_title=skipped_no_title,
                skipped_keyword=skipped_keyword,
                skipped_no_href=skipped_no_href,
                skipped_href_filter=skipped_href_filter,
            )
            record_term_result(term=term, found=len(cards), new=kept, source_name=site_name)

        except Exception as exc:
            log.error(f"{site_name}.playwright.error", term=term, error=str(exc))
            record_term_result(term=term, error=str(exc), source_name=site_name)
            continue

        await asyncio.sleep(random.uniform(1.5, 2.5))

    await browser.close()
    log.info(f"{site_name}.playwright.done", total=len(results))
    return results


# ── Wilsons Auctions ──────────────────────────────────────────────────────────

async def scrape_wilsons_playwright(
    search_terms: list[str],
    min_price: float,
    max_price: float,
) -> list[RawListing]:
    """
    Wilsons Auctions — UK's largest independent auction house.
    IT and office equipment lots appear under their Technology category.
    """
    def url_fn(term, lo, hi):
        return (
            f"https://www.wilsonsauctions.com/lots"
            f"?search={term.replace(' ', '+')}"
        )

    async with managed_playwright() as p:
        return await _scrape_auction_site(
            p,
            site_name="Wilsons Auctions",
            search_url_fn=url_fn,
            lot_selectors=[
                ".cc-card",
                "[class*='cc-card']",
                "li[class*='lot']",
            ],
            title_selectors=[
                ".cc-card__headline", "h3 a", "[class*='title']", "a"
            ],
            # Wilsons doesn't surface a current-bid price on the search-results
            # card itself (only on the individual lot page) — these selectors
            # rarely match, so price falls back to min_price. Real price is
            # visible when the listing URL is opened.
            price_selectors=[
                "[class*='price']", "[class*='bid']", "[class*='estimate']", "strong"
            ],
            link_selectors=[
                "a.cc-card__headline", "a[href*='/lots/']", "a[href]"
            ],
            search_terms=search_terms[:20],
            min_price=min_price,
            max_price=max_price,
            wait_selector=".cc-card, [class*='cc-card']",
            base_url="https://www.wilsonsauctions.com",
            required_href_tokens=["/lots/"],
            enforce_pc_keywords=True,
            strict_price_cap=False,
        )


# ── i-bidder ─────────────────────────────────────────────────────────────────

async def scrape_ibidder_playwright(
    search_terms: list[str],
    min_price: float,
    max_price: float,
) -> list[RawListing]:
    """
    i-bidder — major UK multi-vendor auction aggregator.
    Aggregates lots from hundreds of UK auctioneers.
    """
    def url_fn(term, lo, hi):
        return (
            f"https://www.i-bidder.com/en-gb/search-results"
            f"?searchTerm={term.replace(' ', '+')}"
        )

    async with managed_playwright() as p:
        return await _scrape_auction_site(
            p,
            site_name="i-bidder",
            search_url_fn=url_fn,
            lot_selectors=[
                ".lot-single",
                "[class*='lot-single']",
                "li[class*='lot']",
            ],
            title_selectors=[
                "h3 a", ".lot-title", "[class*='title']", "a"
            ],
            price_selectors=[
                ".opening-price strong",
                "[id^='openingPrice'] strong", "[class*='price'] strong",
                "[class*='bid'] strong", "strong",
            ],
            link_selectors=[
                "a[href*='/lot-']", "a[href*='/catalogue-id-']", "a[href]"
            ],
            search_terms=search_terms[:20],
            min_price=min_price,
            max_price=max_price,
            wait_selector=".lot-single, [class*='lot-single']",
            base_url="https://www.i-bidder.com",
            required_href_tokens=["/lot-"],
            enforce_pc_keywords=True,
            strict_price_cap=False,
        )


# ── The Saleroom ──────────────────────────────────────────────────────────────

async def scrape_the_saleroom_playwright(
    search_terms: list[str],
    min_price: float,
    max_price: float,
) -> list[RawListing]:
    """
    The Saleroom — UK's largest auction marketplace aggregator.
    Shares the same backend platform as BidSpotter/i-bidder (identical
    robots.txt and DOM structure), so the same selectors apply.
    """
    def url_fn(term, lo, hi):
        return (
            f"https://www.the-saleroom.com/en-gb/search-results"
            f"?searchTerm={term.replace(' ', '+')}"
        )

    async with managed_playwright() as p:
        return await _scrape_auction_site(
            p,
            site_name="The Saleroom",
            search_url_fn=url_fn,
            lot_selectors=[
                ".lot-single",
                "[class*='lot-single']",
                "li[class*='lot']",
            ],
            title_selectors=[
                "h3 a", ".lot-title", "[class*='title']", "a"
            ],
            price_selectors=[
                ".opening-price strong",
                "[id^='openingPrice'] strong", "[class*='price'] strong",
                "[class*='bid'] strong", "strong",
            ],
            link_selectors=[
                "a[href*='/lot-']", "a[href*='/catalogue-id-']", "a[href]"
            ],
            search_terms=search_terms[:20],
            min_price=min_price,
            max_price=max_price,
            wait_selector=".lot-single, [class*='lot-single']",
            base_url="https://www.the-saleroom.com",
            required_href_tokens=["/lot-"],
            enforce_pc_keywords=True,
            strict_price_cap=False,
        )


# ── BidSpotter ────────────────────────────────────────────────────────────────

async def scrape_bidspotter_playwright(
    search_terms: list[str],
    min_price: float,
    max_price: float,
) -> list[RawListing]:
    """
    BidSpotter UK — international auction platform with a large UK catalogue.
    Strong coverage of IT/office equipment lots.
    """
    def url_fn(term, lo, hi):
        return (
            f"https://www.bidspotter.co.uk/en-us/search-results"
            f"?searchTerm={term.replace(' ', '+')}"
        )

    async with managed_playwright() as p:
        return await _scrape_auction_site(
            p,
            site_name="BidSpotter",
            search_url_fn=url_fn,
            lot_selectors=[
                ".lot-single",
                "[class*='lot-single']",
                "li[class*='lot']",
            ],
            title_selectors=[
                "h3 a", ".lot-title", "[class*='title']", "a"
            ],
            price_selectors=[
                ".opening-price strong",
                "[id^='openingPrice'] strong", "[class*='price'] strong",
                "[class*='bid'] strong", "strong",
            ],
            link_selectors=[
                "a[href*='/lot-']", "a[href*='/catalogue-id-']", "a[href]"
            ],
            search_terms=search_terms[:20],
            min_price=min_price,
            max_price=max_price,
            wait_selector=".lot-single, [class*='lot-single']",
            base_url="https://www.bidspotter.co.uk",
            required_href_tokens=["/lot-"],
            enforce_pc_keywords=True,
            strict_price_cap=False,
        )


async def scrape_lots_co_uk_playwright(
    search_terms: list[str],
    min_price: float,
    max_price: float,
) -> list[RawListing]:
    """
    Lots.co.uk — UK auction aggregator with frequent corporate IT liquidation
    lots (ex-lease desktops, workstation pallets, office clearances).
    """
    def url_fn(term, lo, hi):
        return (
            f"https://www.lots.co.uk/search"
            f"?q={term.replace(' ', '+')}"
        )

    async with managed_playwright() as p:
        return await _scrape_auction_site(
            p,
            site_name="Lots.co.uk",
            search_url_fn=url_fn,
            lot_selectors=[
                ".lot-card",
                "[class*='lot-card']",
                ".search-result-item",
                "[class*='search-result']",
                "article.lot",
                ".auction-lot",
                "li[class*='lot']",
                "div[class*='lot']",
                "article",
            ],
            title_selectors=[
                ".lot-title", ".lot-card__title", "h3", "h2",
                "[class*='title']", "a[title]", "a"
            ],
            price_selectors=[
                ".current-bid", ".estimate", "[class*='price']",
                "[class*='bid']", "[class*='estimate']", "strong"
            ],
            link_selectors=[
                "a[href*='/lot/']", "a[href*='/lots/']",
                "a[href*='/auction/']", "a[href]"
            ],
            search_terms=search_terms[:20],
            min_price=min_price,
            max_price=max_price,
            wait_selector=".lot-card, .search-result-item, article, [class*='lot-card']",
            base_url="https://www.lots.co.uk",
            required_href_tokens=None,
            enforce_pc_keywords=False,
            strict_price_cap=False,
        )


def _load_fb_cookies() -> list | None:
    """Load Facebook session cookies from fb_cookies.json if it exists."""
    if not FB_COOKIES_PATH.exists():
        return None
    try:
        raw = json.loads(FB_COOKIES_PATH.read_text())
        # Cookie Editor exports sameSite as "no_restriction" / "lax" / "strict".
        # Playwright requires the W3C values: "None" / "Lax" / "Strict".
        _ss_map = {
            "no_restriction": "None",
            "lax": "Lax",
            "strict": "Strict",
            "unspecified": "None",
        }
        cookies = []
        for c in raw:
            if "facebook.com" in c.get("domain", ""):
                ss_raw = str(c.get("sameSite", "no_restriction")).lower()
                cookies.append({
                    "name": c["name"],
                    "value": c["value"],
                    "domain": c.get("domain", ".facebook.com"),
                    "path": c.get("path", "/"),
                    "secure": c.get("secure", True),
                    "httpOnly": c.get("httpOnly", False),
                    "sameSite": _ss_map.get(ss_raw, "None"),
                })
        return cookies if cookies else None
    except Exception as exc:
        log.warning("fb_cookies.load_error", error=str(exc))
        return None


# ── BargainHardware ──────────────────────────────────────────────────────────

async def scrape_bargainhardware_playwright(
    search_terms: list[str],
    min_price: float,
    max_price: float,
) -> list[RawListing]:
    """
    BargainHardware.eu — blocked by Cloudflare managed challenge with plain
    httpx, so we use a real headless browser with anti-detection stealth.

    REQUIREMENT: playwright install chromium
    """
    results: list[RawListing] = []
    seen: set[str] = set()

    async with managed_playwright() as p:
        try:
            browser, context = await _launch_browser(p)
        except Exception:
            return []

        page = await context.new_page()

        for term in search_terms[:8]:
            try:
                url = (
                    "https://www.bargainhardware.co.uk/catalogsearch/result/"
                    f"?q={term.replace(' ', '+')}"
                )
                log.info("bargainhardware.playwright.fetch", term=term, url=url)
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)

                # Scroll to trigger lazy-loaded Magento product grid
                await asyncio.sleep(1.0)
                await page.evaluate("window.scrollBy(0, 700)")
                await asyncio.sleep(0.7)
                await page.evaluate("window.scrollBy(0, 1200)")
                await asyncio.sleep(0.5)

                # Detect Cloudflare challenge page
                page_title = await page.title()
                if "just a moment" in page_title.lower() or "checking your" in page_title.lower():
                    log.warning("bargainhardware.playwright.cloudflare_challenge", term=term)
                    # Wait longer for CF challenge to resolve
                    await asyncio.sleep(8)
                    page_title = await page.title()
                    if "just a moment" in page_title.lower():
                        record_term_result(term=term, found=0, new=0, error="cloudflare_blocked", source_name="BargainHardware")
                        continue

                raw = await page.evaluate(
                    """() => {
                        const out = [];
                        const re = /(?:[£€$])\\s*([\\d,]+\\.?\\d*)/i;

                        // Primary: structured product cards (Magento li.product-item)
                        const cards = document.querySelectorAll('li.product-item, .product-item, [data-price-amount]');
                        cards.forEach(card => {
                            if (out.length >= 30) return;
                            const priceAttr = card.getAttribute('data-price-amount')
                                || card.querySelector('[data-price-amount]')?.getAttribute('data-price-amount')
                                || '';
                            let price = parseFloat((priceAttr || '').replace(/,/g, ''));
                            if (!Number.isFinite(price) || price <= 0) {
                                const m = re.exec(card.textContent || '');
                                price = m ? parseFloat((m[1] || '').replace(/,/g, '')) : 0;
                            }
                            const linkEl = card.querySelector('a[href]');
                            let href = linkEl ? (linkEl.href || linkEl.getAttribute('href') || '') : '';
                            if (href.startsWith('/')) href = location.origin + href;
                            const titleEl = card.querySelector('.product-item-link, a[title], h2, h3');
                            const title = (
                                titleEl?.getAttribute('title')
                                || titleEl?.textContent
                                || ''
                            ).replace(/\\s+/g, ' ').trim();
                            const img = (card.querySelector('img')?.src || '');
                            if (!href || !title || title.length < 5 || !Number.isFinite(price) || price <= 0) return;
                            out.push({title, href, price, img});
                        });

                        // Fallback: generic anchor sweep for any remaining products
                        if (out.length === 0) {
                            const seen = new Set(out.map(x => x.href.split('?')[0]));
                            const anchors = Array.from(document.querySelectorAll('a[href]')).slice(0, 500);
                            for (const a of anchors) {
                                if (out.length >= 30) break;
                                let href = a.href || a.getAttribute('href') || '';
                                if (!href || href.includes('catalogsearch') || href.includes('#')) continue;
                                if (href.startsWith('/')) href = location.origin + href;
                                const key = href.split('?')[0];
                                if (seen.has(key)) continue;
                                const node = a.closest('article,li,div') || a;
                                const title = ((a.title || a.textContent || node.textContent || '').replace(/\\s+/g, ' ').trim());
                                if (!title || title.length < 8) continue;
                                const m = re.exec(node.textContent || '');
                                if (!m) continue;
                                const price = parseFloat((m[1] || '').replace(/,/g, ''));
                                if (!Number.isFinite(price) || price <= 0) continue;
                                const img = (node.querySelector('img')?.src || '');
                                seen.add(key);
                                out.push({title, href, price, img});
                            }
                        }
                        return out;
                    }"""
                )

                term_added = 0
                for item in raw or []:
                    try:
                        title = str(item.get("title", "")).strip()[:200]
                        price = float(item.get("price", 0) or 0)
                        href = str(item.get("href", ""))
                        img = str(item.get("img", ""))

                        if not title or len(title) < 5 or price <= 0:
                            continue
                        if price < min_price or price > max_price:
                            continue
                        if not href.startswith("http"):
                            continue

                        external_id = f"bargainhardware_{abs(hash(href.split('?')[0]))}"
                        if external_id in seen:
                            continue
                        seen.add(external_id)

                        results.append(RawListing(
                            external_id=external_id,
                            title=title,
                            price=price,
                            url=href,
                            location=None,
                            condition="refurb",
                            description="",
                            image_urls=[img] if img else [],
                            source_name="BargainHardware",
                        ))
                        term_added += 1
                    except Exception:
                        continue

                log.info("bargainhardware.playwright.term_done", term=term, found=term_added)
                record_term_result(term=term, found=term_added, new=term_added, source_name="BargainHardware")

            except Exception as exc:
                log.error("bargainhardware.playwright.error", term=term, error=str(exc))
                record_term_result(term=term, found=0, new=0, error=str(exc)[:120], source_name="BargainHardware")
                continue

        try:
            await browser.close()
        except Exception:
            pass

    log.info("bargainhardware.playwright.done", total=len(results))
    return results
