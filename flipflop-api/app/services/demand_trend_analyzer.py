"""Demand Trend Analyzer for Phase 3 F3.1.3.

Analyzes demand trends, moving averages, and volatility.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
from app.models import DemandMetricsSnapshot
from app.services.demand_metrics_calculator import DemandMetricsCalculator
import structlog

log = structlog.get_logger(__name__)


class DemandTrendAnalyzer:
    """Analyzes demand trends and patterns."""

    @staticmethod
    async def calculate_trend(
        db: AsyncSession,
        build_id: int,
        window_days: int = 7,
    ) -> dict:
        """Calculate demand trend over window."""
        try:
            history = await DemandMetricsCalculator.get_metrics_history(
                db, build_id, window_days
            )

            if not history or len(history) < 2:
                return {
                    "trend": "unknown",
                    "confidence": 0.0,
                    "reason": "insufficient_data",
                }

            # Compare first and last conversions
            first_conversions = history[0].conversion_count or 0
            last_conversions = history[-1].conversion_count or 0

            if last_conversions > first_conversions * 1.2:
                trend = "rising"
                confidence = 0.8
            elif last_conversions < first_conversions * 0.8:
                trend = "declining"
                confidence = 0.8
            else:
                trend = "stable"
                confidence = 0.6

            return {
                "trend": trend,
                "confidence": confidence,
                "first_conversions": first_conversions,
                "last_conversions": last_conversions,
            }

        except Exception as e:
            log.error(
                "calculate_trend_failed",
                build_id=build_id,
                window_days=window_days,
                error=str(e),
            )
            return {"trend": "error", "confidence": 0.0}

    @staticmethod
    async def get_moving_average(
        db: AsyncSession,
        build_id: int,
        metric: str,
        window_days: int = 7,
    ) -> float:
        """Get N-day moving average for metric."""
        try:
            history = await DemandMetricsCalculator.get_metrics_history(
                db, build_id, window_days
            )

            if not history:
                return 0.0

            values = []
            for snapshot in history:
                if metric == "view_count":
                    values.append(snapshot.view_count or 0)
                elif metric == "conversion_count":
                    values.append(snapshot.conversion_count or 0)
                elif metric == "conversion_rate":
                    values.append(snapshot.view_to_conversion_rate or 0.0)
                elif metric == "sell_through_rate":
                    values.append(snapshot.sell_through_rate or 0.0)

            return sum(values) / len(values) if values else 0.0

        except Exception as e:
            log.error(
                "get_moving_average_failed",
                build_id=build_id,
                metric=metric,
                error=str(e),
            )
            return 0.0

    @staticmethod
    async def detect_volatility(
        db: AsyncSession,
        build_id: int,
        lookback_days: int = 30,
    ) -> float:
        """Calculate demand volatility (0.0-1.0)."""
        try:
            history = await DemandMetricsCalculator.get_metrics_history(
                db, build_id, lookback_days
            )

            if not history or len(history) < 2:
                return 0.0

            # Use coefficient of variation from latest snapshot
            latest = history[-1]
            return latest.volatility_score or 0.0

        except Exception as e:
            log.error(
                "detect_volatility_failed",
                build_id=build_id,
                lookback_days=lookback_days,
                error=str(e),
            )
            return 0.0

    @staticmethod
    async def estimate_sell_through(
        db: AsyncSession,
        build_id: int,
        days_listed: int,
    ) -> dict:
        """Estimate when build will sell based on trend."""
        try:
            current = await DemandMetricsCalculator.get_current_metrics(db, build_id)

            if not current or not current.conversions_per_day:
                return {
                    "days_to_sell": None,
                    "confidence": 0.0,
                    "reason": "no_conversion_data",
                }

            # Estimate: need 1 conversion to sell (per build)
            days_to_sell = 1.0 / current.conversions_per_day

            confidence = current.trend_confidence

            return {
                "days_to_sell": int(days_to_sell),
                "confidence": confidence,
                "conversions_per_day": current.conversions_per_day,
                "trend": current.demand_trend,
            }

        except Exception as e:
            log.error(
                "estimate_sell_through_failed",
                build_id=build_id,
                days_listed=days_listed,
                error=str(e),
            )
            return {"days_to_sell": None, "confidence": 0.0, "error": str(e)}
