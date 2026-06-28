from __future__ import annotations

import os
import socket
import time
from urllib.parse import urlparse
from typing import Any

from app.config import get_settings

_PROXY_HEALTH_CACHE: dict[str, tuple[bool, float]] = {}


def _proxy_reachable(proxy_url: str) -> bool:
    """Fast reachability probe with short cache to avoid global scrape stalls."""
    if not proxy_url:
        return False
    now = time.monotonic()
    cached = _PROXY_HEALTH_CACHE.get(proxy_url)
    if cached and (now - cached[1] < 30.0):
        return cached[0]

    try:
        parsed = urlparse(proxy_url)
        host = (parsed.hostname or "").strip()
        port = int(parsed.port or (443 if parsed.scheme == "https" else 80))
        if not host:
            _PROXY_HEALTH_CACHE[proxy_url] = (False, now)
            return False
        with socket.create_connection((host, port), timeout=1.0):
            _PROXY_HEALTH_CACHE[proxy_url] = (True, now)
            return True
    except Exception:
        _PROXY_HEALTH_CACHE[proxy_url] = (False, now)
        return False


def get_proxy_url() -> str:
    s = get_settings()
    proxy = (s.outbound_proxy_url or s.ebay_proxy_url or "").strip()
    if not proxy:
        return ""
    # In dev, gracefully fall back to direct internet if proxy is down.
    if os.getenv("APP_MODE", "dev").lower() == "dev" and not _proxy_reachable(proxy):
        return ""
    return proxy


def apply_httpx_proxy(kwargs: dict[str, Any]) -> dict[str, Any]:
    out = dict(kwargs)
    proxy = get_proxy_url()
    if proxy:
        out["proxy"] = proxy
    return out


def playwright_proxy_config() -> dict[str, str] | None:
    proxy = get_proxy_url()
    if not proxy:
        return None
    return {"server": proxy}
