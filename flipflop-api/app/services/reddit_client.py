"""
Reddit OAuth client — handles token acquisition and refresh.

Reddit's API requires OAuth for all programmatic access (since 2023).
Unauthenticated requests to /r/*/new.json return HTML, not JSON.

Setup (free, 2 minutes):
  1. Log in to Reddit → https://www.reddit.com/prefs/apps
  2. Click "Create another app..." → choose "script"
  3. Name: FlipFlop, redirect URI: http://localhost:8080
  4. Copy the client_id (under the app name) and client_secret
  5. Add to .env:
       REDDIT_CLIENT_ID=your_client_id
       REDDIT_CLIENT_SECRET=your_client_secret
       REDDIT_USER_AGENT=FlipFlop/1.0 by /u/your_reddit_username

Without credentials this module returns None for posts — callers fall back
to an empty list and the UI shows the "rate limited" placeholder.
"""
from __future__ import annotations

import time
import base64
import asyncio

import httpx
import structlog

from app.config import get_settings

log = structlog.get_logger(__name__)

_token: str | None = None
_token_expires_at: float = 0.0
_token_lock = asyncio.Lock()

_REDDIT_TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
_REDDIT_API_BASE  = "https://oauth.reddit.com"


async def _refresh_token(client: httpx.AsyncClient) -> str | None:
    settings = get_settings()
    cid     = settings.reddit_client_id
    csecret = settings.reddit_client_secret
    ua      = settings.reddit_user_agent

    if not cid or not csecret:
        return None

    creds = base64.b64encode(f"{cid}:{csecret}".encode()).decode()
    try:
        resp = await client.post(
            _REDDIT_TOKEN_URL,
            headers={
                "Authorization": f"Basic {creds}",
                "User-Agent":    ua,
                "Content-Type":  "application/x-www-form-urlencoded",
            },
            content=b"grant_type=client_credentials",
            timeout=15,
        )
        if resp.status_code != 200:
            log.warning("reddit_oauth.token_failed", status=resp.status_code, body=resp.text[:200])
            return None
        data = resp.json()
        return data.get("access_token")
    except Exception as exc:
        log.warning("reddit_oauth.token_error", error=str(exc))
        return None


async def get_token(client: httpx.AsyncClient) -> str | None:
    global _token, _token_expires_at
    async with _token_lock:
        if _token and time.time() < _token_expires_at - 60:
            return _token
        tok = await _refresh_token(client)
        if tok:
            _token = tok
            _token_expires_at = time.time() + 3600  # Reddit tokens last 1 h
        return _token


async def fetch_new_posts(
    client: httpx.AsyncClient,
    subreddit: str,
    limit: int = 100,
) -> list[dict] | None:
    """
    Fetch new posts from a subreddit via Reddit OAuth.
    Returns None if credentials are not configured or the request fails.
    """
    settings = get_settings()
    ua = settings.reddit_user_agent

    tok = await get_token(client)
    if not tok:
        return None

    try:
        resp = await client.get(
            f"{_REDDIT_API_BASE}/r/{subreddit}/new",
            params={"limit": limit, "raw_json": "1"},
            headers={
                "Authorization": f"Bearer {tok}",
                "User-Agent":    ua,
            },
            timeout=15,
        )
        if resp.status_code == 401:
            # Token expired mid-session — clear and retry once
            global _token, _token_expires_at
            _token = None
            _token_expires_at = 0.0
            tok = await get_token(client)
            if not tok:
                return None
            resp = await client.get(
                f"{_REDDIT_API_BASE}/r/{subreddit}/new",
                params={"limit": limit, "raw_json": "1"},
                headers={"Authorization": f"Bearer {tok}", "User-Agent": ua},
                timeout=15,
            )
        if resp.status_code != 200:
            log.warning("reddit_client.fetch_failed", subreddit=subreddit, status=resp.status_code)
            return None

        data = resp.json()
        return data.get("data", {}).get("children", [])
    except Exception as exc:
        log.warning("reddit_client.fetch_error", subreddit=subreddit, error=str(exc))
        return None
