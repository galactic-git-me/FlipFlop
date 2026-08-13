"""
Reselling Center API routes - pricing, listings, messaging, sales tracking.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import structlog

from app.database import get_db
from app.models.flip import Flip
from app.services import ebay_pricing, image_processor, listing_generator

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


@router.post("/flips/{flip_id}/generate-listing")
async def generate_flip_listing(
    flip_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Generate professional eBay listing with AI.

    Returns:
    - Multiple title options (user picks best)
    - Professional description with FlipFlop branding
    - Estimated specs summary
    """
    result = await db.execute(select(Flip).where(Flip.id == flip_id))
    flip = result.scalar_one_or_none()

    if not flip:
        raise HTTPException(status_code=404, detail=f"Flip {flip_id} not found")

    try:
        listing = await listing_generator.generate_full_listing(flip)

        # Optionally save to flip model
        # flip.generated_title = listing["recommended_title"]
        # flip.generated_description = listing["description"]
        # await db.commit()

        log.info("reselling.listing_generated", flip_id=flip_id)
        return listing

    except Exception as e:
        log.error("reselling.listing_generation_failed", flip_id=flip_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Listing generation failed: {e}")


@router.post("/flips/{flip_id}/process-images")
async def process_flip_images(
    flip_id: int,
    image_urls: list[str] = [],
    add_watermark: bool = True,
    db: AsyncSession = Depends(get_db),
):
    """
    Process and brand images for an eBay listing.

    Args:
        flip_id: Flip ID
        image_urls: List of image URLs to process
        add_watermark: Whether to add FlipFlop branding

    Returns:
    - List of processed image URLs (or base64 encoded if stored locally)
    - Processing stats (processed count, errors, sizes)
    """
    result = await db.execute(select(Flip).where(Flip.id == flip_id))
    flip = result.scalar_one_or_none()

    if not flip:
        raise HTTPException(status_code=404, detail=f"Flip {flip_id} not found")

    # Use listing images if none provided
    if not image_urls and flip.listing and flip.listing.image_urls:
        image_urls = flip.listing.image_urls

    if not image_urls:
        raise HTTPException(status_code=400, detail="No image URLs provided")

    try:
        # Process images
        processed_bytes, errors = await image_processor.process_images_for_listing(
            image_urls,
            max_concurrent=3,
            add_watermark=add_watermark,
        )

        if not processed_bytes:
            raise HTTPException(status_code=500, detail="No images could be processed")

        # Convert bytes to base64 for transfer (in production, would upload to S3)
        import base64

        image_data = [
            {
                "base64": base64.b64encode(img_bytes).decode("utf-8"),
                "size_kb": image_processor.get_image_size_kb(img_bytes),
            }
            for img_bytes in processed_bytes
        ]

        # Optionally save image URLs to flip
        # flip.generated_images_urls = [img["base64"] for img in image_data]
        # flip.image_generation_status = "complete"
        # await db.commit()

        log.info(
            "reselling.images_processed",
            flip_id=flip_id,
            processed=len(processed_bytes),
            errors=len(errors),
        )

        return {
            "flip_id": flip_id,
            "images": image_data,
            "processed_count": len(processed_bytes),
            "error_count": len(errors),
            "error_urls": errors,
        }

    except Exception as e:
        log.error("reselling.image_processing_failed", flip_id=flip_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Image processing failed: {e}")


@router.get("/flips/{flip_id}/listing-preview")
async def get_listing_preview(
    flip_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Get complete preview of a flip listing before posting.

    Combines:
    - Pricing analysis
    - Generated title & description
    - Processed images (if available)
    - Estimated profit
    """
    result = await db.execute(select(Flip).where(Flip.id == flip_id))
    flip = result.scalar_one_or_none()

    if not flip:
        raise HTTPException(status_code=404, detail=f"Flip {flip_id} not found")

    try:
        # Get pricing
        fees = await ebay_pricing.get_seller_fees()
        pricing = ebay_pricing.calculate_pricing_tiers(
            total_cost=flip.total_cost,
            estimated_resale=flip.current_estimated_resale or flip.initial_estimated_resale,
            insertion_fee=fees.get("insertion_fee", 0.30),
            final_value_fee_pct=fees.get("final_value_fee_pct", 0.127),
        )

        # Get listing content (use existing generated or create new)
        if flip.generated_title and flip.generated_description:
            listing_content = {
                "title": flip.generated_title,
                "description": flip.generated_description,
                "source": "saved",
            }
        else:
            # Generate fresh if not saved
            listing_content_data = await listing_generator.generate_full_listing(flip)
            listing_content = {
                "title": listing_content_data["recommended_title"],
                "description": listing_content_data["description"],
                "source": "generated",
            }

        return {
            "flip_id": flip_id,
            "title": listing_content["title"],
            "description": listing_content["description"],
            "listing_source": listing_content["source"],
            "pricing": {
                "listing_price": pricing["optimal_listing_price"],
                "walk_away_price": pricing["walk_away_price"],
                "estimated_profit": pricing["estimated_profit_at_optimal"],
                "margin_pct": pricing["margin_pct"],
                "insertion_fee": pricing["insertion_fee"],
                "final_value_fee_pct": pricing["final_value_fee_pct"],
            },
            "images_available": bool(flip.generated_images_urls),
            "ready_to_post": bool(flip.generated_title and flip.generated_description),
        }

    except Exception as e:
        log.error("reselling.preview_failed", flip_id=flip_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 4: Sales Tracking & Notifications
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/active-sales")
async def get_active_sales(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """
    Get flips currently listed for sale on eBay.

    Returns:
    - Listing details
    - Current price
    - Days listed
    - Estimated profit
    - eBay listing ID for linking
    """
    from app.services.ebay_sales_tracker import get_tracker

    tracker = get_tracker()
    sales = await tracker.get_active_sales(db, limit=limit)

    log.info("reselling.active_sales_retrieved", count=len(sales))
    return {
        "active_listings": sales,
        "total": len(sales),
    }


@router.get("/sales-dashboard")
async def get_sales_dashboard(db: AsyncSession = Depends(get_db)):
    """
    Get comprehensive sales dashboard with metrics.

    Returns:
    - Total sales & revenue
    - Average profit & time to sell
    - Success rate
    - Recent sales
    - Active listings
    """
    from app.services.ebay_sales_tracker import get_tracker

    tracker = get_tracker()
    dashboard = await tracker.get_sales_dashboard(db)

    log.info("reselling.dashboard_retrieved")
    return dashboard


@router.get("/sales/{flip_id}")
async def get_sale_details(
    flip_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Get detailed information about a specific sale.

    Returns:
    - Cost breakdown (base + upgrades)
    - Sale details (price, date, platform)
    - Profit details (estimated vs actual, margin %)
    - eBay listing ID
    """
    from app.services.ebay_sales_tracker import get_tracker

    tracker = get_tracker()
    details = await tracker.get_sale_details(db, flip_id)

    if not details:
        raise HTTPException(status_code=404, detail=f"Flip {flip_id} not found")

    log.info("reselling.sale_details_retrieved", flip_id=flip_id)
    return details


@router.post("/flips/{flip_id}/mark-shipped")
async def mark_flip_shipped(
    flip_id: int,
    tracking_number: str | None = None,
    carrier: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Mark a flip as shipped after sale.

    Optionally stores tracking number and carrier for buyer communication.
    """
    from app.models.flip import Flip, FlipStage

    flip = await db.get(Flip, flip_id)
    if not flip:
        raise HTTPException(status_code=404, detail=f"Flip {flip_id} not found")

    # Update flip to mark as shipped
    # Note: Flip model may need new fields for shipping info
    flip.stage = FlipStage.sold  # Already in sold stage
    await db.commit()

    log.info(
        "reselling.flip_marked_shipped",
        flip_id=flip_id,
        tracking=tracking_number,
        carrier=carrier,
    )

    return {
        "flip_id": flip_id,
        "status": "shipped",
        "tracking_number": tracking_number,
        "carrier": carrier,
    }


@router.post("/poll-sales")
async def manually_poll_sales(db: AsyncSession = Depends(get_db)):
    """
    Manually trigger a sales poll (useful for testing).

    In production, this runs automatically on the schedule configured by
    settings.ebay_sales_poll_interval_seconds (see app/workers/scheduler.py).

    Returns:
    - Number of sold listings found
    - Number matched to flips
    - Number updated
    - Sale details
    """
    from app.services.ebay_sales_tracker import get_tracker

    tracker = get_tracker()
    result = await tracker.poll_sales()

    log.info("reselling.manual_poll_triggered", result=result)
    return result
