"""eBay Catalog API client for product review ratings.

Fetches aggregate review data (average rating + review count) for a catalog
product identified by its epid — a different endpoint from the Browse API
used by ebay_browse.py (which only returns live-listing prices, no review
data). Only ever called for SUPER_GEM/GEM-classified listings (see
phase2_runner.py) since it's a per-epid external call with its own rate
limit, gated behind a 7-day Redis cache mirroring sold_comps_cache.py's
pattern rather than a new caching mechanism.

Reference: https://developer.ebay.com/api-docs/commerce/catalog/resources/product/methods/getProduct
"""
from __future__ import annotations

import json
from dataclasses import dataclass

import httpx
import redis.asyncio as redis
import structlog

from app.api.ebay_compliance import _get_app_token, _ebay_api_root
from app.config import get_settings

log = structlog.get_logger(__name__)

_MARKETPLACE_ID = "EBAY_GB"
_CACHE_TTL_SECONDS = 7 * 24 * 60 * 60  # 7 days — mirrors sold_comps_cache.py
_CACHE_KEY_PREFIX = "ebay_catalog_reviews:"


@dataclass
class ProductReviews:
    average_rating: float | None
    review_count: int | None


_EMPTY = ProductReviews(average_rating=None, review_count=None)


class EbayCatalogReviewCache:
    """Redis-backed 7-day cache for per-epid review data — same shape as
    SoldCompsCacheService (app/services/sold_comps_cache.py), no-ops silently
    when Redis isn't configured rather than blocking the classification
    pipeline on a cache outage."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._redis: redis.Redis | None = None

    async def connect(self) -> None:
        if not self._settings.redis_url:
            log.warning("ebay_catalog_cache.redis_url_not_configured")
            return
        try:
            self._redis = await redis.from_url(self._settings.redis_url, decode_responses=True)
            await self._redis.ping()
            log.info("ebay_catalog_cache.connected")
        except Exception as exc:
            log.warning("ebay_catalog_cache.connection_failed", error=str(exc))
            self._redis = None

    async def get(self, epid: str) -> ProductReviews | None:
        if not self._redis:
            return None
        try:
            raw = await self._redis.get(f"{_CACHE_KEY_PREFIX}{epid}")
            if not raw:
                return None
            data = json.loads(raw)
            return ProductReviews(average_rating=data.get("average_rating"), review_count=data.get("review_count"))
        except Exception as exc:
            log.warning("ebay_catalog_cache.get_failed", epid=epid, error=str(exc))
            return None

    async def set(self, epid: str, reviews: ProductReviews) -> None:
        if not self._redis:
            return
        try:
            data = {"average_rating": reviews.average_rating, "review_count": reviews.review_count}
            await self._redis.setex(f"{_CACHE_KEY_PREFIX}{epid}", _CACHE_TTL_SECONDS, json.dumps(data))
        except Exception as exc:
            log.warning("ebay_catalog_cache.set_failed", epid=epid, error=str(exc))


_cache_instance: EbayCatalogReviewCache | None = None


async def _get_cache() -> EbayCatalogReviewCache:
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = EbayCatalogReviewCache()
        await _cache_instance.connect()
    return _cache_instance


async def _fetch_product_reviews(token: str, epid: str) -> ProductReviews:
    root = _ebay_api_root()
    url = f"{root}/commerce/catalog/v1_beta/product/{epid}"
    headers = {
        "Authorization": f"Bearer {token}",
        "X-EBAY-C-MARKETPLACE-ID": _MARKETPLACE_ID,
    }
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(url, headers=headers)
    except Exception as exc:
        log.warning("ebay_catalog.request_failed", epid=epid, error=str(exc))
        return _EMPTY

    if resp.status_code != 200:
        log.warning("ebay_catalog.get_product_failed", epid=epid, status=resp.status_code)
        return _EMPTY

    review_rating = (resp.json() or {}).get("reviewRating") or {}
    try:
        average_rating = float(review_rating["averageRating"]) if review_rating.get("averageRating") is not None else None
    except (ValueError, TypeError):
        average_rating = None
    try:
        review_count = int(review_rating["reviewCount"]) if review_rating.get("reviewCount") is not None else None
    except (ValueError, TypeError):
        review_count = None

    return ProductReviews(average_rating=average_rating, review_count=review_count)


async def get_product_reviews(epid: str) -> ProductReviews:
    """Fetch (cached, 7 days) average rating + review count for a catalog
    product. Callers must gate this to GEM/SUPER_GEM-classified listings
    (see phase2_runner.py) — it's an extra per-epid API call, not part of
    the free Browse API search response used for prices/seller feedback."""
    cache = await _get_cache()
    cached = await cache.get(epid)
    if cached is not None:
        return cached

    token = await _get_app_token()
    if not token:
        log.warning("ebay_catalog.no_token")
        return _EMPTY

    reviews = await _fetch_product_reviews(token, epid)
    await cache.set(epid, reviews)
    return reviews
