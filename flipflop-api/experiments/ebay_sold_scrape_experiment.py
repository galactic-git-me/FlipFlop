"""EXPERIMENT — not wired into production. Do not import from app/ code.

Investigates whether eBay's sold/completed-listing search
(&LH_Complete=1&LH_Sold=1) can be scraped without ScrapingBee, using the same
"real browser" trick that FlipFlopXtension's content-script scraper relies on
for live listings.

Why the extension avoids anti-bot detection at all: it isn't an automated
HTTP client. flipflopXtension/src/background/scan-orchestrator.ts opens a
REAL chrome.tabs tab (the user's actual browser, actual cookies, actual TLS/
JS fingerprint) and navigates it to a normal eBay search URL; then
src/content/ebay-extractor.ts reads the already-rendered DOM from inside that
tab via a content script. eBay sees a completely ordinary human page load —
there is no bot signature to detect, because there is no bot request pattern.

That mechanism cannot be ported verbatim to a headless backend service (no
`chrome.tabs`, no user profile). This script tries two candidate
approximations, run head-to-head against the identical query:

  1. direct_http()  — httpx with an expanded, ordered header set closer to
     real Chrome navigation headers (sec-ch-ua/-mobile/-platform,
     sec-fetch-*, upgrade-insecure-requests) than the 3-header set already
     used in app/services/resale_scraper.py and the pre-ScrapingBee version
     of app/gem_radar/adapters/sold_comps.py. Cheapest to try, but per
     sold_comps.py's docstring this class of approach was already 403'd —
     included here mainly as a fresh data point since the header set is
     more complete than what was tried before.

  2. playwright_cdp() — if FLIPFLOP_TEST_CDP_URL / settings.browser_cdp_url
     points at a REAL running Chrome (launched with
     --remote-debugging-port=9222 under your own logged-in-or-not profile),
     Playwright attaches to that live browser and drives it — this is the
     closest server-side analogue to what the extension does, since it's
     genuinely your browser's fingerprint/cookies, not a fresh automation
     profile. Falls back to a stealth-launched headless Chromium (same
     _STEALTH_ARGS/_STEALTH_JS as app/services/playwright_scraper.py) if no
     CDP endpoint is configured, which is a much weaker approximation.

Run standalone, prints a comparison. Nothing here is cached, persisted, or
imported by production code — LiveSoldCompsAdapter/ai_build_generator.py are
untouched.

Usage:
    cd flipflop-api
    .venv\\Scripts\\python.exe -m experiments.ebay_sold_scrape_experiment "gaming pc i5-9600k rtx 3060"
"""
from __future__ import annotations

import asyncio
import random
import re
import sys
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx
from bs4 import BeautifulSoup

sys.path.insert(0, ".")  # allow `app.*` imports when run as a script from flipflop-api/

# fake_useragent's `.chrome` shortcut returns ANY UA containing "Chrome" in its
# string — including Android/Chrome ones — which would then contradict a
# `Sec-Ch-Ua-Platform: Windows` header and read as a spoofing mismatch to
# anti-bot heuristics. Use one fixed, internally-consistent desktop Chrome/
# Windows UA instead (same string proven in app/services/playwright_scraper.py).
_DESKTOP_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


@dataclass
class ExperimentComp:
    title: str
    price: float
    url: str | None


def _build_sold_url(query: str, sacat: str = "179") -> str:
    params = {
        "_nkw": query,
        "LH_Sold": "1",
        "LH_Complete": "1",
        "LH_BIN": "1",
        "_sacat": sacat,
        "_sop": "12",
        "LH_PrefLoc": "1",
        "_ipg": "60",
    }
    return f"https://www.ebay.co.uk/sch/i.html?{urlencode(params)}"


def _parse_price(text: str) -> float | None:
    if re.search(r"\bto\b|–|—", text, re.I):
        return None  # price ranges — ambiguous, skip
    match = re.search(r"[\d,]+\.\d{2}|[\d,]+", text.replace(",", ""))
    return float(match.group(0)) if match else None


def _extract_comps(html: str) -> list[ExperimentComp]:
    soup = BeautifulSoup(html, "lxml")
    items = soup.select(".s-item:not(.s-item--placeholder)") or soup.select(".s-card[data-listingid]")
    comps: list[ExperimentComp] = []
    for item in items:
        bid_el = item.select_one(".s-item__bids, [class*='bid']")
        if bid_el and re.search(r"\d+\s*bid", bid_el.get_text(strip=True), re.I):
            continue  # auction, not a fixed sold price
        price_el = item.select_one(".s-item__price .POSITIVE") or item.select_one(".s-item__price") or item.select_one("[class*='s-card__price']")
        if not price_el:
            continue
        price = _parse_price(price_el.get_text(strip=True))
        if price is None or not (3.0 < price < 5000.0):
            continue
        link_el = item.select_one("a[href*='itm/']")
        url = link_el["href"].split("?")[0] if link_el else None
        # Newer `.s-card` markup: the link only wraps the thumbnail image and
        # has no text of its own — the title lives in a separate sibling
        # element. Same migration FlipFlopXtension's ebay-extractor.ts
        # already accounts for (.s-item__title -> [class*='s-card__title']).
        title_el = item.select_one(".s-item__title") or item.select_one("[class*='s-card__title']")
        title = title_el.get_text(strip=True) if title_el else "Untitled"
        # eBay glues "Opens in a new window or tab" accessibility text
        # directly onto the title with no separating whitespace.
        title = re.sub(r"Opens in a new window or tab$", "", title).strip()
        # "Shop on eBay" cards are eBay's own sponsored placeholder tiles
        # (typically £20.00, no real listing behind them) mixed into search
        # results — not real sold comps.
        if title.lower() == "shop on ebay":
            continue
        comps.append(ExperimentComp(title=title, price=price, url=url))
    return comps


# ---------------------------------------------------------------------------
# Method 1: direct HTTP, expanded header set
# ---------------------------------------------------------------------------

def _chrome_navigation_headers() -> dict[str, str]:
    """Closer to what real Chrome sends on a typed-URL / clicked-link
    navigation than the minimal 3-header set elsewhere in this codebase."""
    return {
        "User-Agent": _DESKTOP_UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-GB,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "Referer": "https://www.google.com/",
        "Connection": "keep-alive",
    }


async def direct_http(query: str) -> tuple[list[ExperimentComp], str]:
    url = _build_sold_url(query)
    # http2=True would need the `h2` package (not installed in this venv) --
    # HTTP/1.1 is what resale_scraper.py's already-proven fetches use too.
    async with httpx.AsyncClient(timeout=25, follow_redirects=True) as client:
        # A same-session warm-up hit to the homepage before the search request
        # mimics a human landing on ebay.co.uk before searching, rather than a
        # cold GET straight at the search URL.
        try:
            await client.get("https://www.ebay.co.uk/", headers=_chrome_navigation_headers())
            await asyncio.sleep(random.uniform(0.8, 1.8))
        except Exception:
            pass
        resp = await client.get(url, headers=_chrome_navigation_headers())
    status_note = f"HTTP {resp.status_code}, {len(resp.text)} bytes"
    if resp.status_code != 200:
        return [], status_note
    return _extract_comps(resp.text), status_note


# ---------------------------------------------------------------------------
# Method 2: Playwright — prefer CDP-attach to a real browser, else stealth launch
# ---------------------------------------------------------------------------

_STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3]});
Object.defineProperty(navigator, 'languages', {get: () => ['en-GB','en']});
"""

_STEALTH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--window-size=1366,768",
    "--lang=en-GB",
]


async def playwright_cdp(query: str) -> tuple[list[ExperimentComp], str]:
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return [], "playwright not installed in this venv"

    import os
    from app.config import get_settings

    settings = get_settings()
    cdp_url = os.getenv("FLIPFLOP_TEST_CDP_URL", "").strip() or str(getattr(settings, "browser_cdp_url", "") or "").strip()
    url = _build_sold_url(query)

    async with async_playwright() as pw:
        browser = None
        used_cdp = False
        try:
            if cdp_url:
                browser = await pw.chromium.connect_over_cdp(cdp_url)
                context = browser.contexts[0] if browser.contexts else await browser.new_context(
                    user_agent=_DESKTOP_UA, viewport={"width": 1366, "height": 768}, locale="en-GB",
                )
                used_cdp = True
            else:
                browser = await pw.chromium.launch(headless=True, args=_STEALTH_ARGS)
                context = await browser.new_context(
                    user_agent=_DESKTOP_UA,
                    viewport={"width": 1366, "height": 768},
                    locale="en-GB",
                    timezone_id="Europe/London",
                )
                await context.add_init_script(_STEALTH_JS)

            page = await context.new_page()
            if not used_cdp:
                # Only relevant for a freshly stealth-launched browser with no
                # prior navigation history -- an already-authenticated CDP tab
                # doesn't need a homepage warm-up first.
                await page.goto("https://www.ebay.co.uk/", wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(random.uniform(0.8, 1.6))
            # networkidle times out on eBay's page (continuous background
            # ad/tracker requests never fully idle) even once the actual
            # content has finished loading -- domcontentloaded + a short
            # settle delay is what worked in manual verification.
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(random.uniform(2.0, 3.0))
            html = await page.content()
            note = f"playwright ok ({'CDP-attached' if used_cdp else 'stealth-launched'}), {len(html)} bytes"
            await page.close()
            if not used_cdp:
                await context.close()
            return _extract_comps(html), note
        except Exception as exc:
            return [], f"playwright error: {exc}"
        finally:
            if browser and not used_cdp:
                await browser.close()
            elif browser and used_cdp:
                # Don't close a browser we don't own — just disconnect.
                pass


async def main() -> None:
    query = sys.argv[1] if len(sys.argv) > 1 else "gaming pc i5-9600k rtx 3060"
    print(f"Query: {query!r}")
    print(f"URL:   {_build_sold_url(query)}\n")

    print("=== Method 1: direct HTTP (expanded headers) ===")
    comps1, note1 = await direct_http(query)
    print(f"{note1} -> {len(comps1)} comps")
    for c in comps1[:5]:
        print(f"  £{c.price:>7.2f}  {c.title[:70]}")

    print("\n=== Method 2: Playwright (CDP-attach if configured, else stealth) ===")
    comps2, note2 = await playwright_cdp(query)
    print(f"{note2} -> {len(comps2)} comps")
    for c in comps2[:5]:
        print(f"  £{c.price:>7.2f}  {c.title[:70]}")

    print("\n=== Summary ===")
    print(f"direct_http:    {len(comps1)} comps — {note1}")
    print(f"playwright_cdp: {len(comps2)} comps — {note2}")


if __name__ == "__main__":
    asyncio.run(main())
