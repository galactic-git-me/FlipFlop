"""
Accessories Swarm — runs every 24 hours.
Scrapes budget gaming accessories (mice, keyboards, headsets, mousepads, controllers,
webcams, monitor arms) from eBay UK (BIN, new + used).
These are upsell items to bundle with flipped PCs.
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
from app.services.scraper import scrape_ebay
from app.services.proxy import playwright_proxy_config
from app.services.playwright_scraper import chromium_available
from app.models.source_search_term import SourceSearchTerm
from sqlalchemy import select as sa_select
import structlog

log = structlog.get_logger(__name__)
ua = UserAgent()

MAX_PRICE = 80.0  # Max price for accessories
MAX_SOURCE_URL_LEN = 1900  # DB column is VARCHAR(2000); keep safety headroom

ACCESSORY_SEARCHES = [
    {"theme": "Keyboard",   "term": "gaming keyboard", "condition": "1000"},
    {"theme": "Mouse",      "term": "gaming mouse", "condition": "1000"},
    {"theme": "Headset",    "term": "gaming headset", "condition": "1000"},
    {"theme": "Microphone", "term": "usb microphone", "condition": "1000"},
    {"theme": "Mousepad",   "term": "xl mouse pad", "condition": "1000"},
]

_SOURCE_ALIASES: dict[str, str] = {
    "ebay uk": "eBay",
    "ebay uk auctions": "eBay",
    "facebook marketplace": "Facebook Marketplace",
    "amazon uk": "Amazon",
    "bargain hardware": "BargainHardware",
}


def _canonical_source_name(name: str) -> str:
    raw = str(name or "").strip()
    return _SOURCE_ALIASES.get(raw.lower(), raw)


@dataclass
class RawAccessory:
    name: str
    price: float
    source_site: str
    source_url: str
    image_url: str
    theme: str
    condition: PartCondition


async def _scrape_ebay_accessories(term: str, theme: str, condition_code: str) -> list[RawAccessory]:
    """eBay API-first with scraper fallback for accessory search terms."""
    condition = PartCondition.new if condition_code == "1000" else PartCondition.used
    try:
        listings = await scrape_ebay(
            [term],
            min_price=1,
            max_price=MAX_PRICE,
            auction_mode=False,
            condition_code=condition_code,
            worldwide=False,
        )
        out: list[RawAccessory] = []
        for l in listings[:24]:
            out.append(
                RawAccessory(
                    name=l.title[:200],
                    price=l.price,
                    source_site="eBay",
                    source_url=l.url,
                    image_url=l.image_urls[0] if l.image_urls else "",
                    theme=theme,
                    condition=condition,
                )
            )
        return out
    except Exception as exc:
        log.warning("ebay.accessories.error", term=term, error=str(exc))
        return []


async def _upsert_accessory(db, acc: RawAccessory):
    from sqlalchemy import select as sa_select
    result = await db.execute(
        sa_select(Part).where(
            Part.name == acc.name,
            Part.source_site == acc.source_site,
            Part.category == PartCategory.accessory,
        ).order_by(Part.id.desc())
    )
    existing = list(result.scalars().all())
    part = existing[0] if existing else None
    if len(existing) > 1:
        log.warning(
            "accessories.duplicate_rows",
            name=acc.name,
            source=acc.source_site,
            duplicates=len(existing),
        )
    now = datetime.utcnow()

    safe_url = (acc.source_url or "")[:MAX_SOURCE_URL_LEN]

    if part:
        part.price = acc.price
        if acc.condition == PartCondition.new:
            part.price_new = acc.price
        else:
            part.price_used = acc.price
        part.source_url = safe_url
        part.image_url = acc.image_url or part.image_url
        part.last_price_update = now
    else:
        part = Part(
            name=acc.name,
            category=PartCategory.accessory,
            condition=acc.condition,
            source_site=acc.source_site,
            source_url=safe_url,
            price=acc.price,
            price_new=acc.price if acc.condition == PartCondition.new else None,
            price_used=acc.price if acc.condition == PartCondition.used else None,
            image_url=acc.image_url,
            theme=acc.theme,
            resale_value_add=0.0,
            last_price_update=now,
        )
        db.add(part)
        await db.flush()

    db.add(PriceHistory(
        entity_type=PriceHistoryType.part,
        entity_id=part.id,
        price=acc.price,
        condition=acc.condition.value,
        source=acc.source_site,
    ))


async def run_accessories_swarm(mode: str = "main") -> dict:
    log.info("accessories_swarm.start")
    stats = {"found": 0, "upserted": 0, "errors": 0}
    search_defs = list(ACCESSORY_SEARCHES)
    async with AsyncSessionLocal() as db:
        rows = (
            await db.execute(
                sa_select(SourceSearchTerm).where(
                    SourceSearchTerm.scope == "accessories",
                    SourceSearchTerm.enabled == True,
                )
            )
        ).scalars().all()
    if rows:
        search_defs = [{
            "theme": str(r.group_name or "Accessory"),
            "term": str(r.term),
            "condition": "1000",
            "source_names": [_canonical_source_name(str(s)) for s in list(r.source_names or [])],
        } for r in rows if str(r.term or "").strip()]
    terms_by_vendor: dict[str, list[str]] = {}
    for d in search_defs:
        srcs = d.get("source_names") or ["eBay", "Gumtree", "Facebook Marketplace", "Amazon", "Temu", "AliExpress", "Alibaba", "BargainHardware"]
        for s in srcs:
            terms_by_vendor.setdefault(str(s), []).append(d["term"])
    terms_by_vendor = {k: list(dict.fromkeys(v)) for k, v in terms_by_vendor.items()}
    batch_terms = terms_by_vendor

    async with AsyncSessionLocal() as db:
        for search_def in search_defs:
            try:
                source_batches: list[tuple[str, list[RawAccessory]]] = []
                if search_def["term"] in set(batch_terms.get("eBay", [])):
                    ebay_results = await _scrape_ebay_accessories(
                        search_def["term"],
                        search_def["theme"],
                        search_def["condition"],
                    )
                    source_batches.append(("Accessories:eBay", ebay_results))
                if search_def["term"] in set(batch_terms.get("Gumtree", [])):
                    source_batches.append(
                        ("Accessories:Gumtree", await _scrape_gumtree_accessories(search_def["term"], search_def["theme"]))
                    )
                if search_def["term"] in set(batch_terms.get("Facebook Marketplace", [])):
                    source_batches.append(
                        ("Accessories:Facebook Marketplace", await _scrape_facebook_accessories(search_def["term"], search_def["theme"]))
                    )

                if chromium_available():
                    from playwright.async_api import async_playwright
                    async with async_playwright() as p:
                        browser = await p.chromium.launch(
                            headless=True,
                            args=["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-dev-shm-usage"],
                            proxy=playwright_proxy_config(),
                        )
                        ctx = await browser.new_context(
                            user_agent=ua.random,
                            locale="en-GB",
                            timezone_id="Europe/London",
                        )
                        await ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
                        page = await ctx.new_page()

                        if search_def["term"] in set(batch_terms.get("Amazon", [])):
                            source_batches.append(
                                ("Accessories:Amazon", await _scrape_playwright_accessories(page, search_def["term"], search_def["theme"], "Amazon", f"https://www.amazon.co.uk/s?k={search_def['term'].replace(' ', '+')}&i=computers"))
                            )
                        if search_def["term"] in set(batch_terms.get("Temu", [])):
                            source_batches.append(
                                ("Accessories:Temu", await _scrape_playwright_accessories(page, search_def["term"], search_def["theme"], "Temu", f"https://www.temu.com/search_result.html?search_key={search_def['term'].replace(' ', '+')}&search_method=user"))
                            )
                        if search_def["term"] in set(batch_terms.get("AliExpress", [])):
                            source_batches.append(
                                ("Accessories:AliExpress", await _scrape_playwright_accessories(page, search_def["term"], search_def["theme"], "AliExpress", f"https://www.aliexpress.com/wholesale?SearchText={search_def['term'].replace(' ', '+')}&g=y&SortType=price_asc"))
                            )
                        if search_def["term"] in set(batch_terms.get("Alibaba", [])):
                            source_batches.append(
                                ("Accessories:Alibaba", await _scrape_playwright_accessories(page, search_def["term"], search_def["theme"], "Alibaba", f"https://www.alibaba.com/trade/search?SearchText={search_def['term'].replace(' ', '+')}"))
                            )
                        if search_def["term"] in set(batch_terms.get("BargainHardware", [])):
                            source_batches.append(
                                ("Accessories:BargainHardware", await _scrape_playwright_accessories(page, search_def["term"], search_def["theme"], "BargainHardware", f"https://www.bargainhardware.eu/de/catalogsearch/result/?q={search_def['term'].replace(' ', '+')}"))
                            )
                        await browser.close()
                else:
                    for vendor in ("Amazon", "Temu", "AliExpress", "Alibaba", "BargainHardware"):
                        if search_def["term"] in set(batch_terms.get(vendor, [])):
                            source_batches.append((f"Accessories:{vendor}", []))

                for source_name, results in source_batches:
                    raw_found = len(results)
                    saved_count = min(24, raw_found)
                    stats["found"] += raw_found
                    record_term_result(
                        source_name=source_name,
                        term=search_def["term"],
                        found=raw_found,
                        new=saved_count,
                    )
                    for acc in results[:24]:
                        try:
                            await _upsert_accessory(db, acc)
                            stats["upserted"] += 1
                        except Exception as row_exc:
                            stats["errors"] += 1
                            await db.rollback()
                            record_term_result(
                                source_name=source_name,
                                term=search_def["term"],
                                error=f"row_upsert_error:{row_exc}",
                            )
                            log.error("accessories.upsert.error", term=search_def["term"], source=source_name, error=str(row_exc))
            except Exception as exc:
                stats["errors"] += 1
                await db.rollback()
                record_term_result(
                    source_name="Accessories:eBay",
                    term=search_def["term"],
                    error=str(exc),
                )
                log.error("accessories.scrape.error", term=search_def["term"], error=str(exc))

        await db.commit()

    log.info("accessories_swarm.done", **stats)
    return stats


async def _scrape_playwright_accessories(page, term: str, theme: str, site: str, url: str) -> list[RawAccessory]:
    out: list[RawAccessory] = []
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(1.0)
        await page.evaluate("window.scrollBy(0, 700)")
        await asyncio.sleep(0.6)
        rows = await page.evaluate(
            """() => {
                const data = [];
                const re = /([£$€])\\s*([\\d,]+\\.?\\d*)/;
                const anchors = Array.from(document.querySelectorAll('a[href]')).slice(0, 500);
                const seen = new Set();
                for (const a of anchors) {
                    const href = a.href || '';
                    if (!href || seen.has(href)) continue;
                    const txt = (a.textContent || '').replace(/\\s+/g, ' ').trim();
                    if (!txt || txt.length < 8) continue;
                    let price = 0;
                    const node = a.closest('div,li,article') || a;
                    const scopeText = (node.textContent || '');
                    const m = re.exec(scopeText);
                    if (m) price = parseFloat((m[2] || '').replace(/,/g, ''));
                    if (!Number.isFinite(price) || price <= 0 || price > 80) continue;
                    const img = (node.querySelector('img')?.src || '');
                    seen.add(href);
                    data.push({title: txt, href, price, img});
                    if (data.length >= 60) break;
                }
                return data;
            }"""
        )
        for r in rows or []:
            out.append(
                RawAccessory(
                    name=str(r.get("title") or "")[:200],
                    price=float(r.get("price") or 0.0),
                    source_site=site,
                    source_url=str(r.get("href") or ""),
                    image_url=str(r.get("img") or ""),
                    theme=theme,
                    condition=PartCondition.new,
                )
            )
    except Exception as exc:
        log.warning("accessories.playwright.error", site=site, term=term, error=str(exc))
    return out


async def _scrape_gumtree_accessories(term: str, theme: str) -> list[RawAccessory]:
    try:
        from app.services.playwright_scraper import scrape_gumtree_playwright
    except Exception as exc:
        log.warning("gumtree.accessories.import_error", error=str(exc))
        return []
    out: list[RawAccessory] = []
    try:
        rows = await scrape_gumtree_playwright([term], 1, int(MAX_PRICE))
        for r in rows[:24]:
            out.append(
                RawAccessory(
                    name=str(r.title or "")[:200],
                    price=float(r.price or 0),
                    source_site="Gumtree",
                    source_url=str(r.url or ""),
                    image_url=(r.image_urls[0] if getattr(r, "image_urls", None) else ""),
                    theme=theme,
                    condition=PartCondition.used,
                )
            )
    except Exception as exc:
        log.warning("gumtree.accessories.error", term=term, error=str(exc))
        return []
    return out


async def _scrape_facebook_accessories(term: str, theme: str) -> list[RawAccessory]:
    try:
        from app.services.playwright_scraper import scrape_facebook_playwright
    except Exception as exc:
        log.warning("facebook.accessories.import_error", error=str(exc))
        return []
    out: list[RawAccessory] = []
    try:
        rows = await scrape_facebook_playwright([term], 1, int(MAX_PRICE))
        for r in rows[:24]:
            out.append(
                RawAccessory(
                    name=str(r.title or "")[:200],
                    price=float(r.price or 0),
                    source_site="Facebook Marketplace",
                    source_url=str(r.url or ""),
                    image_url=(r.image_urls[0] if getattr(r, "image_urls", None) else ""),
                    theme=theme,
                    condition=PartCondition.used,
                )
            )
    except Exception as exc:
        if "facebook_login_required" in str(exc):
            raise
        log.warning("facebook.accessories.error", term=term, error=str(exc))
        return []
    return out


def _parse_price(text: str) -> float:
    m = re.search(r"[\d,]+\.?\d*", str(text).replace(",", ""))
    return float(m.group(0)) if m else 0.0
