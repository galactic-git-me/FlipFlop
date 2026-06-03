"""
Reselling Center API routes - pricing, listings, messaging, sales tracking.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import structlog

from app.database import get_db
from app.models.flip import Flip
from app.services import ebay_pricing

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/reselling", tags=["reselling"])


@router.get("/seller-fees")
async def get_current_seller_fees():
    """
    Get current eBay seller fees for the account.

    Returns fees including insertion fee, final value fee %, seller tier, etc.
    """
    try:
        fees = await ebay_pricing.get_seller_fees()
        if not fees:
            raise HTTPException(status_code=503, detail="Unable to fetch eBay seller fees")
        return fees
    except ebay_pricing.eBayPricingError as e:
        log.error("reselling.fetch_fees_failed", error=str(e))
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/flips/{flip_id}/pricing-analysis")
async def analyze_flip_pricing(
    flip_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Analyze pricing for a flip using current eBay seller fees.

    Returns:
    - Walk-away price (minimum acceptable)
    - Total cost position (2x cost)
    - Optimal listing price (estimated resale)
    - Estimated profit at optimal price
    - Break-even price
    - All fee breakdowns
    """
    # Get flip from database
    result = await db.execute(select(Flip).where(Flip.id == flip_id))
    flip = result.scalar_one_or_none()

    if not flip:
        raise HTTPException(status_code=404, detail=f"Flip {flip_id} not found")

    try:
        # Analyze pricing with current fees
        analysis = await ebay_pricing.analyze_flip_pricing(
            flip_id=flip_id,
            total_cost=flip.total_cost,
            estimated_resale=flip.current_estimated_resale or flip.initial_estimated_resale,
        )

        # Optionally save pricing snapshot to flip model (future enhancement)
        # flip.listing_fee_pct = analysis["seller_fees"]["insertion_fee"]
        # flip.final_value_fee_pct = analysis["seller_fees"]["final_value_fee_pct"]
        # await db.commit()

        log.info("reselling.pricing_analysis", flip_id=flip_id,
                optimal_price=analysis["pricing_tiers"]["optimal_listing_price"])

        return analysis

    except Exception as e:
        log.error("reselling.pricing_analysis_failed", flip_id=flip_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Pricing analysis failed: {e}")


@router.get("/flips/{flip_id}/pricing-summary")
async def get_flip_pricing_summary(
    flip_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Get a quick pricing summary for a flip (walk-away + optimal prices).
    Useful for quick UI display.
    """
    result = await db.execute(select(Flip).where(Flip.id == flip_id))
    flip = result.scalar_one_or_none()

    if not flip:
        raise HTTPException(status_code=404, detail=f"Flip {flip_id} not found")

    try:
        # Quick calculation without full analysis
        fees = await ebay_pricing.get_seller_fees()
        tiers = ebay_pricing.calculate_pricing_tiers(
            total_cost=flip.total_cost,
            estimated_resale=flip.current_estimated_resale or flip.initial_estimated_resale,
            insertion_fee=fees.get("insertion_fee", 0.30),
            final_value_fee_pct=fees.get("final_value_fee_pct", 0.127),
        )

        return {
            "flip_id": flip_id,
            "total_cost": flip.total_cost,
            "estimated_resale": flip.current_estimated_resale or flip.initial_estimated_resale,
            "walk_away_price": tiers["walk_away_price"],
            "optimal_listing_price": tiers["optimal_listing_price"],
            "estimated_profit": tiers["estimated_profit_at_optimal"],
            "margin_pct": tiers["margin_pct"],
        }

    except Exception as e:
        log.error("reselling.pricing_summary_failed", flip_id=flip_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
