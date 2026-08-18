"""Track and calculate demand velocity (watch/bid growth over time) for GEM scoring."""
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from app.models.gem_radar_listing_demand_history import GemRadarListingDemandHistory
from app.gem_radar.schemas import ExtractedListing


async def record_demand_snapshot(
    db: AsyncSession,
    listing_id: str,
    search_run_id: str,
    watch_count: int | None,
    bid_count: int | None,
    delivered_price: float,
) -> None:
    """Record a bounded point-in-time snapshot for velocity tracking.

    Phase 2 can be retried repeatedly after a failed sweep. Never append an
    identical observation more than once per hour; doing so previously grew
    this table by millions of redundant rows in a few days.
    """
    latest = (
        await db.execute(
            select(GemRadarListingDemandHistory)
            .where(GemRadarListingDemandHistory.listing_id == listing_id)
            .order_by(GemRadarListingDemandHistory.observed_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    now = datetime.utcnow()
    if latest is not None and now - latest.observed_at < timedelta(hours=1):
        if (
            latest.watch_count == watch_count
            and latest.bid_count == bid_count
            and latest.delivered_price == delivered_price
        ):
            return

    snapshot = GemRadarListingDemandHistory(
        listing_id=listing_id,
        search_run_id=search_run_id,
        watch_count=watch_count,
        bid_count=bid_count,
        delivered_price=delivered_price,
        observed_at=now,
    )
    db.add(snapshot)


async def calculate_watch_velocity(db: AsyncSession, listing_id: str, hours: int = 24) -> float | None:
    """Calculate watch-count growth rate (watches per hour) over the past N hours.
    Returns None if insufficient history (< 2 data points)."""
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    result = await db.execute(
        select(GemRadarListingDemandHistory)
        .where(
            GemRadarListingDemandHistory.listing_id == listing_id,
            GemRadarListingDemandHistory.observed_at >= cutoff,
            GemRadarListingDemandHistory.watch_count.is_not(None),
        )
        .order_by(GemRadarListingDemandHistory.observed_at.asc())
    )
    snapshots = result.scalars().all()

    if len(snapshots) < 2:
        return None

    first, last = snapshots[0], snapshots[-1]
    watch_delta = max(0, last.watch_count - first.watch_count)
    time_delta_hours = (last.observed_at - first.observed_at).total_seconds() / 3600
    if time_delta_hours <= 0:
        return None

    return watch_delta / time_delta_hours


async def calculate_bid_velocity(db: AsyncSession, listing_id: str, hours: int = 24) -> float | None:
    """Calculate bid-count growth rate (bids per hour) over the past N hours.
    Returns None if insufficient history (< 2 data points)."""
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    result = await db.execute(
        select(GemRadarListingDemandHistory)
        .where(
            GemRadarListingDemandHistory.listing_id == listing_id,
            GemRadarListingDemandHistory.observed_at >= cutoff,
            GemRadarListingDemandHistory.bid_count.is_not(None),
        )
        .order_by(GemRadarListingDemandHistory.observed_at.asc())
    )
    snapshots = result.scalars().all()

    if len(snapshots) < 2:
        return None

    first, last = snapshots[0], snapshots[-1]
    bid_delta = max(0, last.bid_count - first.bid_count)
    time_delta_hours = (last.observed_at - first.observed_at).total_seconds() / 3600
    if time_delta_hours <= 0:
        return None

    return bid_delta / time_delta_hours


async def detect_hot_item(db: AsyncSession, listing_id: str) -> bool:
    """Returns True if this listing shows signs of being a hot item:
    - Watch count growing > 2 per hour
    - Bid count growing > 0.5 per hour
    These are used to boost confidence in GEM/SUPER_GEM listings."""
    watch_vel = await calculate_watch_velocity(db, listing_id, hours=6)
    bid_vel = await calculate_bid_velocity(db, listing_id, hours=6)

    if watch_vel is not None and watch_vel > 2.0:
        return True
    if bid_vel is not None and bid_vel > 0.5:
        return True

    return False


async def estimate_time_to_sell(db: AsyncSession, listing_id: str) -> float | None:
    """Estimate time-to-sell (in hours) based on historical disappearance patterns.
    Returns None if listing is still active or insufficient history."""
    result = await db.execute(
        select(GemRadarListingDemandHistory)
        .where(GemRadarListingDemandHistory.listing_id == listing_id)
        .order_by(GemRadarListingDemandHistory.observed_at.desc())
        .limit(1)
    )
    latest = result.scalar_one_or_none()
    if latest is None or latest.status == "active":
        return None

    # If status is sold/ended, calculate hours from first observation to last
    result_all = await db.execute(
        select(GemRadarListingDemandHistory)
        .where(GemRadarListingDemandHistory.listing_id == listing_id)
        .order_by(GemRadarListingDemandHistory.observed_at.asc())
    )
    snapshots = result_all.scalars().all()
    if len(snapshots) < 2:
        return None

    first_seen = snapshots[0].observed_at
    last_seen = snapshots[-1].observed_at
    return (last_seen - first_seen).total_seconds() / 3600
