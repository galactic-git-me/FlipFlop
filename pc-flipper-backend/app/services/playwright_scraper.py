"""
Playwright-based scrapers for sites that require a real browser:
  - Gumtree  (JS SPA, no login needed)
  - Facebook Marketplace (JS SPA, works without login for ~20 items;
    works fully with saved login cookies)

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

        for term in search_terms[:3]:
            try:
                url = (
                    "https://www.facebook.com/marketplace/search"
                    f"?query={term.replace(' ', '%20')}"
                    f"&minPrice={int(min_price)}"
                    f"&maxPrice={int(max_price)}"
                    "&exact=false"
                    "&deliveryMethod=local_pick_up"
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

        page = await context.new_page()

        for term in search_terms[:8]:
            try:
                url = (
                    "https://www.preloved.co.uk/classifieds/computers/all/uk"
                    f"?keywords={term.replace(' ', '+')}"
                    f"&price_max={int(max_price)}"
                    f"&price_min={int(min_price)}"
                    "&sort=date_desc"
                )
                log.info("preloved.playwright.fetch", term=term)
                await page.goto(url, wait_until="domcontentloaded", timeout=25000)

                # Accept cookie banner if present
                try:
                    await page.click(
                        "button:has-text('Accept'), button:has-text('OK'), "
                        "[class*='cookie'] button, #cookie-accept",
                        timeout=3000,
                    )
                except Exception:
                    pass

                # Preloved is a React SPA — wait for JS to render listings.
                # 5 seconds is enough; networkidle never fires (background polling).
                await page.wait_for_timeout(5000)

                # Use page.evaluate to extract all listing data at once — far more
                # reliable than per-element queries on a React SPA where the DOM
                # layout varies by render. We look for £ in the nearest container.
                # NOTE: £ = Unicode U+00A3; using String.fromCharCode(163) avoids
                # any Python string encoding issues with the pound sign in the regex.
                raw_listings = await page.evaluate("""
                    () => {
                        const POUND = String.fromCharCode(163);
                        const priceRe = new RegExp(POUND + '\\\\s*([\\\\d,]+\\\\.?\\\\d*)');
                        const results = [];
                        const seen = new Set();
                        const links = document.querySelectorAll('a[href*="/adverts/show/"]');
                        for (const link of links) {
                            const href = link.getAttribute('href') || '';
                            if (!href || seen.has(href)) continue;
                            seen.add(href);

                            // Walk up DOM tree until we find a node with non-empty text
                            // containing a price — avoids empty-container issue
                            let container = link;
                            let node = link.parentElement;
                            let depth = 0;
                            while (node && depth < 12) {
                                const txt = node.innerText || '';
                                if (txt.length > 5 && priceRe.test(txt)) {
                                    container = node;
                                    break;
                                }
                                node = node.parentElement;
                                depth++;
                            }

                            // Extract price — look for £ in the container text
                            const containerText = (container.innerText || '');
                            const priceMatch = priceRe.exec(containerText);
                            const price = priceMatch ? priceMatch[1].replace(/,/g, '') : '';

                            // Title: link text → fallback to heading → URL slug
                            let title = (link.innerText || '').trim().split('\\n')[0].trim();
                            if (!title || title.length < 5) {
                                const h = container.querySelector('h1, h2, h3, h4');
                                title = h ? h.innerText.trim() : '';
                            }
                            if (!title || title.length < 5) {
                                const parts = href.split('/');
                                const slug = parts[parts.length - 1] || parts[parts.length - 2] || '';
                                title = slug.replace(/-/g, ' ').replace(/_/g, ' ');
                            }

                            // Image in container
                            const img = container.querySelector('img');
                            const imgSrc = img ? (img.getAttribute('src') || '') : '';

                            // Location text
                            const locEl = container.querySelector(
                                '[class*="location"], [class*="area"], [class*="region"]'
                            );
                            const location = locEl ? locEl.innerText.trim() : '';

                            results.push({ href, title, price, imgSrc, location });
                        }
                        return results;
                    }
                """)

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

                        # External ID from the numeric segment of the URL
                        parts = href.rstrip("/").split("/")
                        # URL form: /adverts/show/<numeric-id>/<slug>
                        numeric_id = next(
                            (p for p in reversed(parts) if p.isdigit()), None
                        ) or parts[-1]
                        external_id = "preloved_" + numeric_id
                        if external_id in seen:
                            continue
                        seen.add(external_id)

                        price_str = item.get("price", "")
                        price = float(price_str) if price_str else 0.0
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


def _load_fb_cookies() -> list | None:
    """Load Facebook session cookies from fb_cookies.json if it exists."""
    if not FB_COOKIES_PATH.exists():
        return None
    try:
        raw = json.loads(FB_COOKIES_PATH.read_text())
        # Cookie Editor exports as a list of dicts with 'name','value','domain',etc.
        # Playwright wants: name, value, domain, path
        cookies = []
        for c in raw:
            if "facebook.com" in c.get("domain", ""):
                cookies.append({
                    "name": c["name"],
                    "value": c["value"],
                    "domain": c.get("domain", ".facebook.com"),
                    "path": c.get("path", "/"),
                    "secure": c.get("secure", True),
                    "httpOnly": c.get("httpOnly", False),
                    "sameSite": c.get("sameSite", "None"),
                })
        return cookies if cookies else None
    except Exception as exc:
        log.warning("fb_cookies.load_error", error=str(exc))
        return None
