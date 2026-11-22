"""Amazon SP-API keyword search and public offer-price capture for Gem Radar."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

from app.services.amazon_sp_api import AmazonSPAPI, AmazonSPAPIError


def _amount(value: Any) -> tuple[float | None, str | None]:
    if not isinstance(value, dict):
        return None, None
    try:
        amount = float(value.get("amount"))
    except (TypeError, ValueError):
        return None, None
    return (amount, str(value.get("currencyCode") or "")) if amount >= 0 else (None, None)


def _main_image(item: dict[str, Any]) -> str | None:
    for image_group in item.get("images") or []:
        if not isinstance(image_group, dict):
            continue
        images = image_group.get("images") or []
        for image in images:
            if isinstance(image, dict) and image.get("variant") == "MAIN" and str(image.get("link", "")).startswith("https://"):
                return image["link"]
    return None


def _minimum_new_offer(summary: dict[str, Any]) -> tuple[float, float, str] | None:
    for group in summary.get("lowestPricedOffers") or []:
        condition = str((group.get("lowestPricedOffersInput") or {}).get("itemCondition") or "").casefold()
        if condition != "new":
            continue
        candidates: list[tuple[float, float, str]] = []
        for offer in group.get("offers") or []:
            price, currency = _amount(offer.get("listingPrice"))
            if price is None or currency != "GBP":
                continue
            shipping_prices = [_amount(option.get("price"))[0] for option in offer.get("shippingOptions") or [] if isinstance(option, dict)]
            shipping = min((value for value in shipping_prices if value is not None), default=0.0)
            candidates.append((price, shipping, str(offer.get("sellerId") or "Amazon marketplace")))
        if candidates:
            return min(candidates, key=lambda row: row[0] + row[1])
    return None


async def search_amazon_catalog_with_offers(
    client: AmazonSPAPI,
    query: str,
    *,
    page_token: str | None = None,
) -> dict[str, Any]:
    """Return priced UK new offers and concise diagnostics for one catalog page."""
    if not client.configured:
        raise AmazonSPAPIError("Amazon SP-API credentials are not configured on the API service.", status_code=503)

    catalog = await client.search_catalog_items_by_keywords(query, page_token=page_token)
    catalog_items = [item for item in catalog.get("items", []) if isinstance(item, dict)]
    valid_items = [
        item for item in catalog_items
        if isinstance(item.get("asin"), str) and len(item["asin"]) == 10
    ]
    asins = list(dict.fromkeys(item["asin"].upper() for item in valid_items))
    if not asins:
        return {
            "listings": [],
            "nextPageToken": (catalog.get("pagination") or {}).get("nextToken"),
            "sourceUrl": "https://www.amazon.co.uk/s?" + urlencode({"k": query, "i": "computers"}),
            "diagnostics": {"catalogItems": len(catalog_items), "validAsins": 0, "pricingResponses": 0, "unpricedAsins": 0, "apiErrors": []},
        }

    pricing = await client.get_competitive_summaries(asins)
    responses = [row for row in pricing.get("responses", []) if isinstance(row, dict)]
    summaries: dict[str, dict[str, Any]] = {}
    api_errors: list[dict[str, Any]] = []
    for response in responses:
        body = response.get("body") or {}
        asin = str(body.get("asin") or "").upper()
        status = response.get("status") or {}
        if asin and int(status.get("statusCode") or 0) == 200 and not body.get("errors"):
            summaries[asin] = body
        else:
            # Keep diagnostics actionable while excluding full response bodies
            # and any request authorization material.
            api_errors.append({"asin": asin or None, "statusCode": status.get("statusCode"), "reasonPhrase": status.get("reasonPhrase")})

    listings: list[dict[str, Any]] = []
    unpriced = 0
    for item in valid_items:
        asin = item["asin"].upper()
        summary = summaries.get(asin)
        selected = _minimum_new_offer(summary) if summary else None
        if selected is None:
            unpriced += 1
            continue
        item_price, postage_price, seller = selected
        item_summary = next((row for row in item.get("summaries", []) if isinstance(row, dict)), {})
        title = str(item_summary.get("itemName") or "").strip()
        if not title:
            continue
        url = f"https://www.amazon.co.uk/dp/{asin}"
        listings.append({
            "listingId": asin,
            "url": url,
            "title": title,
            "seller": seller,
            "sellerFeedbackPercent": None,
            "sellerFeedbackCount": None,
            "conditionRaw": "New (Amazon SP-API)",
            "conditionNormalised": "new",
            "itemPrice": item_price,
            "postagePrice": postage_price,
            "currentDeliveredPrice": item_price + postage_price,
            "currency": "GBP",
            "listingType": "buy_it_now",
            "bestOfferEnabled": False,
            "bidCount": None,
            "watchCount": None,
            "auctionEndAt": None,
            "imageUrl": _main_image(item),
            "sponsored": False,
            "extractedAt": datetime.now(timezone.utc).isoformat(),
        })

    return {
        "listings": listings,
        "nextPageToken": (catalog.get("pagination") or {}).get("nextToken"),
        "sourceUrl": "https://www.amazon.co.uk/s?" + urlencode({"k": query, "i": "computers"}),
        "diagnostics": {
            "catalogItems": len(catalog_items),
            "validAsins": len(asins),
            "pricingResponses": len(responses),
            "pricedListings": len(listings),
            "unpricedAsins": unpriced,
            "apiErrors": api_errors[:20],
        },
    }
