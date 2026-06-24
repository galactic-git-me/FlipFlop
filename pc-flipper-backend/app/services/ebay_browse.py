"""
eBay Browse API client for fetching current component prices.

Uses the official eBay Browse API (not HTML scraping) so results are
accurate, rate-limit-friendly, and include proper structured data.

Used by the live-prices endpoint to fetch:
  - "New" BIN price  = lowest BIN listing in NEW or LIKE_NEW condition
  - "Used" BIN prices = all BIN listings in used condition → median + cheapest

Reference: https://developer.ebay.com/api-docs/buy/browse/resources/item_summary/methods/search
"""
from __future__ import annotations

import asyncio
import statistics
import time
from typing import TypedDict

import httpx
import structlog

from app.api.ebay_compliance import _get_app_token, _ebay_api_root

log = structlog.get_logger(__name__)

# Conditions treated as "new" for the RRP column
_NEW_CONDITIONS = {"NEW", "LIKE_NEW", "MANUFACTURER_REFURBISHED"}

# Conditions treated as "used" for the used-price column
_USED_CONDITIONS = {"USED", "EXCELLENT", "VERY_GOOD", "GOOD", "ACCEPTABLE", "FOR_PARTS_OR_NOT_WORKING"}

# EBAY_GB = UK marketplace
_MARKETPLACE_ID = "EBAY_GB"

# Title keywords that indicate accessories/parts, not complete components
_ACCESSORY_TOKENS = frozenset([
    "cooling fan", "heatsink", "backplate", "bracket", "thermal pad",
    "screw", "cable", "adapter", "connector", "waterblock", "water block",
    "sticker", "box only", "packaging only", "manual only", "shroud",
    "replacement fan", "spare", "cooler only", "heat sink",
    "faulty", "for parts", "not working", "no display", "dead", "broken",
    "spares or repair", "spares/repair", "read description",
    "artefacting", "artifacting", "no gpu", "no card", "cooling house",
    "crashes", "crashing", "intermittent", "damaged", "defective",
])

def _is_accessory(title: str) -> bool:
    tl = title.lower()
    return any(tok in tl for tok in _ACCESSORY_TOKENS)

# Global semaphore — Browse API has per-app rate limits
_API_SEM = asyncio.Semaphore(5)

# Simple in-process cache: model_name → (timestamp, result)
_BROWSE_CACHE: dict[str, tuple[float, dict]] = {}
BROWSE_CACHE_TTL = 1800  # 30 minutes


class EbayListing(TypedDict):
    title: str
    price: float
    condition: str
    url: str
    image_url: str | None


class ComponentPrices(TypedDict):
    new_prices: list[float]
    new_cheapest: EbayListing | None
    used_prices: list[float]
    used_cheapest: EbayListing | None
    used_median: float | None
    new_min: float | None


async def _search(token: str, query: str, condition_filter: str, limit: int = 50, min_price: float = 10.0) -> list[EbayListing]:
    """
    Search eBay Buy Browse API for BIN listings of a given condition.
    condition_filter examples: 'NEW|LIKE_NEW', 'USED|EXCELLENT|VERY_GOOD|GOOD|ACCEPTABLE'
    """
    root = _ebay_api_root()
    url = f"{root}/buy/browse/v1/item_summary/search"
    headers = {
        "Authorization": f"Bearer {token}",
        "X-EBAY-C-MARKETPLACE-ID": _MARKETPLACE_ID,
        "Content-Type": "application/json",
    }
    params = {
        "q": query,
        "filter": f"buyingOptions:{{FIXED_PRICE}},conditions:{{{condition_filter}}}",
        "limit": str(limit),
        "fieldgroups": "MATCHING_ITEMS",
    }
    async with _API_SEM:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(url, headers=headers, params=params)

    if resp.status_code != 200:
        log.warning("ebay_browse.search_failed", query=query, status=resp.status_code)
        return []

    items = resp.json().get("itemSummaries", [])
    results: list[EbayListing] = []
    for item in items:
        price_info = item.get("price", {})
        currency = price_info.get("currency", "GBP")
        if currency != "GBP":
            continue
        try:
            price = float(price_info.get("value") or 0)
        except (ValueError, TypeError):
            continue
        if price < min_price or price > 10_000:
            continue
        title = str(item.get("title") or "")
        if _is_accessory(title):
            continue
        image = item.get("image") or {}
        results.append({
            "title": title,
            "price": price,
            "condition": str(item.get("condition") or ""),
            "url": str(item.get("itemWebUrl") or ""),
            "image_url": image.get("imageUrl"),
        })

    return results


async def get_component_prices(model_name: str, force_refresh: bool = False, min_price: float = 20.0) -> ComponentPrices:
    """
    Fetch current eBay BIN prices for a component model.

    Returns median used price, cheapest used listing (with URL + image),
    and cheapest new listing.
    """
    cached = _BROWSE_CACHE.get(model_name)
    if not force_refresh and cached and (time.time() - cached[0]) < BROWSE_CACHE_TTL:
        return cached[1]

    token = await _get_app_token()
    if not token:
        log.warning("ebay_browse.no_token")
        return _empty()

    new_cond  = "NEW|LIKE_NEW|MANUFACTURER_REFURBISHED"
    used_cond = "USED|EXCELLENT|VERY_GOOD|GOOD|ACCEPTABLE"

    try:
        new_items, used_items = await asyncio.gather(
            _search(token, model_name, new_cond,  limit=50, min_price=min_price),
            _search(token, model_name, used_cond, limit=50, min_price=min_price),
            return_exceptions=True,
        )
    except Exception as exc:
        log.warning("ebay_browse.gather_error", model=model_name, error=str(exc))
        return _empty()

    if isinstance(new_items, Exception):
        new_items = []
    if isinstance(used_items, Exception):
        used_items = []

    new_prices  = sorted(i["price"] for i in new_items)
    used_prices = sorted(i["price"] for i in used_items)

    new_cheapest  = new_items[0]  if new_items  else None
    used_cheapest = used_items[0] if used_items else None

    # Sort used items by price to find the true cheapest
    if used_items:
        used_items_sorted = sorted(used_items, key=lambda x: x["price"])
        used_cheapest = used_items_sorted[0]

    if new_items:
        new_items_sorted = sorted(new_items, key=lambda x: x["price"])
        new_cheapest = new_items_sorted[0]

    result: ComponentPrices = {
        "new_prices":   new_prices,
        "new_cheapest": new_cheapest,
        "used_prices":  used_prices,
        "used_cheapest": used_cheapest,
        "used_median":  round(statistics.median(used_prices), 2) if len(used_prices) >= 3 else (used_prices[0] if used_prices else None),
        "new_min":      round(new_prices[0], 2) if new_prices else None,
    }

    _BROWSE_CACHE[model_name] = (time.time(), result)
    log.debug("ebay_browse.fetched", model=model_name, used_count=len(used_prices), new_count=len(new_prices))
    return result


def _empty() -> ComponentPrices:
    return {
        "new_prices": [], "new_cheapest": None,
        "used_prices": [], "used_cheapest": None,
        "used_median": None, "new_min": None,
    }
