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
                if price <= 0 or price > MAX_PRICE:
                    continue
                url = url_el.get("href", "")
                if not url.startswith("http"):
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
                results = await _scrape_ebay_accessories(
                    search_def["term"],
                    search_def["theme"],
                    search_def["condition"],
                )
                stats["found"] += len(results)
                for acc in results[:8]:
                    await _upsert_accessory(db, acc)
                    stats["upserted"] += 1
            except Exception as exc:
                stats["errors"] += 1
                log.error("accessories.scrape.error", term=search_def["term"], error=str(exc))

        await db.commit()

    log.info("accessories_swarm.done", **stats)
    return stats


def _parse_price(text: str) -> float:
    m = re.search(r"[\d,]+\.?\d*", str(text).replace(",", ""))
    return float(m.group(0)) if m else 0.0
