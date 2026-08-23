"""Price History Service for Phase 2 (F2.1.4).

Tracks all price changes and enables trend analysis.
Pattern: Every price change recorded with reason and timestamp.
Immutable audit trail prevents data loss or manipulation.

Uses: Detect stale pricing, analyze volatility, find optimal relist timing.
"""

from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from app.models import PriceHistory, ManualBuild
from app.services.money import Money
import structlog

log = structlog.get_logger(__name__)


class PriceHistoryService:
    """Track and analyze price changes."""

    @staticmethod
    async def record_price_change(
        db: AsyncSession,
        manual_build_id: int,
        new_price: Money,
        reason: str,
    ) -> PriceHistory:
        """Record a price change in history.

        Args:
            db: AsyncSession
            manual_build_id: Build whose price changed
            new_price: New price (Money object)
            reason: Why price changed

        Returns:
            PriceHistory record
        """
        # Get current price as previous
        build = await db.get(ManualBuild, manual_build_id)
        if not build:
            raise ValueError(f"Build {manual_build_id} not found")

        previous_price = build.ebay_price

        # Create history record
        record = PriceHistory(
            manual_build_id=manual_build_id,
            price_gbp=new_price.to_pennies(),
            reason=reason,
            previous_price_gbp=int(previous_price * 100) if previous_price else None,
        )

        db.add(record)
        await db.commit()

        log.info(
            "price_change_recorded",
            build_id=manual_build_id,
            old_price=previous_price,
            new_price=new_price.to_float(),
            reason=reason,
        )

        return record

    @staticmethod
    async def get_price_history(
        db: AsyncSession,
        manual_build_id: int,
        days: int = 30,
    ) -> list[PriceHistory]:
        """Get price history for a build over time period.

        Args:
            db: AsyncSession
            manual_build_id: Build to query
            days: Look back this many days (default 30)

        Returns:
            List of PriceHistory records, newest first
        """
        cutoff = datetime.utcnow() - timedelta(days=days)

        stmt = select(PriceHistory).where(
            and_(
                PriceHistory.manual_build_id == manual_build_id,
                PriceHistory.recorded_at >= cutoff,
            )
        ).order_by(PriceHistory.recorded_at.desc())

        result = await db.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def calculate_price_trend(
        db: AsyncSession,
        manual_build_id: int,
        days: int = 30,
    ) -> dict:
        """Calculate price trend statistics.

        Args:
            db: AsyncSession
            manual_build_id: Build to analyze
            days: Period to analyze

        Returns:
            Dict with: min_price, max_price, avg_price, trend, volatility, age_days
        """
        history = await PriceHistoryService.get_price_history(
            db, manual_build_id, days
        )

        if not history:
            return {
                "min_price": None,
                "max_price": None,
                "avg_price": None,
                "trend": None,
                "volatility": None,
                "age_days": None,
            }

        prices = [Money.from_pennies(h.price_gbp, "GBP") for h in history]

        # Calculate statistics
        min_price = min(prices)
        max_price = max(prices)
        avg_price = sum(p.amount for p in prices) / len(prices)

        # Trend: old price vs new price
        oldest = prices[-1]
        newest = prices[0]
        trend = (newest - oldest).to_float()

        # Volatility: price range as % of average
        volatility_pct = ((max_price - min_price).to_float() / float(avg_price)) * 100 if avg_price > 0 else 0

        # Age: days since first price record
        age_days = (datetime.utcnow() - history[-1].recorded_at).days

        return {
            "min_price": min_price.to_float(),
            "max_price": max_price.to_float(),
            "avg_price": float(avg_price),
            "trend": trend,  # Negative = declining, positive = increasing
            "volatility": volatility_pct,
            "age_days": age_days,
        }

    @staticmethod
    async def is_price_stale(
        db: AsyncSession,
        manual_build_id: int,
        stale_days: int = 7,
    ) -> bool:
        """Check if build price hasn't changed in a while.

        Args:
            db: AsyncSession
            manual_build_id: Build to check
            stale_days: How many days without change = stale

        Returns:
            True if price hasn't changed in stale_days
        """
        history = await PriceHistoryService.get_price_history(
            db, manual_build_id, days=stale_days
        )

        if not history:
            return True  # No history = stale

        # If only one record in the period, price hasn't changed
        return len(history) <= 1
