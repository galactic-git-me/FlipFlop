"""
PC Cases Swarm — runs daily.
Searches for sci-fi / themed PC cases (NEW only) across eBay, Amazon, Temu, AliExpress.
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
    {"name": "eBay", "fn": "ebay"},
    {"name": "Amazon", "fn": "amazon"},
    {"name": "AliExpress", "fn": "aliexpress"},
    {"name": "Temu", "fn": "temu"},
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
                for term in theme_def["terms"][:1]:  # 1 term per source per theme
                    try:
                        scrape_fn = globals().get(f"_scrape_{source['fn']}")
                        if not scrape_fn:
                            continue
                        cases = await scrape_fn(term, theme_def["theme"])
                        stats["found"] += len(cases)

                        for case in cases[:5]:  # Top 5 per search
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


async def _scrape_amazon(search: str, theme: str) -> list[RawCase]:
    """Amazon UK — may be bot-blocked but worth trying."""
    params = {"k": search, "i": "computers"}
    headers = {
        "User-Agent": ua.random,
        "Accept-Language": "en-GB",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
    }
    cases = []
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get("https://www.amazon.co.uk/s", params=params, headers=headers)
        if resp.status_code != 200 or len(resp.text) < 1000:
            return cases
        soup = BeautifulSoup(resp.text, "lxml")
        for item in soup.select('[data-component-type="s-search-result"]')[:6]:
            try:
                title_el = item.select_one("h2 span")
                price_whole = item.select_one(".a-price-whole")
                price_frac = item.select_one(".a-price-fraction")
                url_el = item.select_one("h2 a")
                img_el = item.select_one("img.s-image")
                if not title_el or not url_el:
                    continue
                price = 0.0
                if price_whole:
                    frac = price_frac.get_text(strip=True) if price_frac else "0"
                    try:
                        price = float(price_whole.get_text(strip=True).replace(",", "").replace(".", "") + "." + frac.replace(".", ""))
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
        log.warning("amazon.cases.error", error=str(exc))
    return cases


async def _scrape_aliexpress(search: str, theme: str) -> list[RawCase]:
    """AliExpress — JS-heavy but occasionally returns server-rendered data."""
    params = {"SearchText": search}
    headers = {
        "User-Agent": ua.random,
        "Accept-Language": "en-GB,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    cases = []
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get("https://www.aliexpress.com/wholesale", params=params, headers=headers)
        if resp.status_code != 200 or len(resp.text) < 2000:
            return cases
        soup = BeautifulSoup(resp.text, "lxml")
        # Try multiple AliExpress selectors
        selectors = [
            "[class*='product-snippet']",
            "[class*='list--gallery']",
            "a[href*='aliexpress.com/item']",
        ]
        items = []
        for sel in selectors:
            items = soup.select(sel)[:6]
            if items:
                break
        for item in items:
            try:
                title_el = item.select_one("h3, [class*='title']") or item
                price_el = item.select_one("[class*='price']")
                url_el = item if item.name == "a" else item.select_one("a[href]")
                img_el = item.select_one("img")
                title_text = title_el.get_text(strip=True)[:200] if title_el else ""
                if not title_text or not url_el:
                    continue
                price_text = price_el.get_text(strip=True) if price_el else ""
                price = _parse_price(price_text)
                if price <= 0 or price > 200:
                    continue
                href = url_el.get("href", "")
                if href.startswith("//"):
                    href = "https:" + href
                if not href.startswith("http"):
                    continue
                cases.append(RawCase(
                    name=title_text,
                    price=price,
                    source_site="AliExpress",
                    source_url=href,
                    image_url=img_el.get("src", "") if img_el else "",
                    theme=theme,
                ))
            except Exception:
                continue
    except Exception as exc:
        log.warning("aliexpress.cases.error", error=str(exc))
    return cases


async def _scrape_temu(search: str, theme: str) -> list[RawCase]:
    """Temu — try their search page with browser-like headers."""
    headers = {
        "User-Agent": ua.random,
        "Accept-Language": "en-GB,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": "https://www.temu.com/",
    }
    cases = []
    try:
        search_slug = search.replace(" ", "-").lower()
        url = f"https://www.temu.com/search_result.html?search_key={search.replace(' ', '+')}"
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
        if resp.status_code != 200 or len(resp.text) < 2000:
            log.debug("temu.blocked", status=resp.status_code, length=len(resp.text))
            return cases
        soup = BeautifulSoup(resp.text, "lxml")
        # Temu search results — try common selectors
        items = (
            soup.select("[class*='search-item']") or
            soup.select("[data-type='goods']") or
            soup.select("[class*='goods-item']")
        )[:6]
        for item in items:
            try:
                title_el = item.select_one("[class*='title'], [class*='name'], h3")
                price_el = item.select_one("[class*='price']")
                url_el = item.select_one("a[href]")
                img_el = item.select_one("img")
                if not title_el or not url_el:
                    continue
                title_text = title_el.get_text(strip=True)[:200]
                price = _parse_price(price_el.get_text(strip=True) if price_el else "")
                if price <= 0 or price > 150:
                    continue
                href = url_el.get("href", "")
                if not href.startswith("http"):
                    href = "https://www.temu.com" + href
                cases.append(RawCase(
                    name=title_text,
                    price=price,
                    source_site="Temu",
                    source_url=href,
                    image_url=img_el.get("src", "") if img_el else "",
                    theme=theme,
                ))
            except Exception:
                continue
    except Exception as exc:
        log.warning("temu.cases.error", error=str(exc))
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
