"""Read-only discovery of a newly published eBay offer for a saved build SKU."""
from __future__ import annotations

import httpx

_BASE = {"sandbox": "https://api.sandbox.ebay.com", "production": "https://api.ebay.com"}


async def find_active_listing_for_sku(sku: str, access_token: str, environment: str = "production") -> dict | None:
    """Return the exact-SKU active offer's item ID and URL; never creates or edits offers."""
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            f"{_BASE[environment]}/sell/inventory/v1/offer",
            params={"sku": sku, "limit": 100},
            headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
        )
    response.raise_for_status()
    offers = response.json().get("offers", [])
    for offer in offers:
        listing_id = offer.get("listing", {}).get("listingId") or offer.get("listingId")
        if str(offer.get("sku") or "") != sku or not listing_id:
            continue
        if str(offer.get("status") or "").upper() not in {"PUBLISHED", "ACTIVE"}:
            continue
        return {"listing_id": str(listing_id), "listing_url": f"https://www.ebay.co.uk/itm/{listing_id}"}
    return None
