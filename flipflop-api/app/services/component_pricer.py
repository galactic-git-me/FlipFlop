"""
Component-level eBay resale pricer.

Instead of searching for a whole "gaming PC Ryzen 9 3900X" (which may have
few or no sold comps), we price each component individually:
  • CPU model sold price
  • GPU sold price (actual or budget RX 580 if we're adding one)
  • RAM kit sold price
  • Storage sold price

Then we add an estimated chassis value (motherboard + cooler + PSU bundled
in the original listing), apply a gaming-PC assembled premium, and add the
themed-case revenue bump.

This gives much more accurate resale estimates for unusual CPU/GPU combos
because individual components have thousands of eBay sold listings.

Fallback chain in resale_scraper.py:
  1. Live whole-system eBay comps (best)
  2. Component-based pricing (this module — good)
  3. Buy-price formula (reasonable, anchored to market)
  4. Static CPU-table estimate (last resort)
"""

import re
import asyncio
import httpx
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
import structlog

log = structlog.get_logger(__name__)
ua  = UserAgent()

# ── Constants ────────────────────────────────────────────────────────────────

# Typical value of the "chassis bundle" included in any working PC:
# motherboard + CPU cooler + (basic case, not our themed one).
# We don't scrape these individually since our spec parser doesn't capture them,
# but they always have value.  Conservative midpoint across platforms.
CHASSIS_VALUE = 65.0

# A tested, assembled, working gaming PC commands a premium over the bare sum
# of its parts — the buyer pays for convenience, no sourcing risk, and knowing
# it boots.  Themed / custom-look builds command a bit more.
ASSEMBLED_PREMIUM = 1.15

# Themed case revenue uplift — we always add one.  Higher than the live-comp
# path (£65) because component-based builds have no "themed" comps to compare
# against, so we use the full case premium the user suggested.
CASE_PREMIUM = 100.0

# Per-run cache: component query → median price (or None if not found)
_cache: dict[str, float | None] = {}


def clear_component_cache() -> None:
    _cache.clear()


# ── Query builders ───────────────────────────────────────────────────────────

def _cpu_query(cpu: str) -> str:
    """Extract the bare model string suitable for an eBay component search."""
    cpu_l = cpu.lower()
    m = re.search(
        r"(i[3579]-\d{4,5}[a-z]*"
        r"|ryzen\s+[3579]\s+\d{4}[a-z]*"
        r"|xeon\s+\w[\w-]+"
        r"|threadripper\s+\d{4}[a-z]*)",
        cpu_l,
    )
    if m:
        return m.group(0).strip()
    # Fallback: strip brand words, keep the rest
    short = re.sub(r"intel\s+core\s*|amd\s+", "", cpu_l).strip()[:30]
    return short or cpu[:30]


def _gpu_query(gpu: str) -> str:
    gpu_l = gpu.lower()
    m = re.search(
        r"((?:geforce\s+)?(?:gtx|rtx|rx)\s*\d{3,4}(?:\s*(?:ti|xt|super))?(?:\s*\d+\s*gb)?)",
        gpu_l,
    )
    return m.group(0).strip() if m else gpu[:30]


def _ram_query(ram_gb: int, ram_type: str | None) -> str:
    rt = (ram_type or "ddr4").lower().replace(" ", "")
    if "ddr5" in rt:
        return f"{ram_gb}gb ddr5 desktop ram"
    return f"{ram_gb}gb ddr4 desktop ram"


def _storage_query(storage_gb: int, storage_type: str | None) -> str:
    t = (storage_type or "ssd").lower()
    if "nvme" in t or "m.2" in t:
        return f"{storage_gb}gb nvme m.2 ssd"
    if "ssd" in t:
        return f"{storage_gb}gb sata ssd 2.5"
    gb = storage_gb
    if gb >= 1000:
        return f"{gb // 1000}tb 3.5 hard drive"
    return f"{gb}gb 3.5 hard drive sata"


# ── eBay fetcher ─────────────────────────────────────────────────────────────

async def _fetch_median(
    query: str,
    min_price: float,
    max_price: float,
) -> float | None:
    """
    Search eBay UK completed/sold listings for a single component.
    Returns the median sold price, or None if fewer than 2 comps found.
    Results are cached for the duration of the swarm run.
    """
    cache_key = f"{query}|{int(min_price)}-{int(max_price)}"
    if cache_key in _cache:
        return _cache[cache_key]

    params = {
        "_nkw":      query,
        "LH_Sold":   "1",
        "LH_Complete": "1",
        "_sop":      "12",      # most recent first
        "LH_PrefLoc": "1",     # UK preferred
        "_udlo":     str(int(min_price)),
        "_udhi":     str(int(max_price)),
        "_ipg":      "48",
    }
    headers = {
        "User-Agent":     ua.random,
        "Accept-Language": "en-GB,en;q=0.9",
        "Accept":         "text/html,application/xhtml+xml",
    }

    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get(
                "https://www.ebay.co.uk/sch/i.html",
                params=params,
                headers=headers,
            )
        if resp.status_code != 200 or len(resp.text) < 1000:
            _cache[cache_key] = None
            return None

        soup = BeautifulSoup(resp.text, "lxml")
        prices: list[float] = []

        for item in soup.select(".s-item:not(.s-item--placeholder)"):
            # Skip auction items
            bid_el = item.select_one(".s-item__bids, [class*='bid']")
            if bid_el and re.search(r"\d+\s*bid", bid_el.get_text(), re.I):
                continue

            price_el = (
                item.select_one(".s-item__price .POSITIVE")
                or item.select_one(".s-item__price")
            )
            if not price_el:
                continue
            text = price_el.get_text(strip=True)
            # Skip ranges ("£50 to £80")
            if re.search(r"\bto\b|–|—", text, re.I):
                continue
            m = re.search(r"[\d,]+\.?\d*", text.replace(",", ""))
            if not m:
                continue
            p = float(m.group(0))
            if min_price <= p <= max_price:
                prices.append(p)

        if len(prices) >= 2:
            prices.sort()
            median = prices[len(prices) // 2]
            log.debug("component.price", query=query, median=median, n=len(prices))
            _cache[cache_key] = median
            return median

        _cache[cache_key] = None
        return None

    except Exception as exc:
        log.warning("component.fetch_error", query=query, error=str(exc))
        _cache[cache_key] = None
        return None


# ── Public API ────────────────────────────────────────────────────────────────

async def estimate_component_resale(
    cpu:          str | None,
    ram_gb:       int | None,
    ram_type:     str | None,
    storage_gb:   int | None,
    storage_type: str | None,
    gpu:          str | None,
    add_budget_gpu: bool = False,   # True when listing has no GPU — we'll add one
    add_budget_ssd: bool = False,   # True when listing has no storage — we'll add one
) -> float | None:
    """
    Estimate the resale value of the completed, themed build by pricing each
    component individually on eBay UK sold listings.

    Returns None if we can't obtain a CPU price (minimum viable data).

    The formula:
        parts_sum  = CPU + GPU + RAM + storage + chassis_bundle
        assembled  = parts_sum × ASSEMBLED_PREMIUM   (1.15 — tested, working build)
        resale     = assembled + CASE_PREMIUM         (£100 — themed case uplift)
    """
    # Build a list of (label, coroutine) pairs so we can gather concurrently
    fetches: list[tuple[str, object]] = []

    if cpu:
        q = _cpu_query(cpu)
        fetches.append(("cpu", _fetch_median(q, 15.0, 800.0)))
        log.debug("component.query.cpu", q=q)

    if gpu:
        q = _gpu_query(gpu)
        fetches.append(("gpu", _fetch_median(q, 25.0, 1500.0)))
        log.debug("component.query.gpu", q=q)
    elif add_budget_gpu:
        # RTX 3060 12GB — primary flip GPU target, ~£170-200 used UK
        fetches.append(("gpu", _fetch_median("rtx 3060 12gb", 140.0, 230.0)))

    if ram_gb and ram_gb >= 4:
        q = _ram_query(ram_gb, ram_type)
        fetches.append(("ram", _fetch_median(q, 5.0, 250.0)))
        log.debug("component.query.ram", q=q)

    if storage_gb:
        q = _storage_query(storage_gb, storage_type)
        fetches.append(("storage", _fetch_median(q, 5.0, 250.0)))
        log.debug("component.query.storage", q=q)
    elif add_budget_ssd:
        # 1TB NVMe — standard spec for a 2026 gaming flip
        fetches.append(("storage", _fetch_median("1tb nvme m.2 ssd", 40.0, 120.0)))

    if not fetches:
        return None

    labels  = [f[0] for f in fetches]
    results = await asyncio.gather(*[f[1] for f in fetches], return_exceptions=True)

    component_prices: dict[str, float] = {}
    for label, result in zip(labels, results):
        if isinstance(result, float):
            component_prices[label] = result

    # CPU is non-negotiable — we can't value a PC without its heart
    if "cpu" not in component_prices:
        log.info("component.no_cpu_price", cpu=cpu)
        return None

    parts_sum = sum(component_prices.values()) + CHASSIS_VALUE
    assembled = parts_sum * ASSEMBLED_PREMIUM
    resale    = assembled + CASE_PREMIUM

    log.info(
        "component.estimate",
        components=component_prices,
        chassis=CHASSIS_VALUE,
        parts_sum=parts_sum,
        assembled=assembled,
        resale=resale,
    )
    return round(resale, 2)
