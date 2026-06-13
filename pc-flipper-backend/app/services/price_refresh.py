"""
Daily component price refresh.

Fetches live eBay UK *sold* prices for the standard budget-upgrade parts
that every flip uses, then writes them to data/price_benchmarks.json.

estimator.py reads that file at runtime so profit calculations always use
today's actual market prices rather than hardcoded constants.

Fallback: if fetching fails, the last successful file is kept intact and
estimator.py falls back to its hardcoded defaults only if the file is missing
or older than 48 hours.
"""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import httpx
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
import structlog

log = structlog.get_logger(__name__)

_BENCHMARKS_FILE = Path(__file__).resolve().parents[2] / "data" / "price_benchmarks.json"
_ua = UserAgent()

# ── Queries for each budget component ────────────────────────────────────────
# (label, query, price_floor, price_ceiling)
_COMPONENT_QUERIES: list[tuple[str, str, float, float]] = [
    ("ram_32gb_ddr4_cost",   "32gb ddr4 desktop ram kit",             30.0,  350.0),
    ("ram_32gb_ddr5_cost",   "32gb ddr5 desktop ram kit",             50.0,  500.0),
    ("gpu_rtx3060_cost",     "rtx 3060 12gb graphics card",          120.0,  380.0),
    ("gpu_rtx4060_cost",     "rtx 4060 8gb graphics card",           150.0,  450.0),
    ("gpu_rx6700_cost",      "rx 6700 xt graphics card",             120.0,  360.0),
    ("ssd_1tb_nvme_cost",    "1tb nvme m.2 ssd 2280",                 25.0,  130.0),
    ("psu_650w_cost",        "650w 80 plus bronze psu modular",       25.0,  120.0),
]


async def _fetch_median_sold(
    client: httpx.AsyncClient,
    query: str,
    floor: float,
    ceil: float,
) -> float | None:
    """Scrape eBay UK completed/sold listings and return the median price."""
    params = {
        "_nkw":       query,
        "LH_Sold":    "1",
        "LH_Complete": "1",
        "_sop":       "12",
        "LH_PrefLoc": "1",
        "_ipg":       "60",
    }
    headers = {
        "User-Agent":      _ua.random,
        "Accept-Language": "en-GB,en;q=0.9",
        "Accept":          "text/html,application/xhtml+xml",
    }
    try:
        resp = await client.get(
            "https://www.ebay.co.uk/sch/i.html",
            params=params,
            headers=headers,
            timeout=20,
        )
        if resp.status_code != 200 or len(resp.text) < 1000:
            return None

        soup = BeautifulSoup(resp.text, "lxml")
        prices: list[float] = []

        for item in soup.select(".s-item:not(.s-item--placeholder)"):
            bid_el = item.select_one(".s-item__bids, .x-bid-count, [class*='bid--']")
            if bid_el and __import__("re").search(r"\d+\s*bid", bid_el.get_text(), 2):
                continue
            price_el = (
                item.select_one(".s-item__price .POSITIVE")
                or item.select_one(".s-item__price")
            )
            if not price_el:
                continue
            text = price_el.get_text(strip=True)
            import re
            if re.search(r"\bto\b|–|—", text, re.I):
                continue
            m = re.search(r"[\d,]+\.?\d*", text.replace(",", ""))
            if not m:
                continue
            p = float(m.group(0))
            if floor <= p <= ceil:
                prices.append(p)

        if len(prices) < 3:
            return None

        prices.sort()
        return round(prices[len(prices) // 2], 2)

    except Exception as exc:
        log.warning("price_refresh.fetch_failed", query=query, error=str(exc))
        return None


async def run_price_refresh() -> dict:
    """
    Fetch live eBay UK sold prices for all budget components and write
    data/price_benchmarks.json.

    Called daily by the scheduler. Returns a summary dict.
    """
    log.info("price_refresh.start")
    updated: dict[str, float] = {}
    failed: list[str] = []

    # Load current file so we preserve any labels we can't fetch this run
    existing: dict = {}
    if _BENCHMARKS_FILE.exists():
        try:
            existing = json.loads(_BENCHMARKS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass

    async with httpx.AsyncClient(follow_redirects=True) as client:
        for label, query, floor, ceil in _COMPONENT_QUERIES:
            price = await _fetch_median_sold(client, query, floor, ceil)
            if price is not None:
                updated[label] = price
                log.info("price_refresh.fetched", label=label, price=price, query=query)
            else:
                failed.append(label)
                log.warning("price_refresh.fetch_skipped", label=label, query=query)
            await asyncio.sleep(1.5)  # polite pacing between eBay requests

    if updated:
        merged = {**existing, **updated}
        merged["refreshed_at"] = time.time()
        merged["refreshed_at_iso"] = __import__("datetime").datetime.utcnow().isoformat() + "Z"

        _BENCHMARKS_FILE.parent.mkdir(parents=True, exist_ok=True)
        _BENCHMARKS_FILE.write_text(
            json.dumps(merged, indent=2, ensure_ascii=True),
            encoding="utf-8",
        )
        log.info("price_refresh.saved", labels=list(updated.keys()), file=str(_BENCHMARKS_FILE))

    return {
        "ok": True,
        "updated": updated,
        "failed": failed,
        "file": str(_BENCHMARKS_FILE),
    }


def load_benchmarks() -> dict[str, float]:
    """
    Load the last written price benchmarks.
    Returns {} (empty) if the file is missing or older than 48 hours —
    estimator.py falls back to its hardcoded defaults in that case.
    """
    try:
        if not _BENCHMARKS_FILE.exists():
            return {}
        data = json.loads(_BENCHMARKS_FILE.read_text(encoding="utf-8"))
        refreshed_at = data.get("refreshed_at", 0)
        if time.time() - refreshed_at > 48 * 3600:
            log.warning("price_refresh.benchmarks_stale", age_hours=round((time.time() - refreshed_at) / 3600, 1))
            return {}
        return {k: v for k, v in data.items() if isinstance(v, (int, float))}
    except Exception as exc:
        log.warning("price_refresh.load_failed", error=str(exc))
        return {}
