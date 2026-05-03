"""
Upgrade Parts Swarm — runs every 24 hours.
Scrapes current prices for tracked upgrade components from:
  - eBay UK (sold listings → real market price)
  - BargainHardware.co.uk (refurbished specialist)
Stores new / used / refurb price tiers per part.
"""
import re
import asyncio
import httpx
from bs4 import BeautifulSoup
from datetime import datetime
from fake_useragent import UserAgent
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.part import Part, PartCategory, PartCondition
from app.models.price_history import PriceHistory, PriceHistoryType
import structlog

log = structlog.get_logger(__name__)
ua = UserAgent()


TRACKED_PARTS = [
    # ── GPUs — budget / mid tier (most common flip add-ons) ─────────────────
    {"name": "GTX 1060 6GB",  "category": PartCategory.gpu, "ebay_search": "GTX 1060 6GB",  "bh_search": "gtx+1060+6gb"},
    {"name": "GTX 1060 3GB",  "category": PartCategory.gpu, "ebay_search": "GTX 1060 3GB",  "bh_search": "gtx+1060+3gb"},
    {"name": "GTX 1650 4GB",  "category": PartCategory.gpu, "ebay_search": "GTX 1650 4GB",  "bh_search": "gtx+1650"},
    {"name": "GTX 1660 Super","category": PartCategory.gpu, "ebay_search": "GTX 1660 Super","bh_search": "gtx+1660+super"},
    {"name": "GTX 1070 8GB",  "category": PartCategory.gpu, "ebay_search": "GTX 1070 8GB",  "bh_search": "gtx+1070"},
    {"name": "RX 570 8GB",    "category": PartCategory.gpu, "ebay_search": "RX 570 8GB",    "bh_search": "rx+570+8gb"},
    {"name": "RX 580 8GB",    "category": PartCategory.gpu, "ebay_search": "RX 580 8GB",    "bh_search": "rx+580+8gb"},
    # ── GPUs — mid-high (RTX 20/30 series — main flip upgrade tier) ─────────
    {"name": "RTX 2060 6GB",  "category": PartCategory.gpu, "ebay_search": "RTX 2060 6GB",  "bh_search": "rtx+2060"},
    {"name": "RTX 2070 8GB",  "category": PartCategory.gpu, "ebay_search": "RTX 2070 8GB",  "bh_search": "rtx+2070"},
    {"name": "RTX 2080 8GB",  "category": PartCategory.gpu, "ebay_search": "RTX 2080 8GB",  "bh_search": "rtx+2080"},
    {"name": "RTX 3060 12GB", "category": PartCategory.gpu, "ebay_search": "RTX 3060 12GB", "bh_search": "rtx+3060"},
    {"name": "RTX 3060 Ti",   "category": PartCategory.gpu, "ebay_search": "RTX 3060 Ti",   "bh_search": "rtx+3060+ti"},
    {"name": "RTX 3070 8GB",  "category": PartCategory.gpu, "ebay_search": "RTX 3070 8GB",  "bh_search": "rtx+3070"},
    {"name": "RTX 3080 10GB", "category": PartCategory.gpu, "ebay_search": "RTX 3080 10GB", "bh_search": "rtx+3080"},
    {"name": "RX 6600 8GB",   "category": PartCategory.gpu, "ebay_search": "RX 6600 8GB",   "bh_search": "rx+6600"},
    {"name": "RX 6650 XT",    "category": PartCategory.gpu, "ebay_search": "RX 6650 XT",    "bh_search": "rx+6650+xt"},
    {"name": "RX 6700 XT",    "category": PartCategory.gpu, "ebay_search": "RX 6700 XT",    "bh_search": "rx+6700+xt"},
    # ── GPUs — current gen budget (RTX 4060 / RX 7600) ──────────────────────
    {"name": "RTX 4060 8GB",  "category": PartCategory.gpu, "ebay_search": "RTX 4060 8GB",  "bh_search": "rtx+4060"},
    {"name": "RX 7600 8GB",   "category": PartCategory.gpu, "ebay_search": "RX 7600 8GB",   "bh_search": "rx+7600"},

    # ── CPUs — Intel (LGA1200/LGA1700 drop-in upgrades) ─────────────────────
    {"name": "Intel i5-10400",  "category": PartCategory.cpu, "ebay_search": "i5-10400 CPU", "bh_search": "i5+10400"},
    {"name": "Intel i5-10600K", "category": PartCategory.cpu, "ebay_search": "i5-10600K CPU","bh_search": "i5+10600k"},
    {"name": "Intel i7-10700",  "category": PartCategory.cpu, "ebay_search": "i7-10700 CPU", "bh_search": "i7+10700"},
    {"name": "Intel i7-10700K", "category": PartCategory.cpu, "ebay_search": "i7-10700K CPU","bh_search": "i7+10700k"},
    {"name": "Intel i9-10900K", "category": PartCategory.cpu, "ebay_search": "i9-10900K CPU","bh_search": "i9+10900k"},
    {"name": "Intel i5-12400",  "category": PartCategory.cpu, "ebay_search": "i5-12400 CPU", "bh_search": "i5+12400"},
    {"name": "Intel i7-12700",  "category": PartCategory.cpu, "ebay_search": "i7-12700 CPU", "bh_search": "i7+12700"},
    # ── CPUs — AMD (AM4 — by far the most common flip-platform socket) ───────
    {"name": "Ryzen 5 3600",  "category": PartCategory.cpu, "ebay_search": "Ryzen 5 3600",  "bh_search": "ryzen+5+3600"},
    {"name": "Ryzen 5 5600",  "category": PartCategory.cpu, "ebay_search": "Ryzen 5 5600",  "bh_search": "ryzen+5+5600"},
    {"name": "Ryzen 5 5600X", "category": PartCategory.cpu, "ebay_search": "Ryzen 5 5600X", "bh_search": "ryzen+5+5600x"},
    {"name": "Ryzen 7 5700X", "category": PartCategory.cpu, "ebay_search": "Ryzen 7 5700X", "bh_search": "ryzen+7+5700x"},
    {"name": "Ryzen 7 5800X", "category": PartCategory.cpu, "ebay_search": "Ryzen 7 5800X", "bh_search": "ryzen+7+5800x"},
    {"name": "Ryzen 9 5900X", "category": PartCategory.cpu, "ebay_search": "Ryzen 9 5900X", "bh_search": "ryzen+9+5900x"},

    # ── RAM ──────────────────────────────────────────────────────────────────
    {"name": "8GB DDR4",       "category": PartCategory.ram, "ebay_search": "8GB DDR4 2666 used",  "bh_search": "8gb+ddr4"},
    {"name": "16GB DDR4 Kit",  "category": PartCategory.ram, "ebay_search": "16GB DDR4 3200 used", "bh_search": "16gb+ddr4"},
    {"name": "32GB DDR4 Kit",  "category": PartCategory.ram, "ebay_search": "32GB DDR4 3200 used", "bh_search": "32gb+ddr4"},
    {"name": "16GB DDR5 Kit",  "category": PartCategory.ram, "ebay_search": "16GB DDR5 5200 used", "bh_search": "16gb+ddr5"},
    {"name": "32GB DDR5 Kit",  "category": PartCategory.ram, "ebay_search": "32GB DDR5 5200 used", "bh_search": "32gb+ddr5"},

    # ── Storage ──────────────────────────────────────────────────────────────
    {"name": "256GB SATA SSD", "category": PartCategory.ssd, "ebay_search": "256GB SSD SATA used", "bh_search": "256gb+ssd"},
    {"name": "480GB SATA SSD", "category": PartCategory.ssd, "ebay_search": "480GB SSD SATA used", "bh_search": "480gb+ssd"},
    {"name": "1TB SATA SSD",   "category": PartCategory.ssd, "ebay_search": "1TB SSD SATA used",   "bh_search": "1tb+sata+ssd"},
    {"name": "500GB NVMe SSD", "category": PartCategory.ssd, "ebay_search": "500GB NVMe M.2 used", "bh_search": "500gb+nvme"},
    {"name": "1TB NVMe SSD",   "category": PartCategory.ssd, "ebay_search": "1TB NVMe M.2 used",   "bh_search": "1tb+nvme"},
    {"name": "2TB NVMe SSD",   "category": PartCategory.ssd, "ebay_search": "2TB NVMe M.2 used",   "bh_search": "2tb+nvme"},
    {"name": "2TB HDD",        "category": PartCategory.ssd, "ebay_search": "2TB hard drive used",  "bh_search": "2tb+hdd"},

    # ── PSU ───────────────────────────────────────────────────────────────────
    {"name": "550W PSU 80+ Bronze", "category": PartCategory.psu, "ebay_search": "550W PSU 80 bronze used", "bh_search": "550w+psu"},
    {"name": "650W PSU 80+ Bronze", "category": PartCategory.psu, "ebay_search": "650W PSU 80 bronze used", "bh_search": "650w+psu"},
    {"name": "750W PSU 80+ Gold",   "category": PartCategory.psu, "ebay_search": "750W PSU 80 gold used",   "bh_search": "750w+psu"},
    {"name": "850W PSU 80+ Gold",   "category": PartCategory.psu, "ebay_search": "850W PSU 80 gold used",   "bh_search": "850w+psu"},
]


async def run_upgrade_parts_swarm() -> dict:
    log.info("upgrade_parts_swarm.start")
    stats = {"updated": 0, "errors": 0}

    tasks = [_process_part(part_def) for part_def in TRACKED_PARTS]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    async with AsyncSessionLocal() as db:
        for part_def, result in zip(TRACKED_PARTS, results):
            if isinstance(result, Exception):
                stats["errors"] += 1
                log.error("part.price.error", part=part_def["name"], error=str(result))
                continue
            ebay_used, ebay_sold, bh_refurb = result
            if any([ebay_used, ebay_sold, bh_refurb]):
                await _upsert_part(db, part_def, ebay_used, ebay_sold, bh_refurb)
                stats["updated"] += 1
        await db.commit()

    log.info("upgrade_parts_swarm.done", **stats)
    return stats


async def _process_part(part_def: dict) -> tuple:
    """Fetch prices from all sources concurrently."""
    ebay_used_task = _fetch_ebay_buy_price(part_def["ebay_search"], condition="used")
    ebay_sold_task = _fetch_ebay_sold_median(part_def["ebay_search"])
    bh_task = _fetch_bargainhardware(part_def["bh_search"])
    return await asyncio.gather(ebay_used_task, ebay_sold_task, bh_task, return_exceptions=False)


async def _fetch_ebay_buy_price(search: str, condition: str = "used") -> float | None:
    """Lowest Buy-It-Now price on eBay for a given search."""
    params = {
        "_nkw": search,
        "LH_BIN": "1",
        "LH_ItemCondition": "3000",   # Used
        "_sacat": "0",
        "_sop": "15",  # Sort: price + postage lowest first
        "LH_PrefLoc": "1",  # UK only
    }
    headers = {"User-Agent": ua.random, "Accept-Language": "en-GB"}
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get("https://www.ebay.co.uk/sch/i.html", params=params, headers=headers)
        soup = BeautifulSoup(resp.text, "lxml")
        prices = _extract_prices_from_soup(soup)
        if not prices:
            return None
        prices.sort()
        # Use 25th percentile — skip outlier junk
        return round(prices[max(0, len(prices) // 4)], 2)
    except Exception:
        return None


async def _fetch_ebay_sold_median(search: str) -> float | None:
    """Median of recent eBay sold listings — the real market price."""
    params = {
        "_nkw": search,
        "LH_Sold": "1",
        "LH_Complete": "1",
        "LH_ItemCondition": "3000",
        "_sacat": "0",
        "_sop": "12",
    }
    headers = {"User-Agent": ua.random, "Accept-Language": "en-GB"}
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get("https://www.ebay.co.uk/sch/i.html", params=params, headers=headers)
        soup = BeautifulSoup(resp.text, "lxml")
        prices = _extract_prices_from_soup(soup)
        if not prices:
            return None
        prices.sort()
        return round(prices[len(prices) // 2], 2)
    except Exception:
        return None


async def _fetch_bargainhardware(search_term: str) -> float | None:
    """Lowest refurbished price from BargainHardware.co.uk."""
    url = f"https://www.bargainhardware.co.uk/search?q={search_term}"
    headers = {
        "User-Agent": ua.random,
        "Accept-Language": "en-GB",
        "Accept": "text/html",
    }
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
        if resp.status_code != 200 or len(resp.text) < 500:
            return None
        soup = BeautifulSoup(resp.text, "lxml")
        prices = []
        # BargainHardware uses .price, .product-price, or data-price attributes
        for el in soup.select(".price, .product-price, [data-price], .grid-item__price, .item-price"):
            text = el.get("data-price") or el.get_text(strip=True)
            if text:
                p = _parse_price(text)
                if 1 < p < 2000:
                    prices.append(p)
        if not prices:
            return None
        return round(sorted(prices)[0], 2)  # cheapest available
    except Exception:
        return None


def _extract_prices_from_soup(soup: BeautifulSoup) -> list[float]:
    """Try multiple eBay price selectors (handles layout changes)."""
    prices = []
    selectors = [
        "[class*='s-card__price']",
        ".s-item__price",
        "[class*='price--']",
    ]
    for sel in selectors:
        for el in soup.select(sel):
            text = el.get_text(strip=True)
            p = _parse_price(text)
            if 1 < p < 2000:
                prices.append(p)
        if prices:
            break
    return prices


async def _upsert_part(
    db,
    part_def: dict,
    ebay_used: float | None,
    ebay_sold: float | None,
    bh_refurb: float | None,
):
    result = await db.execute(select(Part).where(Part.name == part_def["name"]))
    part = result.scalar_one_or_none()
    now = datetime.utcnow()

    # Best "buy" price: cheapest of ebay_used buy-it-now or BargainHardware
    candidates = [p for p in [ebay_used, bh_refurb] if p]
    best_buy = min(candidates) if candidates else None

    if part:
        if best_buy:
            part.price = best_buy
            part.price_used = ebay_used or part.price_used
            part.price_refurb = bh_refurb or part.price_refurb
        part.last_price_update = now
    else:
        part = Part(
            name=part_def["name"],
            category=part_def["category"],
            condition=PartCondition.used,
            source_site="eBay UK / BargainHardware",
            price=best_buy,
            price_used=ebay_used,
            price_refurb=bh_refurb,
            resale_value_add=0.0,
            last_price_update=now,
        )
        db.add(part)
        await db.flush()

    # Price history entry
    if ebay_sold:
        db.add(PriceHistory(
            entity_type=PriceHistoryType.part,
            entity_id=part.id,
            price=ebay_sold,
            condition="used",
            source="ebay_sold",
        ))
    if bh_refurb:
        db.add(PriceHistory(
            entity_type=PriceHistoryType.part,
            entity_id=part.id,
            price=bh_refurb,
            condition="refurb",
            source="bargainhardware",
        ))


def _parse_price(text: str) -> float:
    m = re.search(r"[\d,]+\.?\d*", str(text).replace(",", ""))
    return float(m.group(0)) if m else 0.0
