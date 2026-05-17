"""
PC Cases Swarm — runs daily.
Searches for PC cases (new and used) across eBay UK, Amazon UK, Temu, AliExpress, and Etsy.
eBay uses plain httpx. Amazon, Temu, AliExpress, and Etsy use a shared Playwright browser context
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
from app.services.search_telemetry import record_term_result
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
    {"name": "Amazon",            "fn": "amazon"},          # Playwright — JS evaluation
    {"name": "Temu",              "fn": "temu"},            # Playwright — stealth browser (may be rate-limited)
    {"name": "AliExpress",        "fn": "aliexpress"},      # Playwright — stealth browser (may be rate-limited)
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


async def _playbook_extra_themes() -> list[dict]:
    """
    Read active playbooks and return extra case themes derived from their
    component_catalogue.preferred_cases and target_use_case.
    Deduplicates against the global CASE_THEMES search terms.
    """
    from sqlalchemy import select as sa_select
    from app.models.playbook import Playbook

    _use_case_terms: dict[str, list[str]] = {
        "gaming":        ["gaming atx case rgb", "gaming pc case mid tower"],
        "office":        ["slim micro atx case office", "mini tower desktop case"],
        "workstation":   ["full tower workstation case atx", "fractal define case atx"],
        "htpc":          ["mini itx htpc case", "slim htpc case living room"],
        "budget":        ["cheap atx pc case", "budget gaming case atx"],
        "ai_workstation": ["full tower atx case workstation", "server tower case atx"],
    }

    extra: list[dict] = []
    existing_terms: set[str] = {t for td in CASE_THEMES for t in td["terms"]}

    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(sa_select(Playbook).where(Playbook.status == "active"))
            for pb in result.scalars().all():
                cat = pb.component_catalogue or {}
                preferred = cat.get("preferred_cases", [])

                # Explicit preferred case names → direct Google Shopping searches
                for case_name in preferred:
                    term = f"{case_name} pc case"
                    if term not in existing_terms:
                        extra.append({"theme": f"{pb.name} Case", "terms": [term]})
                        existing_terms.add(term)

                # Fallback: map target_use_case to generic search terms
                use_case = (pb.target_use_case or "gaming").lower()
                for term in _use_case_terms.get(use_case, []):
                    if term not in existing_terms:
                        extra.append({"theme": f"{pb.name} Case", "terms": [term]})
                        existing_terms.add(term)
    except Exception as exc:
        log.warning("playbook_extra_themes.error", error=str(exc))

    return extra


async def run_cases_swarm() -> dict:
    log.info("cases_swarm.start")
    stats = {"found": 0, "upserted": 0, "errors": 0}

    playbook_themes = await _playbook_extra_themes()
    all_themes = CASE_THEMES + playbook_themes
    log.info("cases_swarm.themes", base=len(CASE_THEMES), playbook_extra=len(playbook_themes))

    async with AsyncSessionLocal() as db:
        for theme_def in all_themes:
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
                        record_term_result(
                            source_name=f"Cases:{source['name']}",
                            term=term,
                            found=len(cases),
                            new=0,
                        )

                        for case in cases[:8]:  # Top 8 per search (was 5)
                            await _upsert_case(db, case)
                            stats["upserted"] += 1
                    except Exception as exc:
                        stats["errors"] += 1
                        record_term_result(
                            source_name=f"Cases:{source['name']}",
                            term=term,
                            error=str(exc),
                        )
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
    headers = {
        "User-Agent": ua.random,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-GB,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",
    }
    cases = []
    try:
        await asyncio.sleep(random.uniform(1.0, 2.5))
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
    headers = {
        "User-Agent": ua.random,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-GB,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",
    }
    cases = []
    try:
        await asyncio.sleep(random.uniform(1.0, 2.5))
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


# ── Google Shopping (UK) ──────────────────────────────────────────────────────

async def _scrape_google_shopping(search: str, theme: str) -> list[RawCase]:
    """
    Google Shopping UK — Playwright stealth browser.
    Pre-sets the SOCS=CAI cookie to bypass Google's GDPR consent page.
    Uses JS evaluation against the live DOM for resilience against
    Google's frequently-rotating CSS class names.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        log.error("playwright_not_installed", fix="pip install playwright && playwright install chromium")
        return []

    cases = []
    query = search.replace(" ", "+")
    url = f"https://www.google.co.uk/search?q={query}&tbm=shop&hl=en-GB&gl=gb&num=20"

    async with async_playwright() as p:
        try:
            browser, context = await _make_pw_context(p)
        except Exception as exc:
            log.warning("google_shopping.cases.browser_error", error=str(exc))
            return []

        # Pre-set Google's consent cookie — bypasses the EU/UK consent gate entirely
        await context.add_cookies([
            {"name": "SOCS", "value": "CAI", "domain": ".google.co.uk", "path": "/"},
            {"name": "SOCS", "value": "CAI", "domain": ".google.com",   "path": "/"},
        ])

        page = await context.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)

            # Belt-and-braces consent click in case cookie wasn't sufficient
            for selector in [
                "#L2AGLb", "button:has-text('Accept all')", "[aria-label='Accept all']",
            ]:
                try:
                    await page.click(selector, timeout=1500)
                    await asyncio.sleep(0.5)
                    break
                except Exception:
                    pass

            await asyncio.sleep(random.uniform(2.0, 3.0))
            await page.evaluate("window.scrollBy(0, 500)")
            await asyncio.sleep(1.0)

            # Extract products using JS against the live DOM — far more resilient
            # than HTML parsing because it sees the rendered element tree.
            raw = await page.evaluate("""() => {
                const seen = new Set();
                const out  = [];
                const priceRe = /[£$]\\s*([\\d,]+\\.?\\d*)/;

                function getCleanTitle(el) {
                    // Clone node and remove price/retailer child elements
                    const clone = el.cloneNode(true);
                    clone.querySelectorAll(".VbBaOe,.a8Pemb,.T14wmb,.CsnLnf,.UsGWMe," +
                                          "[class*='price'],[class*='Price'],[class*='store'],[class*='Store']")
                         .forEach(n => n.remove());
                    let t = clone.textContent.trim();
                    // Strip trailing price/retailer text: "£49 SomeSite + £3.99 delivery"
                    t = t.replace(/£[\\s\\S]*/g, "").trim();
                    // Strip trailing store suffixes left as raw text
                    t = t.replace(/[-–|·•]?\\s*[A-Z][a-z]+[\\s.]+(?:co\\.uk|UK|de|com)[\\s\\S]*/i, "").trim();
                    // Remove leftover trailing punctuation
                    t = t.replace(/[+\\-\\u2013\\u00B7\\u2022|,\\s]+$/, "").trim();
                    return t;
                }

                function addItem(title, price, href, img) {
                    if (!title || !href || price <= 0) return;
                    // Deduplicate on normalised title (Google repeats the same item in multiple containers)
                    const key = title.toLowerCase().replace(/\\s+/g, " ").slice(0, 80);
                    if (seen.has(key)) return;
                    seen.add(key);
                    out.push({title, price, href, img});
                }

                // Strategy 1: use explicit product containers
                const containers = document.querySelectorAll(
                    ".pla-unit-container, .sh-dgr__grid-result, [data-sh-sr], .g.sh-np"
                );

                containers.forEach(el => {
                    // .orXoSd is Google Shopping's clean product-title div (no price/retailer)
                    const titleEl = el.querySelector("h3, h4, .ropLT, .orXoSd, .rwVHAc");
                    const priceEl = el.querySelector(".VbBaOe, .a8Pemb, .T14wmb");
                    const linkEl  = el.querySelector("a.plantl, a[href*='aclk'], a[href*='/shopping/product/'], a[href]");
                    const imgEl   = el.querySelector("img");

                    const title = titleEl ? getCleanTitle(titleEl) : "";
                    const priceText = priceEl?.textContent?.trim() || "";
                    const pm = priceRe.exec(priceText);
                    const price = pm ? parseFloat(pm[1].replace(",","")) : 0;
                    addItem(title, price, linkEl?.href || "", imgEl?.src || "");
                });

                // Strategy 2: work backwards from price spans if strategy 1 found nothing
                if (out.length === 0) {
                    document.querySelectorAll(".VbBaOe, .a8Pemb").forEach(priceEl => {
                        const pm = priceRe.exec(priceEl.textContent.trim());
                        if (!pm) return;
                        const price = parseFloat(pm[1].replace(",",""));
                        let node = priceEl.parentElement;
                        for (let i = 0; i < 8 && node; i++, node = node.parentElement) {
                            const titleEl = node.querySelector("h3, h4, .ropLT, .orXoSd, .rwVHAc");
                            const linkEl  = node.querySelector("a.plantl, a[href*='aclk'], a[href*='/shopping/product/'], a[href]");
                            if (titleEl && linkEl) {
                                addItem(getCleanTitle(titleEl), price,
                                        linkEl.href, node.querySelector("img")?.src || "");
                                break;
                            }
                        }
                    });
                }

                return out.slice(0, 20);
            }""")

            for item in raw:
                try:
                    title = str(item.get("title", "")).strip()[:200]
                    if not title or len(title) < 5:
                        continue
                    price = float(item.get("price", 0) or 0)
                    if price <= 0 or price > 350:
                        continue
                    href = str(item.get("href", ""))
                    if not href.startswith("http"):
                        continue
                    img_src = str(item.get("img", ""))
                    # Skip tiny data URIs (Google's lazy-load placeholders)
                    if img_src.startswith("data:") and len(img_src) < 300:
                        img_src = ""

                    cases.append(RawCase(
                        name=title,
                        price=price,
                        source_site="Google Shopping",
                        source_url=href,
                        image_url=img_src,
                        theme=theme,
                    ))
                except Exception:
                    continue

        except Exception as exc:
            log.warning("google_shopping.cases.scrape_error", error=str(exc))
        finally:
            await browser.close()

    log.info("google_shopping.cases.done", search=search, found=len(cases))
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
    Amazon UK — Playwright stealth browser with JS evaluation.
    BeautifulSoup on page.content() misses h2 links because Amazon renders
    them client-side. JS evaluation against the live DOM works reliably.
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
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            try:
                await page.wait_for_selector('[data-component-type="s-search-result"]', timeout=12000)
            except Exception:
                pass
            await asyncio.sleep(random.uniform(1.5, 2.5))

            raw = await page.evaluate("""() => {
                const out = [];
                const seen = new Set();
                document.querySelectorAll('[data-component-type="s-search-result"]').forEach(item => {
                    try {
                        const titleEl = item.querySelector('h2 span') || item.querySelector('h2');
                        const linkEl  = item.querySelector('h2 a') || item.querySelector('a.a-link-normal[href*="/dp/"]');
                        const priceW  = item.querySelector('.a-price-whole');
                        const priceF  = item.querySelector('.a-price-fraction');
                        const imgEl   = item.querySelector('img.s-image');
                        if (!titleEl || !linkEl) return;

                        const title = titleEl.textContent.trim().slice(0, 200);
                        if (!title) return;

                        let href = linkEl.href || linkEl.getAttribute('href') || '';
                        if (href.startsWith('/')) href = 'https://www.amazon.co.uk' + href;
                        if (!href.startsWith('http')) return;

                        const key = href.split('?')[0];
                        if (seen.has(key)) return;
                        seen.add(key);

                        let price = 0;
                        if (priceW) {
                            const whole = priceW.textContent.replace(/[^0-9]/g, '');
                            const frac  = priceF ? priceF.textContent.replace(/[^0-9]/g, '').padEnd(2,'0') : '00';
                            price = parseFloat(whole + '.' + frac.slice(0,2));
                        }
                        if (price <= 0 || price > 350) return;

                        out.push({title, price, href, img: imgEl ? imgEl.src : ''});
                    } catch (e) {}
                });
                return out.slice(0, 10);
            }""")

            for item in raw:
                try:
                    title = str(item.get("title", "")).strip()[:200]
                    if not title:
                        continue
                    price = float(item.get("price", 0) or 0)
                    if price <= 0 or price > 350:
                        continue
                    href = str(item.get("href", ""))
                    if not href.startswith("http"):
                        continue
                    cases.append(RawCase(
                        name=title,
                        price=price,
                        source_site="Amazon",
                        source_url=href,
                        image_url=str(item.get("img", "")),
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

            # Use JS evaluation — AliExpress hashes its class names so selectors break
            raw = await page.evaluate("""() => {
                const out = [];
                const priceRe = /[£$€]\\s*([\\d,]+\\.?\\d*)/;
                const seen = new Set();

                document.querySelectorAll("a[href*='/item/']").forEach(link => {
                    try {
                        let href = link.href || "";
                        if (!href.startsWith("http")) return;
                        // Deduplicate by URL
                        const key = href.split("?")[0];
                        if (seen.has(key)) return;
                        seen.add(key);

                        // Title: prefer aria-label, then h1/h3/p inside card
                        let title = link.getAttribute("aria-label") || "";
                        if (!title) {
                            const h = link.querySelector("h1, h3, h4, p");
                            title = h ? h.textContent.trim() : link.textContent.trim();
                        }
                        title = title.replace(/\\s+/g, " ").trim().slice(0, 200);
                        if (!title || title.length < 5) return;

                        // Price: walk up to find a price element
                        let price = 0;
                        let node = link.parentElement;
                        for (let i = 0; i < 6 && node && price === 0; i++, node = node.parentElement) {
                            node.querySelectorAll("*").forEach(el => {
                                if (price > 0) return;
                                const txt = el.textContent.trim();
                                if ((txt.includes("$") || txt.includes("£") || txt.includes("€")) && txt.length < 30) {
                                    const m = priceRe.exec(txt);
                                    if (m) price = parseFloat(m[1].replace(",", ""));
                                }
                            });
                        }
                        if (price <= 0 || price > 200) return;

                        const img = link.querySelector("img");
                        const imgSrc = img ? (img.src || img.getAttribute("data-src") || "") : "";

                        out.push({title, price, href, img: imgSrc});
                    } catch (e) {}
                });
                return out.slice(0, 12);
            }""")

            for item in raw:
                try:
                    title = str(item.get("title", "")).strip()[:200]
                    if not title or len(title) < 5:
                        continue
                    price = float(item.get("price", 0) or 0)
                    if price <= 0 or price > 200:
                        continue
                    href = str(item.get("href", ""))
                    if not href.startswith("http"):
                        continue
                    cases.append(RawCase(
                        name=title,
                        price=price,
                        source_site="AliExpress",
                        source_url=href,
                        image_url=str(item.get("img", "")),
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

            # Use JS evaluation — Temu rotates hashed class names so selectors break
            raw = await page.evaluate("""() => {
                const out = [];
                const priceRe = /[£$€]\\s*([\\d,]+\\.?\\d*)/;
                const seen = new Set();

                document.querySelectorAll("a[href*='/goods']").forEach(link => {
                    try {
                        let href = link.href || "";
                        if (!href.startsWith("http")) {
                            href = "https://www.temu.com" + (href.startsWith("/") ? href : "/" + href);
                        }
                        const key = href.split("?")[0];
                        if (seen.has(key)) return;
                        seen.add(key);

                        // Title: aria-label first, then text children
                        let title = link.getAttribute("aria-label") || "";
                        if (!title) {
                            const h = link.querySelector("h3, h4, p, span");
                            title = h ? h.textContent.trim() : link.textContent.trim();
                        }
                        title = title.replace(/\\s+/g, " ").trim().slice(0, 200);
                        if (!title || title.length < 5) return;

                        // Price: walk up the tree to find price text
                        let price = 0;
                        let node = link.parentElement;
                        for (let i = 0; i < 6 && node && price === 0; i++, node = node.parentElement) {
                            node.querySelectorAll("*").forEach(el => {
                                if (price > 0) return;
                                const txt = el.textContent.trim();
                                if ((txt.includes("$") || txt.includes("£") || txt.includes("€")) && txt.length < 30) {
                                    const m = priceRe.exec(txt);
                                    if (m) price = parseFloat(m[1].replace(",", ""));
                                }
                            });
                        }
                        if (price <= 0 || price > 150) return;

                        const img = link.querySelector("img");
                        const imgSrc = img ? (img.src || img.getAttribute("data-src") || "") : "";

                        out.push({title, price, href, img: imgSrc});
                    } catch (e) {}
                });
                return out.slice(0, 12);
            }""")

            for item in raw:
                try:
                    title = str(item.get("title", "")).strip()[:200]
                    if not title or len(title) < 5:
                        continue
                    price = float(item.get("price", 0) or 0)
                    if price <= 0 or price > 150:
                        continue
                    href = str(item.get("href", ""))
                    if not href.startswith("http"):
                        continue
                    cases.append(RawCase(
                        name=title,
                        price=price,
                        source_site="Temu",
                        source_url=href,
                        image_url=str(item.get("img", "")),
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

            # Wait longer for Etsy's JS-rendered listing grid (5-6s)
            await asyncio.sleep(random.uniform(5.0, 6.0))
            await page.evaluate("window.scrollBy(0, 600)")
            await asyncio.sleep(1.0)

            # Use JS evaluation — Etsy's DOM selectors frequently change;
            # a[href*='/listing/'] links are always present regardless of class names.
            raw = await page.evaluate("""() => {
                const out = [];
                const priceRe = /[£$€]\\s*([\\d,]+\\.?\\d*)/;
                const seen = new Set();

                document.querySelectorAll("a[href*='/listing/']").forEach(link => {
                    try {
                        let href = link.href || "";
                        if (href.startsWith("//")) href = "https:" + href;
                        if (!href.startsWith("http")) return;
                        const key = href.split("?")[0];
                        if (seen.has(key)) return;
                        seen.add(key);

                        // Title: aria-label first, then nearest h3/p inside the card
                        let title = link.getAttribute("aria-label") || "";
                        if (!title) {
                            const h = link.querySelector("h3, h2, p");
                            title = h ? h.textContent.trim() : link.textContent.trim();
                        }
                        // If still empty, walk up to find a heading near this link
                        if (!title || title.length < 5) {
                            let node = link.parentElement;
                            for (let i = 0; i < 4 && node; i++, node = node.parentElement) {
                                const h = node.querySelector("h3, h2, p");
                                if (h) { title = h.textContent.trim(); break; }
                            }
                        }
                        title = title.replace(/\\s+/g, " ").trim().slice(0, 200);
                        if (!title || title.length < 5) return;

                        // Price: .currency-value spans are Etsy's standard price element
                        let price = 0;
                        let node = link.parentElement;
                        for (let i = 0; i < 6 && node && price === 0; i++, node = node.parentElement) {
                            const priceEl = node.querySelector(
                                ".currency-value, [class*='currency-value'], [class*='price']"
                            );
                            if (priceEl) {
                                const m = priceRe.exec(priceEl.textContent.trim());
                                if (m) price = parseFloat(m[1].replace(",", ""));
                            }
                            // Fallback: look for any text matching price pattern
                            if (price === 0) {
                                node.querySelectorAll("span, p").forEach(el => {
                                    if (price > 0) return;
                                    const txt = el.textContent.trim();
                                    if (txt.length < 20 && (txt.includes("£") || txt.includes("$"))) {
                                        const m = priceRe.exec(txt);
                                        if (m) price = parseFloat(m[1].replace(",", ""));
                                    }
                                });
                            }
                        }
                        if (price <= 0 || price > 200) return;

                        const img = link.querySelector("img");
                        const imgSrc = img ? (img.src || img.getAttribute("data-src") || "") : "";

                        out.push({title, price, href, img: imgSrc});
                    } catch (e) {}
                });
                return out.slice(0, 10);
            }""")

            for item in raw:
                try:
                    title = str(item.get("title", "")).strip()[:200]
                    if not title or len(title) < 5:
                        continue
                    price = float(item.get("price", 0) or 0)
                    if price <= 0 or price > 200:
                        continue
                    href = str(item.get("href", ""))
                    if not href.startswith("http"):
                        continue
                    cases.append(RawCase(
                        name=title,
                        price=price,
                        source_site="Etsy",
                        source_url=href,
                        image_url=str(item.get("img", "")),
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
