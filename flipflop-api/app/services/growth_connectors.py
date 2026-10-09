"""Social provider adapters. MVP ships fixture connectors with documented capability."""
from __future__ import annotations

from datetime import datetime
import hashlib

PLATFORM_LIMITS = {
    "facebook": 63206,
    "instagram": 2200,
    "x": 280,
    "linkedin": 3000,
}

PLATFORM_CAPS = {
    "facebook": "fixture",
    "instagram": "fixture",
    "x": "fixture",
    "linkedin": "assisted",
}


def character_limit(platform: str) -> int:
    return PLATFORM_LIMITS.get(platform, 2200)


def publish_fixture(
    *,
    platform: str,
    account_id: int,
    copy: str,
    idempotency_key: str,
    fail: bool = False,
) -> dict:
    """Deterministic sandbox publisher. Same key always returns the same post id."""
    if fail:
        return {
            "status": "failed",
            "provider_post_id": "",
            "error": "Provider rejected the payload",
            "confirmed_at": None,
        }
    digest = hashlib.sha256(f"{platform}:{account_id}:{idempotency_key}".encode()).hexdigest()[:16]
    return {
        "status": "published",
        "provider_post_id": f"{platform}_{digest}",
        "error": "",
        "confirmed_at": datetime.utcnow().isoformat(),
        "metrics_available": ["impressions", "likes", "comments", "shares", "link_clicks"],
    }


def organic_snapshot(provider_post_id: str, platform: str) -> dict:
    seed = int(hashlib.sha256(provider_post_id.encode()).hexdigest()[:6], 16)
    return {
        "reach": 80 + seed % 400,
        "impressions": 120 + seed % 900,
        "likes": 4 + seed % 40,
        "comments": seed % 12,
        "shares": seed % 8,
        "saves": seed % 6,
        "link_clicks": seed % 25,
        "video_views": None,
        "evidence_class": "observed",
        "label": "Organic metrics only — not attributed revenue",
        "provider": platform,
    }
