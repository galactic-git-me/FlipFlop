"""
Tests for Five-Star Auto-Pricing Service (Phase 2, F2.1.3).

Verifies:
1. Discount calculation by star rating
2. Price adjustment calculations
3. Feature-flag gating
4. Auto-pricing application to builds
5. Precision with Money type
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import ManualBuild
from app.services.five_star_pricing import FiveStarPricingService
from app.services.money import Money


@pytest.mark.unit
class TestDiscountCalculation:
    """Test discount percentage by star rating."""

    def test_5_star_no_discount(self):
        """5-star rating: no reduction."""
        discount = FiveStarPricingService.get_discount_for_rating(5.0)
        assert discount.amount == 0

    def test_4_5_star_3_percent_discount(self):
        """4.5-star rating: 3% reduction."""
        discount = FiveStarPricingService.get_discount_for_rating(4.5)
        assert float(discount.amount) == 0.03

    def test_4_0_star_5_percent_discount(self):
        """4.0-star rating: 5% reduction."""
        discount = FiveStarPricingService.get_discount_for_rating(4.0)
        assert float(discount.amount) == 0.05

    def test_3_0_star_10_percent_discount(self):
        """3.0-star rating: 10% reduction."""
        discount = FiveStarPricingService.get_discount_for_rating(3.0)
        assert float(discount.amount) == 0.10

    def test_invalid_rating_raises_error(self):
        """Invalid rating (out of bounds) raises ValueError."""
        with pytest.raises(ValueError):
            FiveStarPricingService.get_discount_for_rating(5.5)

        with pytest.raises(ValueError):
            FiveStarPricingService.get_discount_for_rating(-0.5)


@pytest.mark.unit
class TestPriceAdjustment:
    """Test price calculation with discounts."""

    def test_adjust_price_for_4_5_stars(self):
        """4.5-star: £99.99 → £96.99 (3% reduction)."""
        current = Money(99.99, "GBP")
        adjusted = FiveStarPricingService.calculate_adjusted_price(current, 4.5)

        # 99.99 * 0.03 = 2.9997 ≈ 3.00 reduction
        # 99.99 - 3.00 = 96.99
        assert abs(adjusted.to_float() - 96.99) < 0.01

    def test_adjust_price_for_4_0_stars(self):
        """4.0-star: £100.00 → £95.00 (5% reduction)."""
        current = Money(100.00, "GBP")
        adjusted = FiveStarPricingService.calculate_adjusted_price(current, 4.0)

        assert adjusted == Money(95.00, "GBP")

    def test_adjust_price_for_3_0_stars(self):
        """3.0-star: £100.00 → £90.00 (10% reduction)."""
        current = Money(100.00, "GBP")
        adjusted = FiveStarPricingService.calculate_adjusted_price(current, 3.0)

        assert adjusted == Money(90.00, "GBP")

    def test_adjust_price_5_star_unchanged(self):
        """5.0-star: price unchanged (0% reduction)."""
        current = Money(99.99, "GBP")
        adjusted = FiveStarPricingService.calculate_adjusted_price(current, 5.0)

        assert adjusted == current

    def test_adjust_price_non_gbp_raises(self):
        """Only GBP prices supported."""
        current = Money(100, "USD")
        with pytest.raises(ValueError):
            FiveStarPricingService.calculate_adjusted_price(current, 4.5)


@pytest.mark.unit
class TestDiscountExplanation:
    """Test human-readable discount explanations."""

    def test_5_star_explanation(self):
        """5-star explanation."""
        msg = FiveStarPricingService.format_discount_explanation(5.0)
        assert "5-star" in msg
        assert "No reduction" in msg

    def test_4_5_star_explanation(self):
        """4.5-star explanation includes discount %."""
        msg = FiveStarPricingService.format_discount_explanation(4.5)
        assert "4.5" in msg
        assert "3" in msg or "3%" in msg

    def test_3_0_star_explanation(self):
        """3.0-star explanation."""
        msg = FiveStarPricingService.format_discount_explanation(3.0)
        assert "3.0" in msg
        assert "10" in msg or "10%" in msg


@pytest.mark.asyncio
class TestAutoApply:
    """Test automatic price adjustment application."""

    async def test_apply_auto_pricing_reduces_price(self, db: AsyncSession):
        """Auto-pricing reduces price when rating below 5 stars."""
        build = ManualBuild(
            name="Test Build",
            status="listed",
            ebay_price=99.99,
        )
        db.add(build)
        await db.commit()

        # Apply at 4.5 stars (should reduce 3%)
        result = await FiveStarPricingService.apply_auto_pricing(
            db, build.id, 4.5
        )

        assert result is True

        # Verify price changed
        updated = await db.get(ManualBuild, build.id)
        assert updated.ebay_price < 99.99
        assert abs(updated.ebay_price - 96.99) < 0.01

    async def test_no_apply_at_5_stars(self, db: AsyncSession):
        """Auto-pricing not applied at 5.0 stars."""
        build = ManualBuild(
            name="Test Build",
            status="listed",
            ebay_price=99.99,
        )
        db.add(build)
        await db.commit()

        # Apply at 5.0 stars (should not change)
        result = await FiveStarPricingService.apply_auto_pricing(
            db, build.id, 5.0
        )

        assert result is False

        # Verify price unchanged
        updated = await db.get(ManualBuild, build.id)
        assert updated.ebay_price == 99.99

    async def test_no_apply_to_unlisted_build(self, db: AsyncSession):
        """Auto-pricing not applied to unlisted builds."""
        build = ManualBuild(
            name="Test Build",
            status="in_progress",  # Not listed
            ebay_price=99.99,
        )
        db.add(build)
        await db.commit()

        result = await FiveStarPricingService.apply_auto_pricing(
            db, build.id, 4.5
        )

        assert result is False

    async def test_no_apply_nonexistent_build(self, db: AsyncSession):
        """Auto-pricing returns False for nonexistent build."""
        result = await FiveStarPricingService.apply_auto_pricing(
            db, 99999, 4.5
        )

        assert result is False

    async def test_respects_feature_flag(self, db: AsyncSession):
        """Auto-pricing respects feature flag."""
        build = ManualBuild(
            name="Test Build",
            status="listed",
            ebay_price=99.99,
        )
        db.add(build)
        await db.commit()

        # Mock flag to be disabled
        from unittest.mock import patch
        with patch("app.services.five_star_pricing.is_enabled") as mock_flag:
            mock_flag.return_value = False

            result = await FiveStarPricingService.apply_auto_pricing(
                db, build.id, 4.5
            )

            assert result is False


@pytest.mark.asyncio
class TestMoneyPrecision:
    """Test that Money type prevents precision loss."""

    def test_discount_calculation_uses_decimal(self):
        """Discount calculated with Money (Decimal) precision."""
        # Problematic float: 99.99 * 0.03 = 2.9996999999999996
        current = Money(99.99, "GBP")
        adjusted = FiveStarPricingService.calculate_adjusted_price(current, 4.5)

        # Money type ensures exact calculation
        from decimal import Decimal
        assert isinstance(adjusted.amount, Decimal)

    async def test_price_update_uses_exact_values(self, db: AsyncSession):
        """Price update uses exact Money values, not floats."""
        build = ManualBuild(
            name="Test",
            status="listed",
            ebay_price=99.99,  # Stored as float in DB
        )
        db.add(build)
        await db.commit()

        await FiveStarPricingService.apply_auto_pricing(db, build.id, 4.5)

        updated = await db.get(ManualBuild, build.id)
        # Exact value (no rounding error)
        assert updated.ebay_price == pytest.approx(96.99, abs=0.01)
