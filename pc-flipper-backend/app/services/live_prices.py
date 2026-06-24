"""
Live price fetcher for the catalogue tab.

Uses the eBay Browse API (not HTML scraping) for accurate, rate-limit-friendly
pricing. Results are cached in-process for CACHE_TTL seconds per category.

For each canonical model:
  - "New price"  = cheapest BIN listing in NEW / LIKE_NEW condition (from eBay API)
  - "Used price" = median of all BIN USED listings (from eBay API)
  - "Best deal"  = cheapest used listing with direct URL
  - Gem scoring  = discount % of best deal vs used median
"""
from __future__ import annotations

import asyncio
import time

import structlog

from app.services.component_models import CANONICAL_MODELS
from app.services.ebay_browse import get_component_prices

log = structlog.get_logger(__name__)

CACHE_TTL = 1800  # 30 minutes
_LIVE_CACHE: dict[str, tuple[float, list]] = {}  # category -> (timestamp, rows)

GEM_THRESHOLD       = 10.0   # % below median → gem
SUPER_GEM_THRESHOLD = 20.0   # % below median → super gem

# Minimum realistic price (£) for a complete component by category
# Prevents accessories / spare parts from appearing as cheapest listings
_CATEGORY_MIN_PRICE: dict[str, float] = {
    "gpu":         40.0,
    "cpu":         15.0,
    "ram":         10.0,
    "ssd":         10.0,
    "psu":         15.0,
    "motherboard": 20.0,
    "cooler":      10.0,
}


def _classify(discount_pct: float | None) -> str | None:
    if discount_pct is None:
        return None
    if discount_pct >= SUPER_GEM_THRESHOLD:
        return "super_gem"
    if discount_pct >= GEM_THRESHOLD:
        return "gem"
    return None


async def get_live_prices_for_category(category: str, force_refresh: bool = False) -> list[dict]:
    """
    For each canonical model in the category, fetch live eBay BIN prices
    via the Browse API. Results are cached 30 minutes per category.

    Returned fields per model:
      model, tier,
      new_price (cheapest new BIN), new_count (total new listings),
      used_median (median used BIN), used_count (total used listings),
      used_cheapest_price (cheapest used), used_cheapest_url, used_cheapest_title,
      used_cheapest_image, discount_pct (cheapest vs median),
      gem_classification (super_gem | gem | None)
    """
    now = time.time()
    if not force_refresh:
        cached = _LIVE_CACHE.get(category)
        if cached and (now - cached[0]) < CACHE_TTL:
            return cached[1]

    models = CANONICAL_MODELS.get(category, [])
    if not models:
        return []

    min_price = _CATEGORY_MIN_PRICE.get(category, 15.0)

    # Fetch all models in parallel (eBay Browse API handles concurrency gracefully
    # via its own rate limiter — we have a semaphore inside get_component_prices)
    async def _fetch(m: dict) -> dict:
        prices = await get_component_prices(m["name"], force_refresh=force_refresh, min_price=min_price)

        used_median = prices["used_median"]
        cheapest    = prices["used_cheapest"]
        cheapest_price = cheapest["price"] if cheapest else None

        discount_pct = None
        if used_median and cheapest_price and cheapest_price < used_median:
            discount_pct = round((used_median - cheapest_price) / used_median * 100, 1)

        return {
            "model":              m["name"],
            "tier":               m["tier"],
            "new_price":          prices["new_min"],
            "new_count":          len(prices["new_prices"]),
            "used_median":        used_median,
            "used_count":         len(prices["used_prices"]),
            "used_cheapest_price": cheapest_price,
            "used_cheapest_url":   cheapest["url"]       if cheapest else None,
            "used_cheapest_title": cheapest["title"]     if cheapest else None,
            "used_cheapest_image": cheapest["image_url"] if cheapest else None,
            "discount_pct":        discount_pct,
            "gem_classification":  _classify(discount_pct),
        }

    results = await asyncio.gather(*[_fetch(m) for m in models], return_exceptions=True)
    rows = [r for r in results if isinstance(r, dict)]

    _LIVE_CACHE[category] = (now, rows)
    log.info("live_prices.fetched", category=category, count=len(rows))
    return rows
