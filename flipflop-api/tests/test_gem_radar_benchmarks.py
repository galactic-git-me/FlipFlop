"""Tests for benchmark statistics computation and the honest-unavailable
adapters (PRD §11-12, and the "never fabricate a price" non-negotiable rule).
"""
import pytest

from app.gem_radar.benchmarks import _stat_from_prices, _trimmed_mean, MIN_SAMPLE_FOR_MEDIAN
from app.gem_radar.adapters.sold_comps import UnavailableSoldCompsAdapter, FixtureSoldCompsAdapter, SoldComp
from app.gem_radar.adapters.amazon_price import UnavailableAmazonPriceAdapter, FixtureAmazonPriceAdapter


class TestStatFromPrices:
    def test_empty_list_is_unavailable_not_zero(self):
        stat = _stat_from_prices([], "test-source", None, "exact_sku")
        assert stat.status == "unavailable"
        assert stat.median is None
        assert stat.average is None

    def test_thin_sample_is_insufficient_not_ok(self):
        stat = _stat_from_prices([50.0, 55.0], "test-source", None, "exact_sku")
        assert stat.status == "insufficient_sample"
        assert stat.sample_size == 2
        assert stat.median is None  # median withheld below MIN_SAMPLE_FOR_MEDIAN, not a misleading n=2 median

    def test_sufficient_sample_computes_all_statistics(self):
        prices = [40.0, 45.0, 50.0, 55.0, 60.0]
        stat = _stat_from_prices(prices, "test-source", None, "exact_sku")
        assert stat.status == "ok"
        assert stat.sample_size == 5
        assert stat.median == 50.0
        assert stat.min == 40.0
        assert stat.max == 60.0
        assert stat.average == 50.0

    def test_match_level_is_recorded_not_hidden(self):
        stat = _stat_from_prices([40.0, 45.0, 50.0], "test", None, "category_comparable")
        assert stat.match_level_counts == {"category_comparable": 3}


class TestTrimmedMean:
    def test_trims_outliers(self):
        # One extreme outlier (500) should be trimmed from a 10-item sample.
        prices = sorted([40, 41, 42, 43, 44, 45, 46, 47, 48, 500])
        trimmed = _trimmed_mean(prices)
        plain_mean = sum(prices) / len(prices)
        assert trimmed < plain_mean


class TestSoldCompsAdapter:
    @pytest.mark.asyncio
    async def test_unavailable_adapter_never_returns_a_price(self):
        adapter = UnavailableSoldCompsAdapter()
        result = await adapter.fetch("Ryzen 5600X", "used")
        assert result.available is False
        assert result.comps == []
        assert result.unavailable_reason is not None

    @pytest.mark.asyncio
    async def test_fixture_adapter_filters_by_condition(self):
        adapter = FixtureSoldCompsAdapter(
            {"Ryzen 5600X": [SoldComp(price=90, postage=3, condition="used", sold_at="2026-07-01")]}
        )
        used = await adapter.fetch("Ryzen 5600X", "used")
        new = await adapter.fetch("Ryzen 5600X", "new")
        assert used.available is True
        assert new.available is False


class TestAmazonPriceAdapter:
    @pytest.mark.asyncio
    async def test_unavailable_adapter_never_returns_a_price(self):
        adapter = UnavailableAmazonPriceAdapter()
        result = await adapter.fetch("Corsair Vengeance 16GB")
        assert result.available is False
        assert result.price is None

    @pytest.mark.asyncio
    async def test_fixture_adapter_returns_configured_price(self):
        adapter = FixtureAmazonPriceAdapter({"Corsair Vengeance 16GB": 65.99})
        result = await adapter.fetch("Corsair Vengeance 16GB")
        assert result.available is True
        assert result.price == 65.99
