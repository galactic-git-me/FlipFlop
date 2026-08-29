"""Redis-backed cache for eBay sold comps results.

Stores SoldCompsResult with 7-day TTL in Redis for ultra-fast access and minimal API credit burn.
Cache key is CPU_CPK + MB_CPK + GPU_CPK to capture market comparables for a build configuration.
"""
from __future__ import annotations

import json
from datetime import timedelta

import redis.asyncio as redis
import structlog

from app.gem_radar.adapters.sold_comps import SoldComp, SoldCompsResult
from app.config import get_settings

log = structlog.get_logger(__name__)

_CACHE_TTL_SECONDS = 7 * 24 * 60 * 60  # 7 days
_LISTINGS_KEY_SUFFIX = ":listings"


class SoldCompsCacheService:
    """Redis-backed cache for SoldCompsResult with optional listings data."""

    def __init__(self):
        self._settings = get_settings()
        self._redis: redis.Redis | None = None

    async def connect(self) -> None:
        """Connect to Redis."""
        if not self._settings.redis_url:
            log.info("sold_comps_cache.disabled")
            return
        try:
            self._redis = await redis.from_url(self._settings.redis_url, decode_responses=True)
            await self._redis.ping()
            log.info("sold_comps_cache.connected")
        except Exception as exc:
            log.warning("sold_comps_cache.connection_failed", error=str(exc))
            self._redis = None

    async def disconnect(self) -> None:
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()

    async def get(self, cache_key: str) -> SoldCompsResult | None:
        """Fetch cached SoldCompsResult."""
        if not self._redis:
            return None
        try:
            data_json = await self._redis.get(cache_key)
            if not data_json:
                return None

            data = json.loads(data_json)
            comps = [
                SoldComp(
                    price=c["price"],
                    postage=c.get("postage", 0.0),
                    condition=c["condition"],
                    sold_at=c["sold_at"],
                    url=c.get("url"),
                    title=c.get("title"),
                )
                for c in data.get("comps", [])
            ]
            return SoldCompsResult(
                available=data["available"],
                comps=comps,
                unavailable_reason=data.get("unavailable_reason"),
            )
        except Exception as exc:
            log.warning("sold_comps_cache.get_failed", key=cache_key, error=str(exc))
            return None

    async def get_listings(self, cache_key: str) -> dict | None:
        """Fetch cached listings data if available."""
        if not self._redis:
            return None
        try:
            listings_key = f"{cache_key}{_LISTINGS_KEY_SUFFIX}"
            listings_json = await self._redis.get(listings_key)
            if not listings_json:
                return None
            return json.loads(listings_json)
        except Exception as exc:
            log.warning("sold_comps_cache.get_listings_failed", key=cache_key, error=str(exc))
            return None

    async def set(self, cache_key: str, result: SoldCompsResult, listings_data: dict | None = None) -> None:
        """Store SoldCompsResult with optional listings data for faster lookups."""
        if not self._redis:
            return
        try:
            data = {
                "available": result.available,
                "comps": [
                    {
                        "price": c.price,
                        "postage": c.postage,
                        "condition": c.condition,
                        "sold_at": c.sold_at,
                        "url": c.url,
                        "title": c.title,
                    }
                    for c in result.comps
                ],
                "unavailable_reason": result.unavailable_reason,
            }

            # Set main cache entry
            await self._redis.setex(
                cache_key,
                _CACHE_TTL_SECONDS,
                json.dumps(data),
            )

            # Set listings data if provided
            if listings_data:
                listings_key = f"{cache_key}{_LISTINGS_KEY_SUFFIX}"
                await self._redis.setex(
                    listings_key,
                    _CACHE_TTL_SECONDS,
                    json.dumps(listings_data),
                )

            log.debug("sold_comps_cache.set", key=cache_key, ttl_days=7, has_listings=listings_data is not None)
        except Exception as exc:
            log.warning("sold_comps_cache.set_failed", key=cache_key, error=str(exc))

    async def get_cache_age_and_expiry(self, cache_key: str) -> tuple[int, int] | None:
        """Return (seconds_ago_cached, seconds_until_expiry) or None if not cached."""
        if not self._redis:
            return None
        try:
            ttl = await self._redis.ttl(cache_key)
            if ttl <= 0:  # Key doesn't exist or has no expiry
                return None

            seconds_until_expiry = ttl
            seconds_cached = _CACHE_TTL_SECONDS - ttl

            return (seconds_cached, seconds_until_expiry)
        except Exception as exc:
            log.warning("sold_comps_cache.get_age_failed", key=cache_key, error=str(exc))
            return None


# Global singleton
_cache_instance: SoldCompsCacheService | None = None


async def get_sold_comps_cache() -> SoldCompsCacheService:
    """Get or initialize the cache singleton."""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = SoldCompsCacheService()
        await _cache_instance.connect()
    return _cache_instance
