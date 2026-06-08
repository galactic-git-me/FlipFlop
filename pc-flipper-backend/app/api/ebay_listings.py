"""
eBay Listings API — Post flips to eBay directly.

Endpoints:
  POST /api/ebay/post-listing — Post a flip's listing to eBay
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.flip import Flip
from app.services.ebay_listing_poster import post_flip_to_ebay
from app.config import get_settings

router = APIRouter(prefix="/ebay", tags=["ebay-listings"])


class PostListingRequest(BaseModel):
    flip_id: int
    title: str
    description: str
    price: float
    access_token: str  # User's eBay OAuth token


class PostListingResponse(BaseModel):
    success: bool
    listing_id: str | None = None
    url: str | None = None
    error: str | None = None


@router.post("/post-listing", response_model=PostListingResponse)
async def post_flip_to_ebay_endpoint(
    body: PostListingRequest,
    db: AsyncSession = Depends(get_db),
) -> PostListingResponse:
    """
    Post a flip listing to eBay.

    Requires valid eBay OAuth token from user.
    Updates flip with eBay listing ID and URL on success.
    """
    settings = get_settings()

    # Validate environment
    if not body.access_token:
        raise HTTPException(
            status_code=400,
            detail="eBay OAuth access token required. Please connect your eBay account first.",
        )

    # Post to eBay
    result = await post_flip_to_ebay(
        title=body.title,
        description=body.description,
        price=body.price,
        access_token=body.access_token,
        environment=settings.ebay_environment,
    )

    if result["success"]:
        # Update flip record with eBay listing info
        flip = await db.get(Flip, body.flip_id)
        if flip:
            flip.ebay_listing_id = result["listing_id"]
            flip.ebay_listing_url = result["url"]
            await db.commit()

        return PostListingResponse(
            success=True,
            listing_id=result.get("listing_id"),
            url=result.get("url"),
        )
    else:
        return PostListingResponse(
            success=False,
            error=result.get("error", "Failed to post listing"),
        )


@router.get("/auth-status")
async def check_ebay_auth() -> dict:
    """
    Check if user has valid eBay OAuth token.
    In full implementation, would check database for stored token.
    """
    settings = get_settings()
    return {
        "ebay_configured": bool(settings.ebay_app_id and settings.ebay_client_secret),
        "environment": settings.ebay_environment,
        "sandbox_mode": settings.ebay_environment == "sandbox",
    }
