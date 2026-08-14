"""
eBay Sell Marketing API — Row 40 (Promoted Listings ad-rate).

Not verifiable against live eBay from this environment (no network egress
to any eBay domain here) — same higher-uncertainty caveat as
ebay_negotiation.py: this is implemented to the best of available Marketing
API documentation and should be double-checked against eBay's current
reference before the first live use, since campaign/ad shapes have shifted
across API versions more than the older Trading API has.

Promoted Listings requires a running ad campaign to exist before a listing
can be added to it — this module finds (or creates, once) a single
always-on "General" campaign per environment, then adds/updates the
listing's ad inside it at the requested bid percentage. One campaign is
reused for every promoted build rather than creating one per listing,
since eBay's Promoted Listings model is campaign-scoped, not listing-scoped.
"""
from __future__ import annotations

from datetime import date

import structlog
import httpx

log = structlog.get_logger(__name__)

_CAMPAIGN_NAME = "FlipFlop Always-On"
_API_ROOTS = {
    "sandbox": "https://api.sandbox.ebay.com",
    "production": "https://api.ebay.com",
}


def _root(environment: str) -> str:
    return _API_ROOTS.get(environment, _API_ROOTS["production"])


async def _find_or_create_campaign(token: str, environment: str) -> str | None:
    root = _root(environment)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-EBAY-C-MARKETPLACE-ID": "EBAY_GB",
    }
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(f"{root}/sell/marketing/v1/ad_campaign", headers=headers, params={"limit": "50"})
        if resp.status_code == 200:
            for campaign in resp.json().get("campaigns", []):
                if campaign.get("campaignName") == _CAMPAIGN_NAME and campaign.get("campaignStatus") in ("RUNNING", "SCHEDULED"):
                    return campaign.get("campaignId")

        create_resp = await client.post(
            f"{root}/sell/marketing/v1/ad_campaign",
            headers=headers,
            json={
                "campaignName": _CAMPAIGN_NAME,
                "marketplaceId": "EBAY_GB",
                "fundingStrategy": {"fundingModel": "COST_PER_SALE", "bidPercentage": "5.0"},
                "startDate": date.today().isoformat() + "T00:00:00.000Z",
                "channel": "OTHER_PROMOTED_LISTINGS_CHANNELS",
            },
        )
        if create_resp.status_code not in (200, 201):
            log.warning("ebay_marketing.campaign_create_failed", status=create_resp.status_code, body=create_resp.text[:300])
            return None
        location = create_resp.headers.get("Location", "")
        return location.rstrip("/").rsplit("/", 1)[-1] or None


async def set_promoted_ad(listing_id: str, ad_rate_pct: float, token: str, environment: str) -> bool:
    """Row 40: ensure `listing_id` is promoted in the always-on campaign at
    `ad_rate_pct` (e.g. 5.0 for 5%). Returns True on success."""
    campaign_id = await _find_or_create_campaign(token, environment)
    if not campaign_id:
        log.warning("ebay_marketing.no_campaign", listing_id=listing_id)
        return False

    root = _root(environment)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-EBAY-C-MARKETPLACE-ID": "EBAY_GB",
    }
    body = {"listingId": listing_id, "bidPercentage": f"{ad_rate_pct:.1f}"}
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            f"{root}/sell/marketing/v1/ad_campaign/{campaign_id}/ad", headers=headers, json=body,
        )
    if resp.status_code not in (200, 201, 204):
        log.warning("ebay_marketing.set_ad_failed", listing_id=listing_id, status=resp.status_code, body=resp.text[:300])
        return False
    return True
