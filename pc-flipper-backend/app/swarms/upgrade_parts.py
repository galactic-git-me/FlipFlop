"""
Upgrade Parts Swarm — runs every 24 hours.

Scrapes current prices for tracked upgrade components from:
  - eBay UK sold listings  → real market price (primary source)
  - eBay UK BIN listings   → lowest current ask (secondary)
  - BargainHardware.co.uk  → UK refurb specialist via Playwright
    (NOTE: this server's IP geo-redirects to bargainhardware.eu/de/ which stocks
    enterprise workstations, not consumer components.  BH will return None until
    the backend runs from a UK IP or behind a UK proxy.)
  - Scan / Overclockers / Box → new retail prices via httpx
  - Amazon / Temu / AliExpress → additional new retail lanes via Playwright

Architecture:
  - eBay requests use a single persistent httpx session with bounded concurrency
    per part to improve throughput while still limiting request pressure.
    3-attempt exponential-backoff retry on 403 / empty response.
  - BargainHardware uses a shared Playwright browser context (one launch per swarm).
  - Scan / Overclockers / Box run concurrently at the end (they're new-retail and
    less aggressive about bot detection).
"""
import re
import asyncio
import random
import httpx
from bs4 import BeautifulSoup
from datetime import datetime
from fake_useragent import UserAgent
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.part import Part, PartCategory, PartCondition
from app.models.price_history import PriceHistory, PriceHistoryType
from app.services.search_telemetry import record_term_result
import structlog

log = structlog.get_logger(__name__)
ua = UserAgent()

# EUR → GBP approximate rate (BargainHardware.eu prices are in EUR)
EUR_TO_GBP = 0.84

_STEALTH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-sandbox", "--disable-dev-shm-usage",
    "--disable-extensions", "--disable-infobars",
    "--window-size=1366,768", "--lang=en-GB",
]
_STEALTH_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

_EBAY_HEADERS = {
    "User-Agent": _STEALTH_UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
}


TRACKED_PARTS = [
    # ── Generic market lane (especially useful for Temu/AliExpress discovery) ─
    {"name": "PC Build Bundle", "category": PartCategory.accessory, "ebay_search": "pc build", "bh_search": "pc+build"},

    # ── GPUs — budget / mid tier ─────────────────────────────────────────────
    {"name": "GTX 1060 6GB",   "category": PartCategory.gpu, "ebay_search": "GTX 1060 6GB used",    "bh_search": "gtx+1060+6gb"},
    {"name": "GTX 1060 3GB",   "category": PartCategory.gpu, "ebay_search": "GTX 1060 3GB used",    "bh_search": "gtx+1060+3gb"},
    {"name": "GTX 1650 4GB",   "category": PartCategory.gpu, "ebay_search": "GTX 1650 4GB used",    "bh_search": "gtx+1650"},
    {"name": "GTX 1660 Super", "category": PartCategory.gpu, "ebay_search": "GTX 1660 Super used",  "bh_search": "gtx+1660+super"},
    {"name": "GTX 1070 8GB",   "category": PartCategory.gpu, "ebay_search": "GTX 1070 8GB used",    "bh_search": "gtx+1070"},
    {"name": "RX 570 8GB",     "category": PartCategory.gpu, "ebay_search": "RX 570 8GB used",      "bh_search": "rx+570+8gb"},
    {"name": "RX 580 8GB",     "category": PartCategory.gpu, "ebay_search": "RX 580 8GB used",      "bh_search": "rx+580+8gb"},
    # ── GPUs — mid-high ──────────────────────────────────────────────────────
    {"name": "RTX 2060 6GB",   "category": PartCategory.gpu, "ebay_search": "RTX 2060 6GB used",    "bh_search": "rtx+2060"},
    {"name": "RTX 2070 8GB",   "category": PartCategory.gpu, "ebay_search": "RTX 2070 8GB used",    "bh_search": "rtx+2070"},
    {"name": "RTX 2080 8GB",   "category": PartCategory.gpu, "ebay_search": "RTX 2080 8GB used",    "bh_search": "rtx+2080"},
    {"name": "RTX 3060 12GB",  "category": PartCategory.gpu, "ebay_search": "RTX 3060 12GB used",   "bh_search": "rtx+3060"},
    {"name": "RTX 3060 Ti",    "category": PartCategory.gpu, "ebay_search": "RTX 3060 Ti used",     "bh_search": "rtx+3060+ti"},
    {"name": "RTX 3070 8GB",   "category": PartCategory.gpu, "ebay_search": "RTX 3070 8GB used",    "bh_search": "rtx+3070"},
    {"name": "RTX 3080 10GB",  "category": PartCategory.gpu, "ebay_search": "RTX 3080 10GB used",   "bh_search": "rtx+3080"},
    {"name": "RX 6600 8GB",    "category": PartCategory.gpu, "ebay_search": "RX 6600 8GB used",     "bh_search": "rx+6600"},
    {"name": "RX 6650 XT",     "category": PartCategory.gpu, "ebay_search": "RX 6650 XT used",      "bh_search": "rx+6650+xt"},
    {"name": "RX 6700 XT",     "category": PartCategory.gpu, "ebay_search": "RX 6700 XT used",      "bh_search": "rx+6700+xt"},
    # ── GPUs — current gen ───────────────────────────────────────────────────
    {"name": "RTX 4060 8GB",   "category": PartCategory.gpu, "ebay_search": "RTX 4060 8GB used",    "bh_search": "rtx+4060"},
    {"name": "RX 7600 8GB",    "category": PartCategory.gpu, "ebay_search": "RX 7600 8GB used",     "bh_search": "rx+7600"},

    # ── CPUs — Intel ─────────────────────────────────────────────────────────
    {"name": "Intel i5-10400",  "category": PartCategory.cpu, "ebay_search": "Intel Core i5-10400",  "bh_search": "i5+10400"},
    {"name": "Intel i5-10600K", "category": PartCategory.cpu, "ebay_search": "Intel Core i5-10600K", "bh_search": "i5+10600k"},
    {"name": "Intel i7-10700",  "category": PartCategory.cpu, "ebay_search": "Intel Core i7-10700",  "bh_search": "i7+10700"},
    {"name": "Intel i7-10700K", "category": PartCategory.cpu, "ebay_search": "Intel Core i7-10700K", "bh_search": "i7+10700k"},
    {"name": "Intel i9-10900K", "category": PartCategory.cpu, "ebay_search": "Intel Core i9-10900K", "bh_search": "i9+10900k"},
    {"name": "Intel i5-12400",  "category": PartCategory.cpu, "ebay_search": "Intel Core i5-12400",  "bh_search": "i5+12400"},
    {"name": "Intel i7-12700",  "category": PartCategory.cpu, "ebay_search": "Intel Core i7-12700",  "bh_search": "i7+12700"},
    # ── CPUs — AMD ───────────────────────────────────────────────────────────
    {"name": "Ryzen 5 3600",   "category": PartCategory.cpu, "ebay_search": "AMD Ryzen 5 3600",     "bh_search": "ryzen+5+3600"},
    {"name": "Ryzen 5 5600",   "category": PartCategory.cpu, "ebay_search": "AMD Ryzen 5 5600",     "bh_search": "ryzen+5+5600"},
    {"name": "Ryzen 5 5600X",  "category": PartCategory.cpu, "ebay_search": "AMD Ryzen 5 5600X",    "bh_search": "ryzen+5+5600x"},
    {"name": "Ryzen 7 5700X",  "category": PartCategory.cpu, "ebay_search": "AMD Ryzen 7 5700X",    "bh_search": "ryzen+7+5700x"},
    {"name": "Ryzen 7 5800X",  "category": PartCategory.cpu, "ebay_search": "AMD Ryzen 7 5800X",    "bh_search": "ryzen+7+5800x"},
    {"name": "Ryzen 9 5900X",  "category": PartCategory.cpu, "ebay_search": "AMD Ryzen 9 5900X",    "bh_search": "ryzen+9+5900x"},

    # ── RAM ──────────────────────────────────────────────────────────────────
    {"name": "8GB DDR4",       "category": PartCategory.ram, "ebay_search": "8GB DDR4 2666",        "bh_search": "8gb+ddr4"},
    {"name": "16GB DDR4 Kit",  "category": PartCategory.ram, "ebay_search": "16GB DDR4 3200 kit",   "bh_search": "16gb+ddr4"},
    {"name": "32GB DDR4 Kit",  "category": PartCategory.ram, "ebay_search": "32GB DDR4 3200 kit",   "bh_search": "32gb+ddr4"},
    {"name": "16GB DDR5 Kit",  "category": PartCategory.ram, "ebay_search": "16GB DDR5 5200 kit",   "bh_search": "16gb+ddr5"},
    {"name": "32GB DDR5 Kit",  "category": PartCategory.ram, "ebay_search": "32GB DDR5 5200 kit",   "bh_search": "32gb+ddr5"},

    # ── Storage ──────────────────────────────────────────────────────────────
    {"name": "256GB SATA SSD", "category": PartCategory.ssd, "ebay_search": "256GB SATA SSD",       "bh_search": "256gb+ssd"},
    {"name": "480GB SATA SSD", "category": PartCategory.ssd, "ebay_search": "480GB SATA SSD",       "bh_search": "480gb+ssd"},
    {"name": "1TB SATA SSD",   "category": PartCategory.ssd, "ebay_search": "1TB SATA SSD",         "bh_search": "1tb+sata+ssd"},
    {"name": "500GB NVMe SSD", "category": PartCategory.ssd, "ebay_search": "500GB NVMe M.2 SSD",   "bh_search": "500gb+nvme"},
    {"name": "1TB NVMe SSD",   "category": PartCategory.ssd, "ebay_search": "1TB NVMe M.2 SSD",     "bh_search": "1tb+nvme"},
    {"name": "2TB NVMe SSD",   "category": PartCategory.ssd, "ebay_search": "2TB NVMe M.2 SSD",     "bh_search": "2tb+nvme"},
    {"name": "2TB HDD",        "category": PartCategory.ssd, "ebay_search": "2TB internal hard drive", "bh_search": "2tb+hdd"},

    # ── PSU ───────────────────────────────────────────────────────────────────
    {"name": "550W PSU 80+ Bronze", "category": PartCategory.psu, "ebay_search": "550W ATX PSU 80 bronze", "bh_search": "550w+psu"},
    {"name": "650W PSU 80+ Bronze", "category": PartCategory.psu, "ebay_search": "650W ATX PSU 80 bronze", "bh_search": "650w+psu"},
    {"name": "750W PSU 80+ Gold",   "category": PartCategory.psu, "ebay_search": "750W ATX PSU 80 gold",   "bh_search": "750w+psu"},
    {"name": "850W PSU 80+ Gold",   "category": PartCategory.psu, "ebay_search": "850W ATX PSU 80 gold",   "bh_search": "850w+psu"},
]


async def run_upgrade_parts_swarm() -> dict:
    log.info("upgrade_parts_swarm.start", total_parts=len(TRACKED_PARTS))
    stats = {
        "updated": 0, "errors": 0,
        "ebay_sold": 0, "ebay_buy": 0, "bh": 0,
        "scan": 0, "overclockers": 0, "box": 0,
        "amazon": 0, "temu": 0, "aliexpress": 0,
    }

    # ── Phase 1: eBay — bounded concurrent fetches per part ───────────────────
    ebay_sold_map:  dict[str, float | None] = {}
    ebay_buy_map:   dict[str, float | None] = {}
    ebay_concurrency = 6
    sem = asyncio.Semaphore(ebay_concurrency)

    async def _fetch_ebay_for_part(client: httpx.AsyncClient, part_def: dict):
        async with sem:
            name = part_def["name"]
            search = part_def["ebay_search"]
            sold = await _ebay_sold_median(client, search)
            await asyncio.sleep(random.uniform(0.2, 0.6))
            buy = await _ebay_buy_price(client, search)
            await asyncio.sleep(random.uniform(0.2, 0.6))
            return name, search, sold, buy

    async with httpx.AsyncClient(follow_redirects=True, timeout=25) as client:
        ebay_tasks = [asyncio.create_task(_fetch_ebay_for_part(client, p)) for p in TRACKED_PARTS]
        for done in asyncio.as_completed(ebay_tasks):
            name, search, sold, buy = await done
            ebay_sold_map[name] = sold
            if sold:
                stats["ebay_sold"] += 1
            ebay_buy_map[name] = buy
            if buy:
                stats["ebay_buy"] += 1

            log.debug("upgrade_parts.ebay", part=name, sold=sold, buy=buy)
            record_term_result(
                source_name="UpgradeParts:eBay",
                term=search,
                found=1 if (sold or buy) else 0,
                new=0,
            )

    # ── Phase 2: BargainHardware.co.uk via Playwright ────────────────────────
    bh_map: dict[str, float | None] = {}
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=_STEALTH_ARGS)
            ctx = await browser.new_context(user_agent=_STEALTH_UA, locale="en-GB", timezone_id="Europe/London")
            await ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
            page = await ctx.new_page()
            for part_def in TRACKED_PARTS:
                name = part_def["name"]
                price = await _bh_price(page, part_def["bh_search"])
                bh_map[name] = price
                if price:
                    stats["bh"] += 1
                    log.debug("upgrade_parts.bh", part=name, price_gbp=price)
                await asyncio.sleep(random.uniform(0.6, 1.0))
                record_term_result(
                    source_name="UpgradeParts:BargainHardware",
                    term=part_def["bh_search"],
                    found=1 if price else 0,
                    new=0,
                )
            await browser.close()
    except ImportError:
        log.warning("upgrade_parts.playwright_missing")
        bh_map = {p["name"]: None for p in TRACKED_PARTS}
    except Exception as exc:
        log.error("upgrade_parts.bh.error", error=str(exc))
        bh_map = {p["name"]: bh_map.get(p["name"]) for p in TRACKED_PARTS}

    # ── Phase 3: Scan / Overclockers / Box — concurrent httpx ────────────────
    scan_r  = await asyncio.gather(*[_fetch_scan(p["ebay_search"])        for p in TRACKED_PARTS], return_exceptions=True)
    oc_r    = await asyncio.gather(*[_fetch_overclockers(p["ebay_search"]) for p in TRACKED_PARTS], return_exceptions=True)
    box_r   = await asyncio.gather(*[_fetch_box(p["ebay_search"])         for p in TRACKED_PARTS], return_exceptions=True)
    for v in scan_r:
        if v and not isinstance(v, Exception):
            stats["scan"] += 1
    for v in oc_r:
        if v and not isinstance(v, Exception):
            stats["overclockers"] += 1
    for v in box_r:
        if v and not isinstance(v, Exception):
            stats["box"] += 1

    # ── Phase 3b: Amazon / Temu / AliExpress — concurrent Playwright ─────────
    amz_r = await asyncio.gather(*[_fetch_amazon(p["ebay_search"]) for p in TRACKED_PARTS], return_exceptions=True)
    temu_r = await asyncio.gather(*[_fetch_temu(p["ebay_search"]) for p in TRACKED_PARTS], return_exceptions=True)
    ali_r = await asyncio.gather(*[_fetch_aliexpress(p["ebay_search"]) for p in TRACKED_PARTS], return_exceptions=True)
    for v in amz_r:
        if v and not isinstance(v, Exception):
            stats["amazon"] += 1
    for v in temu_r:
        if v and not isinstance(v, Exception):
            stats["temu"] += 1
    for v in ali_r:
        if v and not isinstance(v, Exception):
            stats["aliexpress"] += 1

    # ── Phase 4: Persist ──────────────────────────────────────────────────────
    async with AsyncSessionLocal() as db:
        for i, part_def in enumerate(TRACKED_PARTS):
            name = part_def["name"]
            try:
                ebay_used = ebay_buy_map.get(name)
                ebay_sold = ebay_sold_map.get(name)
                bh_refurb = bh_map.get(name)
                scan_new  = scan_r[i] if not isinstance(scan_r[i], Exception) else None
                oc_new    = oc_r[i]   if not isinstance(oc_r[i], Exception)   else None
                box_new   = box_r[i]  if not isinstance(box_r[i], Exception)  else None

                amz_new   = amz_r[i]  if not isinstance(amz_r[i], Exception)  else None
                temu_new  = temu_r[i] if not isinstance(temu_r[i], Exception) else None
                ali_new   = ali_r[i]  if not isinstance(ali_r[i], Exception)  else None

                if any([ebay_used, ebay_sold, bh_refurb, scan_new, oc_new, box_new, amz_new, temu_new, ali_new]):
                    await _upsert_part(
                        db, part_def, ebay_used, ebay_sold, bh_refurb,
                        scan_new, oc_new, box_new, amz_new, temu_new, ali_new,
                    )
                    stats["updated"] += 1
                else:
                    log.debug("upgrade_parts.no_price", part=name)
            except Exception as exc:
                stats["errors"] += 1
                log.error("part.upsert.error", part=name, error=str(exc))
        await db.commit()

    log.info("upgrade_parts_swarm.done", **stats)
    return stats


# ── eBay scraping ─────────────────────────────────────────────────────────────

async def _ebay_sold_median(client: httpx.AsyncClient, search: str) -> float | None:
    """Median sold price from eBay completed listings — 3-attempt retry."""
    params = {
        "_nkw": search, "_sacat": "0",
        "LH_Sold": "1", "LH_Complete": "1",
        "_sop": "12", "_ipg": "60",
    }
    for attempt in range(3):
        try:
            r = await client.get("https://www.ebay.co.uk/sch/i.html", params=params, headers=_EBAY_HEADERS)
            if r.status_code == 200:
                prices = _parse_ebay_prices(r.text)
                if prices:
                    prices.sort()
                    return round(prices[len(prices) // 2], 2)
                # got a page but no prices — might be "Access Denied" soft block
                if "access denied" in r.text.lower() or "interruption" in r.text.lower():
                    await asyncio.sleep(2.5 * (attempt + 1))
                    continue
                return None
            if r.status_code == 403:
                await asyncio.sleep(2.5 * (attempt + 1))
                continue
        except Exception:
            await asyncio.sleep(1.5)
    return None


async def _ebay_buy_price(client: httpx.AsyncClient, search: str) -> float | None:
    """25th-percentile Buy-It-Now used price from eBay — 3-attempt retry."""
    params = {
        "_nkw": search, "_sacat": "0",
        "LH_BIN": "1", "LH_ItemCondition": "3000",
        "_sop": "15", "_ipg": "60",
    }
    for attempt in range(3):
        try:
            r = await client.get("https://www.ebay.co.uk/sch/i.html", params=params, headers=_EBAY_HEADERS)
            if r.status_code == 200:
                prices = _parse_ebay_prices(r.text)
                if prices:
                    prices.sort()
                    return round(prices[max(0, len(prices) // 4)], 2)
                if "access denied" in r.text.lower() or "interruption" in r.text.lower():
                    await asyncio.sleep(2.5 * (attempt + 1))
                    continue
                return None
            if r.status_code == 403:
                await asyncio.sleep(2.5 * (attempt + 1))
                continue
        except Exception:
            await asyncio.sleep(1.5)
    return None


def _parse_ebay_prices(html: str) -> list[float]:
    prices = []
    selectors = [".s-item__price", "[class*='s-card__price']", "[class*='price--']"]
    soup = BeautifulSoup(html, "lxml")
    for sel in selectors:
        for el in soup.select(sel):
            p = _parse_price(el.get_text(strip=True))
            if 1 < p < 2000:
                prices.append(p)
        if prices:
            return prices
    # Fallback: regex scan for £ prices
    for m in re.findall(r"£([\d,]+\.?\d*)", html):
        try:
            p = float(m.replace(",", ""))
            if 1 < p < 2000:
                prices.append(p)
        except ValueError:
            pass
    return prices


# ── BargainHardware (Playwright) ──────────────────────────────────────────────

async def _bh_price(page, search_term: str) -> float | None:
    """
    Cheapest price from BargainHardware via Playwright.
    BargainHardware.co.uk geo-redirects to .eu/de/ from non-UK IPs.
    We use the .eu catalogsearch URL directly and convert EUR→GBP.
    The .eu site stocks enterprise/refurb hardware — consumer GPUs & CPUs
    may not appear until BH.co.uk is accessible from a UK IP.
    """
    url = f"https://www.bargainhardware.eu/de/catalogsearch/result/?q={search_term}"
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=25000)
        await asyncio.sleep(1.5)
        html = await page.content()
        soup = BeautifulSoup(html, "lxml")
        prices_eur = []
        for el in soup.select("[data-price-amount]"):
            try:
                p = float(el.get("data-price-amount", 0))
                if 1 < p < 5000:
                    prices_eur.append(p)
            except (ValueError, TypeError):
                pass
        if not prices_eur:
            return None
        cheapest_eur = sorted(prices_eur)[0]
        return round(cheapest_eur * EUR_TO_GBP, 2)
    except Exception as exc:
        log.debug("bh.pw.error", search=search_term, error=str(exc))
        return None


# ── Scan / Overclockers / Box (httpx) ────────────────────────────────────────

async def _fetch_scan(search_term: str) -> float | None:
    url = f"https://www.scan.co.uk/search?q={search_term.replace(' ', '+')}"
    headers = {"User-Agent": ua.random, "Accept-Language": "en-GB", "Accept": "text/html"}
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
        if resp.status_code != 200 or len(resp.text) < 500:
            return None
        soup = BeautifulSoup(resp.text, "lxml")
        prices = [_parse_price(el.get_text(strip=True)) for el in soup.select(".c-product__price, [class*='price']")]
        prices = [p for p in prices if 1 < p < 2000]
        return round(sorted(prices)[0], 2) if prices else None
    except Exception:
        return None


async def _fetch_overclockers(search_term: str) -> float | None:
    url = f"https://www.overclockers.co.uk/search?q={search_term.replace(' ', '+')}"
    headers = {"User-Agent": ua.random, "Accept-Language": "en-GB", "Accept": "text/html"}
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
        if resp.status_code != 200 or len(resp.text) < 500:
            return None
        soup = BeautifulSoup(resp.text, "lxml")
        prices = [_parse_price(el.get_text(strip=True)) for el in soup.select(".product-price, .price, [class*='price']")]
        prices = [p for p in prices if 1 < p < 2000]
        return round(sorted(prices)[0], 2) if prices else None
    except Exception:
        return None


async def _fetch_box(search_term: str) -> float | None:
    url = f"https://www.box.co.uk/search?search={search_term.replace(' ', '+')}"
    headers = {"User-Agent": ua.random, "Accept-Language": "en-GB", "Accept": "text/html"}
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
        if resp.status_code != 200 or len(resp.text) < 500:
            return None
        soup = BeautifulSoup(resp.text, "lxml")
        prices = [_parse_price(el.get_text(strip=True)) for el in soup.select(".price, .product-price, [class*='price']")]
        prices = [p for p in prices if 1 < p < 2000]
        return round(sorted(prices)[0], 2) if prices else None
    except Exception:
        return None


# ── Amazon / Temu / AliExpress (Playwright) ──────────────────────────────────

async def _fetch_amazon(search_term: str) -> float | None:
    return await _fetch_playwright_lowest_price(
        url=f"https://www.amazon.co.uk/s?k={search_term.replace(' ', '+')}&i=computers",
        item_selector='[data-component-type="s-search-result"]',
        title_selector='h2 span, h2',
        link_selector='h2 a, a.a-link-normal[href*="/dp/"]',
        price_selector='.a-price-whole',
        source_name="amazon",
        max_price=2500.0,
    )


async def _fetch_temu(search_term: str) -> float | None:
    return await _fetch_playwright_lowest_price(
        url=f"https://www.temu.com/search_result.html?search_key={search_term.replace(' ', '+')}&search_method=user",
        item_selector='a[href*="/goods"]',
        title_selector='h3, h4, p, span',
        link_selector='a[href*="/goods"]',
        price_selector='*',
        source_name="temu",
        max_price=2500.0,
    )


async def _fetch_aliexpress(search_term: str) -> float | None:
    return await _fetch_playwright_lowest_price(
        url=f"https://www.aliexpress.com/wholesale?SearchText={search_term.replace(' ', '+')}&g=y&SortType=price_asc",
        item_selector='a[href*="/item/"]',
        title_selector='h1, h2, h3, h4, p, span',
        link_selector='a[href*="/item/"]',
        price_selector='*',
        source_name="aliexpress",
        max_price=2500.0,
    )


async def _fetch_playwright_lowest_price(
    *,
    url: str,
    item_selector: str,
    title_selector: str,
    link_selector: str,
    price_selector: str,
    source_name: str,
    max_price: float,
) -> float | None:
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return None

    prices: list[float] = []
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=_STEALTH_ARGS)
            ctx = await browser.new_context(user_agent=_STEALTH_UA, locale="en-GB", timezone_id="Europe/London")
            await ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
            page = await ctx.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            try:
                await page.wait_for_selector(item_selector, timeout=10000)
            except Exception:
                pass
            await asyncio.sleep(random.uniform(0.8, 1.8))
            await page.evaluate("window.scrollBy(0, 700)")
            await asyncio.sleep(0.5)
            raw = await page.evaluate(
                """({itemSelector, titleSelector, linkSelector, priceSelector}) => {
                    const out = [];
                    const seen = new Set();
                    const re = /[£$€]\\s*([\\d,]+\\.?\\d*)/;
                    const nodes = document.querySelectorAll(itemSelector);
                    nodes.forEach((node) => {
                        try {
                            const titleEl = node.matches('a') ? (node.querySelector(titleSelector) || node) : node.querySelector(titleSelector);
                            const linkEl = node.matches('a') ? node : node.querySelector(linkSelector);
                            if (!linkEl) return;
                            let href = linkEl.href || linkEl.getAttribute('href') || '';
                            if (!href) return;
                            if (href.startsWith('/')) href = location.origin + href;
                            const key = href.split('?')[0];
                            if (seen.has(key)) return;
                            seen.add(key);
                            const title = (titleEl ? titleEl.textContent : node.textContent || '').replace(/\\s+/g, ' ').trim();
                            if (!title || title.length < 4) return;
                            let price = 0;
                            const scope = node.matches('a') ? (node.parentElement || node) : node;
                            scope.querySelectorAll(priceSelector).forEach(el => {
                                if (price > 0) return;
                                const txt = (el.textContent || '').trim();
                                const m = re.exec(txt);
                                if (m) price = parseFloat(m[1].replace(',', ''));
                            });
                            if (price > 0) out.push(price);
                        } catch (e) {}
                    });
                    return out;
                }""",
                {
                    "itemSelector": item_selector,
                    "titleSelector": title_selector,
                    "linkSelector": link_selector,
                    "priceSelector": price_selector,
                },
            )
            await browser.close()
            prices = [float(p) for p in raw if 1 < float(p) < max_price]
    except Exception as exc:
        log.debug("upgrade_parts.playwright_fetch.error", source=source_name, error=str(exc))
        return None

    return round(sorted(prices)[0], 2) if prices else None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_price(text: str) -> float:
    m = re.search(r"[\d,]+\.?\d*", str(text).replace(",", ""))
    return float(m.group(0)) if m else 0.0


async def _upsert_part(
    db,
    part_def: dict,
    ebay_used: float | None,
    ebay_sold: float | None,
    bh_refurb: float | None,
    scan_new: float | None = None,
    overclockers_new: float | None = None,
    box_new: float | None = None,
    amazon_new: float | None = None,
    temu_new: float | None = None,
    aliexpress_new: float | None = None,
):
    result = await db.execute(select(Part).where(Part.name == part_def["name"]))
    part = result.scalar_one_or_none()
    now = datetime.utcnow()

    new_prices = {
        "Scan": scan_new,
        "Overclockers": overclockers_new,
        "Box": box_new,
        "Amazon": amazon_new,
        "Temu": temu_new,
        "AliExpress": aliexpress_new,
    }
    valid_new = {k: v for k, v in new_prices.items() if v}
    cheapest_new_source = min(valid_new, key=lambda k: valid_new[k]) if valid_new else None
    cheapest_new = valid_new[cheapest_new_source] if cheapest_new_source else None

    candidates = [p for p in [ebay_used, bh_refurb, cheapest_new] if p]
    best_buy = min(candidates) if candidates else None

    source_parts = []
    if ebay_used or ebay_sold:
        source_parts.append("eBay UK")
    if bh_refurb:
        source_parts.append("BargainHardware")
    if cheapest_new_source:
        source_parts.append(cheapest_new_source)
    source_label = " / ".join(source_parts) if source_parts else "eBay UK"

    if part:
        if best_buy:
            part.price = best_buy
            part.price_used = ebay_used or part.price_used
            part.price_refurb = bh_refurb or part.price_refurb
            part.price_new = cheapest_new or part.price_new
        if source_parts:
            part.source_site = source_label
        part.last_price_update = now
    else:
        part = Part(
            name=part_def["name"],
            category=part_def["category"],
            condition=PartCondition.used,
            source_site=source_label,
            price=best_buy,
            price_used=ebay_used,
            price_refurb=bh_refurb,
            price_new=cheapest_new,
            resale_value_add=0.0,
            last_price_update=now,
        )
        db.add(part)
        await db.flush()

    if ebay_sold:
        db.add(PriceHistory(
            entity_type=PriceHistoryType.part, entity_id=part.id,
            price=ebay_sold, condition="used", source="ebay_sold",
        ))
    if bh_refurb:
        db.add(PriceHistory(
            entity_type=PriceHistoryType.part, entity_id=part.id,
            price=bh_refurb, condition="refurb", source="bargainhardware",
        ))
    if cheapest_new and cheapest_new_source:
        db.add(PriceHistory(
            entity_type=PriceHistoryType.part, entity_id=part.id,
            price=cheapest_new, condition="new", source=cheapest_new_source.lower(),
        ))
