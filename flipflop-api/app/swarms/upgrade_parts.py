from app.services.browser_pool import managed_playwright
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
    Sold HTML requests are single-attempt; repeated 403s are circuit-broken by
    the caller rather than retried, to avoid amplifying eBay blocks.
  - BargainHardware uses a shared Playwright browser context (one launch per swarm).
  - Scan / Overclockers / Box run concurrently at the end (they're new-retail and
    less aggressive about bot detection).
"""
import re
import asyncio
import os
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
from app.services.proxy import apply_httpx_proxy, playwright_proxy_config
from app.services.playwright_scraper import (
    chromium_available,
    scrape_facebook_playwright,
    scrape_gumtree_playwright,
)
from app.services.antibot_preflight import should_defer_source_scrape
from app.services.delivery_filters import allow_temu_aliexpress_listing
from app.models.source_search_term import SourceSearchTerm
from app.services.component_models import CANONICAL_MODELS
from app.services.ebay_browse import search_active_listings
from sqlalchemy import select as sa_select
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


_CATEGORY_TO_PART_CATEGORY = {
    "gpu":         PartCategory.gpu,
    "cpu":         PartCategory.cpu,
    "ram":         PartCategory.ram,
    "ssd":         PartCategory.ssd,
    "psu":         PartCategory.psu,
    "motherboard": PartCategory.motherboard,
    "cooler":      PartCategory.cooler,
}

TRACKED_PARTS = [
    {
        "name":        m["name"],
        "category":    _CATEGORY_TO_PART_CATEGORY.get(cat, PartCategory.accessory),
        "ebay_search": m["name"],
        "bh_search":   m["bh_search"],
    }
    for cat, models in CANONICAL_MODELS.items()
    for m in models
]

_VENDOR_ALIASES: dict[str, str] = {
    "ebay": "eBay",
    "ebay uk": "eBay",
    "ebay uk auctions": "eBay",
    "gumtree uk": "Gumtree",
    "gumtree": "Gumtree",
    "amazon": "Amazon",
    "amazon uk": "Amazon",
    "alibaba uk": "Alibaba",
    "bargain hardware": "BargainHardware",
}


def _canonical_vendor(name: str) -> str:
    raw = str(name or "").strip()
    key = raw.lower()
    return _VENDOR_ALIASES.get(key, raw)


async def run_upgrade_parts_swarm(mode: str = "main") -> dict:
    log.info("upgrade_parts_swarm.start", total_parts=len(TRACKED_PARTS))
    stats = {
        "updated": 0, "errors": 0,
        "ebay_sold": 0, "ebay_buy": 0, "bh": 0,
        "scan": 0, "overclockers": 0, "box": 0,
        "amazon": 0, "temu": 0, "aliexpress": 0, "alibaba": 0,
    }

    async with AsyncSessionLocal() as db:
        db_rows = (
            await db.execute(
                sa_select(SourceSearchTerm).where(
                    SourceSearchTerm.scope == "upgrade_parts",
                    SourceSearchTerm.enabled == True,
                )
            )
        ).scalars().all()

    if db_rows:
        # Use DB terms directly as search queries — matches flip_opportunities pattern.
        # Each term is looked up in TRACKED_PARTS by ebay_search (case-insensitive)
        # to preserve category metadata; unrecognised terms become synthetic entries.
        tracked_by_search = {str(p["ebay_search"]).lower(): p for p in TRACKED_PARTS}
        seen: set[str] = set()
        parts = []
        for row in db_rows:
            term = str(row.term or "").strip()
            if not term or term.lower() in seen:
                continue
            seen.add(term.lower())
            matched = tracked_by_search.get(term.lower())
            if matched:
                parts.append(matched)
            else:
                parts.append({
                    "name": term,
                    "category": PartCategory.accessory,
                    "ebay_search": term,
                    "bh_search": term.replace(" ", "+"),
                })
        if not parts:
            parts = list(TRACKED_PARTS)
    else:
        parts = list(TRACKED_PARTS)

    # ── Phase 1: eBay — sequential within vendor ─────────────────────────────
    ebay_sold_map:  dict[str, float | None] = {}
    ebay_buy_map:   dict[str, float | None] = {}

    async with httpx.AsyncClient(**apply_httpx_proxy({"follow_redirects": True, "timeout": 25})) as client:
        for part_def in parts:
            name = part_def["name"]
            search = part_def["ebay_search"]
            sold, sold_count = await _ebay_sold_median(client, search)
            await asyncio.sleep(random.uniform(0.2, 0.6))
            buy, buy_count = await _ebay_buy_price(client, search)
            await asyncio.sleep(random.uniform(0.2, 0.6))
            ebay_sold_map[name] = sold
            if sold:
                stats["ebay_sold"] += 1
            ebay_buy_map[name] = buy
            if buy:
                stats["ebay_buy"] += 1

            log.debug("upgrade_parts.ebay", part=name, sold=sold, buy=buy)
            record_term_result(
                source_name="UpgradeParts:eBay UK",
                term=search,
                found=sold_count + buy_count,
                new=0,
            )

    has_chromium = chromium_available()

    # ── Phase 2: BargainHardware.co.uk via Playwright ────────────────────────
    bh_map: dict[str, float | None] = {}
    if has_chromium:
        try:
            async with managed_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=_STEALTH_ARGS,
                    proxy=playwright_proxy_config(),
                )
                ctx = await browser.new_context(user_agent=_STEALTH_UA, locale="en-GB", timezone_id="Europe/London")
                await ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
                page = await ctx.new_page()
                for part_def in parts:
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
                        found=1 if price is not None else 0,
                        new=0,
                    )
                await browser.close()
        except ImportError:
            log.warning("upgrade_parts.playwright_missing")
            bh_map = {p["name"]: None for p in parts}
        except Exception as exc:
            log.error("upgrade_parts.bh.error", error=str(exc))
            bh_map = {p["name"]: bh_map.get(p["name"]) for p in parts}
    else:
        bh_map = {p["name"]: None for p in parts}
        for part_def in parts:
            record_term_result(
                source_name="UpgradeParts:BargainHardware",
                term=part_def["bh_search"],
                found=0,
                new=0,
                error="playwright.chromium_not_installed",
            )

    lane_concurrency = max(1, int(os.getenv("COMPONENTS_TERM_CONCURRENCY", "8")))

    async def _fetch_lane_concurrent(fn, max_concurrency: int):
        sem = asyncio.Semaphore(max(1, max_concurrency))

        async def _one(p):
            async with sem:
                try:
                    return await fn(p["ebay_search"])
                except Exception as exc:
                    return exc

        return await asyncio.gather(*[_one(p) for p in parts], return_exceptions=False)

    # ── Phase 3: each vendor sequential, vendors in parallel ──────────────────
    scan_r, oc_r, box_r = await asyncio.gather(
        _fetch_lane_concurrent(_fetch_scan, lane_concurrency),
        _fetch_lane_concurrent(_fetch_overclockers, lane_concurrency),
        _fetch_lane_concurrent(_fetch_box, lane_concurrency),
    )
    for v in scan_r:
        if v and not isinstance(v, Exception):
            stats["scan"] += 1
    for v in oc_r:
        if v and not isinstance(v, Exception):
            stats["overclockers"] += 1
    for v in box_r:
        if v and not isinstance(v, Exception):
            stats["box"] += 1

    # ── Phase 3b: Amazon / Temu / AliExpress / Vinted — sequential per vendor, parallel across vendors ───
    # Vinted uses HTTP (no Playwright) so always runs regardless of has_chromium.
    vint_r, = await asyncio.gather(
        _fetch_lane_concurrent(_fetch_vinted_component, lane_concurrency),
    )
    if has_chromium:
        amz_r, temu_r, ali_r, ali_b_r, gum_r = await asyncio.gather(
            _fetch_lane_concurrent(_fetch_amazon, lane_concurrency),
            _fetch_lane_concurrent(_fetch_temu, lane_concurrency),
            _fetch_lane_concurrent(_fetch_aliexpress, lane_concurrency),
            _fetch_lane_concurrent(_fetch_alibaba, lane_concurrency),
            _fetch_lane_concurrent(_fetch_gumtree_component, lane_concurrency),
        )
    else:
        amz_r = [None for _ in parts]
        temu_r = [None for _ in parts]
        ali_r = [None for _ in parts]
        ali_b_r = [None for _ in parts]
        gum_r = [None for _ in parts]
    for v in amz_r:
        if not isinstance(v, Exception):
            price, _ = _val_count(v)
            if price:
                stats["amazon"] += 1
    for v in temu_r:
        if not isinstance(v, Exception):
            price, _ = _val_count(v)
            if price:
                stats["temu"] += 1
    for v in ali_r:
        if not isinstance(v, Exception):
            price, _ = _val_count(v)
            if price:
                stats["aliexpress"] += 1
    for v in ali_b_r:
        if not isinstance(v, Exception):
            price, _ = _val_count(v)
            if price:
                stats["alibaba"] += 1

    # ── Phase 4: Persist ──────────────────────────────────────────────────────
    async with AsyncSessionLocal() as db:
        for i, part_def in enumerate(parts):
            name = part_def["name"]
            try:
                ebay_used = ebay_buy_map.get(name)
                ebay_sold = ebay_sold_map.get(name)
                bh_refurb = bh_map.get(name)
                scan_new  = scan_r[i] if not isinstance(scan_r[i], Exception) else None
                oc_new    = oc_r[i]   if not isinstance(oc_r[i], Exception)   else None
                box_new   = box_r[i]  if not isinstance(box_r[i], Exception)  else None

                amz_v   = amz_r[i]  if not isinstance(amz_r[i], Exception)  else None
                temu_v  = temu_r[i] if not isinstance(temu_r[i], Exception) else None
                ali_v   = ali_r[i]  if not isinstance(ali_r[i], Exception)  else None
                ali_b_v = ali_b_r[i] if not isinstance(ali_b_r[i], Exception) else None
                gum_v   = gum_r[i] if not isinstance(gum_r[i], Exception) else None
                vint_v  = vint_r[i] if not isinstance(vint_r[i], Exception) else None

                amz_new, amz_count = _val_count(amz_v)
                temu_new, temu_count = _val_count(temu_v)
                ali_new, ali_count = _val_count(ali_v)
                ali_b_new, ali_b_count = _val_count(ali_b_v)
                gum_new, gum_count = _val_count(gum_v)
                vint_new, vint_count = _val_count(vint_v)

                search = part_def["ebay_search"]
                record_term_result(source_name="UpgradeParts:Amazon", term=search, found=amz_count, new=0)
                record_term_result(source_name="UpgradeParts:Temu", term=search, found=temu_count, new=0)
                record_term_result(source_name="UpgradeParts:AliExpress", term=search, found=ali_count, new=0)
                record_term_result(source_name="UpgradeParts:Alibaba", term=search, found=ali_b_count, new=0)
                record_term_result(source_name="UpgradeParts:Gumtree", term=search, found=gum_count, new=0)
                record_term_result(source_name="UpgradeParts:Vinted", term=search, found=vint_count, new=0)

                if any([ebay_used, ebay_sold, bh_refurb, scan_new, oc_new, box_new, amz_new, temu_new, ali_new, ali_b_new, gum_new]):
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

async def _ebay_sold_median(client: httpx.AsyncClient, search: str) -> tuple[float | None, int]:
    """Median sold price from eBay completed listings — 3-attempt retry.
    Returns (median_price, listing_count)."""
    params = {
        "_nkw": search, "_sacat": "0",
        "LH_Sold": "1", "LH_Complete": "1",
        "_sop": "12", "_ipg": "60",
    }
    for attempt in range(1):
        try:
            r = await client.get("https://www.ebay.co.uk/sch/i.html", params=params, headers=_EBAY_HEADERS)
            if r.status_code == 200:
                prices = _parse_ebay_prices(r.text)
                if prices:
                    prices.sort()
                    return round(prices[len(prices) // 2], 2), len(prices)
                # got a page but no prices — might be "Access Denied" soft block
                if "access denied" in r.text.lower() or "interruption" in r.text.lower():
                    await asyncio.sleep(2.5 * (attempt + 1))
                    continue
                return None, 0
            if r.status_code == 403:
                await asyncio.sleep(2.5 * (attempt + 1))
                continue
        except Exception as exc:
            log.debug("ebay_sold.request_retry", search=search, attempt=attempt + 1, error=str(exc))
            await asyncio.sleep(1.5)
    return None, 0


async def _ebay_buy_price(client: httpx.AsyncClient, search: str) -> tuple[float | None, int]:
    """25th-percentile Buy-It-Now used price via the official Browse API."""
    try:
        listings = await search_active_listings(
            search,
            condition_filter="USED|EXCELLENT|VERY_GOOD|GOOD|ACCEPTABLE",
            limit=50,
            min_price=10.0,
        )
        prices = sorted(float(item["price"]) for item in listings)
        if prices:
            return round(prices[max(0, len(prices) // 4)], 2), len(prices)
    except Exception as exc:
        log.warning("ebay_buy.api_error", search=search, error=str(exc))
    return None, 0


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
        except ValueError as exc:
            log.debug("ebay_price.parse_skip", value=str(m), error=str(exc))
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
            except (ValueError, TypeError) as exc:
                log.debug("bh.price.parse_skip", value=str(el.get("data-price-amount", 0)), error=str(exc))
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
        async with httpx.AsyncClient(**apply_httpx_proxy({"timeout": 20, "follow_redirects": True})) as client:
            resp = await client.get(url, headers=headers)
        if resp.status_code != 200 or len(resp.text) < 500:
            return None
        soup = BeautifulSoup(resp.text, "lxml")
        prices = [_parse_price(el.get_text(strip=True)) for el in soup.select(".c-product__price, [class*='price']")]
        prices = [p for p in prices if 1 < p < 2000]
        return round(sorted(prices)[0], 2) if prices else None
    except Exception as exc:
        log.warning("scan.fetch.error", search=search_term, error=str(exc))
        return None


async def _fetch_overclockers(search_term: str) -> float | None:
    url = f"https://www.overclockers.co.uk/search?q={search_term.replace(' ', '+')}"
    headers = {"User-Agent": ua.random, "Accept-Language": "en-GB", "Accept": "text/html"}
    try:
        async with httpx.AsyncClient(**apply_httpx_proxy({"timeout": 20, "follow_redirects": True})) as client:
            resp = await client.get(url, headers=headers)
        if resp.status_code != 200 or len(resp.text) < 500:
            return None
        soup = BeautifulSoup(resp.text, "lxml")
        prices = [_parse_price(el.get_text(strip=True)) for el in soup.select(".product-price, .price, [class*='price']")]
        prices = [p for p in prices if 1 < p < 2000]
        return round(sorted(prices)[0], 2) if prices else None
    except Exception as exc:
        log.warning("overclockers.fetch.error", search=search_term, error=str(exc))
        return None


async def _fetch_box(search_term: str) -> float | None:
    url = f"https://www.box.co.uk/search?search={search_term.replace(' ', '+')}"
    headers = {"User-Agent": ua.random, "Accept-Language": "en-GB", "Accept": "text/html"}
    try:
        async with httpx.AsyncClient(**apply_httpx_proxy({"timeout": 20, "follow_redirects": True})) as client:
            resp = await client.get(url, headers=headers)
        if resp.status_code != 200 or len(resp.text) < 500:
            return None
        soup = BeautifulSoup(resp.text, "lxml")
        prices = [_parse_price(el.get_text(strip=True)) for el in soup.select(".price, .product-price, [class*='price']")]
        prices = [p for p in prices if 1 < p < 2000]
        return round(sorted(prices)[0], 2) if prices else None
    except Exception as exc:
        log.warning("box.fetch.error", search=search_term, error=str(exc))
        return None


# ── Amazon / Temu / AliExpress (Playwright) ──────────────────────────────────

async def _fetch_amazon(search_term: str) -> tuple[float | None, int]:
    return await _fetch_playwright_lowest_price(
        url=f"https://www.amazon.co.uk/s?k={search_term.replace(' ', '+')}&i=computers",
        item_selector='[data-component-type="s-search-result"]',
        title_selector='h2 span, h2',
        link_selector='h2 a, a.a-link-normal[href*="/dp/"]',
        price_selector='.a-price',  # .a-price-whole has no £ symbol; .a-price includes the offscreen £ text
        source_name="amazon",
        max_price=2500.0,
    )


async def _fetch_temu(search_term: str) -> tuple[float | None, int]:
    return await _fetch_playwright_lowest_price(
        url=f"https://www.temu.com/search_result.html?search_key={search_term.replace(' ', '+')}&search_method=user",
        item_selector='a[href*="/goods"]',
        title_selector='h3, h4, p, span',
        link_selector='a[href*="/goods"]',
        price_selector='*',
        source_name="temu",
        max_price=2500.0,
    )


async def _fetch_aliexpress(search_term: str) -> tuple[float | None, int]:
    return await _fetch_playwright_lowest_price(
        url=f"https://www.aliexpress.com/wholesale?SearchText={search_term.replace(' ', '+')}&g=y&SortType=price_asc",
        item_selector='a[href*="/item/"]',
        title_selector='h1, h2, h3, h4, p, span',
        link_selector='a[href*="/item/"]',
        price_selector='*',
        source_name="aliexpress",
        max_price=2500.0,
    )


async def _fetch_alibaba(search_term: str) -> tuple[float | None, int]:
    return await _fetch_playwright_lowest_price(
        url=f"https://www.alibaba.com/trade/search?SearchText={search_term.replace(' ', '+')}",
        item_selector='a[href*="/product-detail/"], a[href*="/x/"]',
        title_selector='h1, h2, h3, h4, p, span',
        link_selector='a[href*="/product-detail/"], a[href*="/x/"]',
        price_selector='*',
        source_name="alibaba",
        max_price=2500.0,
    )


async def _fetch_gumtree_component(search_term: str) -> tuple[float | None, int]:
    try:
        rows = await scrape_gumtree_playwright([search_term], 1, 2500)
        prices = [float(getattr(r, "price", 0) or 0) for r in rows if float(getattr(r, "price", 0) or 0) > 0]
        return (round(min(prices), 2), len(prices)) if prices else (None, 0)
    except Exception as exc:
        log.warning("upgrade_parts.gumtree_fetch.error", search=search_term, error=str(exc))
        return None, 0


async def _fetch_facebook_component(search_term: str) -> tuple[float | None, int]:
    try:
        rows = await scrape_facebook_playwright([search_term], 1, 2500)
        prices = [float(getattr(r, "price", 0) or 0) for r in rows if float(getattr(r, "price", 0) or 0) > 0]
        return (round(min(prices), 2), len(prices)) if prices else (None, 0)
    except Exception as exc:
        log.warning("upgrade_parts.facebook_fetch.error", search=search_term, error=str(exc))
        return None, 0


async def _fetch_vinted_component(search_term: str) -> tuple[float | None, int]:
    try:
        from app.scrapers.vinted_scraper import fetch_vinted_listings
        rows = await fetch_vinted_listings(search_terms=[search_term], min_price=1, max_price=2500)
        prices = [float(r["price"]) for r in rows if float(r.get("price", 0)) > 0]
        return (round(sorted(prices)[0], 2), len(prices)) if prices else (None, 0)
    except Exception as exc:
        log.debug("upgrade_parts.vinted_fetch.error", search=search_term, error=str(exc))
        return None, 0


async def _fetch_playwright_lowest_price(
    *,
    url: str,
    item_selector: str,
    title_selector: str,
    link_selector: str,
    price_selector: str,
    source_name: str,
    max_price: float,
) -> tuple[float | None, int]:
    source_label = {
        "temu": "Temu",
        "aliexpress": "AliExpress",
        "alibaba": "Alibaba",
        "amazon": "Amazon",
    }.get(str(source_name or "").lower(), source_name)
    defer, reason = should_defer_source_scrape(str(source_label))
    if defer:
        log.info("upgrade_parts.playwright.deferred", source=source_label, reason=reason)
        return None, 0

    prices: list[float] = []
    filtered_delivery = 0
    try:
        async with managed_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=_STEALTH_ARGS,
                proxy=playwright_proxy_config(),
            )
            ctx = await browser.new_context(user_agent=_STEALTH_UA, locale="en-GB", timezone_id="Europe/London")
            await ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
            page = await ctx.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            title_l = (await page.title() or "").lower()
            body_l = (await page.content() or "").lower()[:120000]
            if source_name == "temu" and (
                "login" in title_l
                or "/login" in (page.url or "").lower()
                or "kwcdn.com/upload-static/assets/chl/js" in body_l
                or "challenge" in body_l
            ):
                await browser.close()
                return None, 0
            if source_name in {"aliexpress", "alibaba"} and (
                "captcha interception" in title_l
                or "captcha" in body_l
                or "_____tmd_____" in body_l
                or "/punish" in body_l
                or "awsc/captcha" in body_l
            ):
                await browser.close()
                return None, 0
            try:
                await page.wait_for_selector(item_selector, timeout=10000)
            except Exception as exc:
                log.debug("playwright.wait_selector_timeout", source=source_name, selector=item_selector, error=str(exc))
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
                            const contextText = (scope.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 1200);
                            if (price > 0) out.push({price, contextText});
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
            for row in raw:
                try:
                    p = float((row or {}).get("price") or 0)
                except Exception:
                    continue
                if not (1 < p < max_price):
                    continue
                if source_name in {"temu", "aliexpress"}:
                    if not allow_temu_aliexpress_listing((row or {}).get("contextText") or ""):
                        filtered_delivery += 1
                        continue
                prices.append(p)
    except Exception as exc:
        log.debug("upgrade_parts.playwright_fetch.error", source=source_name, error=str(exc))
        return None, 0
    if filtered_delivery > 0 and source_name in {"temu", "aliexpress"}:
        log.info("upgrade_parts.delivery_filtered", source=source_name, search=url, filtered=filtered_delivery)

    return (round(sorted(prices)[0], 2), len(prices)) if prices else (None, 0)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_price(text: str) -> float:
    m = re.search(r"[\d,]+\.?\d*", str(text).replace(",", ""))
    return float(m.group(0)) if m else 0.0


def _val_count(v) -> tuple[float | None, int]:
    """
    Normalize lane return value to (price, count).
    Supports both legacy float and new tuple payload.
    """
    if isinstance(v, tuple):
        price = v[0] if len(v) > 0 else None
        count = int(v[1]) if len(v) > 1 and v[1] is not None else (1 if price else 0)
        return price, max(0, count)
    return v, (1 if v else 0)


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
