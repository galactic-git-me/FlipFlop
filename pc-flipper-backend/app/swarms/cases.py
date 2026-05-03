"""
PC Cases Swarm — runs daily.
Searches for PC cases (new and used) across eBay UK, Amazon UK, Temu, and AliExpress.
eBay uses plain httpx. Amazon, Temu, AliExpress use a shared Playwright browser context
with stealth mode to bypass bot detection — same approach as the Gumtree/Facebook scrapers.
Cases are a key part of the flip — they transform a bare PC into a themed product.
"""
import re
import asyncio
import httpx
from bs4 import BeautifulSoup
from datetime import datetime
from dataclasses import dataclass
from fake_useragent import UserAgent

from app.database import AsyncSessionLocal
from app.models.part import Part, PartCategory, PartCondition
from app.models.price_history import PriceHistory, PriceHistoryType
import structlog

log = structlog.get_logger(__name__)
ua = UserAgent()

# Themes with practical search terms that actually appear on eBay/Amazon/AliExpress
CASE_THEMES = [
    # Generic gaming cases — highest stock, most results
    {"theme": "Gaming RGB", "terms": ["rgb gaming pc case atx", "gaming pc case rgb mid tower", "atx gaming case rgb"]},
    {"theme": "Tempered Glass", "terms": ["tempered glass gaming case atx", "pc case tempered glass rgb"]},
    {"theme": "Mini ITX", "terms": ["mini itx pc case gaming", "small form factor pc case gaming"]},

    # Sci-fi / themed — genuine products but search broadly
    {"theme": "Cyberpunk", "terms": ["cyberpunk gaming case", "neon pc case rgb", "cyberpunk atx case"]},
    {"theme": "Space / Astronaut", "terms": ["astronaut pc case", "space gaming case", "planet pc case rgb"]},
    {"theme": "Star Wars", "terms": ["star wars pc case", "darth vader pc case", "stormtrooper pc case"]},
    {"theme": "Alien", "terms": ["alien pc case gaming", "xenomorph pc case"]},
    {"theme": "Anime / Gaming Art", "terms": ["anime gaming pc case", "gaming pc case custom art", "custom printed pc case"]},

    # Novelty / eye-catching — these are real products on AliExpress / Temu
    {"theme": "Skull / Dark", "terms": ["skull pc case gaming", "dark gaming case skull"]},
    {"theme": "Transparent / Open Frame", "terms": ["open frame pc case atx", "transparent pc case gaming"]},
    {"theme": "Compact / Desktop", "terms": ["desktop gaming case compact atx", "slim gaming pc case"]},
]

SOURCES = [
    {"name": "eBay",              "fn": "ebay"},            # httpx — reliable, UK + worldwide
    {"name": "eBay (Worldwide)",  "fn": "ebay_worldwide"},  # same scraper, worldwide sellers
    {"name": "Amazon",            "fn": "amazon"},          # Playwright — stealth browser
    {"name": "Temu",              "fn": "temu"},            # Playwright — stealth browser
    {"name": "AliExpress",        "fn": "aliexpress"},      # Playwright — stealth browser
    {"name": "Scan",              "fn": "scan"},            # httpx
    {"name": "Overclockers",      "fn": "overclockers"},    # httpx
    {"name": "Box",               "fn": "box"},             # httpx
    {"name": "Etsy",              "fn": "etsy"},            # Playwright — JS-rendered
]


@dataclass
class RawCase:
    name: str
    price: float
    source_site: str
    source_url: str
    image_url: str
    theme: str
    specs: str = "ATX Mid Tower · New"


async def run_cases_swarm() -> dict:
    log.info("cases_swarm.start")
    stats = {"found": 0, "upserted": 0, "errors": 0}

    async with AsyncSessionLocal() as db:
        for theme_def in CASE_THEMES:
            for source in SOURCES:
                # Use up to 2 terms per source per theme for better coverage
                for term in theme_def["terms"][:2]:
                    try:
                        fn_key = source["fn"].replace("-", "_").replace(" ", "_")
                        scrape_fn = globals().get(f"_scrape_{fn_key}")
                        if not scrape_fn:
                            log.warning("cases.no_scraper", source=source["name"])
                            continue
                        cases = await scrape_fn(term, theme_def["theme"])
                        stats["found"] += len(cases)

                        for case in cases[:8]:  # Top 8 per search (was 5)
                            await _upsert_case(db, case)
                            stats["upserted"] += 1
                    except Exception as exc:
                        stats["errors"] += 1
                        log.error("cases.scrape.error", source=source["name"], term=term, error=str(exc))

        await db.commit()

    log.info("cases_swarm.done", **stats)
    return stats


async def _scrape_ebay(search: str, theme: str) -> list[RawCase]:
    """eBay UK — uses new .s-card[data-listingid] structure with .s-item fallback."""
    params = {
        "_nkw": search,
        "LH_BIN": "1",
        "LH_ItemCondition": "1000",  # New only
        "_sacat": "0",    # All categories — themed cases appear in multiple cats
        "_sop": "15",     # Sort: price + shipping lowest first
        "LH_PrefLoc": "2",  # Worldwide (many cases ship from China/HK)
        "_udhi": "350",   # Max £350
    }
    headers = {"User-Agent": ua.random, "Accept-Language": "en-GB"}
    cases = []
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get("https://www.ebay.co.uk/sch/i.html", params=params, headers=headers)
        if resp.status_code != 200:
            return cases
        soup = BeautifulSoup(resp.text, "lxml")

        # Try new card structure first
        items = soup.select(".s-card[data-listingid]")
        use_new = bool(items)
        if not items:
            items = soup.select(".s-item:not(.s-item--placeholder)")

        for item in items[:8]:
            try:
                if use_new:
                    title_el = (
                        item.select_one("[class*='s-card__title']") or
                        item.select_one(".s-item__title") or
                        item.select_one("h3")
                    )
                    price_el = (
                        item.select_one("[class*='s-card__price']") or
                        item.select_one(".s-item__price") or
                        item.select_one("[class*='price--']")
                    )
                    url_el = item.select_one("a[href*='/itm/']") or item.select_one("a[href]")
                    img_el = item.select_one("img")
                else:
                    title_el = item.select_one(".s-item__title")
                    price_el = item.select_one(".s-item__price")
                    url_el = item.select_one("a.s-item__link")
                    img_el = item.select_one("img.s-item__image-img")

                if not all([title_el, price_el, url_el]):
                    continue
                title = title_el.get_text(strip=True)
                if title.lower() in ("shop on ebay", ""):
                    continue
                price = _parse_price(price_el.get_text(strip=True))
                if price <= 0 or price > 350:
                    continue
                url = url_el.get("href", "")
                if not url.startswith("http"):
                    continue
                cases.append(RawCase(
                    name=title[:200],
                    price=price,
                    source_site="eBay",
                    source_url=url,
                    image_url=img_el.get("src", "") if img_el else "",
                    theme=theme,
                ))
            except Exception:
                continue
    except Exception as exc:
        log.warning("ebay.cases.error", error=str(exc))
    return cases


async def _scrape_ebay_worldwide(search: str, theme: str) -> list[RawCase]:
    """
    eBay UK with worldwide seller location — pulls in Chinese/HK sellers who list
    new ATX cases at 40-60% of UK retail with free shipping. Excellent for finding
    cheap themed cases to include in flips.
    """
    params = {
        "_nkw": search,
        "LH_BIN": "1",
        "LH_ItemCondition": "1000",  # New only
        "_sacat": "0",
        "_sop": "15",     # Price + shipping lowest first
        "LH_PrefLoc": "2",  # Worldwide
        "_udhi": "200",   # Max £200 (international cases are cheaper)
    }
    headers = {"User-Agent": ua.random, "Accept-Language": "en-GB"}
    cases = []
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get("https://www.ebay.co.uk/sch/i.html", params=params, headers=headers)
        if resp.status_code != 200:
            return cases
        soup = BeautifulSoup(resp.text, "lxml")

        items = soup.select(".s-card[data-listingid]")
        use_new = bool(items)
        if not items:
            items = soup.select(".s-item:not(.s-item--placeholder)")

        for item in items[:10]:
            try:
                if use_new:
                    title_el = (
                        item.select_one("[class*='s-card__title']") or
                        item.select_one(".s-item__title") or
                        item.select_one("h3")
                    )
                    price_el = (
                        item.select_one("[class*='s-card__price']") or
                        item.select_one(".s-item__price") or
                        item.select_one("[class*='price--']")
                    )
                    url_el = item.select_one("a[href*='/itm/']") or item.select_one("a[href]")
                    img_el = item.select_one("img")
                else:
                    title_el = item.select_one(".s-item__title")
                    price_el = item.select_one(".s-item__price")
                    url_el = item.select_one("a.s-item__link")
                    img_el = item.select_one("img.s-item__image-img")

                if not all([title_el, price_el, url_el]):
                    continue
                title = title_el.get_text(strip=True)
                if title.lower() in ("shop on ebay", ""):
                    continue
                price = _parse_price(price_el.get_text(strip=True))
                if price <= 0 or price > 200:
                    continue
                url = url_el.get("href", "")
                if not url.startswith("http"):
                    continue
                cases.append(RawCase(
                    name=title[:200],
                    price=price,
                    source_site="eBay",
                    source_url=url,
                    image_url=img_el.get("src", "") if img_el else "",
                    theme=theme,
                ))
            except Exception:
                continue
    except Exception as exc:
        log.warning("ebay_worldwide.cases.error", error=str(exc))
    return cases


# ── Shared Playwright browser factory for bot-protected sites ────────────────
# Amazon, Temu and AliExpress are JS-rendered SPAs that block plain httpx.
# We reuse a single browser context per swarm run to save on launch overhead.

_STEALTH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-extensions",
    "--disable-infobars",
    "--window-size=1366,768",
    "--lang=en-GB",
]
_STEALTH_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
_STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3]});
Object.defineProperty(navigator, 'languages', {get: () => ['en-GB','en']});
"""


async def _make_pw_context(playwright):
    """Launch a stealthy Chromium context. Returns (browser, context)."""
    browser = await playwright.chromium.launch(headless=True, args=_STEALTH_ARGS)
    context = await browser.new_context(
        user_agent=_STEALTH_UA,
        viewport={"width": 1366, "height": 768},
        locale="en-GB",
        timezone_id="Europe/London",
        java_script_enabled=True,
    )
    await context.add_init_script(_STEALTH_JS)
    return browser, context


async def _pw_get_page_html(page, url: str, wait_selector: str, timeout: int = 15000) -> str:
    """Navigate to URL and return page HTML once wait_selector appears (or timeout)."""
    await page.goto(url, wait_until="domcontentloaded", timeout=25000)
    try:
        await page.wait_for_selector(wait_selector, timeout=timeout)
    except Exception:
        pass  # grab whatever rendered
    await asyncio.sleep(random.uniform(0.8, 1.5))
    return await page.content()


import random


# ── Amazon UK ─────────────────────────────────────────────────────────────────

async def _scrape_amazon(search: str, theme: str) -> list[RawCase]:
    """
    Amazon UK — Playwright stealth browser.
    Amazon aggressively bot-detects plain httpx but a headless Chromium with stealth
    patches passes consistently.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        log.error("playwright_not_installed", fix="pip install playwright && playwright install chromium")
        return []

    cases = []
    url = f"https://www.amazon.co.uk/s?k={search.replace(' ', '+')}&i=computers"

    async with async_playwright() as p:
        try:
            browser, context = await _make_pw_context(p)
        except Exception as exc:
            log.warning("amazon.cases.browser_error", error=str(exc))
            return []

        page = await context.new_page()
        try:
            html = await _pw_get_page_html(page, url, '[data-component-type="s-search-result"]')
            soup = BeautifulSoup(html, "lxml")

            for item in soup.select('[data-component-type="s-search-result"]')[:10]:
                try:
                    title_el = item.select_one("h2 span")
                    price_whole = item.select_one(".a-price-whole")
                    price_frac  = item.select_one(".a-price-fraction")
                    url_el  = item.select_one("h2 a")
                    img_el  = item.select_one("img.s-image")
                    if not title_el or not url_el:
                        continue
                    price = 0.0
                    if price_whole:
                        frac = (price_frac.get_text(strip=True) if price_frac else "0").replace(".", "")
                        whole = price_whole.get_text(strip=True).replace(",", "").rstrip(".")
                        try:
                            price = float(f"{whole}.{frac}")
                        except ValueError:
                            pass
                    if price <= 0 or price > 350:
                        continue
                    href = url_el.get("href", "")
                    if not href.startswith("http"):
                        href = "https://www.amazon.co.uk" + href
                    cases.append(RawCase(
                        name=title_el.get_text(strip=True)[:200],
                        price=price,
                        source_site="Amazon",
                        source_url=href,
                        image_url=img_el.get("src", "") if img_el else "",
                        theme=theme,
                    ))
                except Exception:
                    continue
        except Exception as exc:
            log.warning("amazon.cases.scrape_error", error=str(exc))
        finally:
            await browser.close()

    log.info("amazon.cases.done", search=search, found=len(cases))
    return cases


# ── AliExpress ────────────────────────────────────────────────────────────────

async def _scrape_aliexpress(search: str, theme: str) -> list[RawCase]:
    """
    AliExpress — Playwright stealth browser.
    AliExpress is fully JS-rendered. Playwright renders the SPA and extracts
    product cards from the DOM after the search results load.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        log.error("playwright_not_installed", fix="pip install playwright && playwright install chromium")
        return []

    cases = []
    url = f"https://www.aliexpress.com/wholesale?SearchText={search.replace(' ', '+')}&g=y&SortType=price_asc"

    async with async_playwright() as p:
        try:
            browser, context = await _make_pw_context(p)
        except Exception as exc:
            log.warning("aliexpress.cases.browser_error", error=str(exc))
            return []

        page = await context.new_page()
        try:
            # AliExpress may show a region/language popup — dismiss it
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            for selector in ["button:has-text('Ship to')", ".close-btn", "[class*='close']", "button:has-text('OK')"]:
                try:
                    await page.click(selector, timeout=2000)
                    await asyncio.sleep(0.3)
                except Exception:
                    pass

            # Wait for product listing cards
            try:
                await page.wait_for_selector(
                    "a[href*='/item/'], [class*='product-snippet'], [class*='search-item-card']",
                    timeout=12000,
                )
            except Exception:
                pass

            await asyncio.sleep(random.uniform(1.0, 2.0))

            # Scroll to load lazy images
            await page.evaluate("window.scrollBy(0, 600)")
            await asyncio.sleep(0.8)

            html = await page.content()
            soup = BeautifulSoup(html, "lxml")

            # AliExpress uses hashed class names — rely on structural patterns
            items = (
                soup.select("[class*='search-item-card']") or
                soup.select("[class*='product-snippet']") or
                soup.select("a[href*='aliexpress.com/item']")
            )

            for item in items[:12]:
                try:
                    # Link
                    link_el = item if item.name == "a" else item.select_one("a[href*='/item/']")
                    if not link_el:
                        continue
                    href = link_el.get("href", "")
                    if href.startswith("//"):
                        href = "https:" + href
                    if not href.startswith("http"):
                        continue

                    # Title
                    title_el = item.select_one("h3, [class*='title'], [class*='name']") or link_el
                    title = title_el.get_text(strip=True)[:200]
                    if not title or len(title) < 5:
                        continue

                    # Price — look for a £ or $ amount
                    price_el = item.select_one("[class*='price'], [class*='Price']")
                    price_text = price_el.get_text(strip=True) if price_el else ""
                    price = _parse_price(price_text)
                    if price <= 0 or price > 200:
                        continue

                    img_el = item.select_one("img")
                    img_src = img_el.get("src") or img_el.get("data-src") or "" if img_el else ""

                    cases.append(RawCase(
                        name=title,
                        price=price,
                        source_site="AliExpress",
                        source_url=href,
                        image_url=img_src,
                        theme=theme,
                    ))
                except Exception:
                    continue

        except Exception as exc:
            log.warning("aliexpress.cases.scrape_error", error=str(exc))
        finally:
            await browser.close()

    log.info("aliexpress.cases.done", search=search, found=len(cases))
    return cases


# ── Temu ──────────────────────────────────────────────────────────────────────

async def _scrape_temu(search: str, theme: str) -> list[RawCase]:
    """
    Temu — Playwright stealth browser.
    Temu is a fully client-side React SPA with aggressive bot detection.
    Playwright with stealth patches gets past the initial JS challenge.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        log.error("playwright_not_installed", fix="pip install playwright && playwright install chromium")
        return []

    cases = []
    url = f"https://www.temu.com/search_result.html?search_key={search.replace(' ', '+')}&search_method=user"

    async with async_playwright() as p:
        try:
            browser, context = await _make_pw_context(p)
        except Exception as exc:
            log.warning("temu.cases.browser_error", error=str(exc))
            return []

        page = await context.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)

            # Dismiss cookie/region modals
            for selector in [
                "button:has-text('Accept')", "button:has-text('OK')",
                "[class*='modal'] button", "[class*='close']",
            ]:
                try:
                    await page.click(selector, timeout=2000)
                    await asyncio.sleep(0.3)
                except Exception:
                    pass

            # Wait for product grid
            try:
                await page.wait_for_selector(
                    "[class*='search-result'], [data-type='goods'], [class*='goods-item'], "
                    "[class*='product-item'], [class*='SearchResult']",
                    timeout=15000,
                )
            except Exception:
                pass

            # Scroll to trigger lazy loading
            await asyncio.sleep(random.uniform(1.0, 2.0))
            await page.evaluate("window.scrollBy(0, 800)")
            await asyncio.sleep(0.8)

            html = await page.content()
            soup = BeautifulSoup(html, "lxml")

            # Temu hashes its class names — use structural/data attributes
            items = (
                soup.select("[data-type='goods']") or
                soup.select("[class*='goods-item']") or
                soup.select("[class*='product-item']") or
                soup.select("[class*='SearchResult'] li") or
                soup.select("a[href*='/goods.html']")
            )

            for item in items[:12]:
                try:
                    link_el = item if item.name == "a" else item.select_one("a[href]")
                    if not link_el:
                        continue
                    href = link_el.get("href", "")
                    if not href.startswith("http"):
                        href = "https://www.temu.com" + href

                    title_el = item.select_one("[class*='title'], [class*='name'], [class*='Title'], h3, p")
                    title = title_el.get_text(strip=True)[:200] if title_el else ""
                    if not title or len(title) < 5:
                        continue

                    price_el = item.select_one("[class*='price'], [class*='Price']")
                    price = _parse_price(price_el.get_text(strip=True) if price_el else "")
                    if price <= 0 or price > 150:
                        continue

                    img_el = item.select_one("img")
                    img_src = img_el.get("src") or img_el.get("data-src") or "" if img_el else ""

                    cases.append(RawCase(
                        name=title,
                        price=price,
                        source_site="Temu",
                        source_url=href,
                        image_url=img_src,
                        theme=theme,
                    ))
                except Exception:
                    continue

        except Exception as exc:
            log.warning("temu.cases.scrape_error", error=str(exc))
        finally:
            await browser.close()

    log.info("temu.cases.done", search=search, found=len(cases))
    return cases


async def _scrape_scan(search: str, theme: str) -> list[RawCase]:
    """Scan.co.uk — httpx + BeautifulSoup."""
    url = f"https://www.scan.co.uk/search?q={search.replace(' ', '+')}"
    headers = {"User-Agent": ua.random, "Accept-Language": "en-GB", "Accept": "text/html"}
    cases = []
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
        if resp.status_code != 200 or len(resp.text) < 500:
            return cases
        soup = BeautifulSoup(resp.text, "lxml")

        # Scan product cards
        items = soup.select(".c-product, [class*='product-item'], li[class*='product']")
        if not items:
            items = soup.select("li.product, div.product")

        for item in items[:8]:
            try:
                title_el = item.select_one("a[class*='title'], h2, h3, .product-title, [class*='name']")
                price_el = item.select_one(".c-product__price, [class*='price']")
                url_el = item.select_one("a[href]")
                img_el = item.select_one("img")

                if not title_el or not price_el or not url_el:
                    continue
                title = title_el.get_text(strip=True)[:200]
                if not title:
                    continue
                price = _parse_price(price_el.get_text(strip=True))
                if price <= 0 or price > 350:
                    continue
                href = url_el.get("href", "")
                if not href.startswith("http"):
                    href = "https://www.scan.co.uk" + href
                cases.append(RawCase(
                    name=title,
                    price=price,
                    source_site="Scan",
                    source_url=href,
                    image_url=img_el.get("src", "") if img_el else "",
                    theme=theme,
                ))
            except Exception:
                continue
    except Exception as exc:
        log.warning("scan.cases.error", search=search, error=str(exc))
    return cases


async def _scrape_overclockers(search: str, theme: str) -> list[RawCase]:
    """Overclockers.co.uk — httpx + BeautifulSoup."""
    url = f"https://www.overclockers.co.uk/search?q={search.replace(' ', '+')}"
    headers = {"User-Agent": ua.random, "Accept-Language": "en-GB", "Accept": "text/html"}
    cases = []
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
        if resp.status_code != 200 or len(resp.text) < 500:
            return cases
        soup = BeautifulSoup(resp.text, "lxml")

        items = soup.select(".product-item, .product, [class*='product-card']")
        if not items:
            items = soup.select("li.item, div.item")

        for item in items[:8]:
            try:
                title_el = item.select_one("a[class*='title'], h2, h3, .product-title, [class*='name']")
                price_el = item.select_one(".product-price, .price, [class*='price']")
                url_el = item.select_one("a[href]")
                img_el = item.select_one("img")

                if not title_el or not price_el or not url_el:
                    continue
                title = title_el.get_text(strip=True)[:200]
                if not title:
                    continue
                price = _parse_price(price_el.get_text(strip=True))
                if price <= 0 or price > 350:
                    continue
                href = url_el.get("href", "")
                if not href.startswith("http"):
                    href = "https://www.overclockers.co.uk" + href
                cases.append(RawCase(
                    name=title,
                    price=price,
                    source_site="Overclockers",
                    source_url=href,
                    image_url=img_el.get("src", "") if img_el else "",
                    theme=theme,
                ))
            except Exception:
                continue
    except Exception as exc:
        log.warning("overclockers.cases.error", search=search, error=str(exc))
    return cases


async def _scrape_box(search: str, theme: str) -> list[RawCase]:
    """Box.co.uk — httpx + BeautifulSoup."""
    url = f"https://www.box.co.uk/search?search={search.replace(' ', '+')}"
    headers = {"User-Agent": ua.random, "Accept-Language": "en-GB", "Accept": "text/html"}
    cases = []
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
        if resp.status_code != 200 or len(resp.text) < 500:
            return cases
        soup = BeautifulSoup(resp.text, "lxml")

        items = soup.select(".product, .product-item, [class*='product-card']")
        if not items:
            items = soup.select("li.item, div.product-list-item")

        for item in items[:8]:
            try:
                title_el = item.select_one("a[class*='title'], h2, h3, .product-title, [class*='name']")
                price_el = item.select_one(".price, .product-price, [class*='price']")
                url_el = item.select_one("a[href]")
                img_el = item.select_one("img")

                if not title_el or not price_el or not url_el:
                    continue
                title = title_el.get_text(strip=True)[:200]
                if not title:
                    continue
                price = _parse_price(price_el.get_text(strip=True))
                if price <= 0 or price > 350:
                    continue
                href = url_el.get("href", "")
                if not href.startswith("http"):
                    href = "https://www.box.co.uk" + href
                cases.append(RawCase(
                    name=title,
                    price=price,
                    source_site="Box",
                    source_url=href,
                    image_url=img_el.get("src", "") if img_el else "",
                    theme=theme,
                ))
            except Exception:
                continue
    except Exception as exc:
        log.warning("box.cases.error", search=search, error=str(exc))
    return cases


async def _scrape_etsy(search: str, theme: str) -> list[RawCase]:
    """
    Etsy UK — Playwright stealth browser (JS-rendered).
    Etsy is a fully client-side SPA; Playwright renders the search results.
    Price cap £200 (handmade cases tend to be pricier).
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        log.error("playwright_not_installed", fix="pip install playwright && playwright install chromium")
        return []

    cases = []
    url = f"https://www.etsy.com/uk/search?q={search.replace(' ', '+')}&explicit=1"

    async with async_playwright() as p:
        try:
            browser, context = await _make_pw_context(p)
        except Exception as exc:
            log.warning("etsy.cases.browser_error", error=str(exc))
            return []

        page = await context.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)

            # Dismiss cookie/consent dialogs
            for selector in ["button:has-text('Accept')", "[data-gdpr-single-choice-accept]", "button:has-text('OK')"]:
                try:
                    await page.click(selector, timeout=2000)
                    await asyncio.sleep(0.3)
                except Exception:
                    pass

            # Wait for listing cards
            try:
                await page.wait_for_selector(
                    "[data-search-results], .listing-link, [class*='listing'], [class*='v2-listing']",
                    timeout=12000,
                )
            except Exception:
                pass

            await asyncio.sleep(random.uniform(1.0, 2.0))
            await page.evaluate("window.scrollBy(0, 600)")
            await asyncio.sleep(0.8)

            html = await page.content()
            soup = BeautifulSoup(html, "lxml")

            # Etsy listing cards
            items = (
                soup.select("[class*='listing-link']") or
                soup.select("a[href*='/listing/']") or
                soup.select("[class*='v2-listing-card']")
            )

            for item in items[:10]:
                try:
                    link_el = item if item.name == "a" else item.select_one("a[href*='/listing/']")
                    if not link_el:
                        continue
                    href = link_el.get("href", "")
                    if href.startswith("//"):
                        href = "https:" + href
                    if not href.startswith("http"):
                        continue

                    title_el = item.select_one("h3, [class*='title'], [class*='listing-title'], p")
                    title = title_el.get_text(strip=True)[:200] if title_el else ""
                    if not title or len(title) < 5:
                        continue

                    price_el = item.select_one("[class*='price'], [class*='currency-value']")
                    price = _parse_price(price_el.get_text(strip=True) if price_el else "")
                    if price <= 0 or price > 200:
                        continue

                    img_el = item.select_one("img")
                    img_src = img_el.get("src") or img_el.get("data-src") or "" if img_el else ""

                    cases.append(RawCase(
                        name=title,
                        price=price,
                        source_site="Etsy",
                        source_url=href,
                        image_url=img_src,
                        theme=theme,
                    ))
                except Exception:
                    continue
        except Exception as exc:
            log.warning("etsy.cases.scrape_error", error=str(exc))
        finally:
            await browser.close()

    log.info("etsy.cases.done", search=search, found=len(cases))
    return cases


async def _upsert_case(db, case: RawCase):
    from sqlalchemy import select
    result = await db.execute(
        select(Part).where(
            Part.name == case.name,
            Part.source_site == case.source_site,
            Part.category == PartCategory.case,
        )
    )
    part = result.scalar_one_or_none()
    now = datetime.utcnow()
    if part:
        part.price = case.price
        part.price_new = case.price
        part.source_url = case.source_url
        part.image_url = case.image_url
        part.last_price_update = now
    else:
        part = Part(
            name=case.name,
            category=PartCategory.case,
            condition=PartCondition.new,
            source_site=case.source_site,
            source_url=case.source_url,
            price=case.price,
            price_new=case.price,
            image_url=case.image_url,
            theme=case.theme,
            specs=case.specs,
            resale_value_add=0.0,
            last_price_update=now,
        )
        db.add(part)
        await db.flush()

    db.add(PriceHistory(
        entity_type=PriceHistoryType.part,
        entity_id=part.id,
        price=case.price,
        condition="new",
        source=case.source_site,
    ))


def _parse_price(text: str) -> float:
    m = re.search(r"[\d,]+\.?\d*", str(text).replace(",", ""))
    return float(m.group(0)) if m else 0.0
