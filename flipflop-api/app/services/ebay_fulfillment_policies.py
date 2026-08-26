"""Fetches the seller's real fulfillment policies from eBay's Account API,
so the admin UI can let a build pick one instead of always posting with the
single global EBAY_*_FULFILLMENT_POLICY_ID default (see
app/api/manual_builds.py's post_to_ebay). A fulfillment policy is eBay's own
bundle of shipping services, rates, and destination countries/regions,
configured once in the seller's eBay Seller Hub — this endpoint only reads
that list, it never creates or edits policies.

Uses the same user OAuth token as posting listings (get_valid_ebay_access_token),
since GET /sell/account/v1/fulfillment_policy requires sell.account(.readonly)
scope tied to the authorized seller, not an app-only client-credentials token.
"""
from __future__ import annotations

from dataclasses import dataclass

import httpx
import structlog

from app.services.ebay_token_manager import get_valid_ebay_access_token

log = structlog.get_logger(__name__)

_EBAY_API_BASE = {
    "sandbox": "https://api.sandbox.ebay.com",
    "production": "https://api.ebay.com",
}


@dataclass(frozen=True)
class FulfillmentPolicySummary:
    policy_id: str
    name: str
    marketplace_id: str
    ship_to_regions: list[str]
    handling_time_days: int | None


def _summarize(policy: dict) -> FulfillmentPolicySummary:
    handling = policy.get("handlingTime") or {}
    handling_days = handling.get("value") if handling.get("unit") == "DAY" else None

    regions: list[str] = []
    for option in policy.get("shippingOptions", []):
        for region in (option.get("shipToLocations", {}) or {}).get("regionIncluded", []) or []:
            name = region.get("regionName")
            if name and name not in regions:
                regions.append(name)
        if option.get("shipToLocations", {}).get("worldwide"):
            regions.append("Worldwide")

    return FulfillmentPolicySummary(
        policy_id=policy["fulfillmentPolicyId"],
        name=policy.get("name", policy["fulfillmentPolicyId"]),
        marketplace_id=policy.get("marketplaceId", ""),
        ship_to_regions=regions or ["Domestic (UK)"],
        handling_time_days=handling_days,
    )


class EbayFulfillmentPoliciesError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


async def list_fulfillment_policies(
    environment: str, marketplace_id: str = "EBAY_GB"
) -> list[FulfillmentPolicySummary]:
    """Raises EbayFulfillmentPoliciesError (with the real eBay error message)
    on failure — most commonly a 403 if the stored OAuth token was granted
    sell.inventory but not sell.account scope, which needs re-consenting via
    eBay's OAuth flow rather than anything fixable here."""
    try:
        access_token = await get_valid_ebay_access_token(environment)
    except ValueError as exc:
        # Token refresh failures happen before the Account API request below.
        # Normalize them into this service's public error type so the route
        # returns a useful HTTP response instead of an unhandled 500 (which
        # browsers commonly reduce to the opaque message "Failed to fetch").
        message = str(exc)
        if "invalid_grant" in message:
            raise EbayFulfillmentPoliciesError(
                "Your eBay connection has expired or belongs to different app credentials. "
                "Reconnect the production eBay account in Settings, then try again.",
                401,
            ) from exc
        raise EbayFulfillmentPoliciesError(
            f"Couldn't refresh the eBay access token: {message}",
            502,
        ) from exc
    base_url = _EBAY_API_BASE[environment]

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"{base_url}/sell/account/v1/fulfillment_policy",
            params={"marketplace_id": marketplace_id},
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            },
        )

    if resp.status_code != 200:
        try:
            error_json = resp.json()
            errors = error_json.get("errors", [])
            message = errors[0].get("longMessage") or errors[0].get("message") if errors else resp.text
        except Exception:
            message = resp.text
        log.error("ebay.fulfillment_policies_failed", status=resp.status_code, error=message)
        raise EbayFulfillmentPoliciesError(message or "Failed to fetch fulfillment policies", resp.status_code)

    data = resp.json()
    return [_summarize(p) for p in data.get("fulfillmentPolicies", [])]
