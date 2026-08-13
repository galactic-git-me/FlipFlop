"""
eBay Token Manager — keeps a valid access token available for either the
sandbox or production listing environment, without requiring a browser
sign-in each time it expires (every 2 hours).

Uses the long-lived refresh token (~18 months) to silently mint fresh
access tokens, caching the result to disk per-environment so restarts
don't force an unnecessary refresh call.
"""

import base64
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx
import structlog

from app.config import get_settings

log = structlog.get_logger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
_REFRESH_MARGIN_SECONDS = 300  # renew 5 minutes before actual expiry

_TOKEN_ENDPOINTS = {
    "sandbox": "https://api.sandbox.ebay.com/identity/v1/oauth2/token",
    "production": "https://api.ebay.com/identity/v1/oauth2/token",
}


@dataclass(frozen=True)
class _EnvCredentials:
    app_id: str
    client_secret: str
    refresh_token: str
    static_token: str


def _credentials_for(environment: str) -> _EnvCredentials:
    settings = get_settings()
    if environment == "production":
        return _EnvCredentials(
            app_id=settings.ebay_app_id,
            client_secret=settings.ebay_client_secret,
            refresh_token=settings.ebay_production_refresh_token,
            static_token=settings.ebay_production_oauth_user_token,
        )
    return _EnvCredentials(
        app_id=settings.ebay_sandbox_app_id,
        client_secret=settings.ebay_sandbox_client_secret,
        refresh_token=settings.ebay_sandbox_refresh_token,
        static_token=settings.ebay_sandbox_oauth_user_token,
    )


def _cache_path(environment: str) -> Path:
    return _DATA_DIR / f"ebay_{environment}_token_cache.json"


def _load_cache(environment: str) -> Optional[dict]:
    path = _cache_path(environment)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def _save_cache(environment: str, access_token: str, expires_at: float) -> None:
    path = _cache_path(environment)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"access_token": access_token, "expires_at": expires_at}))


async def get_valid_ebay_access_token(environment: str = "sandbox", force_refresh: bool = False) -> str:
    """
    Returns a currently-valid eBay access token for the given environment
    ("sandbox" or "production"), refreshing it via the stored refresh token
    if the cached one is missing or near expiry.
    """
    if not force_refresh:
        cached = _load_cache(environment)
        if cached and cached.get("expires_at", 0) - _REFRESH_MARGIN_SECONDS > time.time():
            return cached["access_token"]

    creds = _credentials_for(environment)

    if not creds.refresh_token:
        # No refresh token on file — fall back to the static token from .env.local
        # (requires manual renewal every 2 hours until a refresh token is saved).
        if creds.static_token:
            return creds.static_token
        raise ValueError(
            f"No eBay {environment} refresh token or access token configured. "
            "Complete the OAuth sign-in flow once via /api/ebay/exchange-auth-code."
        )

    if not creds.app_id or not creds.client_secret:
        raise ValueError(f"eBay {environment} app credentials not configured")

    credentials = f"{creds.app_id}:{creds.client_secret}"
    encoded = base64.b64encode(credentials.encode()).decode()

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            _TOKEN_ENDPOINTS[environment],
            headers={
                "Authorization": f"Basic {encoded}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "refresh_token",
                "refresh_token": creds.refresh_token,
                # sell.inventory (create/manage listings) + sell.account
                # (read fulfillment/payment/return Business Policies) — a
                # refresh can only re-grant scopes already present on the
                # refresh token's original consent, so both must also be
                # requested in the initial browser authorize URL's scope
                # param, not just here.
                "scope": (
                    "https://api.ebay.com/oauth/api_scope/sell.inventory "
                    "https://api.ebay.com/oauth/api_scope/sell.account"
                ),
            },
        )

        if resp.status_code != 200:
            log.error("ebay.token_refresh_failed", environment=environment, status=resp.status_code, body=resp.text)
            raise ValueError(f"Failed to refresh eBay {environment} token: {resp.text}")

        data = resp.json()
        access_token = data["access_token"]
        expires_at = time.time() + data.get("expires_in", 7200)
        _save_cache(environment, access_token, expires_at)
        log.info("ebay.token_refreshed", environment=environment, expires_in=data.get("expires_in"))
        return access_token


async def get_valid_sandbox_access_token(force_refresh: bool = False) -> str:
    """Backwards-compatible sandbox-only wrapper."""
    return await get_valid_ebay_access_token("sandbox", force_refresh=force_refresh)
