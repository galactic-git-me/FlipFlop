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
import re
import random
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

import structlog

log = structlog.get_logger(__name__)

# Path to optional Facebook session cookies
FB_COOKIES_PATH = Path(__file__).parent.parent.parent / "fb_cookies.json"

# Stealth args that suppress automation signals
_STEALTH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-extensions",
    "--disable-infobars",
    "--window-size=1366,768",
    "--lang=en-GB",
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

async def _make_context(playwright, cookies: list | None = None):
    browser = await playwright.chromium.launch(
        headless=True,
        args=_STEALTH_ARGS,
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
        if "Executable doesn't exist" in msg or "chromium" in msg.lower():
            log.error(
                "playwright.chromium_not_installed",
                error=msg,
                fix="Run this command once: playwright install chromium",
            )
        raise


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
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        log.error(
            "playwright_not_installed",
            fix="pip install playwright && playwright install chromium",
        )
        return []

    results: list[RawListing] = []
    seen: set[str] = set()

    async with async_playwright() as p:
        try:
            browser, context = await _launch_browser(p)
        except Exception:
            return []

        page = await context.new_page()

        for term in search_terms[:6]:  # cap terms — each takes ~5s
            try:
                url = (
                    "https://www.gumtree.com/search"
                    f"?q={term.replace(' ', '+')}"
                    f"&search_category=desktop-pcs-towers-computers"
                    f"&max_price={int(max_price)}"
                    f"&min_price={int(min_price)}"
                    "&sort=date"
                    "&distance=nationwide"
                )
                log.info("gumtree.playwright.fetch", url=url)
                await page.goto(url, wait_until="domcontentloaded", timeout=20000)

                # Accept cookie banner if present
                try:
                    await page.click(
                        "button:has-text('Accept'), button:has-text('I Accept'), "
                        "[data-testid='cookie-accept'], #gdpr-banner-accept",
                        timeout=3000,
                    )
                    await asyncio.sleep(0.5)
                except Exception:
                    pass

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
                            "[data-q='listing-title'], .listing-title, h2, h3"
                        )
                        price_el = await card.query_selector(
                            "[data-q='listing-price'], .listing-price strong, "
                            ".listing-price, [class*='price']"
                        )
                        link_el = await card.query_selector(
                            "a[href*='/ad/'], a[href*='/p/'], a[href]"
                        )
                        img_el = await card.query_selector("img")
                        loc_el = await card.query_selector(
                            "[data-q='listing-location'], .listing-location, [class*='location']"
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
                            continue

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
                    except Exception:
                        continue

            except Exception as exc:
                log.error("gumtree.playwright.error", term=term, error=str(exc))
                continue

        await browser.close()

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
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        log.error(
            "playwright_not_installed",
            fix="pip install playwright && playwright install chromium",
        )
        return []

    # Load cookies if available
    cookies = _load_fb_cookies()
    if cookies:
        log.info("facebook.playwright.cookies_loaded", count=len(cookies))
    else:
        log.info("facebook.playwright.no_cookies", hint="Save fb_cookies.json for full access")

    results: list[RawListing] = []
    seen: set[str] = set()

    async with async_playwright() as p:
        try:
            browser, context = await _make_context(p, cookies)
        except Exception as exc:
            msg = str(exc)
            if "Executable doesn't exist" in msg or "chromium" in msg.lower():
                log.error(
                    "playwright.chromium_not_installed",
                    fix="Run: playwright install chromium",
                )
            return []

        page = await context.new_page()

        for term in search_terms[:20]:
            try:
                url = (
                    "https://www.facebook.com/marketplace/search"
                    f"?query={term.replace(' ', '%20')}"
                    f"&minPrice={int(min_price)}"
                    f"&maxPrice={int(max_price)}"
                    "&exact=false"
                )
                log.info("facebook.playwright.fetch", url=url)
                await page.goto(url, wait_until="domcontentloaded", timeout=25000)

                # Dismiss any login/cookie modals
                for selector in [
                    "div[aria-label='Close']",
                    "button:has-text('Allow all cookies')",
                    "button:has-text('Accept all')",
                    "[data-testid='cookie-policy-manage-dialog-accept-button']",
                ]:
                    try:
                        await page.click(selector, timeout=2000)
                        await asyncio.sleep(0.3)
                    except Exception:
                        pass

                # Check if we hit the login wall
                login_wall = await page.query_selector(
                    "input[name='email'], form[data-testid='royal_login_form']"
                )
                if login_wall:
                    log.warning(
                        "facebook.playwright.login_required",
                        hint="Save fb_cookies.json — see playwright_scraper.py instructions",
                    )
                    break  # No point trying other terms without auth

                # Wait for listing cards
                try:
                    await page.wait_for_selector(
                        "[data-testid='marketplace_feed_item'], "
                        "[aria-label='Marketplace item'], "
                        "div[class*='x3ct3a4']",  # FB uses hashed class names
                        timeout=10000,
                    )
                except Exception:
                    pass  # Some items may still be visible

                await asyncio.sleep(random.uniform(1.0, 2.0))

                # Scroll once to load more
                await page.evaluate("window.scrollBy(0, 800)")
                await asyncio.sleep(1.0)

                # Extract items — FB's DOM uses aria-label heavily
                items = await page.query_selector_all(
                    "[data-testid='marketplace_feed_item'], "
                    "[aria-label='Marketplace item'], "
                    "a[href*='/marketplace/item/']"
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
                    # Fallback: parse direct marketplace item anchors if card selectors failed.
                    items = await page.query_selector_all("a[href*='/marketplace/item/']")

                for item in items:
                    try:
                        # Get the link element (may be the item itself)
                        link_el = item if await item.get_attribute("href") else \
                                  await item.query_selector("a[href*='/marketplace/item/']")
                        if not link_el:
                            continue

                        href = await link_el.get_attribute("href") or ""
                        if not href.startswith("http"):
                            href = "https://www.facebook.com" + href

                        # Item ID from URL
                        m = re.search(r"/item/(\d+)", href)
                        if not m:
                            continue
                        external_id = f"fb_{m.group(1)}"
                        if external_id in seen:
                            continue
                        seen.add(external_id)

                        # Title and price are in span elements within the card
                        spans = await item.query_selector_all("span")
                        texts = [
                            (await s.inner_text()).strip()
                            for s in spans
                            if (await s.inner_text()).strip()
                        ]

                        # Price is usually the first span with a £ sign
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

                        results.append(RawListing(
                            external_id=external_id,
                            title=title,
                            price=price,
                            url=href,
                            location=None,
                            condition="used",
                            description="",
                            image_urls=[image_url] if image_url else [],
                            source_name="Facebook Marketplace",
                        ))
                    except Exception:
                        continue

            except Exception as exc:
                log.error("facebook.playwright.error", term=term, error=str(exc))
                continue

        await browser.close()

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
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        log.error(
            "playwright_not_installed",
            fix="pip install playwright && playwright install chromium",
        )
        return []

    results: list[RawListing] = []
    seen: set[str] = set()

    async with async_playwright() as p:
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
        except Exception:
            pass
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
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        log.error("playwright_not_installed", fix="pip install playwright && playwright install chromium")
        return []

    results: list[RawListing] = []
    seen: set[str] = set()
    intercepted: list[dict] = []

    async with async_playwright() as p:
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
                    except Exception:
                        pass

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
            except Exception:
                pass

            # Filter to UK auctions using the country dropdown
            try:
                await page.select_option("#countryFilter", "United Kingdom")
                await asyncio.sleep(2)
            except Exception:
                pass

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
            for auction_href in auction_links[:6]:
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

                    # BidJS renders lots as <li> elements inside the auction section
                    lot_els = await page.query_selector_all(
                        "section[aria-label='Auction Listings'] li, "
                        "ul.timed-auction__lots li, "
                        "#lot-list li, "
                        ".bidjs-lot, [class*='timed-lot']"
                    )
                    log.info("apex.playwright.lots", href=auction_href, count=len(lot_els))

                    for lot_el in lot_els:
                        try:
                            title_el = await lot_el.query_selector("h3, h2, h4, .lot-title, .title, a[title]")
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

                            link_el = await lot_el.query_selector("a[href]")
                            href_val = await link_el.get_attribute("href") if link_el else ""
                            if href_val and not href_val.startswith("http"):
                                href_val = "https://www.apexauctions.co.uk/auction/" + href_val.lstrip("/")

                            price_el = await lot_el.query_selector(
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

_AUCTION_PC_KW = {
    "pc", "computer", "desktop", "tower", "workstation", "server",
    "i3", "i5", "i7", "i9", "ryzen", "xeon",
    "optiplex", "elitedesk", "thinkcentre", "prodesk", "thinkstation",
    "nvidia", "radeon", "rtx", "gtx", "gpu", "graphics",
    "z240", "z440", "z640",
    # component and chassis lanes
    "motherboard", "mainboard", "cpu", "processor", "ram", "ddr4", "ddr5",
    "ssd", "nvme", "psu", "power supply", "case", "chassis", "mid tower", "atx",
}

_AUCTION_SEARCH_TERMS = [
    "desktop pc",
    "gaming pc",
    "computer tower",
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
                except Exception:
                    pass

            if wait_selector:
                try:
                    await page.wait_for_selector(wait_selector, timeout=12000)
                except Exception:
                    log.warning(f"{site_name}.playwright.no_results", term=term)
                    continue

            await asyncio.sleep(random.uniform(1.0, 2.0))
            await page.evaluate("window.scrollBy(0, 600)")
            await asyncio.sleep(0.8)

            # Try lot selectors in priority order
            cards = []
            for sel in lot_selectors:
                cards = await page.query_selector_all(sel)
                if cards:
                    break

            log.info(f"{site_name}.playwright.cards", term=term, count=len(cards))
            kept = 0
            skipped_no_title = 0
            skipped_keyword = 0

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
                    if not title or len(title) < 5:
                        skipped_no_title += 1
                        continue
                    t = title.lower()
                    if not any(kw in t for kw in _AUCTION_PC_KW):
                        # Some auction search pages are catalogue cards with sparse titles.
                        # If search term itself is target-like, keep the card as a lead.
                        if not any(kw in term.lower() for kw in _AUCTION_PC_KW):
                            skipped_keyword += 1
                            continue
                    if _is_mini_pc(title):
                        continue

                    # URL
                    href = ""
                    for sel in link_selectors:
                        el = await card.query_selector(sel)
                        if el:
                            href = await el.get_attribute("href") or ""
                            if href:
                                break
                    if not href:
                        continue
                    if not href.startswith("http"):
                        href = base_url + href

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

                    if max_price > 0 and price > max_price:
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
            )

        except Exception as exc:
            log.error(f"{site_name}.playwright.error", term=term, error=str(exc))
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
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return []

    def url_fn(term, lo, hi):
        return (
            f"https://www.wilsonsauctions.com/lots"
            f"?query={term.replace(' ', '+')}"
            f"&priceMin={int(lo)}&priceMax={int(hi)}"
            f"&categoryId=65"  # IT / Technology category
        )

    async with async_playwright() as p:
        return await _scrape_auction_site(
            p,
            site_name="Wilsons Auctions",
            search_url_fn=url_fn,
            lot_selectors=[
                ".lot-card",
                ".auction-lot",
                "[class*='lot-item']",
                "article.lot",
                ".search-result-item",
                "[class*='search-result']",
                "li[class*='lot']",
                "div[class*='lot']",
            ],
            title_selectors=["h3", "h2", ".lot-title", ".title", "[class*='title']", "a"],
            price_selectors=[
                ".current-bid", ".estimate", "[class*='price']",
                "[class*='bid']", "[class*='estimate']", "strong"
            ],
            link_selectors=["a[href*='/lot/']", "a[href*='/lots/']", "a[href]"],
            search_terms=search_terms[:20],
            min_price=min_price,
            max_price=max_price,
            wait_selector=".lot-card, .auction-lot, [class*='lot-item'], article",
            base_url="https://www.wilsonsauctions.com",
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
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return []

    def url_fn(term, lo, hi):
        return (
            f"https://www.i-bidder.com/en-gb/auction-catalogues/all/search"
            f"?q={term.replace(' ', '+')}"
            f"&country=gb"
            f"&priceFrom={int(lo)}&priceTo={int(hi)}"
        )

    async with async_playwright() as p:
        return await _scrape_auction_site(
            p,
            site_name="i-bidder",
            search_url_fn=url_fn,
            lot_selectors=[
                ".lot-card",
                "[class*='lot-card']",
                ".search-result",
                "[class*='search-result']",
                "article.lot",
                ".auction-lot",
                "li.lot",
                "[data-lot-id]",
            ],
            title_selectors=[
                ".lot-card__title", ".lot-title", "h3", "h2",
                "[class*='title']", "a[title]", "a"
            ],
            price_selectors=[
                ".lot-card__estimate", ".current-bid", ".estimate",
                "[class*='estimate']", "[class*='price']", "[class*='bid']"
            ],
            link_selectors=[
                "a[href*='/lot/']", "a[href*='/catalogue/']",
                "a[href*='/auction/']", "a[href]"
            ],
            search_terms=search_terms[:20],
            min_price=min_price,
            max_price=max_price,
            wait_selector=".lot-card, .search-result, [class*='lot-card'], article",
            base_url="https://www.i-bidder.com",
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
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return []

    def url_fn(term, lo, hi):
        return (
            f"https://www.bidspotter.co.uk/en-us/auction-catalogues"
            f"?search={term.replace(' ', '+')}"
            f"&country=gb"
        )

    async with async_playwright() as p:
        return await _scrape_auction_site(
            p,
            site_name="BidSpotter",
            search_url_fn=url_fn,
            lot_selectors=[
                ".bsp-lot-card",
                "[class*='lot-card']",
                ".item-card",
                "[class*='item-card']",
                ".auction-item",
                "[class*='auction-item']",
                "li[class*='lot']",
                "article",
            ],
            title_selectors=[
                ".bsp-lot-card__title", ".lot-title", ".item-title",
                "h3", "h2", "[class*='title']", "a"
            ],
            price_selectors=[
                ".bsp-lot-card__estimate", ".estimate", ".current-bid",
                "[class*='estimate']", "[class*='price']", "[class*='bid']"
            ],
            link_selectors=[
                "a[href*='/lot/']", "a[href*='/lots/']",
                "a[href*='/auction-catalogues/']", "a[href]"
            ],
            search_terms=search_terms[:20],
            min_price=min_price,
            max_price=max_price,
            wait_selector=".bsp-lot-card, .item-card, .auction-item, [class*='lot-card'], article",
            base_url="https://www.bidspotter.co.uk",
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
