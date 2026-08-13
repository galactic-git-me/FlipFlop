"""Marks an eBay order as dispatched with a real tracking number, once a
Parcel2Go shipment has actually been booked and paid for (see
app/services/parcel2go_booking.py). This is what makes the buyer see
tracking info and satisfies eBay's dispatch-time policy — nothing else in
this codebase does that.

Docs: https://developer.ebay.com/api-docs/sell/fulfillment/resources/order/shipping_fulfillment/methods/createShippingFulfillment
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

# eBay's shippingCarrierCode enum only recognizes specific values — an
# unrecognized courier name falls back to "OTHER" rather than guessing at
# a spelling/casing that might reject the whole request. The tracking
# number itself is unaffected by this, and eBay/buyers can usually still
# resolve tracking from the number's format regardless of the code sent.
_CARRIER_CODE_MAP = {
    "royal mail": "ROYAL_MAIL",
    "parcelforce": "PARCELFORCE",
    "dpd": "DPD",
    "ups": "UPS",
    "tnt": "TNT",
    "dhl": "DHL",
    "fedex": "FEDEX",
    "yodel": "YODEL",
    "hermes": "HERMES",
    "myhermes": "HERMES",
}


def _carrier_code_for(courier_name: str) -> str:
    return _CARRIER_CODE_MAP.get(courier_name.strip().lower(), "OTHER")


class EbayShippingFulfillmentError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


async def mark_order_shipped(
    order_id: str,
    line_item_id: str,
    tracking_number: str,
    courier_name: str,
    environment: str = "production",
    quantity: int = 1,
) -> dict:
    """Pushes tracking info to eBay so the buyer sees it and the order is
    marked dispatched. Raises on failure — callers should surface this
    clearly, since a failed push here means Parcel2Go got paid but eBay
    (and the buyer) never found out."""
    access_token = await get_valid_ebay_access_token(environment)
    base_url = _EBAY_API_BASE[environment]

    payload = {
        "lineItems": [{"lineItemId": line_item_id, "quantity": quantity}],
        "trackingNumber": tracking_number,
        "shippingCarrierCode": _carrier_code_for(courier_name),
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{base_url}/sell/fulfillment/v1/order/{order_id}/shipping_fulfillment",
            json=payload,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )

    if resp.status_code not in (200, 201):
        try:
            error_json = resp.json()
            errors = error_json.get("errors", [])
            message = errors[0].get("longMessage") or errors[0].get("message") if errors else resp.text
        except Exception:
            message = resp.text
        log.error(
            "ebay_shipping_fulfillment.push_failed",
            status=resp.status_code, error=message, order_id=order_id, tracking_number=tracking_number,
        )
        raise EbayShippingFulfillmentError(message or "Failed to mark eBay order as shipped", resp.status_code)

    log.info("ebay_shipping_fulfillment.pushed", order_id=order_id, tracking_number=tracking_number)
    return resp.json()
