"""Tests for Demand Alert Service (Phase 3, F3.1.4).

Verifies alert generation and management.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import ManualBuild, DemandAlert, DemandMetricsSnapshot
from app.services.demand_alert_service import DemandAlertService


@pytest.mark.asyncio
class TestCheckAlerts:
    """Test alert triggering."""

    async def test_high_demand_alert(self, db: AsyncSession):
        """Trigger high demand alert."""
        build = ManualBuild(name="High Demand")
        db.add(build)
        await db.commit()

        # High demand: 15 conversions at 60% rate
        metrics = DemandMetricsSnapshot(
            manual_build_id=build.id,
            conversion_count=15,
            view_to_conversion_rate=0.6,
        )
        db.add(metrics)
        await db.commit()

        alerts = await DemandAlertService.check_demand_alerts(db, build.id)

        assert len(alerts) > 0
        high_demand = [a for a in alerts if a.alert_type == "high_demand"]
        assert len(high_demand) > 0

    async def test_low_demand_alert(self, db: AsyncSession):
        """Trigger low demand alert."""
        build = ManualBuild(name="Low Demand")
        db.add(build)
        await db.commit()

        # Low demand: 150 views at 5% rate
        metrics = DemandMetricsSnapshot(
            manual_build_id=build.id,
            view_count=150,
            view_to_conversion_rate=0.05,
        )
        db.add(metrics)
        await db.commit()

        alerts = await DemandAlertService.check_demand_alerts(db, build.id)

        assert len(alerts) > 0
        low_demand = [a for a in alerts if a.alert_type == "low_demand"]
        assert len(low_demand) > 0

    async def test_risk_flag_alert(self, db: AsyncSession):
        """Trigger risk flag alert."""
        build = ManualBuild(name="Volatile")
        db.add(build)
        await db.commit()

        # High volatility
        metrics = DemandMetricsSnapshot(
            manual_build_id=build.id,
            volatility_score=0.8,
        )
        db.add(metrics)
        await db.commit()

        alerts = await DemandAlertService.check_demand_alerts(db, build.id)

        risk_flags = [a for a in alerts if a.alert_type == "risk_flag"]
        assert len(risk_flags) > 0

    async def test_no_alerts(self, db: AsyncSession):
        """No alerts when within thresholds."""
        build = ManualBuild(name="Normal")
        db.add(build)
        await db.commit()

        # Normal metrics
        metrics = DemandMetricsSnapshot(
            manual_build_id=build.id,
            conversion_count=3,
            view_to_conversion_rate=0.15,
            volatility_score=0.3,
        )
        db.add(metrics)
        await db.commit()

        alerts = await DemandAlertService.check_demand_alerts(db, build.id)

        assert len(alerts) == 0


@pytest.mark.asyncio
class TestAlertManagement:
    """Test alert acknowledgement."""

    async def test_acknowledge_alert(self, db: AsyncSession):
        """Acknowledge an alert."""
        build = ManualBuild(name="Test")
        db.add(build)
        await db.commit()

        alert = DemandAlert(
            manual_build_id=build.id,
            alert_type="high_demand",
            severity="info",
            message="Test alert",
            metric_name="view_count",
            threshold_value=100,
            actual_value=150,
        )
        db.add(alert)
        await db.commit()

        result = await DemandAlertService.acknowledge_alert(db, alert.id)

        assert result is True

        # Verify acknowledged
        updated = await db.get(DemandAlert, alert.id)
        assert updated.acknowledged_at is not None

    async def test_get_active_alerts(self, db: AsyncSession):
        """Get unacknowledged alerts."""
        build = ManualBuild(name="Test")
        db.add(build)
        await db.commit()

        # Add unacknowledged alert
        alert = DemandAlert(
            manual_build_id=build.id,
            alert_type="low_demand",
            severity="warning",
            message="Test",
            metric_name="conversion_rate",
            threshold_value=0.1,
            actual_value=0.05,
        )
        db.add(alert)
        await db.commit()

        active = await DemandAlertService.get_active_alerts(db, build.id)

        assert len(active) == 1
        assert active[0].acknowledged_at is None

    async def test_get_alert_stats(self, db: AsyncSession):
        """Get alert statistics."""
        build = ManualBuild(name="Test")
        db.add(build)
        await db.commit()

        # Add alerts of different severities
        for severity in ["info", "warning", "critical"]:
            alert = DemandAlert(
                manual_build_id=build.id,
                alert_type="high_demand",
                severity=severity,
                message="Test",
                metric_name="view_count",
                threshold_value=100,
                actual_value=150,
            )
            db.add(alert)
        await db.commit()

        stats = await DemandAlertService.get_alert_stats(db)

        assert stats["total_alerts"] >= 3
        assert "info" in stats["by_severity"]
