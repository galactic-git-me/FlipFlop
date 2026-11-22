"""Tests for Price History Service (Phase 2, F2.1.4)."""

import pytest
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import PriceHistory, ManualBuild
from app.services.price_history import PriceHistoryService
from app.services.money import Money


@pytest.mark.asyncio
class TestPriceHistoryRecording:
    """Test recording price changes."""

    async def test_record_price_change(self, db: AsyncSession):
        """Record a price change with reason."""
        build = ManualBuild(name="Test", ebay_price=100.0)
        db.add(build)
        await db.commit()

        new_price = Money(95.0, "GBP")
        record = await PriceHistoryService.record_price_change(
            db, build.id, new_price, "five_star_adjustment"
        )

        assert record.id is not None
        assert record.manual_build_id == build.id
        assert record.price_gbp == 9500
        assert record.reason == "five_star_adjustment"
        assert record.previous_price_gbp == 10000

    async def test_multiple_price_changes(self, db: AsyncSession):
        """Record multiple price changes."""
        build = ManualBuild(name="Test", ebay_price=100.0)
        db.add(build)
        await db.commit()

        # First change
        await PriceHistoryService.record_price_change(
            db, build.id, Money(95.0, "GBP"), "recreate_cycle"
        )

        # Second change
        await PriceHistoryService.record_price_change(
            db, build.id, Money(90.0, "GBP"), "alert_triggered"
        )

        history = await PriceHistoryService.get_price_history(db, build.id)
        assert len(history) == 2


@pytest.mark.asyncio
class TestPriceTrendAnalysis:
    """Test price trend calculation."""

    async def test_calculate_trend_declining(self, db: AsyncSession):
        """Calculate trend for declining price."""
        build = ManualBuild(name="Test", ebay_price=100.0)
        db.add(build)
        await db.commit()

        # Record declining prices
        await PriceHistoryService.record_price_change(
            db, build.id, Money(95.0, "GBP"), "cycle1"
        )
        await PriceHistoryService.record_price_change(
            db, build.id, Money(90.0, "GBP"), "cycle2"
        )
        await PriceHistoryService.record_price_change(
            db, build.id, Money(85.0, "GBP"), "cycle3"
        )

        trend = await PriceHistoryService.calculate_price_trend(db, build.id)

        assert trend["min_price"] == 85.0
        assert trend["max_price"] == 95.0
        assert trend["trend"] < 0  # Declining

    async def test_calculate_volatility(self, db: AsyncSession):
        """Calculate price volatility."""
        build = ManualBuild(name="Test", ebay_price=100.0)
        db.add(build)
        await db.commit()

        # High volatility: price bounces
        await PriceHistoryService.record_price_change(
            db, build.id, Money(80.0, "GBP"), "drop"
        )
        await PriceHistoryService.record_price_change(
            db, build.id, Money(95.0, "GBP"), "raise"
        )
        await PriceHistoryService.record_price_change(
            db, build.id, Money(82.0, "GBP"), "drop"
        )

        trend = await PriceHistoryService.calculate_price_trend(db, build.id)

        # Volatility = range / average * 100
        assert trend["volatility"] > 15  # High volatility


@pytest.mark.asyncio
class TestStalePricingDetection:
    """Test stale price detection."""

    async def test_detect_stale_price(self, db: AsyncSession):
        """Detect when price hasn't changed."""
        build = ManualBuild(name="Test", ebay_price=100.0)
        db.add(build)
        await db.commit()

        # Record one price, then wait
        await PriceHistoryService.record_price_change(
            db, build.id, Money(100.0, "GBP"), "initial"
        )

        is_stale = await PriceHistoryService.is_price_stale(db, build.id, stale_days=7)
        assert is_stale is True

    async def test_fresh_price_with_recent_change(self, db: AsyncSession):
        """Fresh price when recently changed."""
        build = ManualBuild(name="Test", ebay_price=100.0)
        db.add(build)
        await db.commit()

        # Record two prices (implies recent change)
        await PriceHistoryService.record_price_change(
            db, build.id, Money(95.0, "GBP"), "change1"
        )
        await PriceHistoryService.record_price_change(
            db, build.id, Money(90.0, "GBP"), "change2"
        )

        is_stale = await PriceHistoryService.is_price_stale(db, build.id, stale_days=7)
        assert is_stale is False


@pytest.mark.asyncio
class TestMoneyPrecision:
    """Test Money type in price history."""

    async def test_price_precision_stored_in_pennies(self, db: AsyncSession):
        """Prices stored as pennies avoid rounding."""
        build = ManualBuild(name="Test", ebay_price=99.99)
        db.add(build)
        await db.commit()

        new_price = Money(75.50, "GBP")
        record = await PriceHistoryService.record_price_change(
            db, build.id, new_price, "test"
        )

        # Restore from pennies
        restored = Money.from_pennies(record.price_gbp, "GBP")
        assert restored == new_price

    async def test_price_change_calculation(self, db: AsyncSession):
        """Price change calculated exactly."""
        build = ManualBuild(name="Test", ebay_price=100.0)
        db.add(build)
        await db.commit()

        new_price = Money(79.99, "GBP")
        record = await PriceHistoryService.record_price_change(
            db, build.id, new_price, "test"
        )

        # Change should be -£20.01
        change = record.price_change_gbp
        assert change == -2001  # pennies
