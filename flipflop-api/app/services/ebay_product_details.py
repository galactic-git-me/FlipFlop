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


def _working_days_until(target: datetime) -> int:
    today = datetime.now(timezone.utc).date()
    target_day = target.astimezone(timezone.utc).date()
    if target_day <= today:
        return 0
    return sum(1 for offset in range(1, (target_day - today).days + 1)
               if (today.weekday() + offset) % 7 < 5)


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
    # The API can return several choices (for example Standard and Express).
    # Price the normal standard service, not an arbitrary or premium option.
    standard_rows = [row for row in shipping_rows if str(row.get("type") or "").casefold() == "standard delivery"]
    shipping_row = (standard_rows[0] if standard_rows else
                    shipping_rows[0] if len(shipping_rows) == 1 else None)
    shipping_cost = (shipping_row or {}).get("shippingCost") or {}
    shipping_price: float | None = None
    shipping_verified = False
    if shipping_cost.get("value") is not None:
        try:
            shipping_price = float(shipping_cost["value"])
            shipping_verified = str(shipping_cost.get("currency") or "").upper() == currency and shipping_price >= 0
        except ValueError:
            pass

    availabilities = [row for row in (item.get("estimatedAvailabilities") or []) if isinstance(row, dict)]
    availability_row = next((row for row in availabilities
                             if "SHIP_TO_HOME" in (row.get("deliveryOptions") or [])),
                            availabilities[0] if len(availabilities) == 1 else {})
    availability_text = str(item.get("estimatedAvailabilityStatus")
                             or availability_row.get("estimatedAvailabilityStatus") or "").upper()
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
    max_delivery = None
    min_delivery = None
    if shipping_row:
        for key, field in (("minEstimatedDeliveryDate", "min"), ("maxEstimatedDeliveryDate", "max")):
            raw = shipping_row.get(key)
            if not raw:
                continue
            try:
                parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            except ValueError:
                continue
            if field == "min":
                min_delivery = parsed
            else:
                max_delivery = parsed
    delivery_target = max_delivery or min_delivery
    delivery_days = _working_days_until(delivery_target) if delivery_target else None
    seller = item.get("seller") if isinstance(item.get("seller"), dict) else {}
    try:
        feedback_percent = float(seller["feedbackPercentage"]) if seller.get("feedbackPercentage") is not None else None
    except (TypeError, ValueError):
        feedback_percent = None
    try:
        feedback_count = int(seller["feedbackScore"]) if seller.get("feedbackScore") is not None else None
    except (TypeError, ValueError):
        feedback_count = None
    availability_quantity = availability_row.get("estimatedAvailableQuantity")
    return {
        "marketplaceVariantId": variation_id,
        "selectedOptions": selected_options,
        "price": amount,
        "currency": currency,
        "priceText": f"{currency} {amount:.2f}",
        "condition": str(item.get("condition") or ""),
        "conditionId": str(item.get("conditionId") or ""),
        "buyingOptions": [str(value) for value in (item.get("buyingOptions") or [])],
        "sourcePageVerified": True,
        "sourceMethod": "ebay_browse_api",
        "variantControlsDetected": variation_id is not None,
        "selectedOptionsCaptureComplete": variation_id is None or bool(selected_options),
        "selectedPriceStable": True,
        "shippingPrice": shipping_price if shipping_verified else None,
        "shippingVerified": shipping_verified,
        "shippingService": str(shipping_row.get("shippingServiceCode") or shipping_row.get("type") or "") if shipping_row else None,
        "availability": availability,
        "availabilityPageVerified": availability != "unknown",
        "availableQuantity": availability_quantity if isinstance(availability_quantity, int) and availability_quantity >= 0 else None,
        "deliveryText": ({"minimum": min_delivery.isoformat() if min_delivery else None,
                          "maximum": max_delivery.isoformat() if max_delivery else None} if delivery_target else None),
        "deliveryWorkingDays": delivery_days,
        "deliveryEstimateSource": "ebay_browse_api_destination_estimate" if delivery_days is not None else None,
        "seller": {
            "username": str(seller.get("username") or "") or None,
            "accountType": str(seller.get("sellerAccountType") or "") or None,
            "feedbackPercent": feedback_percent,
            "feedbackCount": feedback_count,
        },
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
