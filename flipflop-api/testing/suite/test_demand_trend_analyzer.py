"""Tests for Demand Trend Analyzer (Phase 3, F3.1.3).

Verifies trend analysis, moving averages, and volatility.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import ManualBuild, DemandMetricsSnapshot
from app.services.demand_trend_analyzer import DemandTrendAnalyzer
from datetime import datetime, timedelta


@pytest.mark.asyncio
class TestTrendCalculation:
    """Test trend calculation."""

    async def test_calculate_rising_trend(self, db: AsyncSession):
        """Detect rising demand trend."""
        build = ManualBuild(name="Rising")
        db.add(build)
        await db.commit()

        # Increasing conversions
        for i in range(3):
            snapshot = DemandMetricsSnapshot(
                manual_build_id=build.id,
                conversion_count=2 + (i * 4),  # 2, 6, 10
                recorded_at=datetime.utcnow() - timedelta(days=2-i),
            )
            db.add(snapshot)
        await db.commit()

        result = await DemandTrendAnalyzer.calculate_trend(db, build.id, 7)

        assert result["trend"] == "rising"
        assert result["confidence"] >= 0.7

    async def test_calculate_declining_trend(self, db: AsyncSession):
        """Detect declining demand trend."""
        build = ManualBuild(name="Declining")
        db.add(build)
        await db.commit()

        # Decreasing conversions
        for i in range(3):
            snapshot = DemandMetricsSnapshot(
                manual_build_id=build.id,
                conversion_count=10 - (i * 4),  # 10, 6, 2
                recorded_at=datetime.utcnow() - timedelta(days=2-i),
            )
            db.add(snapshot)
        await db.commit()

        result = await DemandTrendAnalyzer.calculate_trend(db, build.id, 7)

        assert result["trend"] == "declining"

    async def test_insufficient_data_trend(self, db: AsyncSession):
        """Handle insufficient data for trend."""
        build = ManualBuild(name="Empty")
        db.add(build)
        await db.commit()

        result = await DemandTrendAnalyzer.calculate_trend(db, build.id, 7)

        assert result["trend"] == "unknown"


@pytest.mark.asyncio
class TestMovingAverage:
    """Test moving average calculation."""

    async def test_moving_average_views(self, db: AsyncSession):
        """Calculate moving average of views."""
        build = ManualBuild(name="MA Test")
        db.add(build)
        await db.commit()

        # Add snapshots with known view counts
        for i in range(3):
            snapshot = DemandMetricsSnapshot(
                manual_build_id=build.id,
                view_count=100 + (i * 50),  # 100, 150, 200
                recorded_at=datetime.utcnow() - timedelta(days=2-i),
            )
            db.add(snapshot)
        await db.commit()

        result = await DemandTrendAnalyzer.get_moving_average(
            db, build.id, "view_count", 7
        )

        # MA should be (100+150+200)/3 = 150
        assert 145 < result < 155

    async def test_moving_average_conversions(self, db: AsyncSession):
        """Calculate moving average of conversions."""
        build = ManualBuild(name="Conv MA")
        db.add(build)
        await db.commit()

        for i in range(3):
            snapshot = DemandMetricsSnapshot(
                manual_build_id=build.id,
                conversion_count=5 + i,  # 5, 6, 7
                recorded_at=datetime.utcnow() - timedelta(days=2-i),
            )
            db.add(snapshot)
        await db.commit()

        result = await DemandTrendAnalyzer.get_moving_average(
            db, build.id, "conversion_count", 7
        )

        assert 5 < result < 7


@pytest.mark.asyncio
class TestVolatility:
    """Test volatility detection."""

    async def test_high_volatility(self, db: AsyncSession):
        """Detect high volatility."""
        build = ManualBuild(name="Volatile")
        db.add(build)
        await db.commit()

        # Create volatile conversions
        for conversions in [1, 10, 2, 12, 3]:
            snapshot = DemandMetricsSnapshot(
                manual_build_id=build.id,
                conversion_count=conversions,
                volatility_score=0.8,
            )
            db.add(snapshot)
        await db.commit()

        result = await DemandTrendAnalyzer.detect_volatility(db, build.id, 30)

        assert result >= 0.7

    async def test_low_volatility(self, db: AsyncSession):
        """Detect low volatility."""
        build = ManualBuild(name="Stable")
        db.add(build)
        await db.commit()

        # Consistent conversions
        for _ in range(3):
            snapshot = DemandMetricsSnapshot(
                manual_build_id=build.id,
                conversion_count=5,
                volatility_score=0.1,
            )
            db.add(snapshot)
        await db.commit()

        result = await DemandTrendAnalyzer.detect_volatility(db, build.id, 30)

        assert result < 0.3


@pytest.mark.asyncio
class TestSellThroughEstimation:
    """Test sell-through time estimation."""

    async def test_estimate_sell_through(self, db: AsyncSession):
        """Estimate days to sale."""
        build = ManualBuild(name="Estimate")
        db.add(build)
        await db.commit()

        # 0.5 conversions per day = 2 days to sell
        snapshot = DemandMetricsSnapshot(
            manual_build_id=build.id,
            conversions_per_day=0.5,
            trend_confidence=0.8,
        )
        db.add(snapshot)
        await db.commit()

        result = await DemandTrendAnalyzer.estimate_sell_through(db, build.id, 10)

        assert result["days_to_sell"] == 2
        assert result["confidence"] >= 0.7

    async def test_no_conversion_data(self, db: AsyncSession):
        """Handle no conversion data."""
        build = ManualBuild(name="No Conv")
        db.add(build)
        await db.commit()

        result = await DemandTrendAnalyzer.estimate_sell_through(db, build.id, 10)

        assert result["days_to_sell"] is None
