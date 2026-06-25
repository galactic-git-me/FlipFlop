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
from app.services.component_search import (
    ComponentListing,
    search_component_all_sources,
)
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


async def get_live_prices_for_category(
    category: str,
    force_refresh: bool = False,
    include_all_sources: bool = True,
) -> list[dict]:
    """
    Get live component prices for a category.

    Returns eBay benchmarks + listings from all sources (if include_all_sources=True).
    Gem scoring based on eBay NEW/USED prices only.

    Returned fields per model:
      model, tier,
      new_price (cheapest new BIN), new_count (total new listings),
      used_median (median used BIN), used_count (total used listings),
      used_cheapest_price (cheapest used), used_cheapest_url, used_cheapest_title,
      used_cheapest_image, discount_pct (cheapest vs median),
      gem_classification (super_gem | gem | None),
      all_sources (listings from Vinted, Gumtree, Amazon, Temu, AliExpress)
    """
    cached = _LIVE_CACHE.get(category)
    if not force_refresh and cached and (time.time() - cached[0]) < CACHE_TTL:
        return cached[1]

    models = CANONICAL_MODELS.get(category, [])
    results = []

    async def fetch_model_data(model: dict) -> dict | None:
        model_name = model["name"]

        # 1. Get eBay benchmarks (NEW and USED prices)
        ebay_data = await get_component_prices(
            model_name,
            force_refresh=force_refresh,
            min_price=_CATEGORY_MIN_PRICE.get(category, 15.0),
        )

        if not ebay_data.get("used_prices"):
            return None

        new_price = ebay_data.get("new_min")
        used_prices = ebay_data.get("used_prices", [])
        used_median = ebay_data.get("used_median")
        used_cheapest = ebay_data.get("used_cheapest")

        # 2. Search all sources for this component
        all_source_listings = []
        if include_all_sources:
            try:
                all_source_listings = await search_component_all_sources(
                    model_name,
                    min_price=_CATEGORY_MIN_PRICE.get(category, 15.0),
                    max_price=10000.0,
                )
            except Exception as exc:
                log.debug("live_prices.multi_source_error", model=model_name, error=str(exc))

        # 3. Calculate gem classification based on eBay benchmarks
        discount_pct = None
        if used_median and used_cheapest and used_cheapest.get("price"):
            cheapest_price = used_cheapest["price"]
            if cheapest_price < used_median:
                discount_pct = round((used_median - cheapest_price) / used_median * 100, 1)

        gem_classification = _classify(discount_pct)

        # 4. Build response with eBay benchmarks + all sources
        return {
            "model": model_name,
            "tier": model.get("tier"),
            "new_price": new_price,
            "new_count": len(ebay_data.get("new_prices", [])),
            "used_median": used_median,
            "used_count": len(used_prices),
            "used_cheapest_price": used_cheapest.get("price") if used_cheapest else None,
            "used_cheapest_url": used_cheapest.get("url") if used_cheapest else None,
            "used_cheapest_title": used_cheapest.get("title") if used_cheapest else None,
            "used_cheapest_image": used_cheapest.get("image_url") if used_cheapest else None,
            "discount_pct": discount_pct,
            "gem_classification": gem_classification,
            # NEW: All-source listings
            "all_sources": [
                {
                    "source": l.source,
                    "price": l.price,
                    "title": l.title,
                    "url": l.url,
                    "image_url": l.image_url,
                    "condition": l.condition,
                }
                for l in all_source_listings
            ] if include_all_sources else [],
        }

    # Fetch all models concurrently
    model_results = await asyncio.gather(
        *[fetch_model_data(m) for m in models],
        return_exceptions=True,
    )

    for result in model_results:
        if isinstance(result, dict):
            results.append(result)

    _LIVE_CACHE[category] = (time.time(), results)
    log.info("live_prices.fetched", category=category, models=len(results))
    return results
