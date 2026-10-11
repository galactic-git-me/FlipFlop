"""Owner and scoped guest access to customer Welcome Guides."""

from datetime import datetime
import os

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Order, PortalAccessGrant, WelcomeGuide
from app.schemas.guide import WelcomeGuideRequest, WelcomeGuideResponse
from app.services.auth_service import get_customer_by_token
from app.services.guide_service import GuideService
from app.services.portal_access import verify_guest_portal_token

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/guides", tags=["guides"])


async def _authorized_order(
    order_id: int,
    authorization: str | None,
    db: AsyncSession,
) -> tuple[Order, bool]:
    """Return the order only to its owner or a valid one-order guest grant."""
    parts = authorization.split() if authorization else []
    if len(parts) != 2 or parts[0].casefold() != "bearer":
        raise HTTPException(401, "Customer or guest portal access token required")

    token = parts[1]
    customer = await get_customer_by_token(db, token)
    if customer:
        order = await db.get(Order, order_id)
        if not order or order.customer_id != customer.id:
            raise HTTPException(404, "Welcome guide not found")
        return order, False

    grant: PortalAccessGrant | None = await verify_guest_portal_token(db, token)
    if not grant or grant.order_id != order_id:
        raise HTTPException(404, "Welcome guide not found")
    order = await db.get(Order, order_id)
    if not order:
        raise HTTPException(404, "Welcome guide not found")
    return order, True


def _private_pdf_response(path: str, order: Order) -> FileResponse:
    if not os.path.exists(path):
        raise HTTPException(404, "Welcome guide file not found")
    return FileResponse(
        path=path,
        media_type="application/pdf",
        filename=f"flipflop_order_{order.order_id}_welcome_guide.pdf",
        headers={
            "Cache-Control": "private, no-store, max-age=0",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
        },
    )


@router.post("/orders/{order_id}/generate", response_model=WelcomeGuideResponse)
async def generate_welcome_guide(
    order_id: int,
    request: WelcomeGuideRequest,
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
) -> WelcomeGuideResponse:
    order, guest = await _authorized_order(order_id, authorization, db)
    if guest:
        raise HTTPException(403, "Guest portal tokens cannot regenerate customer documents")

    existing = (await db.execute(
        select(WelcomeGuide).where(WelcomeGuide.order_id == order_id)
    )).scalar_one_or_none()
    if existing and not request.regenerate and (existing.content_json or {}).get("schema_version") == 2:
        return WelcomeGuideResponse(
            order_id=order_id,
            pdf_url=f"/api/guides/orders/{order_id}/download",
            generated_at=existing.generated_at,
        )

    try:
        filepath = await GuideService(db).generate_welcome_guide(order_id)
        file_size = os.path.getsize(filepath) if os.path.exists(filepath) else None
        log.info("guide_generated", order_id=order_id)
        refreshed = (await db.execute(
            select(WelcomeGuide).where(WelcomeGuide.order_id == order_id)
        )).scalar_one_or_none()
        return WelcomeGuideResponse(
            order_id=order_id,
            pdf_url=f"/api/guides/orders/{order_id}/download",
            generated_at=refreshed.generated_at if refreshed else datetime.utcnow(),
            file_size_bytes=file_size,
        )
    except ValueError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(error)) from error
    except Exception as error:
        log.exception("guide_generation_error", order_id=order_id, error=str(error))
        raise HTTPException(500, "Failed to generate welcome guide") from error


@router.get("/orders/{order_id}/download")
async def download_welcome_guide(
    order_id: int,
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    order, _guest = await _authorized_order(order_id, authorization, db)
    guide = (await db.execute(
        select(WelcomeGuide).where(WelcomeGuide.order_id == order_id)
    )).scalar_one_or_none()

    # Existing versions included the Windows product key. Rebuild those PDFs
    # before serving them, and never cache this order-specific document.
    if not guide or (guide.content_json or {}).get("schema_version") != 2:
        try:
            filepath = await GuideService(db).generate_welcome_guide(order_id)
            guide = (await db.execute(
                select(WelcomeGuide).where(WelcomeGuide.order_id == order_id)
            )).scalar_one_or_none()
        except Exception as error:
            log.exception("guide_generation_failed_on_download", order_id=order_id, error=str(error))
            raise HTTPException(500, "Failed to generate welcome guide") from error
    if not guide:
        raise HTTPException(404, "Welcome guide not found")
    filepath = (guide.content_json or {}).get("file_path") or f"/tmp/guides/order_{order_id}_welcome_guide.pdf"
    return _private_pdf_response(filepath, order)


@router.get("/orders/{order_id}/status")
async def get_guide_status(
    order_id: int,
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    _order, _guest = await _authorized_order(order_id, authorization, db)
    guide = (await db.execute(
        select(WelcomeGuide).where(WelcomeGuide.order_id == order_id)
    )).scalar_one_or_none()
    return {
        "order_id": order_id,
        "exists": guide is not None,
        "generated_at": guide.generated_at if guide else None,
        "download_url": f"/api/guides/orders/{order_id}/download" if guide else None,
    }
