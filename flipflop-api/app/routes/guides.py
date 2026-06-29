"""Welcome Guide routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Order, WelcomeGuide
from app.schemas.guide import WelcomeGuideRequest, WelcomeGuideResponse
from app.services.guide_service import GuideService
from datetime import datetime
import os
import structlog

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/guides", tags=["guides"])


@router.post("/orders/{order_id}/generate")
async def generate_welcome_guide(
    order_id: int,
    request: WelcomeGuideRequest,
    db: Session = Depends(get_db),
) -> WelcomeGuideResponse:
    """Generate a welcome guide PDF for an order.

    Args:
        order_id: Order ID
        request: Generation request (regenerate flag)
        db: Database session

    Returns:
        WelcomeGuideResponse with PDF URL and metadata

    Raises:
        HTTPException: If order not found or generation fails
    """
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order {order_id} not found",
        )

    # Check if guide already exists
    existing_guide = db.query(WelcomeGuide).filter(
        WelcomeGuide.order_id == order_id
    ).first()

    if existing_guide and not request.regenerate:
        log.info("returning_existing_guide", order_id=order_id)
        return WelcomeGuideResponse(
            order_id=order_id,
            pdf_url=f"/api/guides/orders/{order_id}/download",
            generated_at=existing_guide.generated_at,
        )

    # Generate new guide
    try:
        guide_service = GuideService(db)
        filepath = guide_service.generate_welcome_guide(order_id)

        # Get file size
        file_size = os.path.getsize(filepath) if os.path.exists(filepath) else None

        log.info("guide_generated", order_id=order_id, filepath=filepath)

        return WelcomeGuideResponse(
            order_id=order_id,
            pdf_url=f"/api/guides/orders/{order_id}/download",
            generated_at=datetime.utcnow(),
            file_size_bytes=file_size,
        )

    except ValueError as e:
        log.error("guide_generation_failed", error=str(e), order_id=order_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        log.error("guide_generation_error", error=str(e), order_id=order_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate welcome guide",
        )


@router.get("/orders/{order_id}/download")
async def download_welcome_guide(
    order_id: int,
    db: Session = Depends(get_db),
) -> FileResponse:
    """Download existing welcome guide or generate if missing.

    Args:
        order_id: Order ID
        db: Database session

    Returns:
        PDF file response

    Raises:
        HTTPException: If order not found or file not found
    """
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order {order_id} not found",
        )

    # Check if guide exists
    guide = db.query(WelcomeGuide).filter(WelcomeGuide.order_id == order_id).first()

    if not guide:
        # Generate on-the-fly if missing
        try:
            guide_service = GuideService(db)
            filepath = guide_service.generate_welcome_guide(order_id)
            guide = db.query(WelcomeGuide).filter(WelcomeGuide.order_id == order_id).first()
        except Exception as e:
            log.error("guide_generation_failed_on_download", error=str(e), order_id=order_id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate welcome guide",
            )

    # Get filepath from metadata
    if guide.content_json and 'file_path' in guide.content_json:
        filepath = guide.content_json['file_path']
    else:
        # Fallback to default location
        filepath = f"/tmp/guides/order_{order_id}_welcome_guide.pdf"

    if not os.path.exists(filepath):
        log.error("guide_file_not_found", filepath=filepath, order_id=order_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Welcome guide file not found",
        )

    log.info("guide_downloaded", order_id=order_id, filepath=filepath)

    return FileResponse(
        path=filepath,
        media_type="application/pdf",
        filename=f"flipflop_order_{order.order_id}_welcome_guide.pdf",
    )


@router.get("/orders/{order_id}/status")
async def get_guide_status(
    order_id: int,
    db: Session = Depends(get_db),
) -> dict:
    """Get welcome guide generation status.

    Args:
        order_id: Order ID
        db: Database session

    Returns:
        Status information

    Raises:
        HTTPException: If order not found
    """
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order {order_id} not found",
        )

    guide = db.query(WelcomeGuide).filter(WelcomeGuide.order_id == order_id).first()

    return {
        "order_id": order_id,
        "exists": guide is not None,
        "generated_at": guide.generated_at if guide else None,
        "download_url": f"/api/guides/orders/{order_id}/download" if guide else None,
    }
