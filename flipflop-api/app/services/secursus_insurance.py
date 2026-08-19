"""Live, price-only shipping-insurance quotes from Secursus.

This module never creates an insurance order. Purchasing cover belongs to the
post-sale shipment-booking flow, when the real buyer and delivery details exist.
Official API reference: https://developer.secursus.com/v1/parcels/fees
"""
from __future__ import annotations

from dataclasses import dataclass

import httpx
import structlog

from app.config import get_settings

log = structlog.get_logger(__name__)
_PRICE_URL = "https://developer.secursus.com/api/parcels/price"


class SecursusError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class InsuranceQuote:
    insured_value_gbp: float
    price_gbp: float
    currency: str


async def get_insurance_quote(value_gbp: float) -> InsuranceQuote:
    """Return Secursus' live premium without purchasing or reserving cover."""
    settings = get_settings()
    if not settings.secursus_api_identifier or not settings.secursus_api_secret_key:
        raise SecursusError(
            "SECURSUS_API_IDENTIFIER / SECURSUS_API_SECRET_KEY are not configured."
        )
    value_pence = round(value_gbp * 100)
    if value_pence <= 0:
        raise SecursusError("The listing value must be greater than £0.", 400)

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            _PRICE_URL,
            auth=(settings.secursus_api_identifier, settings.secursus_api_secret_key),
            data={"parcel_value": value_pence, "currency": "gbp"},
            headers={"Accept": "application/json"},
        )

    try:
        payload = response.json()
    except ValueError:
        payload = {}
    api_response = payload.get("response", {})
    if response.status_code != 200 or api_response.get("success") is False:
        detail = api_response.get("detail") or api_response.get("title") or response.text[:300]
        log.error("secursus.quote_failed", status=response.status_code, detail=detail)
        raise SecursusError(f"Secursus quote failed: {detail}", response.status_code or 502)

    data = payload.get("data", {})
    premium_pence = data.get("value")
    if premium_pence is None:
        raise SecursusError("Secursus returned a quote without a premium.", 502)
    return InsuranceQuote(
        insured_value_gbp=value_pence / 100,
        price_gbp=int(premium_pence) / 100,
        currency=str(data.get("currency", "gbp")).upper(),
    )
