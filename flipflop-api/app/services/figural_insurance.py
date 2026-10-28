"""Live, price-only shipping-insurance quotes from the Figural API.

This module never creates an insurance order. Purchasing cover belongs to the
post-sale shipment-booking flow, when the real buyer and delivery details exist.
Official API reference: https://developer.figural.com/api#operation/getPrice
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

import httpx
import structlog

from app.config import get_settings

log = structlog.get_logger(__name__)
_PRICE_URL = "https://api.figural.com/v2/parcel/get_price"
_CREATE_PARCEL_URL = "https://developer.secursus.com/api/parcels/new"


class FiguralError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class InsuranceQuote:
    insured_value_gbp: float
    price_gbp: float
    currency: str


@dataclass(frozen=True)
class InsurancePolicy:
    policy_id: str
    invoice_id: str | None
    insured_value_gbp: float
    price_gbp: float
    currency: str
    mode: str | None


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


async def create_insurance_policy(payload: dict[str, Any]) -> InsurancePolicy:
    """Create/register one Secursus/Figural parcel after an explicit admin action.

    Live creation is disabled by default. The service intentionally has no
    retry loop because a timeout can occur after the provider creates a paid
    policy; callers must reconcile an uncertain result before retrying.
    """
    settings = get_settings()
    if not settings.secursus_live_parcel_creation_enabled:
        raise FiguralError("Live insurance policy creation is disabled until the provider account is approved.", 409)
    api_key = settings.secursus_api_identifier
    api_secret = settings.secursus_api_secret_key
    if not api_key or not api_secret:
        raise FiguralError("The Figural/Secursus API key and secret are not configured.", 503)
    required = {"parcel_value", "first_name", "last_name", "email", "full_address", "country_origin", "country_destination", "cart_data"}
    missing = sorted(field for field in required if not payload.get(field))
    if missing:
        raise FiguralError(f"Missing required insurer fields: {', '.join(missing)}", 400)

    form_data = dict(payload)
    form_data["currency"] = "gbp"
    form_data["send_email"] = "false"
    form_data["lang"] = "en"
    form_data["cart_data"] = json.dumps(payload["cart_data"], ensure_ascii=False, separators=(",", ":"))
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                _CREATE_PARCEL_URL,
                auth=(api_key, api_secret),
                data=form_data,
                headers={"Accept": "application/json"},
            )
    except httpx.RequestError as error:
        log.error("figural.policy_creation_transport_uncertain", error=str(error))
        raise FiguralError("The insurer request outcome is uncertain. Do not retry until the provider account is checked.", 502) from error

    try:
        response_payload = response.json()
    except ValueError:
        response_payload = {}
    api_response = response_payload.get("response", {})
    if response.status_code != 200 or api_response.get("success") is False:
        # Provider error bodies can echo submitted customer details. Keep the
        # durable application log free of raw response data and let the admin
        # reconcile the provider account using the HTTP status only.
        log.error("figural.policy_creation_failed", status=response.status_code)
        raise FiguralError(
            f"Figural policy creation failed (HTTP {response.status_code}). Check the provider account before retrying.",
            response.status_code if response.status_code < 500 else 502,
        )

    data = response_payload.get("data", {})
    attributes = data.get("attributes", {})
    policy_id = data.get("id")
    if not policy_id:
        log.error(
            "figural.policy_creation_missing_id",
            status=response.status_code,
            response_fields=sorted(str(key) for key in data.keys())[:30],
        )
        raise FiguralError("Insurer response did not include a policy ID; reconcile the account before retrying.", 502)
    return InsurancePolicy(
        policy_id=str(policy_id),
        invoice_id=str(attributes["invoice_id"]) if attributes.get("invoice_id") else None,
        insured_value_gbp=float(attributes.get("parcel_value", 0)) / 100,
        price_gbp=float(attributes.get("price", 0)) / 100,
        currency=str(attributes.get("currency", "gbp")).upper(),
        mode=str(attributes.get("mode")) if attributes.get("mode") is not None else None,
    )
