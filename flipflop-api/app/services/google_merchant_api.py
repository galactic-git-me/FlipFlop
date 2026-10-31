"""Google Merchant API adapter for the single FlipFlop Merchant Center.

Authentication uses a Google service account. Product inputs are keyed by
build SKU, replaced idempotently on updates, and removed when that physical
build sells or is withdrawn. Google evaluates submitted products separately;
an accepted input is not a promise of approval or Shopping visibility.
"""
from __future__ import annotations

import asyncio
import hashlib
import html
import ipaddress
import json
import logging
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import service_account

from app.config import get_settings

log = logging.getLogger(__name__)

MERCHANT_API_ROOT = "https://merchantapi.googleapis.com"
MERCHANT_SCOPE = "https://www.googleapis.com/auth/content"


class GoogleMerchantError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class MerchantSubmission:
    offer_id: str
    input_name: str
    product_url: str
    payload_hash: str
    selected_images: list[str]
    response: dict[str, Any]


def _plain_text(value: str) -> str:
    without_tags = re.sub(r"<[^>]*>", " ", value or "")
    return re.sub(r"\s+", " ", html.unescape(without_tags)).strip()


def _public_https_url(value: str) -> bool:
    parsed = urlparse(value.strip())
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        return False
    hostname = parsed.hostname.rstrip(".").lower()
    if hostname == "localhost" or hostname.endswith((".localhost", ".local", ".internal")):
        return False
    try:
        return ipaddress.ip_address(hostname).is_global
    except ValueError:
        return "." in hostname


def product_input_for_build(
    build: Any,
    product_id: int,
    settings: Any | None = None,
    image_urls: list[str] | None = None,
    availability: str = "IN_STOCK",
) -> tuple[dict[str, Any], str]:
    """Build a truthful UK product input from a live canonical build."""
    settings = settings or get_settings()
    if getattr(build, "status", "") == "sold":
        raise GoogleMerchantError("Sold builds cannot be submitted to Merchant Center.")
    if not product_id:
        raise GoogleMerchantError("Publish the FlipFlop.shop product first so Google has a purchasable product page.")

    price = getattr(build, "ebay_price", None)
    if price is None or price <= 0:
        raise GoogleMerchantError("Set a saved listing price before submitting this build to Merchant Center.")
    amount = Decimal(str(price)).quantize(Decimal("0.01"))
    if not amount.is_finite() or amount <= 0:
        raise GoogleMerchantError("The saved listing price is invalid.")

    title = (getattr(build, "generated_title", None) or getattr(build, "name", "")).strip()
    description = _plain_text(getattr(build, "generated_description", None) or "")
    if not title or not description:
        raise GoogleMerchantError("A listing title and description are required.")
    photos = [
        str(photo.get("url", "")).strip()
        for photo in (getattr(build, "photos", None) or [])
        if isinstance(photo, dict) and photo.get("kind", "photo") == "photo"
    ]
    hero = (getattr(build, "hero_photo_url", None) or "").strip()
    chosen_images = list(dict.fromkeys(image_urls or (([hero] if hero else []) + photos)))
    if not chosen_images or len(chosen_images) > 10 or not all(_public_https_url(url) for url in chosen_images):
        raise GoogleMerchantError("At least one publicly reachable HTTPS product image is required; local/private image URLs cannot be sent to Google.")

    condition_raw = (getattr(build, "ebay_condition", None) or "").strip().lower()
    if "new" in condition_raw:
        condition = "NEW"
    elif "used" in condition_raw or "second" in condition_raw or not condition_raw:
        condition = "USED"
    else:
        raise GoogleMerchantError("The saved item condition cannot be mapped safely to Google's NEW or USED values.")

    origin = settings.google_merchant_store_url.rstrip("/")
    product_url = f"{origin}/builds/{int(product_id)}"
    offer_id = f"FF-BUILD-{int(build.id)}"
    attrs: dict[str, Any] = {
        "title": title[:150],
        "description": description[:5000],
        "link": product_url,
        "imageLink": chosen_images[0],
        "availability": availability,
        "price": {"amountMicros": str(int(amount * 1_000_000)), "currencyCode": "GBP"},
        "condition": condition,
        "identifierExists": False,
    }
    if len(chosen_images) > 1:
        attrs["additionalImageLinks"] = chosen_images[1:11]

    payload = {
        "contentLanguage": settings.google_merchant_content_language,
        "feedLabel": settings.google_merchant_feed_label,
        "offerId": offer_id,
        "productAttributes": attrs,
    }
    fingerprint = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return payload, fingerprint


class GoogleMerchantAPI:
    def __init__(self, settings: Any | None = None, client: httpx.AsyncClient | None = None):
        self.settings = settings or get_settings()
        self.client = client
        self.account_id = str(self.settings.google_merchant_account_id or "").strip()
        self.data_source_id = str(self.settings.google_merchant_data_source_id or "").strip()
        self.key_file = str(self.settings.google_merchant_service_account_file or "").strip()
        self.key_json = str(self.settings.google_merchant_service_account_json or "").strip()

    @property
    def configured(self) -> bool:
        return bool(self.account_id and self.data_source_id and (self.key_json or (self.key_file and Path(self.key_file).is_file())))

    @property
    def enabled_for_writes(self) -> bool:
        runtime = str(__import__("os").getenv("FLIPFLOP_RUNTIME_ENV", "development")).lower()
        return self.configured and bool(self.settings.google_merchant_writes_enabled) and runtime in {
            "live", "production", "prod"
        }

    def _credentials(self):
        if self.key_json:
            try:
                info = json.loads(self.key_json)
                return service_account.Credentials.from_service_account_info(info, scopes=[MERCHANT_SCOPE])
            except (ValueError, TypeError) as exc:
                raise GoogleMerchantError("The configured Google Merchant service-account JSON is invalid.") from exc
        if not self.key_file or not Path(self.key_file).is_file():
            raise GoogleMerchantError("Google Merchant service-account credentials are not configured.")
        try:
            return service_account.Credentials.from_service_account_file(
                self.key_file, scopes=[MERCHANT_SCOPE]
            )
        except (OSError, ValueError) as exc:
            raise GoogleMerchantError("The configured Google Merchant service-account file is invalid.") from exc

    async def _access_token(self) -> str:
        credentials = self._credentials()
        if not credentials.valid:
            try:
                await asyncio.to_thread(credentials.refresh, GoogleAuthRequest())
            except Exception as exc:
                raise GoogleMerchantError("Could not obtain a Google Merchant API access token.") from exc
        if not credentials.token:
            raise GoogleMerchantError("Google did not return an access token.")
        return credentials.token

    async def _request(self, method: str, path: str, *, params: dict[str, str] | None = None, body: dict | None = None) -> dict[str, Any]:
        if not self.account_id:
            raise GoogleMerchantError("Set GOOGLE_MERCHANT_ACCOUNT_ID on the API service.")
        token = await self._access_token()
        own_client = self.client is None
        client = self.client or httpx.AsyncClient(timeout=30)
        try:
            response = await client.request(
                method,
                f"{MERCHANT_API_ROOT}{path}",
                params=params,
                json=body,
                headers={"Authorization": f"Bearer {token}"},
            )
        except httpx.HTTPError as exc:
            raise GoogleMerchantError("Google Merchant API could not be reached.") from exc
        finally:
            if own_client:
                await client.aclose()
        if response.is_error:
            detail = ""
            try:
                error_data = response.json().get("error", {})
                detail = str(error_data.get("message", ""))[:300]
            except (ValueError, AttributeError):
                pass
            log.warning("google_merchant_api.request_failed", extra={"status": response.status_code, "path": path, "detail": detail})
            raise GoogleMerchantError(
                f"Google Merchant API rejected the request{(': ' + detail) if detail else '.'}",
                response.status_code,
            )
        if response.status_code == 204 or not response.content:
            return {}
        try:
            return response.json()
        except ValueError as exc:
            raise GoogleMerchantError("Google Merchant API returned an unreadable response.", response.status_code) from exc

    async def verify_connection(self) -> dict[str, Any]:
        if not self.account_id or not (self.key_json or (self.key_file and Path(self.key_file).is_file())):
            return {"configured": False, "connected": False, "writes_enabled": False, "message": "Merchant Center account ID and service-account credentials are required."}
        try:
            await self._access_token()
            if not self.data_source_id:
                return {"configured": True, "connected": False, "writes_enabled": False, "message": "API credentials work; create an API product data source and set GOOGLE_MERCHANT_DATA_SOURCE_ID."}
            await self._request(
                "GET",
                f"/datasources/v1/accounts/{self.account_id}/dataSources/{self.data_source_id}",
            )
            return {
                "configured": True,
                "connected": True,
                "writes_enabled": self.enabled_for_writes,
                "account_id": self.account_id,
                "data_source_id": self.data_source_id,
                "message": None if self.enabled_for_writes else "Merchant API is connected, but product writes are disabled for this runtime.",
            }
        except GoogleMerchantError as exc:
            return {"configured": True, "connected": False, "writes_enabled": False, "account_id": self.account_id, "message": str(exc), "status_code": exc.status_code}

    async def create_primary_data_source(self) -> dict[str, Any]:
        if not self.account_id:
            raise GoogleMerchantError("Set GOOGLE_MERCHANT_ACCOUNT_ID before creating the Merchant Center data source.")
        return await self._request(
            "POST",
            f"/datasources/v1/accounts/{self.account_id}/dataSources",
            body={
                "displayName": "FlipFlop API inventory",
                "primaryProductDataSource": {"countries": ["GB"]},
            },
        )

    async def upsert_build(
        self,
        build: Any,
        image_urls: list[str] | None = None,
        availability: str = "IN_STOCK",
    ) -> MerchantSubmission:
        if not self.enabled_for_writes:
            raise GoogleMerchantError("Google Merchant writes are not enabled in this LIVE API environment.")
        product_id = getattr(build, "storefront_product_id", None)
        payload, fingerprint = product_input_for_build(
            build, product_id, self.settings, image_urls, availability
        )
        source_name = f"accounts/{self.account_id}/dataSources/{self.data_source_id}"
        response = await self._request(
            "POST",
            f"/products/v1/accounts/{self.account_id}/productInputs:insert",
            params={"dataSource": source_name},
            body=payload,
        )
        input_name = str(response.get("name") or "")
        if not input_name:
            input_name = f"accounts/{self.account_id}/productInputs/{payload['contentLanguage']}~{payload['feedLabel']}~{payload['offerId']}"
        selected_images = [payload["productAttributes"]["imageLink"], *payload["productAttributes"].get("additionalImageLinks", [])]
        return MerchantSubmission(
            offer_id=payload["offerId"],
            input_name=input_name,
            product_url=payload["productAttributes"]["link"],
            payload_hash=fingerprint,
            selected_images=selected_images,
            response=response,
        )

    async def delete_build(self, build: Any) -> bool:
        """Remove the Google product input; a missing input is already in sync."""
        return await self.delete_offer_id(f"FF-BUILD-{int(build.id)}")

    async def delete_offer_id(self, offer_id: str) -> bool:
        """Remove an input even if its local build row was archived or lost."""
        if not self.enabled_for_writes:
            raise GoogleMerchantError("Google Merchant writes are not enabled in this LIVE API environment.")
        product_input_id = "~".join(
            [self.settings.google_merchant_content_language, self.settings.google_merchant_feed_label, offer_id]
        )
        try:
            await self._request(
                "DELETE",
                f"/products/v1/accounts/{self.account_id}/productInputs/{product_input_id}",
                params={"dataSource": f"accounts/{self.account_id}/dataSources/{self.data_source_id}"},
            )
            return True
        except GoogleMerchantError as exc:
            if exc.status_code == 404:
                return False
            raise
