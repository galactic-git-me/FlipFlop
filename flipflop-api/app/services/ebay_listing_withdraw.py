"""Ends a live eBay listing — used when the same physical build sells
through a different channel (the storefront) first, so the same unit can
never be sold twice. See app/services/cross_channel_guard.py for where this
gets called from.

eBay's publish response only returns listingId, not the offerId needed to
withdraw it — this looks the offer back up by its SKU first (SKU is
persisted at listing time, see ManualBuild.ebay_sku).

Docs: https://developer.ebay.com/api-docs/sell/inventory/resources/offer/methods/withdrawOffer
"""
from __future__ import annotations

import httpx
import structlog

from app.services.ebay_token_manager import get_valid_ebay_access_token

log = structlog.get_logger(__name__)

_EBAY_API_BASE = {
    "sandbox": "https://api.sandbox.ebay.com",
    "production": "https://api.ebay.com",
}


class EbayListingWithdrawError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


async def withdraw_listing_by_sku(sku: str, environment: str = "production") -> None:
    """Ends the live listing for the offer with this SKU. Raises on failure —
    callers should log this loudly rather than swallow it, since a failed
    withdrawal means an already-sold item is still live for sale elsewhere."""
    access_token = await get_valid_ebay_access_token(environment)
    base_url = _EBAY_API_BASE[environment]

    async with httpx.AsyncClient(timeout=30.0) as client:
        lookup_resp = await client.get(
            f"{base_url}/sell/inventory/v1/offer",
            params={"sku": sku},
            headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
        )

    if lookup_resp.status_code != 200:
        log.error("ebay_listing_withdraw.offer_lookup_failed", status=lookup_resp.status_code, body=lookup_resp.text[:500], sku=sku)
        raise EbayListingWithdrawError(f"Failed to look up offer for SKU {sku}: {lookup_resp.text[:300]}", lookup_resp.status_code)

    offers = lookup_resp.json().get("offers", [])
    if not offers:
        raise EbayListingWithdrawError(f"No eBay offer found for SKU {sku} — nothing to withdraw")
    offer_id = offers[0]["offerId"]

    async with httpx.AsyncClient(timeout=30.0) as client:
        withdraw_resp = await client.post(
            f"{base_url}/sell/inventory/v1/offer/{offer_id}/withdraw",
            headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
        )

    if withdraw_resp.status_code not in (200, 204):
        log.error("ebay_listing_withdraw.withdraw_failed", status=withdraw_resp.status_code, body=withdraw_resp.text[:500], offer_id=offer_id, sku=sku)
        raise EbayListingWithdrawError(f"Failed to withdraw offer {offer_id}: {withdraw_resp.text[:300]}", withdraw_resp.status_code)

    log.info("ebay_listing_withdraw.withdrawn", sku=sku, offer_id=offer_id)
