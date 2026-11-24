"""Regression coverage for Gem Radar API empty-market behaviour."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.api import gem_radar


class _EmptyResult:
    def scalar_one_or_none(self):
        return None


class _ScalarsResult:
    def __init__(self, rows):
        self.rows = rows

    def scalars(self):
        return iter(self.rows)


@pytest.mark.asyncio
async def test_component_lookup_returns_empty_when_no_active_listing(monkeypatch):
    """A temporarily empty category is a normal dashboard state, not a 500."""
    monkeypatch.setattr(gem_radar, "get_active_buy_it_now_listing_ids", AsyncMock(return_value=[101]))
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_EmptyResult())

    result = await gem_radar._fetch_best_gem_for_category(db, "gpu", since=datetime.utcnow())

    assert result is None
    assert db.execute.await_count == 2


@pytest.mark.asyncio
async def test_platform_spotlight_candidate_pool_keeps_lower_ranked_compatible_listing(monkeypatch):
    """Platform compatibility must run before the global objective cutoffs."""
    from app.services import curated_media

    rows = [
        SimpleNamespace(
            id=index,
            listing_id=str(index),
            title=f"AM4 motherboard {index}",
            category="motherboard",
            classification="GEM",
            deal_score=100 - index,
            delivered_price=100 + index,
            conservative_resale_price=300 - index,
            market_median_price=300 - index,
            market_new_price=300 - index,
            market_used_price=300 - index,
            expected_profit=200 - index * 2,
            desirability_score=100 - index,
            liquidity_score=100 - index,
            watch_count=100 - index,
            bid_count=100 - index,
            image_url=f"https://images.example/{index}.jpg",
            image_urls=[],
            url=f"https://market.example/{index}",
            seller_name="seller",
            condition="used",
            source="ebay",
            canonical_model_id=None,
            release_year=None,
        )
        for index in range(1, 11)
    ]
    monkeypatch.setattr(curated_media, "media_urls", lambda urls: [urls[0]])
    monkeypatch.setattr(
        gem_radar.identity_mod,
        "resolve_identity",
        lambda *args, **kwargs: SimpleNamespace(category="motherboard"),
    )
    for name in (
        "_is_server_hardware",
        "_is_complete_system",
        "_is_bundled_components",
        "_is_obsolete_socket",
        "_is_damaged",
        "_is_component_price_anomaly",
        "_is_price_misaligned_to_market",
    ):
        monkeypatch.setattr(gem_radar, name, lambda *args, **kwargs: False)
    monkeypatch.setattr(gem_radar, "_has_valid_category", lambda category: True)
    monkeypatch.setattr(gem_radar, "_is_reasonable_price", lambda *args: True)
    monkeypatch.setattr(gem_radar, "_is_desktop_appropriate", lambda *args: True)
    monkeypatch.setattr(gem_radar, "_is_current_gen", lambda *args: True)

    db = SimpleNamespace(execute=AsyncMock(return_value=_ScalarsResult(rows)))
    pool = await gem_radar._gem_spotlight_candidates(
        db, "motherboard", {str(index) for index in range(1, 11)},
        preserve_full_pool=True,
    )

    assert {candidate["id"] for candidate in pool} == set(range(1, 11))


@pytest.mark.asyncio
async def test_platform_spotlight_requests_full_candidate_pools(monkeypatch):
    """The platform path must pass the untrimmed pool to reviewed-fact filters."""
    from app.services import hardware_performance

    preserve_flags = []

    async def candidates(db, category, actionable_ids, benchmark_context, *, preserve_full_pool=False):
        preserve_flags.append(preserve_full_pool)
        return []

    async def platform_builds(db, pools, platform):
        return {}

    monkeypatch.setattr(hardware_performance, "load_benchmark_context", AsyncMock(return_value=None))
    monkeypatch.setattr(gem_radar, "_gem_spotlight_candidates", candidates)
    monkeypatch.setattr(gem_radar, "_gem_spotlight_platform_builds", platform_builds)

    await gem_radar.get_gem_spotlight(AsyncMock(), actionable_ids={"1"}, platform="am4")

    assert preserve_flags and all(preserve_flags)
