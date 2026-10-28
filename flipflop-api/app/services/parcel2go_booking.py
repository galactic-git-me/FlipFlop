"""Books and pays for a real courier shipment via Parcel2Go, using a buyer's
real delivery address (from app/services/ebay_order_sync.py) and a build's
saved package dimensions. This is the step that spends real money — see
app/api/manual_builds.py's book_shipment endpoint, which requires an
explicit user confirmation before calling this, never an automatic trigger.

Schema confirmed against Parcel2Go's Swagger docs (www.parcel2go.com/api/swagger)
as of 2026-08. The exact success-response shape of PayWithPrepay wasn't fully
documented in what's publicly readable — pay_order_with_prepay defensively
parses several plausible field paths for the label URL and tracking number.
Provider response bodies are not logged or retained because they may contain
buyer and delivery details.
"""
from __future__ import annotations

import math
import uuid
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx
import structlog

from app.config import get_settings
from app.services.ebay_order_sync import BuyerAddress
from app.services.parcel2go_courier import _get_access_token, _BASE_URLS

log = structlog.get_logger(__name__)


def _safe_provider_tracking_url(value: object) -> str | None:
    """Accept only bounded, credential-free HTTPS links for customer display."""
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if not candidate or len(candidate) > 1000:
        return None
    try:
        parsed = urlsplit(candidate)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
        ):
            return None
    except ValueError:
        return None
    return candidate


class Parcel2GoBookingError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class BookedShipment:
    parcel2go_order_id: str
    tracking_number: str | None
    label_url: str | None
    tracking_url: str | None


def _seller_collection_address(settings) -> dict:
    missing = [
        field
        for field in (
            "seller_forename", "seller_surname", "seller_address_street",
            "seller_address_town", "seller_address_postcode",
        )
        if not getattr(settings, field)
    ]
    if missing:
        raise Parcel2GoBookingError(
            f"Seller collection address not configured (missing: {', '.join(missing)}) — "
            "set SELLER_* fields in .env.local before booking a shipment."
        )
    return {
        "ContactName": f"{settings.seller_forename} {settings.seller_surname}",
        "Email": settings.seller_email or None,
        "Phone": settings.seller_phone or None,
        "Property": settings.seller_address_property or None,
        "Street": settings.seller_address_street,
        "Town": settings.seller_address_town,
        "County": settings.seller_address_county or None,
        "Postcode": settings.seller_address_postcode,
        "CountryIsoCode": settings.seller_address_country_iso,
    }


def _buyer_delivery_address(buyer: BuyerAddress) -> dict:
    return {
        "ContactName": buyer.contact_name,
        "Phone": buyer.phone,
        "Street": buyer.address_line1,
        "Locality": buyer.address_line2,
        "Town": buyer.city,
        "County": buyer.state_or_province,
        "Postcode": buyer.postal_code,
        # eBay returns ISO 3166-1 alpha-2 (e.g. "GB"); Parcel2Go expects
        # alpha-3 (e.g. "GBR"). Only GB is mapped for now since that's the
        # only destination this shop currently supports (see the domestic
        # -vs-remote-region pricing note in EbayShippingSection.tsx).
        "CountryIsoCode": "GBR" if buyer.country_code == "GB" else buyer.country_code,
    }


async def create_order(
    *,
    service_slug: str,
    weight_kg: float,
    length_cm: float,
    width_cm: float,
    height_cm: float,
    value_gbp: float,
    buyer_address: BuyerAddress,
    upsells: list[str],
    contents_summary: str = "PC hardware (built computer)",
    environment: str | None = None,
) -> tuple[str, str, str | None, float | None]:
    """Create an unpaid order and return its IDs and validated provider total."""
    settings = get_settings()
    env = environment or settings.parcel2go_environment
    token = await _get_access_token(env)
    base_url = _BASE_URLS[env]

    item_id = str(uuid.uuid4())
    parcel_id = str(uuid.uuid4())

    payload = {
        "Items": [
            {
                "Id": item_id,
                "Service": service_slug,
                "Upsells": [{"Type": upsell} for upsell in upsells],
                "CollectionAddress": _seller_collection_address(settings),
                "OriginCountry": settings.seller_address_country_iso,
                "VatStatus": "NotRegistered",
                "Parcels": [
                    {
                        "Id": parcel_id,
                        "Weight": round(weight_kg, 2),
                        "Length": round(length_cm, 2),
                        "Width": round(width_cm, 2),
                        "Height": round(height_cm, 2),
                        "EstimatedValue": round(value_gbp, 2),
                        "DeliveryAddress": _buyer_delivery_address(buyer_address),
                        "ContentsSummary": contents_summary,
                    }
                ],
            }
        ],
        "CustomerDetails": {
            "Email": settings.seller_email,
            "Forename": settings.seller_forename,
            "Surname": settings.seller_surname,
        },
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{base_url}/api/orders",
            json=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )

    if resp.status_code not in (200, 201):
        # The payload includes the buyer's delivery address and phone. Keep
        # provider diagnostics without copying customer data into application logs.
        log.error("parcel2go_booking.create_order_failed", status=resp.status_code)
        raise Parcel2GoBookingError(f"Parcel2Go order creation failed ({resp.status_code}).", resp.status_code)

    data = resp.json()
    order_id = data.get("OrderId")
    order_hash = data.get("Hash", "")
    if not order_id:
        raise Parcel2GoBookingError("Parcel2Go order creation returned no order reference.")

    line_map = data.get("OrderlineIdMap") or data.get("OrderLineIdMap") or []
    order_line_id = None
    if isinstance(line_map, list):
        match = next((line for line in line_map if isinstance(line, dict) and str(line.get("ItemId") or "") == item_id), None)
        if match:
            order_line_id = str(match.get("OrderLineId") or "").strip() or None

    log.info(
        "parcel2go_booking.order_created",
        order_id=order_id,
        has_order_line_id=bool(order_line_id),
        total_price=data.get("TotalPrice"),
    )
    total_price = data.get("TotalPrice")
    try:
        parsed_total_price = float(total_price)
    except (TypeError, ValueError, OverflowError):
        parsed_total_price = None
    if parsed_total_price is not None and (
        not math.isfinite(parsed_total_price) or parsed_total_price <= 0
    ):
        parsed_total_price = None
    return str(order_id), str(order_hash or ""), order_line_id, parsed_total_price


async def pay_order_with_prepay(
    order_id: str, order_hash: str = "", environment: str | None = None
) -> BookedShipment:
    """Pays for a created order from the account's Parcel2Go PrePay balance —
    the account must have sufficient balance topped up already; this call
    fails outright if it doesn't (Parcel2Go does not silently fall back to
    a card). Returns only parsed dispatch fields; provider response bodies
    are not retained because they may contain buyer and delivery details."""
    settings = get_settings()
    env = environment or settings.parcel2go_environment
    token = await _get_access_token(env)
    base_url = _BASE_URLS[env]

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{base_url}/api/orders/{order_id}/paywithprepay",
            params={"hash": order_hash} if order_hash else None,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            },
        )

    if resp.status_code not in (200, 201):
        log.error(
            "parcel2go_booking.payment_failed",
            status=resp.status_code,
            order_id=order_id,
        )
        raise Parcel2GoBookingError(
            f"Parcel2Go payment failed ({resp.status_code}).",
            resp.status_code,
        )

    data = resp.json()
    links = data.get("Links", [])

    label_url = None
    tracking_number = None
    tracking_url = None
    for link in links:
        rel = (link.get("Rel") or link.get("rel") or "").lower()
        href = link.get("Href") or link.get("href")
        if "label" in rel:
            label_url = href
        if "track" in rel:
            tracking_number = link.get("TrackingNumber") or link.get("trackingNumber")
            tracking_url = _safe_provider_tracking_url(href)

    if not tracking_number:
        # Fall back: some Parcel2Go responses carry tracking numbers per-parcel
        # rather than in Links — check common alternate locations.
        tracking_number = data.get("TrackingNumber") or data.get("trackingNumber")

    log.info(
        "parcel2go_booking.paid",
        order_id=order_id,
        has_label_url=bool(label_url),
        has_tracking_number=bool(tracking_number),
    )

    return BookedShipment(
        parcel2go_order_id=order_id,
        tracking_number=tracking_number,
        label_url=label_url,
        tracking_url=tracking_url,
    )
