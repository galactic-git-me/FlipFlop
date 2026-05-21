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
from playwright.async_api import async_playwright

from app.database import AsyncSessionLocal
from app.models.part import Part, PartCategory, PartCondition
from app.models.price_history import PriceHistory, PriceHistoryType
from app.services.search_telemetry import record_term_result
import structlog

log = structlog.get_logger(__name__)
ua = UserAgent()

MAX_PRICE = 80.0  # Max price for accessories

ACCESSORY_SEARCHES = [
    # Mice
    {"theme": "Mouse",      "term": "gaming mouse wired",    "condition": "1000"},  # New
    {"theme": "Mouse",      "term": "budget gaming mouse",   "condition": "1000"},
    {"theme": "Mouse",      "term": "optical mouse",         "condition": "3000"},  # Used
    # Keyboards
    {"theme": "Keyboard",   "term": "gaming keyboard rgb",   "condition": "1000"},
    {"theme": "Keyboard",   "term": "budget gaming keyboard","condition": "1000"},
    {"theme": "Keyboard",   "term": "mechanical keyboard",   "condition": "3000"},
    # Headsets
    {"theme": "Headset",    "term": "gaming headset usb",    "condition": "1000"},
    {"theme": "Headset",    "term": "pc headset microphone", "condition": "3000"},
    # Mousepads
    {"theme": "Mousepad",   "term": "gaming mousepad xl",    "condition": "1000"},
    {"theme": "Mousepad",   "term": "large desk mat",        "condition": "1000"},
    # Controllers
    {"theme": "Controller", "term": "pc controller usb",     "condition": "3000"},
    {"theme": "Controller", "term": "gamepad pc usb",        "condition": "3000"},
    # Webcams
    {"theme": "Webcam",     "term": "webcam 1080p usb",      "condition": "1000"},
    {"theme": "Webcam",     "term": "hd webcam pc",          "condition": "3000"},
    # Monitor Arms
    {"theme": "Monitor Arm","term": "monitor arm single",    "condition": "3000"},
    {"theme": "Monitor Arm","term": "monitor stand adjustable","condition": "3000"},
]


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
    """Scrape eBay UK BIN listings for an accessory search term."""
    condition = PartCondition.new if condition_code == "1000" else PartCondition.used
    params = {
        "_nkw": term,
        "LH_BIN": "1",
        "LH_ItemCondition": condition_code,
        "_sacat": "0",
        "_sop": "15",       # Price + shipping lowest first
        "LH_PrefLoc": "1",  # UK only
        "_udhi": str(int(MAX_PRICE)),
    }
    headers = {"User-Agent": ua.random, "Accept-Language": "en-GB"}
    items_out = []
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get("https://www.ebay.co.uk/sch/i.html", params=params, headers=headers)
        if resp.status_code != 200:
            return items_out
        soup = BeautifulSoup(resp.text, "lxml")

        items = (
            soup.select(".s-card[data-listingid]")
            or soup.select("li.s-item[data-view]")
            or soup.select(".s-item:not(.s-item--placeholder)")
        )
        use_new = bool(items)

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
                if price <= 0 or price > MAX_PRICE:
                    continue
                url = url_el.get("href", "")
                if not url or "javascript:void(0)" in url:
                    continue
                items_out.append(RawAccessory(
                    name=title[:200],
                    price=price,
                    source_site="eBay",
                    source_url=url,
                    image_url=img_el.get("src", "") if img_el else "",
                    theme=theme,
                    condition=condition,
                ))
            except Exception:
                continue
    except Exception as exc:
        log.warning("ebay.accessories.error", term=term, error=str(exc))
    return items_out


async def _upsert_accessory(db, acc: RawAccessory):
    from sqlalchemy import select as sa_select
    result = await db.execute(
        sa_select(Part).where(
            Part.name == acc.name,
            Part.source_site == acc.source_site,
            Part.category == PartCategory.accessory,
        )
    )
    part = result.scalar_one_or_none()
    now = datetime.utcnow()

    if part:
        part.price = acc.price
        if acc.condition == PartCondition.new:
            part.price_new = acc.price
        else:
            part.price_used = acc.price
        part.source_url = acc.source_url
        part.image_url = acc.image_url or part.image_url
        part.last_price_update = now
    else:
        part = Part(
            name=acc.name,
            category=PartCategory.accessory,
            condition=acc.condition,
            source_site=acc.source_site,
            source_url=acc.source_url,
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


async def run_accessories_swarm() -> dict:
    log.info("accessories_swarm.start")
    stats = {"found": 0, "upserted": 0, "errors": 0}

    async with AsyncSessionLocal() as db:
        for search_def in ACCESSORY_SEARCHES:
            try:
                source_batches: list[tuple[str, list[RawAccessory]]] = []
                ebay_results = await _scrape_ebay_accessories(
                    search_def["term"],
                    search_def["theme"],
                    search_def["condition"],
                )
                source_batches.append(("Accessories:eBay", ebay_results))

                async with async_playwright() as p:
                    browser = await p.chromium.launch(
                        headless=True,
                        args=["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-dev-shm-usage"],
                    )
                    ctx = await browser.new_context(
                        user_agent=ua.random,
                        locale="en-GB",
                        timezone_id="Europe/London",
                    )
                    await ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
                    page = await ctx.new_page()

                    source_batches.append(
                        ("Accessories:Amazon", await _scrape_playwright_accessories(page, search_def["term"], search_def["theme"], "Amazon", f"https://www.amazon.co.uk/s?k={search_def['term'].replace(' ', '+')}&i=computers"))
                    )
                    source_batches.append(
                        ("Accessories:Temu", await _scrape_playwright_accessories(page, search_def["term"], search_def["theme"], "Temu", f"https://www.temu.com/search_result.html?search_key={search_def['term'].replace(' ', '+')}&search_method=user"))
                    )
                    source_batches.append(
                        ("Accessories:AliExpress", await _scrape_playwright_accessories(page, search_def["term"], search_def["theme"], "AliExpress", f"https://www.aliexpress.com/wholesale?SearchText={search_def['term'].replace(' ', '+')}&g=y&SortType=price_asc"))
                    )
                    source_batches.append(
                        ("Accessories:Alibaba", await _scrape_playwright_accessories(page, search_def["term"], search_def["theme"], "Alibaba", f"https://www.alibaba.com/trade/search?SearchText={search_def['term'].replace(' ', '+')}"))
                    )
                    source_batches.append(
                        ("Accessories:BargainHardware", await _scrape_playwright_accessories(page, search_def["term"], search_def["theme"], "BargainHardware", f"https://www.bargainhardware.eu/de/catalogsearch/result/?q={search_def['term'].replace(' ', '+')}"))
                    )
                    await browser.close()

                for source_name, results in source_batches:
                    stats["found"] += len(results)
                    record_term_result(
                        source_name=source_name,
                        term=search_def["term"],
                        found=len(results),
                        new=0,
                    )
                    for acc in results[:8]:
                        await _upsert_accessory(db, acc)
                        stats["upserted"] += 1
            except Exception as exc:
                stats["errors"] += 1
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
                    if (data.length >= 12) break;
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


def _parse_price(text: str) -> float:
    m = re.search(r"[\d,]+\.?\d*", str(text).replace(",", ""))
    return float(m.group(0)) if m else 0.0
