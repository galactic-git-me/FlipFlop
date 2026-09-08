"""
eBay 3-legged seller OAuth — unblocks every live eBay write this app makes
(posting/ending/republishing listings, pushing Business Policies, creating
Promoted Listings campaigns, polling buyer messages). Distinct from
`_get_app_token` in ebay_compliance.py, which is client-credentials
(app-only) and can only do read-only Browse/search calls.

Flow (eBay's OAuth quirk: the authorize URL's `redirect_uri` param is
actually your app's registered RuName from the eBay Developer Portal, not a
literal URL — the portal maps the RuName to the real callback URL
server-side):

  1. GET /api/ebay/oauth/authorize-url -> user visits it, logs into eBay,
     consents to the scopes below.
  2. eBay redirects to the registered callback with ?code=...
  3. GET /api/ebay/oauth/callback exchanges the code for an access_token
     (~2h) + refresh_token (~18mo) and stores both on AppSettings.
  4. get_valid_access_token(db) is what every live-write call site should
     use — returns the cached access token if still valid, transparently
     refreshes via the refresh_token if expired, or None if never connected.

Not verifiable against live eBay from this environment (no network egress
to any eBay domain here) — tested against mocked HTTP responses matching
eBay's documented OAuth2 token-endpoint contract.
"""
from __future__ import annotations

import base64
import hashlib
import urllib.parse
from datetime import datetime, timedelta
from typing import Optional

import httpx
import structlog
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.api.ebay_compliance import _ebay_api_root

log = structlog.get_logger(__name__)

# Scopes needed across every live-write feature this app has: Inventory
# (post/end/republish listings), Account (Business Policies), Marketing
# (Promoted Listings campaigns). Trading API calls (legacy, e.g. message
# polling / Best Offer response) accept the same OAuth token via IAF auth.
SCOPES = [
    "https://api.ebay.com/oauth/api_scope/sell.inventory",
    "https://api.ebay.com/oauth/api_scope/sell.account",
    "https://api.ebay.com/oauth/api_scope/sell.marketing",
    "https://api.ebay.com/oauth/api_scope/sell.fulfillment",
]

_AUTH_ROOT = {
    "production": "https://auth.ebay.com",
    "sandbox": "https://auth.sandbox.ebay.com",
}

# Refresh 5 minutes before actual expiry to avoid a race where a call starts
# with a token that expires mid-flight.
_REFRESH_SKEW = timedelta(minutes=5)
_ENCRYPTED_PREFIX = "enc:v1:"


class EbayOAuthError(Exception):
    pass


def _token_cipher() -> Fernet:
    """Build a stable application cipher without ever persisting raw key material."""
    settings = get_settings()
    key_material = (
        settings.ebay_token_encryption_key
        or settings.ebay_client_secret
        or settings.secret_key
    )
    if not key_material or key_material == "dev-secret-key-change-in-production":
        raise EbayOAuthError(
            "Configure EBAY_TOKEN_ENCRYPTION_KEY, EBAY_CLIENT_SECRET, or a production SECRET_KEY"
        )
    key = base64.urlsafe_b64encode(hashlib.sha256(key_material.encode("utf-8")).digest())
    return Fernet(key)


def _encrypt_token(token: str) -> str:
    if not token:
        return ""
    if token.startswith(_ENCRYPTED_PREFIX):
        return token
    encrypted = _token_cipher().encrypt(token.encode("utf-8")).decode("ascii")
    return f"{_ENCRYPTED_PREFIX}{encrypted}"


def _decrypt_token(token: str) -> tuple[str, bool]:
    """Return plaintext plus whether a legacy plaintext value needs migration."""
    if not token:
        return "", False
    if not token.startswith(_ENCRYPTED_PREFIX):
        return token, True
    try:
        plaintext = _token_cipher().decrypt(
            token.removeprefix(_ENCRYPTED_PREFIX).encode("ascii")
        )
    except (InvalidToken, ValueError) as exc:
        raise EbayOAuthError("Stored eBay OAuth token could not be decrypted") from exc
    return plaintext.decode("utf-8"), False


def _basic_auth_header() -> str:
    settings = get_settings()
    creds = f"{settings.ebay_app_id}:{settings.ebay_client_secret}".encode("utf-8")
    return base64.b64encode(creds).decode("ascii")


def build_authorize_url() -> str:
    """Row-agnostic: the URL to send the seller to for one-time consent."""
    settings = get_settings()
    root = _AUTH_ROOT.get(settings.ebay_environment, _AUTH_ROOT["production"])
    params = {
        "client_id": settings.ebay_app_id,
        "redirect_uri": settings.ebay_ru_name,
        "response_type": "code",
        "scope": " ".join(SCOPES),
    }
    return f"{root}/oauth2/authorize?{urllib.parse.urlencode(params)}"


async def exchange_code_for_tokens(code: str) -> dict:
    """Step 3: trade the authorize-callback's ?code= for access + refresh tokens."""
    settings = get_settings()
    root = _ebay_api_root()
    headers = {
        "Authorization": f"Basic {_basic_auth_header()}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.ebay_ru_name,
    }
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(f"{root}/identity/v1/oauth2/token", data=data, headers=headers)
    if resp.status_code != 200:
        log.error("ebay_oauth.exchange_failed", status=resp.status_code, body=resp.text[:400])
        raise EbayOAuthError(f"eBay token exchange failed: {resp.status_code} {resp.text[:200]}")
    return resp.json()


async def refresh_access_token(refresh_token: str) -> dict:
    """Re-derive a fresh access token from the long-lived refresh token, no user interaction needed."""
    root = _ebay_api_root()
    headers = {
        "Authorization": f"Basic {_basic_auth_header()}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "scope": " ".join(SCOPES),
    }
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(f"{root}/identity/v1/oauth2/token", data=data, headers=headers)
    if resp.status_code != 200:
        log.error("ebay_oauth.refresh_failed", status=resp.status_code, body=resp.text[:400])
        raise EbayOAuthError(f"eBay token refresh failed: {resp.status_code} {resp.text[:200]}")
    return resp.json()


async def store_tokens_from_exchange(db: AsyncSession, payload: dict) -> None:
    """Persists the result of exchange_code_for_tokens onto AppSettings."""
    from app.models.app_settings import AppSettings
    from sqlalchemy import select

    result = await db.execute(select(AppSettings).where(AppSettings.name == "default"))
    settings_row = result.scalar_one_or_none()
    if not settings_row:
        settings_row = AppSettings(name="default")
        db.add(settings_row)

    now = datetime.utcnow()
    settings_row.ebay_seller_access_token = _encrypt_token(payload["access_token"])
    settings_row.ebay_seller_access_token_expires_at = now + timedelta(seconds=int(payload.get("expires_in", 7200)))
    settings_row.ebay_seller_refresh_token = _encrypt_token(payload["refresh_token"])
    settings_row.ebay_seller_refresh_token_expires_at = now + timedelta(
        seconds=int(payload.get("refresh_token_expires_in", 47304000))
    )
    settings_row.ebay_seller_connected_at = now
    settings_row.ebay_seller_scopes = payload.get("scope", " ".join(SCOPES))
    await db.flush()


async def get_valid_access_token(db: AsyncSession) -> Optional[str]:
    """
    The one function every live-write call site should use instead of reading
    a static token. Returns a valid access token — refreshing transparently
    via the stored refresh_token if the cached one has expired — or None if
    the seller has never completed the "Connect eBay" consent flow.
    """
    from app.models.app_settings import AppSettings
    from sqlalchemy import select

    result = await db.execute(select(AppSettings).where(AppSettings.name == "default"))
    settings_row = result.scalar_one_or_none()
    if not settings_row or not settings_row.ebay_seller_refresh_token:
        return None

    now = datetime.utcnow()
    expires_at = settings_row.ebay_seller_access_token_expires_at
    if settings_row.ebay_seller_access_token and expires_at and now < expires_at - _REFRESH_SKEW:
        access_token, needs_migration = _decrypt_token(settings_row.ebay_seller_access_token)
        if needs_migration:
            settings_row.ebay_seller_access_token = _encrypt_token(access_token)
            await db.flush()
        return access_token

    # Access token missing/expiring soon — refresh via the long-lived refresh_token.
    if settings_row.ebay_seller_refresh_token_expires_at and now >= settings_row.ebay_seller_refresh_token_expires_at:
        log.warning("ebay_oauth.refresh_token_expired", connected_at=settings_row.ebay_seller_connected_at)
        return None

    try:
        refresh_token, refresh_needs_migration = _decrypt_token(settings_row.ebay_seller_refresh_token)
        if refresh_needs_migration:
            settings_row.ebay_seller_refresh_token = _encrypt_token(refresh_token)
        payload = await refresh_access_token(refresh_token)
    except EbayOAuthError as exc:
        log.warning("ebay_oauth.auto_refresh_failed", error=str(exc))
        return None

    settings_row.ebay_seller_access_token = _encrypt_token(payload["access_token"])
    settings_row.ebay_seller_access_token_expires_at = now + timedelta(seconds=int(payload.get("expires_in", 7200)))
    await db.flush()
    return payload["access_token"]


async def disconnect(db: AsyncSession) -> None:
    from app.models.app_settings import AppSettings
    from sqlalchemy import select

    result = await db.execute(select(AppSettings).where(AppSettings.name == "default"))
    settings_row = result.scalar_one_or_none()
    if settings_row:
        settings_row.ebay_seller_access_token = ""
        settings_row.ebay_seller_access_token_expires_at = None
        settings_row.ebay_seller_refresh_token = ""
        settings_row.ebay_seller_refresh_token_expires_at = None
        settings_row.ebay_seller_connected_at = None
        settings_row.ebay_seller_scopes = ""
        await db.flush()


async def get_connection_status(db: AsyncSession) -> dict:
    from app.models.app_settings import AppSettings
    from sqlalchemy import select

    result = await db.execute(select(AppSettings).where(AppSettings.name == "default"))
    settings_row = result.scalar_one_or_none()
    if not settings_row or not settings_row.ebay_seller_refresh_token:
        return {"connected": False, "connected_at": None, "scopes": [], "refresh_token_expires_at": None}
    return {
        "connected": True,
        "connected_at": settings_row.ebay_seller_connected_at.isoformat() if settings_row.ebay_seller_connected_at else None,
        "scopes": settings_row.ebay_seller_scopes.split(" ") if settings_row.ebay_seller_scopes else [],
        "refresh_token_expires_at": (
            settings_row.ebay_seller_refresh_token_expires_at.isoformat()
            if settings_row.ebay_seller_refresh_token_expires_at else None
        ),
    }
