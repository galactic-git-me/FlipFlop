"""Margin verification API—check if a GEM listing has verified as a profitable flip."""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from app.routes.admin_auth import get_current_admin

router = APIRouter(prefix="/api/gem-radar/verification", tags=["gem-radar"], dependencies=[Depends(get_current_admin)])


class VerificationResponse(BaseModel):
    listing_id: str
    is_verified: bool
    actual_buy_price_gbp: float | None = None
    realistic_resale_price_gbp: float | None = None
    profit_margin_gbp: float | None = None
    reasoning: str | None = None
    is_viable_flip: bool | None = None


@router.get("/{listing_id}", response_model=VerificationResponse)
async def get_verification_status(listing_id: str):
    """Check if a GEM listing has completed margin verification via Qwen2:7b.

    Returns is_verified=false if verification hasn't completed yet (non-blocking).
    Viable flips have is_viable_flip=true and profit_margin_gbp > £30.
    """
    from app.gem_radar.margin_verifier import get_verification

    result = await get_verification(listing_id)

    if not result:
        return VerificationResponse(
            listing_id=listing_id,
            is_verified=False,
        )

    return VerificationResponse(
        listing_id=listing_id,
        is_verified=True,
        actual_buy_price_gbp=result.actual_buy_price_gbp,
        realistic_resale_price_gbp=result.realistic_resale_price_gbp,
        profit_margin_gbp=result.profit_margin_gbp,
        reasoning=result.reasoning,
        is_viable_flip=result.is_viable_flip,
    )
