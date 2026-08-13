"""
eBay Sell Negotiation API — row 45 (proactively send offers to watchers).

Distinct from ebay_trading_api.py's Best-Offer response (buyer-initiated),
this is the seller-initiated direction eBay's REST "Send offers to buyers"
feature covers: find_eligible_items, then send_offer_to_interested_buyers.

Not verifiable against live eBay from this environment (no network egress
to any eBay domain here) — the request body shape below is implemented to
the best of available documentation and should be double-checked against
eBay's current Negotiation API reference before the first live send; this
is a genuinely higher-uncertainty integration than the OAuth/Trading API
code (which mirror longer-stable, better-documented contracts) because
eBay's Negotiation API is newer and its exact field names have shifted
across versions.
"""
from __future__ import annotations

import structlog
import httpx

from app.api.ebay_compliance import _ebay_api_root

log = structlog.get_logger(__name__)


async def send_offer_to_watchers(listing_id: str, offer_price: float, message: str, token: str) -> bool:
    """Row 45: push an unsolicited discount offer to everyone watching/viewing the listing."""
    root = _ebay_api_root()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-EBAY-C-MARKETPLACE-ID": "EBAY_GB",
    }
    body = {
        "offerItems": [{"listingId": listing_id, "quantity": 1}],
        "message": message[:250],
        "priceOverride": {"value": f"{offer_price:.2f}", "currency": "GBP"},
    }
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            f"{root}/sell/negotiation/v1/send_offer_to_interested_buyers", json=body, headers=headers,
        )
    if resp.status_code not in (200, 201, 204):
        log.warning("ebay_negotiation.send_failed", listing_id=listing_id, status=resp.status_code, body=resp.text[:300])
        return False
    return True
