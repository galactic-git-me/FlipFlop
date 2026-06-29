import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.oauth_service import OAuthService
from app.services.auth_service import create_access_token
from app.schemas.auth import TokenResponse

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/auth/oauth", tags=["oauth"])


class OAuthCodeRequest(BaseModel):
    code: str


class OAuthUrlResponse(BaseModel):
    url: str


@router.get("/google/url", response_model=OAuthUrlResponse)
async def google_auth_url():
    """
    Get Google OAuth authorization URL.

    Returns the URL to redirect users to for Google login.
    """
    try:
        url = await OAuthService.get_google_auth_url()
        return OAuthUrlResponse(url=url)
    except Exception as e:
        log.error("oauth.google_url_failed", error=str(e))
        raise HTTPException(status_code=400, detail="Failed to generate Google auth URL")


@router.get("/github/url", response_model=OAuthUrlResponse)
async def github_auth_url():
    """
    Get GitHub OAuth authorization URL.

    Returns the URL to redirect users to for GitHub login.
    """
    try:
        url = await OAuthService.get_github_auth_url()
        return OAuthUrlResponse(url=url)
    except Exception as e:
        log.error("oauth.github_url_failed", error=str(e))
        raise HTTPException(status_code=400, detail="Failed to generate GitHub auth URL")


@router.post("/google/callback", response_model=TokenResponse)
async def google_callback(
    request: OAuthCodeRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Handle Google OAuth callback.

    Exchanges authorization code for user info, creates/links customer, and returns JWT token.
    """
    try:
        # Exchange code for Google user info
        google_user = await OAuthService.exchange_google_code(request.code)

        # Get or create customer
        customer = await OAuthService.get_or_create_user_from_google(db, google_user)

        # Create JWT token
        token = create_access_token(customer.id)

        log.info("oauth.google_callback_success", customer_id=customer.id)
        return TokenResponse(access_token=token, token_type="bearer")

    except ValueError as e:
        log.warning("oauth.google_callback_invalid", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.error("oauth.google_callback_failed", error=str(e))
        raise HTTPException(status_code=400, detail="Google authentication failed")


@router.post("/github/callback", response_model=TokenResponse)
async def github_callback(
    request: OAuthCodeRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Handle GitHub OAuth callback.

    Exchanges authorization code for user info, creates/links customer, and returns JWT token.
    """
    try:
        # Exchange code for GitHub user info
        github_user = await OAuthService.exchange_github_code(request.code)

        # Get or create customer
        customer = await OAuthService.get_or_create_user_from_github(db, github_user)

        # Create JWT token
        token = create_access_token(customer.id)

        log.info("oauth.github_callback_success", customer_id=customer.id)
        return TokenResponse(access_token=token, token_type="bearer")

    except ValueError as e:
        log.warning("oauth.github_callback_invalid", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.error("oauth.github_callback_failed", error=str(e))
        raise HTTPException(status_code=400, detail="GitHub authentication failed")
