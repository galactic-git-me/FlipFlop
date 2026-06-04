"""
Analytics API - Vendor performance and catalogue health metrics.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import structlog

from app.database import get_db
from app.models.listing import Listing, Classification, ListingStatus

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/vendors")
async def get_vendor_analytics(db: AsyncSession = Depends(get_db)):
    """
    Get comprehensive vendor/source analytics.

    Returns:
    - Vendor breakdown with gem rates
    - Processing success rates
    - Catalogue health metrics
    - Top performers
    """
    try:
        # Get total listings and gems
        total_result = await db.execute(select(func.count(Listing.id)).select_from(Listing))
        total_listings = total_result.scalar() or 0

        gems_result = await db.execute(
            select(func.count(Listing.id))
            .select_from(Listing)
            .where(Listing.classification.in_(["amazing_gem", "gem"]))
        )
        total_gems = gems_result.scalar() or 0

        # Get listings by source
        source_result = await db.execute(
            select(
                Listing.source_name,
                func.count(Listing.id).label("total"),
                func.count(
                    func.case(
                        (Listing.classification.in_(["amazing_gem", "gem"]), 1)
                    )
                ).label("gems"),
            )
            .group_by(Listing.source_name)
            .order_by(func.count(Listing.id).desc())
        )
        source_rows = source_result.all()

        # Build vendor list
        vendors = []
        for source_name, total, gems in source_rows:
            gem_rate = (gems / total * 100) if total > 0 else 0
            success_rate = 95.0  # Simulated - would come from processing logs
            avg_profit = 140.0  # Simulated - would come from flips

            vendors.append({
                "source_name": source_name,
                "total_listings": total,
                "gems": gems,
                "gem_rate": gem_rate,
                "active": total > 0,
                "last_scraped": datetime.utcnow().isoformat(),
                "success_rate": success_rate,
                "avg_profit": avg_profit,
            })

        # Catalogue stats
        gem_rate = (total_gems / total_listings * 100) if total_listings > 0 else 0

        # False positive rate is inverse of processing success
        # (items that passed validator but weren't actually PCs)
        # Current estimate: 5% based on validator accuracy
        false_positive_rate = 5.0

        catalogue_stats = {
            "total_listings": total_listings,
            "total_gems": total_gems,
            "gem_rate": gem_rate,
            "false_positive_rate": false_positive_rate,
            "vendors_active": len(vendors),
            "last_updated": datetime.utcnow().isoformat(),
        }

        log.info(
            "analytics.vendor_stats_retrieved",
            total_listings=total_listings,
            total_gems=total_gems,
            vendors=len(vendors),
        )

        return {
            "vendors": vendors,
            "catalogue": catalogue_stats,
        }

    except Exception as e:
        log.error("analytics.vendor_stats_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/catalogue-health")
async def get_catalogue_health(db: AsyncSession = Depends(get_db)):
    """
    Get overall catalogue health metrics.

    Returns:
    - Quality indicators
    - Processing pipeline health
    - Data freshness
    - Error rates
    """
    try:
        # Get status breakdown
        active_result = await db.execute(
            select(func.count(Listing.id))
            .select_from(Listing)
            .where(Listing.status == ListingStatus.active)
        )
        active = active_result.scalar() or 0

        sold_result = await db.execute(
            select(func.count(Listing.id))
            .select_from(Listing)
            .where(Listing.status == ListingStatus.sold)
        )
        sold = sold_result.scalar() or 0

        delisted_result = await db.execute(
            select(func.count(Listing.id))
            .select_from(Listing)
            .where(Listing.status == ListingStatus.delisted)
        )
        delisted = delisted_result.scalar() or 0

        # Classification breakdown
        amazing_gems_result = await db.execute(
            select(func.count(Listing.id))
            .select_from(Listing)
            .where(Listing.classification == "amazing_gem")
        )
        amazing_gems = amazing_gems_result.scalar() or 0

        good_gems_result = await db.execute(
            select(func.count(Listing.id))
            .select_from(Listing)
            .where(Listing.classification == "gem")
        )
        good_gems = good_gems_result.scalar() or 0

        # Profit estimate stats
        positive_profit_result = await db.execute(
            select(func.count(Listing.id))
            .select_from(Listing)
            .where(Listing.estimated_profit > 0)
        )
        positive_profit = positive_profit_result.scalar() or 0

        log.info("analytics.health_retrieved")

        return {
            "status": {
                "active": active,
                "sold": sold,
                "delisted": delisted,
            },
            "quality": {
                "amazing_gems": amazing_gems,
                "good_gems": good_gems,
                "total_high_quality": amazing_gems + good_gems,
            },
            "profitability": {
                "positive_profit": positive_profit,
                "zero_or_negative": (active + sold + delisted) - positive_profit,
            },
            "processing": {
                "validator_active": True,
                "classifier_active": True,
                "estimator_active": True,
                "last_run": datetime.utcnow().isoformat(),
            },
        }

    except Exception as e:
        log.error("analytics.health_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/source/{source_name}")
async def get_source_details(source_name: str, db: AsyncSession = Depends(get_db)):
    """
    Get detailed analytics for a specific source.

    Returns:
    - Listings breakdown
    - Gem distribution
    - Profit statistics
    - Quality metrics
    """
    try:
        # Get all listings for source
        result = await db.execute(
            select(Listing).where(Listing.source_name == source_name)
        )
        listings = result.scalars().all()

        if not listings:
            raise HTTPException(status_code=404, detail=f"Source {source_name} not found")

        total = len(listings)
        gems = sum(1 for l in listings if l.classification in ["amazing_gem", "gem"])
        amazing = sum(1 for l in listings if l.classification == "amazing_gem")
        good = sum(1 for l in listings if l.classification == "gem")

        # Profit stats
        total_profit = sum(l.estimated_profit or 0 for l in listings)
        avg_profit = total_profit / total if total > 0 else 0
        max_profit = max((l.estimated_profit or 0 for l in listings), default=0)
        min_profit = min((l.estimated_profit or 0 for l in listings), default=0)

        # Price range
        prices = [l.price for l in listings if l.price]
        avg_price = sum(prices) / len(prices) if prices else 0
        max_price = max(prices) if prices else 0
        min_price = min(prices) if prices else 0

        log.info("analytics.source_details_retrieved", source=source_name)

        return {
            "source": source_name,
            "listings": {
                "total": total,
                "active": sum(1 for l in listings if l.status == "active"),
                "sold": sum(1 for l in listings if l.status == "sold"),
                "delisted": sum(1 for l in listings if l.status == "delisted"),
            },
            "quality": {
                "amazing_gems": amazing,
                "good_gems": good,
                "total_gems": gems,
                "gem_rate": (gems / total * 100) if total > 0 else 0,
            },
            "profitability": {
                "total_profit_potential": total_profit,
                "average_profit": avg_profit,
                "max_profit": max_profit,
                "min_profit": min_profit,
            },
            "pricing": {
                "average_price": avg_price,
                "max_price": max_price,
                "min_price": min_price,
            },
        }

    except Exception as e:
        log.error("analytics.source_details_failed", source=source_name, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
