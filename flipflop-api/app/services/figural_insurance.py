"""Live, price-only shipping-insurance quotes from the Figural API.

This module never creates an insurance order. Purchasing cover belongs to the
post-sale shipment-booking flow, when the real buyer and delivery details exist.
Official API reference: https://developer.figural.com/api#operation/getPrice
"""
from __future__ import annotations

from dataclasses import dataclass

import httpx
import structlog

from app.config import get_settings

log = structlog.get_logger(__name__)
_PRICE_URL = "https://api.figural.com/v2/parcel/get_price"


class FiguralError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class InsuranceQuote:
    insured_value_gbp: float
    price_gbp: float
    currency: str


async def get_insurance_quote(value_gbp: float) -> InsuranceQuote:
    """Return Figural's live premium without purchasing or reserving cover."""
    settings = get_settings()
    api_key = settings.secursus_api_identifier
    api_secret = settings.secursus_api_secret_key
    if not api_key or not api_secret:
        raise FiguralError("The Figural API key and secret are not configured.")
    value_pence = round(value_gbp * 100)
    if value_pence <= 0:
        raise FiguralError("The listing value must be greater than £0.", 400)

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            _PRICE_URL,
            auth=(api_key, api_secret),
            json={"parcel_value": value_pence, "currency": "gbp"},
            headers={"Accept": "application/json"},
        )

    try:
        payload = response.json()
    except ValueError:
        payload = {}
    api_response = payload.get("response", {})
    if response.status_code != 200 or api_response.get("success") is False:
        detail = api_response.get("detail") or api_response.get("title") or response.text[:300]
        log.error("figural.quote_failed", status=response.status_code, detail=detail)
        raise FiguralError(f"Figural quote failed: {detail}", response.status_code or 502)

    data = payload.get("data", {})
    premium_pence = data.get("value")
    if premium_pence is None:
        raise FiguralError("Figural returned a quote without a premium.", 502)
    return InsuranceQuote(
        insured_value_gbp=value_pence / 100,
        price_gbp=int(premium_pence) / 100,
        currency=str(data.get("currency", "gbp")).upper(),
    )
