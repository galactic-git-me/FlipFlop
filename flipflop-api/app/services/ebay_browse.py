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

# Conditions treated as "used" for the used-price column (excluding broken/parts items)
_USED_CONDITIONS = {"USED", "EXCELLENT", "VERY_GOOD", "GOOD", "ACCEPTABLE"}

# EBAY_GB = UK marketplace
_MARKETPLACE_ID = "EBAY_GB"

# Title keywords that indicate accessories/parts, not complete components
_ACCESSORY_TOKENS = frozenset([
    # Accessories/fans/parts
    "cooling fan", "cooler fan", "graphics card cooler", "heatsink", "backplate", "bracket", "thermal pad",
    "screw", "cable", "adapter", "connector", "waterblock", "water block",
    "sticker", "box only", "packaging only", "manual only", "shroud",
    "replacement fan", "spare", "cooler only", "heat sink",
    # Defective/damaged (comprehensive patterns)
    "faulty", "for parts", "not working", "no display", "dead", "broken",
    "spares or repair", "spares/repair", "parts/repair", "parts or repair", "parts not working", "parts only",
    "for parts or not working", "for spares or repair", "read description",
    "artefacting", "artifacting", "no gpu", "no card",
    "crashes", "crashing", "intermittent", "damaged", "defective",
    # RAM: exclude laptop/server types — keep only desktop UDIMM
    "sdimm", "sodimm", "laptop", "notebook", "mobile", "rdimm", "lrdimm",
    "registered dimm", "for server", "workstation memory",
])

def _is_accessory(title: str) -> bool:
    tl = title.lower()
    return any(tok in tl for tok in _ACCESSORY_TOKENS)

# Global semaphore — Browse API has per-app rate limits
_API_SEM = asyncio.Semaphore(1)

# Simple in-process cache: model_name → (timestamp, result)
_BROWSE_CACHE: dict[str, tuple[float, dict]] = {}
BROWSE_CACHE_TTL = 1800  # 30 minutes

# get_component_prices() is called once per unique component model during
# scan scoring — with hundreds of listings per scan and no pacing, every
# call fires near-instantly and eBay's Browse API 429s almost every single
# request (burst rate limit, not the daily quota). Serialize requests with a
# minimum spacing and retry 429s with backoff instead of silently returning
# an empty result, mirroring the pacer already used for the extension's own
# eBay Finding API calls (see FlipFlopXtension/src/background/scan-orchestrator.ts).
_EBAY_API_MIN_INTERVAL_S = 1.0
# Kept low deliberately: the extension's own /scans request aborts client-side
# after 2 minutes (REQUEST_TIMEOUT_MS in api-client.ts). With the old value
# of 4, the FIRST few rare/new-model queries in a batch — before the circuit
# breaker has tripped — could each burn ~30s of backoff (2+4+8+16s), and just
# a couple of those blew straight through the client's timeout, failing the
# whole submission. 1 retry (2s max) keeps that startup cost small regardless
# of how many unique models a batch hits before the breaker opens below.
_EBAY_API_MAX_RETRIES = 1
_ebay_api_lock = asyncio.Lock()
_last_ebay_api_request_at = 0.0

# Circuit breaker: retry-with-backoff only helps against a transient burst
# limit. If eBay's quota is fully exhausted for the day, every retry still
# 429s and the backoff per listing is pure wasted latency, multiplied across
# every listing in a scan. After enough consecutive failures we stop
# retrying and fail immediately for a cooldown window, then let one request
# through to check whether the quota recovered. Kept low (2, not 5) for the
# same client-timeout reason as _EBAY_API_MAX_RETRIES above — a scan right
# after a reset/observation-clear can have many rare models in a row with no
# batch/history match, and each one pays the retry cost until the breaker
# trips; tripping after 2 failures instead of 5 caps that startup cost.
_CIRCUIT_BREAKER_THRESHOLD = 10
_CIRCUIT_BREAKER_COOLDOWN_S = 60  # 1 minute
_consecutive_429_failures = 0
_circuit_open_until = 0.0


async def _wait_for_api_slot() -> None:
    """Serializes callers onto a minimum-interval schedule so concurrent
    get_component_prices() calls (there are two _search() calls per model,
    plus however many models are in flight under _API_SEM) don't all land
    on eBay in the same instant."""
    global _last_ebay_api_request_at
    async with _ebay_api_lock:
        wait = _last_ebay_api_request_at + _EBAY_API_MIN_INTERVAL_S - time.time()
        if wait > 0:
            await asyncio.sleep(wait)
        _last_ebay_api_request_at = time.time()


class EbayListing(TypedDict):
    title: str
    price: float  # delivered price (item + shipping), not just the item price — see _search()
    condition: str
    url: str
    image_url: str | None
    epid: str | None  # eBay catalog product ID — a real cross-listing identity
    # key when present (unlike our own title-regex-derived model string, which
    # fragments the same product into different keys across title variants).
    # Not populated by every seller/listing, so callers must still fall back
    # to title-based matching when this is None.
    gtin: str | None  # Global Trade Item Number (UPC/barcode) — canonical product identifier
    # across all retailers and title variants. More stable than epid for cross-retailer
    # matching. When present, consolidates all variants of a product (e.g. "9800X3D",
    # "Ryzen 9 9800X3D", "AMD Ryzen 9 9800X3D") into a single price bucket.
    mpn: str | None  # Manufacturer Part Number — another stable identifier for grouping
    # the same product across title variants. eBay Browse API returns this in productSummary.
    seller_feedback_percent: float | None  # item.seller.feedbackPercentage — already present
    # on every Browse API item summary at no extra cost, previously discarded.
    seller_feedback_count: int | None  # item.seller.feedbackScore
    model_number: str | None  # Product model number from eBay API productSummary.modelNumber
    # (e.g. "100-10000108​4WOF" for AMD 9800X3D). Stable across title variants.


class ComponentPrices(TypedDict):
    new_prices: list[float]
    new_cheapest: EbayListing | None
    used_prices: list[float]
    used_cheapest: EbayListing | None
    used_median: float | None
    new_min: float | None


async def _search(token: str, query: str, condition_filter: str, limit: int = 50, min_price: float = 10.0, offset: int = 0) -> list[EbayListing]:
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
        "offset": str(offset),
        "fieldgroups": "MATCHING_ITEMS",
    }

    global _consecutive_429_failures, _circuit_open_until

    if time.time() < _circuit_open_until:
        log.warning(
            "ebay_browse.circuit_open", query=query,
            resumes_in_s=round(_circuit_open_until - time.time(), 1),
        )
        return []

    resp: httpx.Response | None = None
    async with _API_SEM:
        async with httpx.AsyncClient(timeout=20) as client:
            for attempt in range(_EBAY_API_MAX_RETRIES + 1):
                await _wait_for_api_slot()
                resp = await client.get(url, headers=headers, params=params)
                if resp.status_code != 429 or attempt == _EBAY_API_MAX_RETRIES:
                    break
                retry_after = resp.headers.get("Retry-After")
                try:
                    backoff = float(retry_after) if retry_after else 2.0 * (2 ** attempt)
                except ValueError:
                    backoff = 2.0 * (2 ** attempt)
                log.warning(
                    "ebay_browse.rate_limited", query=query, attempt=attempt + 1,
                    max_attempts=_EBAY_API_MAX_RETRIES, backoff_s=backoff,
                )
                await asyncio.sleep(backoff)

    if resp is not None and resp.status_code == 429:
        _consecutive_429_failures += 1
        if _consecutive_429_failures >= _CIRCUIT_BREAKER_THRESHOLD:
            _circuit_open_until = time.time() + _CIRCUIT_BREAKER_COOLDOWN_S
            log.warning(
                "ebay_browse.circuit_opened",
                consecutive_failures=_consecutive_429_failures,
                cooldown_s=_CIRCUIT_BREAKER_COOLDOWN_S,
            )
    elif resp is not None and resp.status_code == 200:
        _consecutive_429_failures = 0

    if resp is None or resp.status_code != 200:
        status = resp.status_code if resp is not None else None
        log.warning("ebay_browse.search_failed", query=query, status=status)
        return []

    items = resp.json().get("itemSummaries", [])
    results: list[EbayListing] = []
    for item in items:
        price_info = item.get("price", {})
        currency = price_info.get("currency", "GBP")
        if currency != "GBP":
            continue
        try:
            item_price = float(price_info.get("value") or 0)
        except (ValueError, TypeError):
            continue
        # Comparisons/medians/"cheapest" need the actual delivered cost, not
        # the bare item price — a £160 item with £25 shipping is not cheaper
        # than a £180 item with free shipping, but sorting on item price
        # alone would rank it first. shippingOptions can be absent (eBay
        # sometimes omits it on the summary endpoint) or calculated-at-
        # checkout with no value yet; both default to 0 (best-effort — this
        # will slightly favour listings with unstated/calculated shipping).
        shipping_cost = 0.0
        for option in item.get("shippingOptions") or []:
            cost = (option or {}).get("shippingCost") or {}
            if cost.get("currency", "GBP") != "GBP":
                continue
            try:
                shipping_cost = float(cost.get("value") or 0)
            except (ValueError, TypeError):
                shipping_cost = 0.0
            break  # first shipping option is eBay's default/cheapest one
        price = item_price + shipping_cost
        if price < min_price or price > 10_000:
            continue
        title = str(item.get("title") or "")
        if _is_accessory(title):
            continue

        # Verify condition is acceptable (eBay sometimes returns unwanted conditions)
        condition = str(item.get("condition") or "").upper()
        item_url = str(item.get("itemWebUrl") or "")

        # Filter out "for parts or not working" in any format
        defect_conditions = [
            "FOR_PARTS", "NOT_WORKING", "PARTS_OR_NOT", "PARTS OR NOT",
            "FOR_SPARES", "SPARES_OR_REPAIR", "PARTS_NOT_WORKING"
        ]
        if any(x in condition for x in defect_conditions):
            continue

        image = item.get("image") or {}
        # Extract canonical identifiers from productSummary if available. These are stable,
        # canonical identifiers that consolidate the same product across title
        # variants ("9800X3D" vs "Ryzen 9 9800X3D" vs "AMD Ryzen 9 9800X3D" all
        # have the same GTIN/MPN/modelNumber), unlike title-based regex matching which
        # fragments them into separate price buckets.
        gtin = None
        mpn = None
        model_number = None
        product_summary = item.get("productSummary") or {}
        if product_summary:
            gtin = product_summary.get("gtin")
            mpn = product_summary.get("mpn")
            model_number = product_summary.get("modelNumber")

        seller = item.get("seller") or {}
        try:
            seller_feedback_percent = float(seller["feedbackPercentage"]) if seller.get("feedbackPercentage") is not None else None
        except (ValueError, TypeError):
            seller_feedback_percent = None
        try:
            seller_feedback_count = int(seller["feedbackScore"]) if seller.get("feedbackScore") is not None else None
        except (ValueError, TypeError):
            seller_feedback_count = None

        results.append({
            "title": title,
            "price": price,
            "condition": condition,
            "url": item_url,
            "image_url": image.get("imageUrl"),
            "epid": item.get("epid"),
            "gtin": gtin,
            "mpn": mpn,
            "model_number": model_number,
            "seller_feedback_percent": seller_feedback_percent,
            "seller_feedback_count": seller_feedback_count,
            "best_offer_enabled": "BEST_OFFER" in (item.get("buyingOptions") or []),
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


async def search_active_listings(
    query: str, condition_filter: str = "USED|EXCELLENT|VERY_GOOD|GOOD|ACCEPTABLE", limit: int = 50, min_price: float = 20.0, offset: int = 0
) -> list[EbayListing]:
    """Public entry point for a raw free-text active-BIN-listing search (e.g.
    a whole finished-PC query like "gaming pc ryzen 5 5600x rtx 3070 32gb"),
    as opposed to get_component_prices() which is keyed to a single component
    model name. Used by ai_build_generator to price a complete build against
    comparable finished builds rather than summing individual parts."""
    token = await _get_app_token()
    if not token:
        log.warning("ebay_browse.no_token")
        return []
    return await _search(token, query, condition_filter, limit=limit, min_price=min_price, offset=offset)


def _empty() -> ComponentPrices:
    return {
        "new_prices": [], "new_cheapest": None,
        "used_prices": [], "used_cheapest": None,
        "used_median": None, "new_min": None,
    }
