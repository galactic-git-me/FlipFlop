"""
Demand analysis API.

GET /demand/categories   — category-level demand signals derived from listings
GET /demand/auction-intel — live auction listings sorted by time-to-end
GET /demand/summary      — top-line demand summary for the dashboard
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.demand_service import compute_demand, compute_auction_intel
from app.services.external_demand import latest_external_signal_snapshot, ingest_external_demand_signals
from app.services.rich_demand_collector import get_rich_signals
from app.services.demand_pricing import compute_demand_pricing_multipliers
from app.services.sold_market_demand import build_sold_market_snapshot, generate_ai_insights, list_sold_market_observations

router = APIRouter(prefix="/demand", tags=["demand"])


@router.get("/categories")
async def get_demand_categories(db: AsyncSession = Depends(get_db)):
    """
    Returns all build categories with demand signals:
    count, gem_count, sparkline (7 days), trend direction, strength, insight.
    Sorted High → Medium → Low demand.
    """
    return await compute_demand(db)


@router.get("/auction-intel")
async def get_auction_intel(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    Active auction listings sorted by time-to-end (soonest first).
    Includes urgency classification: ending_soon / today / upcoming.
    """
    return await compute_auction_intel(db, limit=limit)


@router.get("/summary")
async def get_demand_summary(db: AsyncSession = Depends(get_db)):
    """
    Compact top-line summary for the dashboard Current Strategy card.
    Returns the hottest category + overall market health signal.
    """
    categories = await compute_demand(db)
    auctions = await compute_auction_intel(db, limit=5)

    # Use true total listing count as denominator (not just categorised subset)
    from sqlalchemy import func as sqlfunc
    from app.models.listing import Listing, Classification
    total_row = await db.execute(
        sqlfunc.count(Listing.id).select().select_from(Listing)
    )
    true_total = total_row.scalar() or 0

    total_gems = sum(c["gem_count"] for c in categories)
    total_listings = true_total or sum(c["count"] for c in categories)
    gem_rate = round(total_gems / total_listings * 100, 2) if total_listings else 0.0

    hottest = next((c for c in categories if c["strength"] == "High"), None)
    rising = [c for c in categories if c["trend"] == "rising"]
    falling = [c for c in categories if c["trend"] == "falling"]

    # Market health: proportion of High-demand categories
    high_count = sum(1 for c in categories if c["strength"] == "High")
    health = "hot" if high_count >= 3 else "warm" if high_count >= 1 else "cold"

    return {
        "total_listings": total_listings,
        "total_gems": total_gems,
        "gem_rate_pct": gem_rate,
        "market_health": health,   # hot | warm | cold
        "hottest_category": hottest,
        "rising_count": len(rising),
        "falling_count": len(falling),
        "categories": categories,
        "ending_soon_auctions": len([a for a in auctions if a["urgency"] == "ending_soon"]),
    }


@router.get("/external-signals")
async def get_external_signals(limit_per_source: int = Query(25, ge=1, le=100)):
    return await latest_external_signal_snapshot(limit_per_source=limit_per_source)


@router.post("/external-signals/refresh")
async def refresh_external_signals():
    return await ingest_external_demand_signals()


@router.get("/rich-signals")
async def get_rich_demand_signals():
    """
    Rich demand data: Google Trends time-series + geo, Reddit posts, Steam hardware stats.
    Returns empty collections if Refresh has not been run yet.
    """
    return await get_rich_signals()


@router.get("/pricing-multipliers")
async def get_pricing_multipliers(db: AsyncSession = Depends(get_db)):
    return await compute_demand_pricing_multipliers(db)


@router.get("/sold-market")
async def get_sold_market_demand(
    days: int = Query(90, ge=30, le=365),
    db: AsyncSession = Depends(get_db),
):
    return await build_sold_market_snapshot(db, days=days)


@router.get("/sold-market/insights")
async def get_sold_market_insights(
    refresh: bool = Query(False),
    days: int = Query(90, ge=30, le=365),
    db: AsyncSession = Depends(get_db),
):
    snapshot = await build_sold_market_snapshot(db, days=days)
    return await generate_ai_insights(snapshot, refresh=refresh)


@router.get("/sold-market/listings")
async def get_sold_market_listings(
    category: str = Query(..., pattern="^(cpu|gpu|motherboard|ram|case|psu)$"),
    days: int = Query(90, ge=30, le=365),
    limit: int = Query(250, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    return await list_sold_market_observations(db, category=category, days=days, limit=limit)
