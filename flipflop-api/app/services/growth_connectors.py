"""Social provider adapters. MVP ships fixture connectors with documented capability."""
from __future__ import annotations

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

# Add a platform here only alongside an implemented provider adapter and its
# separately verified credential/status contract.
LIVE_PUBLISHER_PLATFORMS: frozenset[str] = frozenset()


def character_limit(platform: str) -> int:
    return PLATFORM_LIMITS.get(platform, 2200)


def publish_fixture(
    *,
    platform: str,
    account_id: int,
    copy: str,
    idempotency_key: str,
    fail: bool = False,
    media_urls: list[str] | None = None,
) -> dict:
    """Deterministic simulation helper. It never represents an external post."""
    if fail:
        return {
            "status": "simulated",
            "simulation_id": "",
            "provider_post_id": "",
            "error": "Simulated provider rejection; no external request was made",
        }
    digest = hashlib.sha256(f"{platform}:{account_id}:{idempotency_key}".encode()).hexdigest()[:16]
    return {
        "status": "simulated",
        "simulation_id": f"sim_{platform}_{digest}",
        "provider_post_id": "",
        "error": "",
        "media_urls": media_urls or [],
    }
