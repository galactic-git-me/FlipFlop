"""Tests for Demand Metrics Calculator (Phase 3, F3.1.1).

Verifies metrics calculation from gem_radar data.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import ManualBuild, DemandMetricsSnapshot, GemRadarListingDemandHistory
from app.services.demand_metrics_calculator import DemandMetricsCalculator
from datetime import datetime, timedelta


@pytest.mark.asyncio
class TestCalculateMetrics:
    """Test metrics calculation."""

    async def test_calculate_from_gem_radar_data(self, db: AsyncSession):
        """Calculate metrics from gem_radar demand history."""
        build = ManualBuild(
            name="Test Build",
            ebay_listing_id="ITEM-123456",
        )
        db.add(build)
        await db.commit()

        # Add demand history
        for i in range(5):
            history = GemRadarListingDemandHistory(
                listing_id="ITEM-123456",
                watch_count=100 + (i * 10),
                bid_count=5 + i,
                delivered_price=99.99,
                status="active",
                observed_at=datetime.utcnow() - timedelta(days=4-i),
            )
            db.add(history)
        await db.commit()

        result = await DemandMetricsCalculator.calculate_metrics(db, build.id)

        assert result is not None
        assert result.view_count > 0
        assert result.conversion_count > 0
        assert 0 <= (result.view_to_conversion_rate or 0) <= 1

    async def test_no_listing_id(self, db: AsyncSession):
        """Handle build with no eBay listing ID."""
        build = ManualBuild(name="No Listing")
        db.add(build)
        await db.commit()

        result = await DemandMetricsCalculator.calculate_metrics(db, build.id)

        # Should return empty snapshot
        assert result is not None
        assert result.view_count == 0
        assert result.conversion_count == 0

    async def test_nonexistent_build(self, db: AsyncSession):
        """Handle nonexistent build."""
        result = await DemandMetricsCalculator.calculate_metrics(db, 99999)

        assert result is None

    async def test_conversion_rate_calculation(self, db: AsyncSession):
        """Verify conversion rate calculation."""
        build = ManualBuild(
            name="Test",
            ebay_listing_id="ITEM-123",
        )
        db.add(build)
        await db.commit()

        # 100 views, 10 conversions = 10% rate
        history = GemRadarListingDemandHistory(
            listing_id="ITEM-123",
            watch_count=100,
            bid_count=10,
            delivered_price=99.99,
        )
        db.add(history)
        await db.commit()

        result = await DemandMetricsCalculator.calculate_metrics(db, build.id)

        assert result is not None
        assert abs((result.view_to_conversion_rate or 0) - 0.1) < 0.01

    async def test_trend_rising(self, db: AsyncSession):
        """Detect rising demand trend."""
        build = ManualBuild(
            name="Rising",
            ebay_listing_id="ITEM-123",
        )
        db.add(build)
        await db.commit()

        # Conversions increase over time
        for i in range(5):
            history = GemRadarListingDemandHistory(
                listing_id="ITEM-123",
                watch_count=100,
                bid_count=2 + (i * 3),  # 2, 5, 8, 11, 14
                delivered_price=99.99,
                observed_at=datetime.utcnow() - timedelta(days=4-i),
            )
            db.add(history)
        await db.commit()

        result = await DemandMetricsCalculator.calculate_metrics(db, build.id)

        assert result is not None
        assert result.demand_trend == "rising"

    async def test_volatility_calculation(self, db: AsyncSession):
        """Calculate volatility score."""
        build = ManualBuild(
            name="Volatile",
            ebay_listing_id="ITEM-123",
        )
        db.add(build)
        await db.commit()

        # Highly variable conversion rates
        rates = [0.05, 0.25, 0.03, 0.20, 0.08]
        for i, rate in enumerate(rates):
            conversions = int(100 * rate)
            history = GemRadarListingDemandHistory(
                listing_id="ITEM-123",
                watch_count=100,
                bid_count=conversions,
                delivered_price=99.99,
                observed_at=datetime.utcnow() - timedelta(days=4-i),
            )
            db.add(history)
        await db.commit()

        result = await DemandMetricsCalculator.calculate_metrics(db, build.id)

        assert result is not None
        assert (result.volatility_score or 0) > 0

    async def test_get_current_metrics(self, db: AsyncSession):
        """Retrieve latest metrics snapshot."""
        build = ManualBuild(
            name="Test",
            ebay_listing_id="ITEM-123",
        )
        db.add(build)
        await db.commit()

        # Create metrics
        await DemandMetricsCalculator.calculate_metrics(db, build.id)

        result = await DemandMetricsCalculator.get_current_metrics(db, build.id)

        assert result is not None
        assert result.manual_build_id == build.id

    async def test_get_metrics_history(self, db: AsyncSession):
        """Get historical metrics over time period."""
        build = ManualBuild(
            name="History",
            ebay_listing_id="ITEM-123",
        )
        db.add(build)
        await db.commit()

        # Create multiple snapshots
        for day in range(5):
            snapshot = DemandMetricsSnapshot(
                manual_build_id=build.id,
                view_count=100 + (day * 10),
                conversion_count=5 + day,
                recorded_at=datetime.utcnow() - timedelta(days=4-day),
            )
            db.add(snapshot)
        await db.commit()

        result = await DemandMetricsCalculator.get_metrics_history(db, build.id, 10)

        assert len(result) >= 5

    async def test_insufficient_data(self, db: AsyncSession):
        """Handle insufficient historical data."""
        build = ManualBuild(
            name="Empty",
            ebay_listing_id="ITEM-123",
        )
        db.add(build)
        await db.commit()

        result = await DemandMetricsCalculator.calculate_metrics(db, build.id)

        # Should return empty snapshot
        assert result is not None
        assert result.view_count == 0
