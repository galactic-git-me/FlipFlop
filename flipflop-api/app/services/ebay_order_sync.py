"""Fetches real order data — buyer name, actual delivery address, actual
sale price — from eBay's Sell Fulfillment API once a listing has sold.

This data is only knowable after the sale (a buyer's real shipping address
is never available at listing time), so this is a separate, later step from
posting a listing — see app/api/manual_builds.py's sync_ebay_order endpoint,
which calls this once a build's ebay_listing_id is confirmed sold.

Docs: https://developer.ebay.com/api-docs/sell/fulfillment/resources/order/methods/getOrders
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


class EbayOrderSyncError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class BuyerAddress:
    contact_name: str
    address_line1: str | None
    address_line2: str | None
    city: str | None
    state_or_province: str | None
    postal_code: str | None
    country_code: str  # ISO 3166-1 alpha-2 (eBay's format, e.g. "GB")
    phone: str | None

    def to_dict(self) -> dict:
        return {
            "contact_name": self.contact_name,
            "address_line1": self.address_line1,
            "address_line2": self.address_line2,
            "city": self.city,
            "state_or_province": self.state_or_province,
            "postal_code": self.postal_code,
            "country_code": self.country_code,
            "phone": self.phone,
        }


@dataclass(frozen=True)
class EbayOrderInfo:
    order_id: str
    line_item_id: str
    buyer_username: str
    buyer_address: BuyerAddress
    sale_price: float
    currency: str


def _parse_order(order: dict, matching_legacy_item_id: str | None = None) -> EbayOrderInfo | None:
    fulfillment_start = (order.get("fulfillmentStartInstructions") or [{}])[0]
    ship_to = fulfillment_start.get("shippingStep", {}).get("shipTo")
    if not ship_to:
        return None

    line_items = order.get("lineItems", [])
    line_item = None
    if matching_legacy_item_id:
        line_item = next((li for li in line_items if li.get("legacyItemId") == matching_legacy_item_id), None)
    if line_item is None and line_items:
        line_item = line_items[0]
    if line_item is None:
        return None

    contact = ship_to.get("contactAddress", {})
    address = BuyerAddress(
        contact_name=ship_to.get("fullName", "Unknown"),
        address_line1=contact.get("addressLine1"),
        address_line2=contact.get("addressLine2"),
        city=contact.get("city"),
        state_or_province=contact.get("stateOrProvince"),
        postal_code=contact.get("postalCode"),
        country_code=contact.get("countryCode", "GB"),
        phone=ship_to.get("primaryPhone", {}).get("phoneNumber"),
    )

    pricing_summary = order.get("pricingSummary", {})
    total = pricing_summary.get("total", {})

    return EbayOrderInfo(
        order_id=order["orderId"],
        line_item_id=line_item["lineItemId"],
        buyer_username=order.get("buyer", {}).get("username", "unknown"),
        buyer_address=address,
        sale_price=float(total.get("value", 0)),
        currency=total.get("currency", "GBP"),
    )


async def get_order(
    order_id: str, environment: str = "production", ebay_listing_id: str | None = None
) -> EbayOrderInfo:
    """Fetch a single order's real buyer address + sale price by eBay order ID.
    Pass ebay_listing_id to pick the right line item on a multi-item order —
    otherwise the first line item is used."""
    access_token = await get_valid_ebay_access_token(environment)
    base_url = _EBAY_API_BASE[environment]

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"{base_url}/sell/fulfillment/v1/order/{order_id}",
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
        log.error("ebay_order_sync.get_order_failed", status=resp.status_code, error=message, order_id=order_id)
        raise EbayOrderSyncError(message or "Failed to fetch eBay order", resp.status_code)

    parsed = _parse_order(resp.json(), matching_legacy_item_id=ebay_listing_id)
    if parsed is None:
        raise EbayOrderSyncError(f"Order {order_id} has no shipping address on file yet")
    return parsed


async def find_order_for_listing(
    ebay_listing_id: str, environment: str = "production", lookback_days: int = 90
) -> EbayOrderInfo | None:
    """Search recent orders for one containing the given listing ID, since a
    ManualBuild only stores its listing ID (not the order ID) until now.
    Returns None if no matching paid order is found — either it hasn't sold
    yet, or it sold further back than lookback_days."""
    from datetime import datetime, timedelta, timezone

    access_token = await get_valid_ebay_access_token(environment)
    base_url = _EBAY_API_BASE[environment]

    date_from = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"{base_url}/sell/fulfillment/v1/order",
            params={
                "filter": f"creationdate:[{date_from}..]",
                "limit": "50",
            },
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
        log.error("ebay_order_sync.list_orders_failed", status=resp.status_code, error=message)
        raise EbayOrderSyncError(message or "Failed to list eBay orders", resp.status_code)

    orders = resp.json().get("orders", [])
    for order in orders:
        line_items = order.get("lineItems", [])
        if any(item.get("legacyItemId") == ebay_listing_id for item in line_items):
            return _parse_order(order, matching_legacy_item_id=ebay_listing_id)
    return None
