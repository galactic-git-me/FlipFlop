"""Small, server-side Amazon SP-API client used by cross-listing.

The client deliberately keeps credentials and refresh-token exchange out of
the admin browser. Amazon's Listings Items API is schema-driven; this module
creates the common listing attributes and returns Amazon's validation details
when a category or approval requirement still needs seller action.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.config import get_settings


class AmazonSPAPIError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, details: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.details = details


class AmazonSPAPI:
    def __init__(self) -> None:
        settings = get_settings()
        self.client_id = settings.amazon_sp_api_client_id
        self.client_secret = settings.amazon_sp_api_client_secret
        self.refresh_token = settings.amazon_sp_api_refresh_token
        self.seller_id = settings.amazon_sp_api_seller_id
        self.marketplace_id = settings.amazon_sp_api_marketplace_id
        self.environment = settings.amazon_sp_api_environment.lower()
        self.endpoint = (
            settings.amazon_sp_api_sandbox_endpoint
            if self.environment == "sandbox"
            else settings.amazon_sp_api_endpoint
        ).rstrip("/")

    @property
    def configured(self) -> bool:
        return all((self.client_id, self.client_secret, self.refresh_token, self.seller_id, self.marketplace_id, self.endpoint))

    async def _access_token(self, client: httpx.AsyncClient) -> str:
        if not self.configured:
            raise AmazonSPAPIError("Amazon SP-API credentials are not configured on the API service.")
        response = await client.post(
            "https://api.amazon.com/auth/o2/token",
            data={
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
        )
        if response.status_code >= 400:
            raise AmazonSPAPIError("Amazon rejected the refresh token.", status_code=response.status_code, details=_json(response))
        token = response.json().get("access_token")
        if not token:
            raise AmazonSPAPIError("Amazon token response did not contain an access token.", details=_json(response))
        return token

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        timeout = httpx.Timeout(45.0, connect=15.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            token = await self._access_token(client)
            headers = {"x-amz-access-token": token, "accept": "application/json"}
            if "json" in kwargs:
                headers["content-type"] = "application/json"
            response = await client.request(method, f"{self.endpoint}{path}", headers=headers, **kwargs)
        if response.status_code >= 400:
            raise AmazonSPAPIError(
                f"Amazon SP-API returned HTTP {response.status_code}.",
                status_code=response.status_code,
                details=_json(response),
            )
        return response

    async def status(self) -> dict[str, Any]:
        response = await self._request("GET", "/sellers/v1/marketplaceParticipations")
        payload = _json(response) or {}
        participations = payload.get("payload", [])
        matching = next((item for item in participations if item.get("marketplace", {}).get("id") == self.marketplace_id), None)
        return {
            "connected": True,
            "environment": self.environment,
            "seller_id": self.seller_id,
            "marketplace_id": self.marketplace_id,
            "marketplace_found": matching is not None,
            "marketplace": matching,
        }

    async def upsert_listing(self, *, sku: str, title: str, description: str, bullet_points: list[str], price: float, quantity: int, condition: str, images: list[str]) -> dict[str, Any]:
        if not sku.strip():
            raise AmazonSPAPIError("Amazon listing SKU cannot be empty.")
        if price <= 0:
            raise AmazonSPAPIError("Amazon listing price must be greater than zero.")
        if not images or any(not url.startswith(("https://", "http://")) for url in images):
            raise AmazonSPAPIError("Amazon requires at least one publicly reachable product image URL.")

        attributes: dict[str, Any] = {
            "item_name": [{"value": title[:200], "language_tag": "en_GB", "marketplace_id": self.marketplace_id}],
            "brand": [{"value": "FlipFlop", "language_tag": "en_GB", "marketplace_id": self.marketplace_id}],
            "manufacturer": [{"value": "FlipFlop", "language_tag": "en_GB", "marketplace_id": self.marketplace_id}],
            "product_description": [{"value": description[:2000], "language_tag": "en_GB", "marketplace_id": self.marketplace_id}],
            "bullet_point": [{"value": value[:500], "language_tag": "en_GB", "marketplace_id": self.marketplace_id} for value in bullet_points[:5] if value.strip()],
            "condition_type": [{"value": _condition(condition), "marketplace_id": self.marketplace_id}],
            "fulfillment_availability": [{"fulfillment_channel_code": "DEFAULT", "quantity": max(0, quantity)}],
            "purchasable_offer": [{"currency": "GBP", "our_price": [{"schedule": [{"value_with_tax": round(price, 2)}]}], "marketplace_id": self.marketplace_id}],
            "main_product_image_locator": [{"media_location": images[0], "marketplace_id": self.marketplace_id}],
        }
        response = await self._request(
            "PUT",
            f"/listings/2021-08-01/items/{self.seller_id}/{sku}",
            params={"marketplaceIds": self.marketplace_id, "requirements": "LISTING"},
            json={"productType": get_settings().amazon_sp_api_product_type, "requirements": "LISTING", "attributes": attributes},
        )
        return _json(response) or {}


def _condition(value: str) -> str:
    normalized = value.lower().replace("_", " ")
    if "like new" in normalized or "excellent" in normalized:
        return "used_like_new"
    if "very good" in normalized:
        return "used_very_good"
    if "good" in normalized:
        return "used_good"
    return "used_acceptable"


def _json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return {"raw": response.text[:1000]}
