"""Tests for quote generation service."""
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.quote_service import (
    QuoteService,
    BUDGET_TIERS,
    COMPONENT_CATEGORY_MAP,
    LABOR_COST_PER_HOUR,
    LABOR_HOURS_PER_BUILD,
    OVERHEAD_PERCENTAGE,
)


class TestQuoteService:
    """Test suite for QuoteService."""

    def test_get_budget_tiers(self):
        """Test getting all budget tiers."""
        tiers = QuoteService.get_budget_tiers()
        assert isinstance(tiers, dict)
        assert len(tiers) == 5
        assert 800 in tiers
        assert 1200 in tiers
        assert 1500 in tiers
        assert 2000 in tiers
        assert 3000 in tiers

    def test_get_budget_tiers_content(self):
        """Test budget tier contents."""
        tiers = QuoteService.get_budget_tiers()
        tier_800 = tiers[800]

        assert "name" in tier_800
        assert tier_800["name"] == "Budget Gaming"
        assert "cpu" in tier_800
        assert "gpu" in tier_800
        assert "ram" in tier_800

    def test_find_closest_budget_tier_exact_match(self):
        """Test finding exact budget tier match."""
        assert QuoteService.find_closest_budget_tier(1200) == 1200
        assert QuoteService.find_closest_budget_tier(800) == 800
        assert QuoteService.find_closest_budget_tier(3000) == 3000

    def test_find_closest_budget_tier_fuzzy_match(self):
        """Test finding closest budget tier with fuzzy matching."""
        # 1000 is closer to 800 than 1200
        assert QuoteService.find_closest_budget_tier(1000) == 1200

        # 1350 is closer to 1500 than 1200
        assert QuoteService.find_closest_budget_tier(1350) == 1500

    def test_find_closest_budget_tier_below_minimum(self):
        """Test budget below minimum range returns None."""
        assert QuoteService.find_closest_budget_tier(500) is None

    def test_find_closest_budget_tier_above_maximum(self):
        """Test budget above maximum range returns None."""
        assert QuoteService.find_closest_budget_tier(5000) is None

    def test_get_recommended_specs_valid_budget(self):
        """Test getting recommended specs for valid budget."""
        specs = QuoteService.get_recommended_specs(1200)
        assert specs is not None
        assert "cpu" in specs
        assert "gpu" in specs
        assert "ram" in specs
        assert specs["cpu"] == "Ryzen 5 5600X"
        assert specs["gpu"] == "RTX 3070"

    def test_get_recommended_specs_invalid_budget(self):
        """Test getting recommended specs for invalid budget."""
        assert QuoteService.get_recommended_specs(500) is None
        assert QuoteService.get_recommended_specs(5000) is None

    def test_get_recommended_specs_not_mutated(self):
        """Test that getting specs doesn't mutate the tier definition."""
        specs1 = QuoteService.get_recommended_specs(1200)
        specs2 = QuoteService.get_recommended_specs(1200)

        assert specs1 == specs2
        assert "name" in specs1

    @pytest.mark.asyncio
    async def test_calculate_component_costs_with_mocked_db(self):
        """Test component cost calculation with mocked database."""
        # Mock database session
        db = AsyncMock()

        # Mock a component result
        mock_component = MagicMock()
        mock_component.market_price = 250.0

        # Mock execute to return our component
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_component
        db.execute = AsyncMock(return_value=mock_result)

        specs = {
            "cpu": "Ryzen 5 5600X",
            "gpu": "RTX 3070",
        }

        components, total_cost = await QuoteService.calculate_component_costs(
            db, specs
        )

        assert len(components) == 2
        assert total_cost > 0
        assert all("price" in c for c in components)

    @pytest.mark.asyncio
    async def test_calculate_component_costs_with_fallback(self):
        """Test component cost calculation falls back to defaults."""
        # Mock database session with no results
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=mock_result)

        specs = {
            "cpu": "Ryzen 5 5600X",
        }

        components, total_cost = await QuoteService.calculate_component_costs(
            db, specs
        )

        assert len(components) == 1
        assert total_cost > 0
        assert components[0]["price"] > 0

    @pytest.mark.asyncio
    async def test_find_component_price_found(self):
        """Test finding component price when it exists."""
        db = AsyncMock()

        mock_component = MagicMock()
        mock_component.market_price = 300.0

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_component
        db.execute = AsyncMock(return_value=mock_result)

        price = await QuoteService._find_component_price(db, "CPU", "Ryzen 5 5600X")

        assert price == Decimal("300.0")

    @pytest.mark.asyncio
    async def test_find_component_price_not_found(self):
        """Test finding component price when it doesn't exist."""
        db = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=mock_result)

        price = await QuoteService._find_component_price(db, "CPU", "Unknown CPU")

        assert price is None

    @pytest.mark.asyncio
    async def test_generate_quote_valid_budget(self):
        """Test generating quote for valid budget."""
        db = AsyncMock()

        # Mock component lookups
        mock_component = MagicMock()
        mock_component.market_price = 200.0

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_component
        db.execute = AsyncMock(return_value=mock_result)

        quote = await QuoteService.generate_quote(1200, db)

        assert quote is not None
        assert quote["budget"] == 1200
        assert "tier_name" in quote
        assert "components" in quote
        assert "parts_cost_total" in quote
        assert "labor_cost" in quote
        assert "overhead_cost" in quote
        assert "total_price" in quote
        assert "within_budget" in quote

    @pytest.mark.asyncio
    async def test_generate_quote_components_populated(self):
        """Test that quote includes all expected components."""
        db = AsyncMock()

        mock_component = MagicMock()
        mock_component.market_price = 250.0

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_component
        db.execute = AsyncMock(return_value=mock_result)

        quote = await QuoteService.generate_quote(800, db)

        assert quote is not None
        # Budget Gaming tier has 8 components
        assert len(quote["components"]) == 8
        assert all("component_name" in c for c in quote["components"])
        assert all("price" in c for c in quote["components"])

    @pytest.mark.asyncio
    async def test_generate_quote_labor_calculation(self):
        """Test that labor cost is calculated correctly."""
        db = AsyncMock()

        mock_component = MagicMock()
        mock_component.market_price = 100.0

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_component
        db.execute = AsyncMock(return_value=mock_result)

        quote = await QuoteService.generate_quote(1200, db)

        assert quote is not None
        expected_labor = float(LABOR_COST_PER_HOUR * LABOR_HOURS_PER_BUILD)
        assert quote["labor_cost"] == expected_labor

    @pytest.mark.asyncio
    async def test_generate_quote_overhead_calculation(self):
        """Test that overhead is calculated correctly."""
        db = AsyncMock()

        mock_component = MagicMock()
        mock_component.market_price = 100.0

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_component
        db.execute = AsyncMock(return_value=mock_result)

        quote = await QuoteService.generate_quote(1200, db)

        assert quote is not None
        # Overhead should be 10% of (parts + labor)
        subtotal = quote["parts_cost_total"] + quote["labor_cost"]
        expected_overhead = subtotal * float(OVERHEAD_PERCENTAGE)
        assert abs(quote["overhead_cost"] - expected_overhead) < 0.01

    @pytest.mark.asyncio
    async def test_generate_quote_within_budget(self):
        """Test that quote stays within budget when possible."""
        db = AsyncMock()

        # Use very cheap components to stay within budget
        mock_component = MagicMock()
        mock_component.market_price = 50.0

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_component
        db.execute = AsyncMock(return_value=mock_result)

        quote = await QuoteService.generate_quote(1200, db)

        assert quote is not None
        assert quote["total_price"] <= 1200
        assert quote["within_budget"] is True

    @pytest.mark.asyncio
    async def test_generate_quote_invalid_budget(self):
        """Test generating quote with invalid budget returns None."""
        db = AsyncMock()

        quote = await QuoteService.generate_quote(500, db)
        assert quote is None

        quote = await QuoteService.generate_quote(5000, db)
        assert quote is None

    def test_component_category_map_complete(self):
        """Test that component category map covers all spec keys."""
        for tier_name, specs in BUDGET_TIERS.items():
            for spec_key in specs.keys():
                if spec_key != "name":
                    assert spec_key in COMPONENT_CATEGORY_MAP, (
                        f"Spec key '{spec_key}' not in COMPONENT_CATEGORY_MAP"
                    )

    @pytest.mark.asyncio
    async def test_generate_quote_budget_remaining(self):
        """Test that budget remaining is calculated correctly."""
        db = AsyncMock()

        mock_component = MagicMock()
        mock_component.market_price = 100.0

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_component
        db.execute = AsyncMock(return_value=mock_result)

        budget = 1500
        quote = await QuoteService.generate_quote(budget, db)

        assert quote is not None
        expected_remaining = budget - quote["total_price"]
        assert abs(quote["budget_remaining"] - expected_remaining) < 0.01
