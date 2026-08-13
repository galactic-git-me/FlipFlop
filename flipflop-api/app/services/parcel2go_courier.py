"""Real-time courier quotes via Parcel2Go's API, for pricing a build's
actual tracked-delivery cost from its physical package dimensions rather
than a hand-guessed flat rate — used by the build sell page so the asking
price can bake in real shipping cost (see the free-delivery pricing
discussion this was built for: fold the real courier cost into the price
and offer free postage, rather than showing it as a separate charge).

Auth: OAuth2 client_credentials grant (PARCEL2GO_CLIENT_ID/SECRET in
.env.local — see app/config.py). Docs: https://api-docs.parcel2go.com/

Deliberately does NOT guess a build's weight/dimensions — those come from
whatever the caller passes in (see ManualBuild.package_weight_kg etc.),
same reasoning as why the eBay Item Specifics generator never invents
Screen Size / Item Length / Item Width: a wrong physical measurement
reaching a real courier booking or a real listing is worse than requiring
it to be entered once per build.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime

import httpx
import structlog

from app.config import get_settings

log = structlog.get_logger(__name__)


def _estimate_delivery_days(collection_iso: str | None, delivery_iso: str | None) -> int | None:
    """Derives a day count from Parcel2Go's Collection/EstimatedDeliveryDate
    timestamps — the API doesn't return a pre-computed day count directly."""
    if not collection_iso or not delivery_iso:
        return None
    try:
        collection = datetime.fromisoformat(collection_iso)
        delivery = datetime.fromisoformat(delivery_iso)
        return max((delivery - collection).days, 0)
    except (ValueError, TypeError):
        return None

_BASE_URLS = {
    "sandbox": "https://sandbox.parcel2go.com",
    "production": "https://www.parcel2go.com",
}

# In-memory token cache — client_credentials tokens are short-lived (~1h)
# and re-fetching per request would add real latency to every quote call.
# Module-level is fine here: this process only ever talks to one
# Parcel2Go account (whichever environment is configured), same pattern as
# app/gem_radar/cpk_extractor's simpler in-memory caches.
_token_cache: dict[str, tuple[str, float]] = {}
_TOKEN_REFRESH_MARGIN_SECONDS = 60


class Parcel2GoError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class CourierQuote:
    courier_name: str
    service_name: str
    price_gbp: float
    tracked: bool
    estimated_days: int | None
    # Slug identifying this exact service (e.g. "dpd-drop-off") — required
    # by Parcel2Go's order-creation endpoint (Items[].Service) to book this
    # specific quoted service. See app/services/parcel2go_booking.py.
    service_slug: str


async def _get_access_token(environment: str) -> str:
    settings = get_settings()
    if not settings.parcel2go_client_id or not settings.parcel2go_client_secret:
        raise Parcel2GoError(
            "PARCEL2GO_CLIENT_ID / PARCEL2GO_CLIENT_SECRET not set in .env.local — "
            "create credentials at https://www.parcel2go.com/myaccount/api"
        )

    cached = _token_cache.get(environment)
    if cached is not None:
        token, expires_at = cached
        if time.monotonic() < expires_at - _TOKEN_REFRESH_MARGIN_SECONDS:
            return token

    base_url = _BASE_URLS[environment]
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{base_url}/auth/connect/token",
            data={
                "grant_type": "client_credentials",
                "client_id": settings.parcel2go_client_id,
                "client_secret": settings.parcel2go_client_secret,
                "scope": "public-api",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    if resp.status_code != 200:
        log.error("parcel2go.auth_failed", status=resp.status_code, body=resp.text[:500])
        raise Parcel2GoError(f"Parcel2Go auth failed ({resp.status_code}): {resp.text[:300]}", resp.status_code)

    data = resp.json()
    token = data["access_token"]
    expires_in = data.get("expires_in", 3600)
    _token_cache[environment] = (token, time.monotonic() + expires_in)
    return token


async def get_cheapest_tracked_quote(
    weight_kg: float,
    length_cm: float,
    width_cm: float,
    height_cm: float,
    value_gbp: float,
    delivery_country: str = "GBR",
    environment: str | None = None,
) -> CourierQuote | None:
    """Returns the cheapest TRACKED service quote, or None if no tracked
    service is available for these dimensions/destination. Untracked
    services are deliberately excluded — see the free-delivery pricing
    discussion this was built for: for anything of real value (a built PC
    is always well above the threshold where untracked is a bad idea),
    tracked is the only option worth quoting."""
    settings = get_settings()
    env = environment or settings.parcel2go_environment
    token = await _get_access_token(env)
    base_url = _BASE_URLS[env]

    payload = {
        "CollectionAddress": {"Country": "GBR"},
        "DeliveryAddress": {"Country": delivery_country},
        "Parcels": [
            {
                "Value": value_gbp,
                "Weight": weight_kg,
                "Length": length_cm,
                "Width": width_cm,
                "Height": height_cm,
            }
        ],
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{base_url}/api/quotes",
            json=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )

    if resp.status_code != 200:
        error_body = resp.text[:500]
        log.error("parcel2go.quote_failed", status=resp.status_code, body=error_body,
                  payload=payload)
        # Try to extract detailed error from response
        try:
            error_data = resp.json()
            error_msg = error_data.get("Message") or error_data.get("message") or error_data.get("error")
            if error_msg:
                error_body = error_msg
        except:
            pass
        raise Parcel2GoError(f"Parcel2Go quote failed ({resp.status_code}): {error_body}", resp.status_code)

    data = resp.json()
    quotes = data.get("Quotes", data.get("quotes", []))

    # Parcel2Go's quote response has no explicit tracked/untracked flag —
    # every service this account's quote endpoint returns (Parcelforce, UPS,
    # DPD, TNT, Yodel, etc.) is a standard tracked UK courier, so all
    # returned quotes are treated as tracked. Courier/service name live
    # under the nested "Service" object, not at the quote's top level.
    parsed_quotes: list[CourierQuote] = []
    for q in quotes:
        service = q.get("Service", {})
        price = q.get("TotalPrice")
        if price is None:
            continue
        estimated_days = _estimate_delivery_days(q.get("Collection"), q.get("EstimatedDeliveryDate"))
        parsed_quotes.append(
            CourierQuote(
                courier_name=service.get("CourierName", "Unknown courier"),
                service_name=service.get("Name", "Tracked"),
                price_gbp=float(price),
                tracked=True,
                estimated_days=estimated_days,
                service_slug=service.get("Slug", ""),
            )
        )

    if not parsed_quotes:
        return None
    return min(parsed_quotes, key=lambda q: q.price_gbp)
