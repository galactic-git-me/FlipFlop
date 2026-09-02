"""Sold/completed-listing comparables adapter (PRD §11.4/§11.5 — eBay New/Used
Sold, the two mandatory benchmarks).

Scrapes eBay UK's public sold/completed listings using ScrapingBee proxy service
to bypass anti-bot detection. ScrapingBee handles residential IP rotation,
realistic headers, and JavaScript rendering if needed.

Falls back gracefully: if sold comps are unavailable, the pricing engine
(benchmarks.py) treats that as first-class and degrades to the next source
in the priority chain (BIN), never fabricating results.
"""
from __future__ import annotations

import re
import os
import json
import random
import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import urlencode

import httpx
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
import structlog

from app.services.proxy import apply_httpx_proxy, playwright_proxy_config
from app.services.browser_pool import BACKGROUND_HEADED_ARGS, focus_page_for_human, managed_playwright
from app.services.playwright_scraper import chromium_available

log = structlog.get_logger(__name__)
ua = UserAgent()
_EBAY_VERIFICATION_BLOCK_UNTIL = 0.0


@dataclass
class SoldComp:
    price: float
    postage: float
    condition: str
    sold_at: str
    url: str | None = None
    title: str | None = None  # eBay listing title (for build description & RAM filtering)


@dataclass
class SoldCompsResult:
    available: bool
    comps: list[SoldComp] = field(default_factory=list)
    unavailable_reason: str | None = None


class EbayLoginRequired(RuntimeError):
    """Raised when sold-comps retrieval needs a human eBay sign-in."""


class SoldCompsAdapter(ABC):
    """Fetches recently-sold/completed comparable listings for a query."""

    @abstractmethod
    async def fetch(self, query: str, condition: str) -> SoldCompsResult: ...


class UnavailableSoldCompsAdapter(SoldCompsAdapter):
    """Production adapter — PENDING. Returns an explicit unavailable result
    for every query rather than fabricating sold prices. Wire up eBay
    Marketplace Insights API access (or a compliant sold-listings scraper)
    here when available, and swap this out in benchmarks.py.
    """

    async def fetch(self, query: str, condition: str) -> SoldCompsResult:
        return SoldCompsResult(
            available=False,
            unavailable_reason=(
                "eBay sold/completed-listing data requires Marketplace Insights API access, "
                "which is not currently provisioned. See docs/ARCHITECTURE_GAP_ANALYSIS.md §4."
            ),
        )


class LiveSoldCompsAdapter(SoldCompsAdapter):
    """Production adapter — scrapes eBay UK's public completed/sold listings
    using direct HTTP requests with spoofed headers, the same proven technique
    as app.services.resale_scraper. Avoids Playwright/headless-browser detection
    by using httpx with random User-Agent and browser-mimicking headers.

    Strategy:
    1. Two-pass approach: Desktop PCs category (179) first, then all categories (0)
    2. Dual-filter for BIN+sold/completed (LH_Sold=1&LH_Complete=1&LH_BIN=1)
    3. Breaks early when sufficient results found (5+ comps)
    4. Graceful error handling: returns unavailable rather than fabricating

    This is a compliant public-search scrape, the same class of access eBay's
    own public search UI performs.
    """

    _CONDITION_IDS = {"new": "1000", "used": "3000"}
    _MIN_PRICE = 3.0
    _MAX_PRICE = 3000.0
    _MIN_COMPS_BEFORE_BREAK = 5  # stop searching after finding this many

    async def fetch(self, query: str, condition: str) -> SoldCompsResult:
        try:
            comps = await self._fetch_sold_comps(query, condition)
            if not comps:
                return SoldCompsResult(available=False, unavailable_reason="No comparable sold listings found")
            return SoldCompsResult(available=True, comps=comps)
        except Exception as exc:
            return SoldCompsResult(available=False, unavailable_reason=f"eBay scrape failed: {exc}")

    async def _fetch_sold_comps(self, query: str, condition: str) -> list[SoldComp]:
        """Dual-pass scrape via ScrapingBee: Desktop PCs category first (179), then all categories (0).

        Uses ScrapingBee to bypass eBay anti-bot detection via residential IP rotation
        and realistic browser rendering.
        """
        import random
        from app.config import get_settings

        comps: list[SoldComp] = []
        condition_id = self._CONDITION_IDS.get(condition)
        settings = get_settings()
        scrapingbee_key = settings.scrapingbee_api_key

        if not scrapingbee_key:
            log.error("sold_comps.missing_scrapingbee_key")
            return []

        for sacat in ("179", "0"):  # Desktop PCs → all categories
            params = {
                "_nkw": query,
                "LH_Sold": "1",
                "LH_Complete": "1",
                "LH_BIN": "1",       # fixed-price sold comps only
                "_sacat": sacat,
                "_sop": "12",        # most recent first
                "LH_PrefLoc": "1",   # UK sellers preferred
                "_ipg": "60",
            }
            if condition_id:
                params["LH_ItemCondition"] = condition_id

            # Build eBay URL
            from urllib.parse import urlencode
            ebay_url = f"https://www.ebay.co.uk/sch/i.html?{urlencode(params)}"

            # Retry with backoff
            for attempt in range(3):
                try:
                    # Use ScrapingBee API to fetch HTML (handles anti-bot)
                    # ScrapingBee: premium_proxy required for eBay's strict anti-bot
                    scrapingbee_params = {
                        "api_key": scrapingbee_key,
                        "url": ebay_url,
                        "premium_proxy": "true",  # Required for eBay
                        "block_resources": "false",  # Allow all resources for proper parsing
                    }

                    async with httpx.AsyncClient(timeout=60) as client:
                        resp = await client.get(
                            "https://app.scrapingbee.com/api/v1",
                            params=scrapingbee_params,
                        )

                    if resp.status_code in (401, 403):
                        # Authentication/authorisation failures are
                        # configuration errors, not transient network errors.
                        # Retrying them only stalls pricing while guaranteeing
                        # the same response on every attempt/category pass.
                        log.error(
                            "sold_comps.scrapingbee_auth_failed",
                            query=query,
                            condition=condition,
                            status=resp.status_code,
                        )
                        raise RuntimeError(
                            f"ScrapingBee rejected the configured credential (HTTP {resp.status_code})"
                        )

                    if resp.status_code != 200:
                        log.debug(
                            "sold_comps.scrapingbee_error",
                            query=query,
                            condition=condition,
                            sacat=sacat,
                            status=resp.status_code,
                            attempt=attempt,
                        )
                        await asyncio.sleep(2.0 + random.uniform(0, 2.0))
                        continue

                    html = resp.text
                    if len(html) < 2000:
                        log.debug(
                            "sold_comps.scrapingbee_small_response",
                            query=query,
                            condition=condition,
                            sacat=sacat,
                            size=len(html),
                        )
                        await asyncio.sleep(1.0)
                        continue

                    batch = self._extract_comps_from_html(html, condition)
                    comps.extend(batch)
                    log.debug(
                        "sold_comps.fetch_pass",
                        query=query,
                        condition=condition,
                        sacat=sacat,
                        found=len(batch),
                    )
                    break  # Success, break retry loop

                except Exception as exc:
                    log.debug(
                        "sold_comps.fetch_error",
                        query=query,
                        condition=condition,
                        sacat=sacat,
                        attempt=attempt,
                        error=str(exc),
                    )
                    if attempt < 2:
                        await asyncio.sleep(2.0 + random.uniform(0, 2.0))

            # Break early if we have enough comps
            if len(comps) >= self._MIN_COMPS_BEFORE_BREAK:
                break

            # Delay between category passes
            await asyncio.sleep(random.uniform(1.0, 2.0))

        return comps

    def _extract_comps_from_html(self, html: str, condition: str) -> list[SoldComp]:
        """Extract sold prices from eBay HTML, skipping auctions and price ranges."""
        comps: list[SoldComp] = []
        soup = BeautifulSoup(html, "lxml")

        # eBay completed listings use .s-item structure
        items = soup.select(".s-item:not(.s-item--placeholder)")
        if not items:
            # Try new card structure as fallback
            items = soup.select(".s-card[data-listingid]")

        for item in items:
            try:
                # The new result layout includes sponsored "Shop on eBay"
                # cards alongside completed listings.  Only accept cards that
                # eBay itself labels as sold.
                if "s-card" in (item.get("class") or []) and not item.select_one(
                    "[aria-label='Sold item']"
                ):
                    continue

                # Skip auction items (those with bid counts)
                bid_el = item.select_one(
                    ".s-item__bids, .x-bid-count, [class*='bid--'], [class*='bidCount']"
                )
                if bid_el and re.search(r"\d+\s*bid", bid_el.get_text(strip=True), re.I):
                    continue

                # Extract price
                price_el = (
                    item.select_one(".s-item__price .POSITIVE")
                    or item.select_one(".s-item__price")
                    or item.select_one("[class*='s-card__price']")
                )
                if not price_el:
                    continue

                price_text = price_el.get_text(strip=True)

                # Skip price ranges
                if re.search(r"\bto\b|–|—", price_text, re.I):
                    continue

                price = self._parse_price(price_text)
                if not (self._MIN_PRICE < price < self._MAX_PRICE):
                    continue

                # Extract URL and title
                title_el = item.select_one(".s-card__title")
                link_el = (
                    title_el.find_parent("a", href=re.compile(r"/itm/"))
                    if title_el
                    else None
                ) or item.select_one("a[href*='itm/']")
                url = link_el["href"].split("?")[0] if link_el else None
                title = title_el.get_text(strip=True) if title_el else (link_el.get_text(strip=True) if link_el else None)

                comps.append(
                    SoldComp(
                        price=price,
                        postage=0.0,  # eBay sold-search cards don't separate postage
                        condition=condition,
                        sold_at=datetime.now(timezone.utc).isoformat(),
                        url=url,
                        title=title,
                    )
                )
            except Exception:
                continue

        return comps

    @staticmethod
    def _parse_price(text: str) -> float:
        """Extract numeric price from text like '£1,234.56'."""
        match = re.search(r"[\d,]+\.?\d*", str(text).replace(",", ""))
        return float(match.group(0)) if match else 0.0


class PlaywrightSoldCompsAdapter(SoldCompsAdapter):
    """Production adapter — scrapes eBay UK's sold/completed listings using a
    real Playwright browser with a persisted, logged-in eBay session (the
    same storage_state file app.services.scraper's general listing scraper
    maintains at settings.ebay_playwright_state_path).

    Unauthenticated access to LH_Sold=1&LH_Complete=1 (both the direct httpx
    path in resale_scraper.py and the ScrapingBee-proxied path in
    LiveSoldCompsAdapter above) gets blocked/403'd by eBay's anti-bot — sold
    listings are gated harder than active ones since there's no official API
    fallback for them. A real logged-in session reading the page like an
    actual signed-in user is what gets past that wall.

    Shares app.services.scraper's Playwright semaphore so this and the
    general listing scraper never open two contexts against the same
    storage_state file concurrently.
    """

    _CONDITION_IDS = {"new": "1000", "used": "3000"}
    _MIN_PRICE = 3.0
    _MAX_PRICE = 3000.0
    _MIN_COMPS_BEFORE_BREAK = 5
    _CHALLENGE_MARKERS = (
        "verify you are human",
        "security verification",
        "checking your browser",
        "pardon our interruption",
        "confirm your identity",
        "robot check",
    )
    # eBay includes an invisible reCAPTCHA iframe in ordinary result pages.
    # Treat a page with actual result cards as usable even when that background
    # integration puts the word "captcha" in the raw HTML.
    _RESULTS_MARKERS = (
        "s-item__title",
        "srp-river-results",
        "srp-results",
    )
    _EBAY_ACCOUNT_CHECK_URL = "https://www.ebay.co.uk/myb/WatchList"
    _LOGIN_MARKERS = (
        "signin.ebay.",
        "sign in or register | ebay",
        "sign in to continue",
        '"pagename":"signin',
    )

    _STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3]});
Object.defineProperty(navigator, 'languages', {get: () => ['en-GB','en']});
"""

    async def fetch(self, query: str, condition: str) -> SoldCompsResult:
        try:
            comps = await self._fetch_sold_comps(query, condition)
            if not comps:
                return SoldCompsResult(available=False, unavailable_reason="No comparable sold listings found")
            return SoldCompsResult(available=True, comps=comps)
        except EbayLoginRequired as exc:
            return SoldCompsResult(available=False, unavailable_reason=str(exc))
        except Exception as exc:
            return SoldCompsResult(available=False, unavailable_reason=f"eBay sold-comps scrape failed: {exc}")

    async def _fetch_sold_comps(self, query: str, condition: str) -> list[SoldComp]:
        global _EBAY_VERIFICATION_BLOCK_UNTIL
        if not chromium_available():
            log.warning("sold_comps.playwright.chromium_unavailable")
            return []
        if time.monotonic() < _EBAY_VERIFICATION_BLOCK_UNTIL:
            # The cooldown belongs only to the disposable fallback browser
            # that hit a verification wall. If the operator has since started
            # the dedicated signed-in CDP browser, use it immediately instead
            # of making Refresh sold evidence remain broken for 30 minutes.
            cdp_url = os.getenv("BROWSER_CDP_URL", "http://localhost:9222").strip()
            cdp_ready = False
            if cdp_url:
                try:
                    async with httpx.AsyncClient(timeout=2.0) as client:
                        probe = await client.get(f"{cdp_url.rstrip('/')}/json/version")
                    cdp_ready = probe.status_code == 200
                except Exception:
                    cdp_ready = False
            if cdp_ready:
                _EBAY_VERIFICATION_BLOCK_UNTIL = 0.0
                log.info("sold_comps.playwright.verification_cooldown_cleared", query=query)
            else:
                log.info(
                    "sold_comps.playwright.verification_cooldown",
                    query=query,
                    remaining_seconds=round(_EBAY_VERIFICATION_BLOCK_UNTIL - time.monotonic()),
                )
                return []

        # Deferred import: app.services.scraper owns the shared login-state
        # file and semaphore for eBay Playwright sessions — reuse both so a
        # concurrent general-listing scrape never races this on the same
        # storage_state file.
        from app.services.scraper import _ebay_state_path, _EBAY_PLAYWRIGHT_SEM

        comps: list[SoldComp] = []
        condition_id = self._CONDITION_IDS.get(condition)

        async with _EBAY_PLAYWRIGHT_SEM:
            async with managed_playwright() as p:
                browser = None
                attached_cdp = False
                headless = False
                cdp_url = os.getenv("BROWSER_CDP_URL", "http://localhost:9222").strip()
                if cdp_url:
                    try:
                        browser = await p.chromium.connect_over_cdp(cdp_url, timeout=5000)
                        attached_cdp = True
                        log.debug("sold_comps.playwright.cdp_attached", cdp_url=cdp_url)
                    except Exception as exc:
                        log.debug("sold_comps.playwright.cdp_unavailable", cdp_url=cdp_url, error=str(exc))
                if browser is None:
                    # This fallback starts minimized so normal work is not
                    # interrupted. It must remain headed, however, because an
                    # eBay challenge can only be completed by the operator.
                    headless = os.getenv("SOLD_COMPS_HEADLESS", "0").lower() not in {"0", "false", "no"}
                    browser = await p.chromium.launch(
                        headless=headless,
                        args=[
                            "--disable-blink-features=AutomationControlled",
                            "--disable-dev-shm-usage",
                            "--disable-infobars",
                            "--window-size=1366,768",
                            "--lang=en-GB",
                            *([] if headless else BACKGROUND_HEADED_ARGS),
                        ],
                        proxy=playwright_proxy_config(),
                    )
                state_path = _ebay_state_path()
                context_kwargs = {
                    "user_agent": ua.random,
                    "locale": "en-GB",
                    "viewport": {"width": 1366, "height": 768},
                }
                if state_path.exists():
                    try:
                        with state_path.open(encoding="utf-8") as state_file:
                            state = json.load(state_file)
                        if not isinstance(state, dict):
                            raise ValueError("storage state is not an object")
                        context_kwargs["storage_state"] = str(state_path)
                    except (OSError, ValueError, json.JSONDecodeError) as exc:
                        # A zero-byte/partial state file must not prevent the
                        # headed browser from opening the eBay sign-in page.
                        # Successful manual login below replaces it cleanly.
                        log.warning(
                            "sold_comps.playwright.invalid_saved_state_ignored",
                            path=str(state_path),
                            error=str(exc),
                        )
                if attached_cdp and browser.contexts:
                    context = browser.contexts[0]
                else:
                    context = await browser.new_context(**context_kwargs)
                await context.add_init_script(self._STEALTH_JS)
                page = await context.new_page()
                try:
                    await self._ensure_ebay_login(page, query=query, headless=headless)
                    for sacat in ("179", "0"):  # Desktop PCs → all categories
                        params = {
                            "_nkw": query,
                            "LH_Sold": "1",
                            "LH_Complete": "1",
                            "LH_BIN": "1",  # fixed-price sold comps only
                            "_sacat": sacat,
                            "_sop": "12",  # most recent first
                            "LH_PrefLoc": "1",
                            "_ipg": "60",
                        }
                        if condition_id:
                            params["LH_ItemCondition"] = condition_id
                        url = f"https://www.ebay.co.uk/sch/i.html?{urlencode(params)}"

                        try:
                            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                            await page.wait_for_timeout(1200)
                            await page.mouse.wheel(0, 900)
                            await page.wait_for_timeout(600)
                            html = await page.content()
                        except Exception as exc:
                            log.debug("sold_comps.playwright.page_error", query=query, sacat=sacat, error=str(exc))
                            continue

                        if self._is_human_verification_page(await page.title(), html):
                            if not headless:
                                html = await self._wait_for_human_verification(page, query)
                            else:
                                log.warning(
                                    "sold_comps.playwright.verification_required_headless",
                                    query=query,
                                )
                                break

                        if self._is_human_verification_page(await page.title(), html):
                            # Do not immediately open another window for the
                            # fallback category. One unresolved challenge is
                            # authoritative for this lookup.
                            break

                        if self._is_ebay_login_page(page.url, await page.title(), html):
                            # eBay can expire a session between the account
                            # check and the actual sold-results request. Put
                            # the same real window in front of the operator
                            # and resume this exact request once signed in.
                            await self._ensure_ebay_login(page, query=query, headless=headless)
                            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                            await page.wait_for_timeout(1200)
                            html = await page.content()
                            if self._is_ebay_login_page(page.url, await page.title(), html):
                                raise EbayLoginRequired(
                                    "eBay sign-in did not complete, so sold prices were not refreshed."
                                )

                        batch = self._extract_comps_from_html(html, condition)
                        comps.extend(batch)
                        log.debug(
                            "sold_comps.playwright.fetch_pass",
                            query=query,
                            condition=condition,
                            sacat=sacat,
                            found=len(batch),
                        )

                        if len(comps) >= self._MIN_COMPS_BEFORE_BREAK:
                            break
                        await asyncio.sleep(random.uniform(0.8, 1.5))
                finally:
                    if attached_cdp:
                        await page.close()
                    else:
                        try:
                            await context.storage_state(path=str(state_path))
                        except Exception as exc:
                            log.debug("sold_comps.playwright.state_persist_failed", error=str(exc))
                        await context.close()
                        await browser.close()

        return comps

    @classmethod
    def _is_human_verification_page(cls, title: str, html: str) -> bool:
        body = html[:150000].lower()
        if any(marker in body for marker in cls._RESULTS_MARKERS):
            return False
        probe = f"{title} {body}".lower()
        return any(marker in probe for marker in cls._CHALLENGE_MARKERS)

    @classmethod
    def _is_ebay_login_page(cls, url: str, title: str, html: str) -> bool:
        """Detect eBay's authentication wall without relying on fragile nav UI.

        The protected Watch List route is eBay's own signed-in check.  The
        URL is the primary signal; the title/body markers cover their newer
        in-page sign-in experience.
        """
        probe = f"{url} {title} {html[:150000]}".lower()
        return any(marker in probe for marker in cls._LOGIN_MARKERS)

    async def _ensure_ebay_login(self, page, *, query: str, headless: bool) -> None:
        """Require a real signed-in eBay session before reading sold comps.

        Credentials are entered only by the operator in eBay's own window.
        On the headed fallback browser the window is initially hidden to keep
        normal work unobtrusive, then promoted here only when sign-in is
        actually required.  Its saved storage state is persisted by the
        caller's normal cleanup path.
        """
        try:
            await page.goto(self._EBAY_ACCOUNT_CHECK_URL, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(800)
            html = await page.content()
            if not self._is_ebay_login_page(page.url, await page.title(), html):
                return
        except Exception as exc:
            log.warning("sold_comps.playwright.login_check_failed", query=query, error=str(exc))
            return

        if headless:
            raise EbayLoginRequired(
                "eBay sign-in is required for sold prices, but SOLD_COMPS_HEADLESS is enabled. "
                "Run it headed so the eBay login window can be completed."
            )

        await focus_page_for_human(page)
        wait_seconds = max(60, int(os.getenv("EBAY_LOGIN_WAIT_SECONDS", "900")))
        poll_seconds = 2
        log.warning(
            "sold_comps.playwright.waiting_for_ebay_login",
            query=query,
            wait_seconds=wait_seconds,
            url=page.url,
        )

        loop = asyncio.get_running_loop()
        deadline = loop.time() + wait_seconds
        while loop.time() < deadline:
            await asyncio.sleep(poll_seconds)
            try:
                html = await page.content()
                if not self._is_ebay_login_page(page.url, await page.title(), html):
                    # Verify the account session on eBay's protected route,
                    # rather than trusting a cosmetic page transition.
                    await page.goto(self._EBAY_ACCOUNT_CHECK_URL, wait_until="domcontentloaded", timeout=30000)
                    await page.wait_for_timeout(800)
                    html = await page.content()
                    if not self._is_ebay_login_page(page.url, await page.title(), html):
                        log.info("sold_comps.playwright.ebay_login_completed", query=query)
                        return
            except Exception as exc:
                log.debug("sold_comps.playwright.login_wait_poll_failed", query=query, error=str(exc))

        raise EbayLoginRequired(
            f"Timed out after {wait_seconds // 60} minutes waiting for eBay sign-in; sold prices were not refreshed."
        )

    async def _wait_for_human_verification(self, page, query: str) -> str:
        """Keep the one visible eBay window alive while the operator solves
        the challenge, instead of closing/reopening it for every comp query."""
        global _EBAY_VERIFICATION_BLOCK_UNTIL
        await focus_page_for_human(page)
        wait_seconds = max(60, int(os.getenv("EBAY_HUMAN_VERIFICATION_WAIT_SECONDS", "300")))
        poll_seconds = 2
        log.warning(
            "sold_comps.playwright.waiting_for_human_verification",
            query=query,
            wait_seconds=wait_seconds,
            url=page.url,
        )

        loop = asyncio.get_running_loop()
        deadline = loop.time() + wait_seconds
        html = await page.content()
        while loop.time() < deadline:
            await asyncio.sleep(poll_seconds)
            try:
                html = await page.content()
                title = await page.title()
            except Exception:
                break
            if not self._is_human_verification_page(title, html):
                await page.wait_for_timeout(1200)
                html = await page.content()
                _EBAY_VERIFICATION_BLOCK_UNTIL = 0.0
                log.info("sold_comps.playwright.human_verification_completed", query=query)
                return html

        cooldown_seconds = max(300, int(os.getenv("EBAY_HUMAN_VERIFICATION_COOLDOWN_SECONDS", "1800")))
        _EBAY_VERIFICATION_BLOCK_UNTIL = time.monotonic() + cooldown_seconds
        log.warning("sold_comps.playwright.human_verification_timed_out", query=query)
        return html

    # Same markup, same parsing rules as LiveSoldCompsAdapter — eBay serves
    # identical HTML regardless of which client fetched it.
    _extract_comps_from_html = LiveSoldCompsAdapter._extract_comps_from_html
    _parse_price = staticmethod(LiveSoldCompsAdapter._parse_price)


class FixtureSoldCompsAdapter(SoldCompsAdapter):
    """Deterministic in-memory fixture for tests — never used in production
    wiring (see api/gem_radar.py, which instantiates LiveSoldCompsAdapter,
    unless explicitly overridden for a test).
    """

    def __init__(self, fixtures: dict[str, list[SoldComp]]):
        self._fixtures = fixtures

    async def fetch(self, query: str, condition: str) -> SoldCompsResult:
        comps = [c for c in self._fixtures.get(query, []) if c.condition == condition]
        if not comps:
            return SoldCompsResult(available=False, unavailable_reason="No fixture data for this query/condition")
        return SoldCompsResult(available=True, comps=comps)
