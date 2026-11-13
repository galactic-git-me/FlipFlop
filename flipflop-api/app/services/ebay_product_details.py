"""eBay product detail capture through the official Browse API only."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from app.services.scraper import _ebay_base_url, _get_ebay_access_token


class EbayBrowseDetailsError(RuntimeError):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


def _aspects(item: dict[str, Any]) -> tuple[dict[str, list[str]], dict[str, str]]:
    specifications: dict[str, list[str]] = {}
    identifiers: dict[str, str] = {}
    rows = [*(item.get("localizedAspects") or []), *(item.get("inferredLocalizedAspects") or [])]
    aliases = {
        "brand": "brand",
        "manufacturer part number": "mpn", "mpn": "mpn", "part number": "mpn",
        "model": "modelNumber", "model number": "modelNumber",
        "gtin": "gtin", "upc": "gtin", "ean": "gtin",
    }
    for aspect in rows:
        if not isinstance(aspect, dict):
            continue
        name = str(aspect.get("name") or "").strip()
        value = str(aspect.get("value") or "").strip()
        if not name or not value:
            continue
        values = specifications.setdefault(name, [])
        if value not in values:
            values.append(value)
        key = aliases.get(name.casefold())
        if key and key not in identifiers:
            identifiers[key] = value
    product = item.get("product") or {}
    if isinstance(product, dict):
        for source, target in (("epid", "epid"), ("mpn", "mpn"), ("brand", "brand"), ("gtin", "gtin")):
            value = product.get(source)
            if value and target not in identifiers:
                identifiers[target] = str(value)
    return specifications, identifiers


def _selected_offer(item: dict[str, Any], variation_id: str | None) -> dict[str, Any] | None:
    price = item.get("price") or item.get("currentBidPrice") or {}
    try:
        amount = float(price.get("value"))
    except (AttributeError, TypeError, ValueError):
        return None
    currency = str(price.get("currency") or "").upper()
    if amount <= 0 or currency not in {"GBP", "EUR", "USD"}:
        return None

    shipping_rows = [row for row in (item.get("shippingOptions") or []) if isinstance(row, dict)]
    shipping_costs = [row.get("shippingCost") or {} for row in shipping_rows]
    normalized_costs = {
        (str(cost.get("currency") or "").upper(), str(cost.get("value") or ""))
        for cost in shipping_costs if cost.get("value") is not None
    }
    shipping_price: float | None = None
    shipping_verified = False
    if len(normalized_costs) == 1:
        shipping_currency, raw_shipping = next(iter(normalized_costs))
        try:
            shipping_price = float(raw_shipping)
            shipping_verified = shipping_currency == currency and shipping_price >= 0
        except ValueError:
            pass

    availability_text = str(item.get("estimatedAvailabilityStatus") or "").upper()
    if availability_text in {"IN_STOCK", "IN_STOCK_SCARCE"}:
        availability = "available"
    elif availability_text in {"OUT_OF_STOCK", "UNAVAILABLE"}:
        availability = "unavailable"
    else:
        availability = "unknown"

    selected_options = {
        str(row.get("name")): str(row.get("value"))
        for row in (item.get("localizedAspects") or [])
        if isinstance(row, dict) and row.get("name") and row.get("value")
    }
    return {
        "marketplaceVariantId": variation_id,
        "selectedOptions": selected_options,
        "price": amount,
        "currency": currency,
        "priceText": f"{currency} {amount:.2f}",
        "sourcePageVerified": True,
        "sourceMethod": "ebay_browse_api",
        "variantControlsDetected": variation_id is not None,
        "selectedOptionsCaptureComplete": variation_id is None or bool(selected_options),
        "selectedPriceStable": True,
        "shippingPrice": shipping_price if shipping_verified else None,
        "shippingVerified": shipping_verified,
        "availability": availability,
        "availabilityPageVerified": availability != "unknown",
        "deliveryText": None,
        "deliveryWorkingDays": None,
    }


async def fetch_ebay_item_details(
    client: httpx.AsyncClient,
    item_id: str,
    variation_id: str | None = None,
) -> dict[str, Any]:
    """Fetch one exact eBay item or legacy variation, with no HTML fallback."""
    token = await _get_ebay_access_token(client)
    if not token:
        raise EbayBrowseDetailsError("eBay Browse API credentials are not configured", 503)

    params = {"legacy_item_id": item_id}
    if variation_id:
        params["legacy_variation_id"] = variation_id
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "X-EBAY-C-MARKETPLACE-ID": "EBAY_GB",
    }
    endpoint = f"{_ebay_base_url()}/buy/browse/v1/item/get_item_by_legacy_id"
    try:
        response = await client.get(endpoint, params=params, headers=headers, timeout=20)
    except httpx.HTTPError as error:
        raise EbayBrowseDetailsError("eBay Browse API request failed") from error
    if response.status_code == 404:
        raise EbayBrowseDetailsError("eBay item or variation was not found by Browse API", 404)
    if response.status_code == 429:
        raise EbayBrowseDetailsError("eBay Browse API rate limit reached", 503)
    if response.status_code != 200:
        raise EbayBrowseDetailsError(f"eBay Browse API returned HTTP {response.status_code}")

    item = response.json()
    if str(item.get("legacyItemId") or "") != item_id:
        raise EbayBrowseDetailsError("Browse API response did not match the requested eBay item")
    if variation_id and str(item.get("legacyVariationId") or "") != variation_id:
        raise EbayBrowseDetailsError("Browse API response did not match the requested eBay variation")
    specifications, identifiers = _aspects(item)
    offer = _selected_offer(item, variation_id)
    return {
        "status": "ok",
        "sourceUrl": str(item.get("itemWebUrl") or f"https://www.ebay.co.uk/itm/{item_id}"),
        "sourceMethod": "ebay_browse_api",
        "capturedAt": datetime.now(timezone.utc).isoformat(),
        "specifications": specifications,
        "identifiers": identifiers,
        "conflicts": [],
        "selectedOffer": offer,
    }
