"""Demand Alert Service for Phase 3 F3.1.4.

Generates predictive alerts based on demand signals.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import ManualBuild, DemandAlert
from app.services.demand_metrics_calculator import DemandMetricsCalculator
import structlog

log = structlog.get_logger(__name__)


class DemandAlertService:
    """Manages demand-based alerts."""

    @staticmethod
    async def check_demand_alerts(
        db: AsyncSession,
        build_id: int,
    ) -> list[DemandAlert]:
        """Check if build triggers any demand alerts."""
        try:
            build = await db.get(ManualBuild, build_id)
            if not build:
                return []

            metrics = await DemandMetricsCalculator.get_current_metrics(db, build_id)
            if not metrics:
                return []

            alerts = []

            # High demand alert: conversions > 10 AND rate > 50%
            if (
                (metrics.conversion_count or 0) > 10
                and (metrics.view_to_conversion_rate or 0) > 0.5
            ):
                alert = DemandAlert(
                    manual_build_id=build_id,
                    alert_type="high_demand",
                    severity="info",
                    message=f"Build showing strong demand ({metrics.conversion_count} conversions at {(metrics.view_to_conversion_rate or 0)*100:.1f}%)",
                    metric_name="view_to_conversion_rate",
                    threshold_value=0.5,
                    actual_value=metrics.view_to_conversion_rate or 0.0,
                )
                db.add(alert)
                alerts.append(alert)

            # Low demand alert: views > 100 AND rate < 10%
            if (
                (metrics.view_count or 0) > 100
                and (metrics.view_to_conversion_rate or 0) < 0.1
            ):
                alert = DemandAlert(
                    manual_build_id=build_id,
                    alert_type="low_demand",
                    severity="warning",
                    message=f"Build has low conversion rate ({(metrics.view_to_conversion_rate or 0)*100:.1f}%) despite {metrics.view_count} views",
                    metric_name="view_to_conversion_rate",
                    threshold_value=0.1,
                    actual_value=metrics.view_to_conversion_rate or 0.0,
                )
                db.add(alert)
                alerts.append(alert)

            # Risk flag: high volatility (unstable demand)
            if (metrics.volatility_score or 0) > 0.7:
                alert = DemandAlert(
                    manual_build_id=build_id,
                    alert_type="risk_flag",
                    severity="warning",
                    message=f"Build demand is highly volatile ({metrics.volatility_score*100:.1f}%) - may be unpredictable",
                    metric_name="volatility_score",
                    threshold_value=0.7,
                    actual_value=metrics.volatility_score or 0.0,
                )
                db.add(alert)
                alerts.append(alert)

            if alerts:
                await db.commit()
                log.info(
                    "demand_alerts_created",
                    build_id=build_id,
                    alert_count=len(alerts),
                )

            return alerts

        except Exception as e:
            log.error(
                "check_demand_alerts_failed",
                build_id=build_id,
                error=str(e),
            )
            await db.rollback()
            return []

    @staticmethod
    async def get_active_alerts(
        db: AsyncSession,
        build_id: int,
    ) -> list[DemandAlert]:
        """Get unacknowledged alerts for build."""
        try:
            stmt = select(DemandAlert).where(
                DemandAlert.manual_build_id == build_id,
                DemandAlert.acknowledged_at.is_(None),
            ).order_by(DemandAlert.created_at.desc())

            result = await db.execute(stmt)
            return result.scalars().all()

        except Exception as e:
            log.error(
                "get_active_alerts_failed",
                build_id=build_id,
                error=str(e),
            )
            return []

    @staticmethod
    async def acknowledge_alert(
        db: AsyncSession,
        alert_id: int,
    ) -> bool:
        """Mark alert as acknowledged."""
        try:
            from datetime import datetime

            alert = await db.get(DemandAlert, alert_id)
            if not alert:
                return False

            alert.acknowledged_at = datetime.utcnow()
            await db.commit()

            log.info("demand_alert_acknowledged", alert_id=alert_id)
            return True

        except Exception as e:
            log.error(
                "acknowledge_alert_failed",
                alert_id=alert_id,
                error=str(e),
            )
            await db.rollback()
            return False

    @staticmethod
    async def get_alert_stats(db: AsyncSession) -> dict:
        """Get statistics on all active alerts."""
        try:
            stmt = select(DemandAlert).where(
                DemandAlert.acknowledged_at.is_(None)
            )

            result = await db.execute(stmt)
            alerts = result.scalars().all()

            by_severity = {}
            by_type = {}

            for alert in alerts:
                by_severity[alert.severity] = by_severity.get(alert.severity, 0) + 1
                by_type[alert.alert_type] = by_type.get(alert.alert_type, 0) + 1

            return {
                "total_alerts": len(alerts),
                "by_severity": by_severity,
                "by_type": by_type,
            }

        except Exception as e:
            log.error(
                "get_alert_stats_failed",
                error=str(e),
            )
            return {"total_alerts": 0, "by_severity": {}, "by_type": {}}
