from __future__ import annotations

from typing import Any

from app.config import get_settings


def get_proxy_url() -> str:
    s = get_settings()
    return (s.outbound_proxy_url or s.ebay_proxy_url or "").strip()


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

