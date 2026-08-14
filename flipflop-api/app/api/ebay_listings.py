"""
eBay Listings API — Post flips to eBay directly.

Endpoints:
  POST /api/ebay/post-listing — Post a flip's listing to eBay
"""

import base64
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

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

    # Fetch flip to get generated images
    result = await db.execute(select(Flip).where(Flip.id == body.flip_id))
    flip = result.scalar_one_or_none()
    if not flip:
        raise HTTPException(status_code=404, detail="Flip not found")

    # Validate images exist
    image_urls = flip.generated_images_urls or []
    if not image_urls:
        raise HTTPException(
            status_code=400,
            detail="No images found for this flip. Generate images before listing on eBay.",
        )

    # Post to eBay (uses Application Token with server credentials)
    result = await post_flip_to_ebay(
        title=body.title,
        description=body.description,
        price=body.price,
        image_urls=image_urls,
        access_token=body.access_token,
        environment=settings.ebay_environment,
        app_id=settings.ebay_app_id,
        client_secret=settings.ebay_client_secret,
    )

    if result["success"]:
        # Update flip record with eBay listing info
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


_OAUTH_TOKEN_ENDPOINTS = {
    "sandbox": "https://api.sandbox.ebay.com/identity/v1/oauth2/token",
    "production": "https://api.ebay.com/identity/v1/oauth2/token",
}


@router.post("/exchange-auth-code")
async def exchange_authorization_code(body: dict) -> dict:
    """
    Exchange eBay authorization code for an access token, for either the
    sandbox or production environment.

    Usage: After user authorizes in OAuth flow, eBay redirects with `code` parameter.
    Call this endpoint with that code to get the access token.

    Request body:
    {
        "code": "v^1.1^i^1^...",
        "redirect_uri": "Michael_Clark-MichaelC-FlipFl-uooqypq",
        "environment": "sandbox"  // or "production" — defaults to "sandbox"
    }
    """
    settings = get_settings()
    environment = body.get("environment", "sandbox")
    if environment not in _OAUTH_TOKEN_ENDPOINTS:
        raise HTTPException(400, "environment must be 'sandbox' or 'production'")

    if environment == "production":
        app_id, client_secret = settings.ebay_app_id, settings.ebay_client_secret
        missing_msg = "eBay production credentials not configured (EBAY_APP_ID / EBAY_CLIENT_SECRET)"
    else:
        app_id, client_secret = settings.ebay_sandbox_app_id, settings.ebay_sandbox_client_secret
        missing_msg = "eBay sandbox credentials not configured (EBAY_SANDBOX_APP_ID / EBAY_SANDBOX_CLIENT_SECRET)"

    if not app_id or not client_secret:
        raise HTTPException(status_code=400, detail=missing_msg)

    code = body.get("code")
    redirect_uri = body.get("redirect_uri")

    if not code or not redirect_uri:
        raise HTTPException(
            status_code=400,
            detail="Missing 'code' or 'redirect_uri' in request body"
        )

    credentials = f"{app_id}:{client_secret}"
    encoded = base64.b64encode(credentials.encode()).decode()

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            token_resp = await client.post(
                _OAUTH_TOKEN_ENDPOINTS[environment],
                headers={
                    "Authorization": f"Basic {encoded}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
            )

            if token_resp.status_code != 200:
                error_text = token_resp.text
                try:
                    error_json = token_resp.json()
                    error_text = error_json.get("error_description", error_text)
                except:
                    pass
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to exchange code for token: {error_text}"
                )

            token_data = token_resp.json()
            access_token = token_data.get("access_token")
            expires_in = token_data.get("expires_in", 3600)
            refresh_token = token_data.get("refresh_token")
            refresh_token_expires_in = token_data.get("refresh_token_expires_in")

            env_prefix = "EBAY_PRODUCTION" if environment == "production" else "EBAY_SANDBOX"
            return {
                "success": True,
                "environment": environment,
                "access_token": access_token,
                "expires_in": expires_in,
                "refresh_token": refresh_token,
                "refresh_token_expires_in": refresh_token_expires_in,
                "message": (
                    "Add both to .env.local (the refresh token lets the backend "
                    "auto-renew the access token from now on):\n"
                    f"{env_prefix}_OAUTH_USER_TOKEN={access_token}\n"
                    f"{env_prefix}_REFRESH_TOKEN={refresh_token}"
                ),
            }

    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=500,
            detail=f"HTTP error during token exchange: {str(e)}"
        )


@router.post("/refresh-token")
async def refresh_sandbox_token() -> dict:
    """
    Use the stored EBAY_SANDBOX_REFRESH_TOKEN to mint a fresh access token,
    without requiring the user to sign in again via the browser.
    """
    from app.services.ebay_token_manager import get_valid_sandbox_access_token

    access_token = await get_valid_sandbox_access_token(force_refresh=True)
    return {"success": True, "access_token": access_token}


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
