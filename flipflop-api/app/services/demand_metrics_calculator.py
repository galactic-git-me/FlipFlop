"""Demand Metrics Calculator for Phase 3 F3.1.1.

Calculates demand metrics (views, conversions, rates) from gem_radar data.
Stores denormalized snapshots for fast dashboard queries.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timedelta
from app.models import (
    ManualBuild,
    DemandMetricsSnapshot,
    GemRadarListingDemandHistory,
)
from app.services.feature_flags import is_enabled, FeatureFlags
import structlog

log = structlog.get_logger(__name__)


class DemandMetricsCalculator:
    """Calculates demand metrics from marketplace data."""

    @staticmethod
    async def calculate_metrics(
        db: AsyncSession,
        build_id: int,
        lookback_days: int = 30,
    ) -> DemandMetricsSnapshot | None:
        """
        Calculate demand metrics for build from gem_radar_listing_demand_history.

        Args:
            db: AsyncSession
            build_id: Build to calculate metrics for
            lookback_days: Historical window (default 30 days)

        Returns:
            DemandMetricsSnapshot or None
        """
        if not is_enabled(FeatureFlags.DEMAND_INTEL_ENABLED):
            return None

        try:
            build = await db.get(ManualBuild, build_id)
            if not build:
                log.error("calculate_metrics_build_not_found", build_id=build_id)
                return None

            # Query gem_radar demand history for this build
            cutoff_date = datetime.utcnow() - timedelta(days=lookback_days)

            # Note: gem_radar uses listing_id, not manual_build_id
            # We need to join through a mapping table or use ebay_listing_id
            if not build.ebay_listing_id:
                log.warning(
                    "calculate_metrics_no_listing_id",
                    build_id=build_id,
                )
                # Return empty snapshot if no listing
                snapshot = DemandMetricsSnapshot(
                    manual_build_id=build_id,
                    view_count=0,
                    impression_count=0,
                    conversion_count=0,
                    demand_trend="unknown",
                )
                db.add(snapshot)
                await db.commit()
                return snapshot

            # Query demand history
            stmt = select(GemRadarListingDemandHistory).where(
                GemRadarListingDemandHistory.listing_id == build.ebay_listing_id,
                GemRadarListingDemandHistory.observed_at >= cutoff_date,
            ).order_by(GemRadarListingDemandHistory.observed_at)

            result = await db.execute(stmt)
            demand_history = result.scalars().all()

            if not demand_history:
                # No data, return empty snapshot
                snapshot = DemandMetricsSnapshot(
                    manual_build_id=build_id,
                    view_count=0,
                    impression_count=0,
                    conversion_count=0,
                    demand_trend="unknown",
                )
                db.add(snapshot)
                await db.commit()
                return snapshot

            # Calculate aggregates
            total_views = sum(h.watch_count or 0 for h in demand_history)
            total_conversions = sum(h.bid_count or 0 for h in demand_history)
            total_impressions = len(demand_history)

            # Calculate rates
            view_to_conversion_rate = (
                total_conversions / total_views if total_views > 0 else 0.0
            )
            sell_through_rate = (
                total_conversions / total_impressions if total_impressions > 0 else 0.0
            )

            # Calculate velocity
            days_in_window = (
                (demand_history[-1].observed_at - demand_history[0].observed_at).days
                or 1
            )
            views_per_day = total_views / max(days_in_window, 1)
            conversions_per_day = total_conversions / max(days_in_window, 1)

            # Determine trend (simple: compare first half vs second half)
            midpoint = len(demand_history) // 2
            if midpoint > 0:
                first_half_conversions = sum(
                    h.bid_count or 0 for h in demand_history[:midpoint]
                )
                second_half_conversions = sum(
                    h.bid_count or 0 for h in demand_history[midpoint:]
                )

                if second_half_conversions > first_half_conversions * 1.2:
                    trend = "rising"
                    confidence = 0.8
                elif second_half_conversions < first_half_conversions * 0.8:
                    trend = "declining"
                    confidence = 0.8
                else:
                    trend = "stable"
                    confidence = 0.6
            else:
                trend = "unknown"
                confidence = 0.0

            # Calculate volatility (coefficient of variation in conversion rate)
            daily_rates = []
            for h in demand_history:
                if h.watch_count and h.watch_count > 0:
                    rate = (h.bid_count or 0) / h.watch_count
                    daily_rates.append(rate)

            if daily_rates:
                mean_rate = sum(daily_rates) / len(daily_rates)
                variance = sum((r - mean_rate) ** 2 for r in daily_rates) / len(
                    daily_rates
                )
                volatility = (variance ** 0.5) / (mean_rate or 1)
                volatility_score = min(1.0, volatility / 2)  # Normalize to 0-1
            else:
                volatility_score = 0.0

            # Create snapshot
            snapshot = DemandMetricsSnapshot(
                manual_build_id=build_id,
                view_count=total_views,
                impression_count=total_impressions,
                conversion_count=total_conversions,
                view_to_conversion_rate=view_to_conversion_rate,
                sell_through_rate=sell_through_rate,
                views_per_day=views_per_day,
                conversions_per_day=conversions_per_day,
                demand_trend=trend,
                trend_confidence=confidence,
                volatility_score=volatility_score,
            )

            db.add(snapshot)
            await db.commit()

            log.info(
                "demand_metrics_calculated",
                build_id=build_id,
                views=total_views,
                conversions=total_conversions,
                trend=trend,
                volatility=volatility_score,
            )

            return snapshot

        except Exception as e:
            log.error(
                "calculate_metrics_failed",
                build_id=build_id,
                lookback_days=lookback_days,
                error=str(e),
            )
            await db.rollback()
            return None

    @staticmethod
    async def get_current_metrics(
        db: AsyncSession,
        build_id: int,
    ) -> DemandMetricsSnapshot | None:
        """Get latest metrics snapshot for build."""
        try:
            stmt = select(DemandMetricsSnapshot).where(
                DemandMetricsSnapshot.manual_build_id == build_id,
            ).order_by(DemandMetricsSnapshot.recorded_at.desc())

            result = await db.execute(stmt)
            return result.scalars().first()

        except Exception as e:
            log.error(
                "get_current_metrics_failed",
                build_id=build_id,
                error=str(e),
            )
            return None

    @staticmethod
    async def get_metrics_history(
        db: AsyncSession,
        build_id: int,
        days: int = 30,
    ) -> list[DemandMetricsSnapshot]:
        """Get historical metrics over time period."""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)

            stmt = select(DemandMetricsSnapshot).where(
                DemandMetricsSnapshot.manual_build_id == build_id,
                DemandMetricsSnapshot.recorded_at >= cutoff_date,
            ).order_by(DemandMetricsSnapshot.recorded_at)

            result = await db.execute(stmt)
            return result.scalars().all()

        except Exception as e:
            log.error(
                "get_metrics_history_failed",
                build_id=build_id,
                days=days,
                error=str(e),
            )
            return []
