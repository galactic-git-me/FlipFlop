"""eBay seller OAuth (3-legged) — see app/services/ebay_oauth.py for the full flow writeup."""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.config import get_settings
from app.services import ebay_oauth

router = APIRouter(prefix="/ebay/oauth", tags=["ebay-oauth"])


@router.get("/authorize-url")
async def authorize_url():
    settings = get_settings()
    if not settings.ebay_app_id or not settings.ebay_ru_name:
        raise HTTPException(
            400,
            "ebay_app_id and ebay_ru_name must be configured before connecting — "
            "register the app and a redirect URL (RuName) in the eBay Developer Portal first.",
        )
    return {"url": ebay_oauth.build_authorize_url()}


@router.get("/callback")
async def oauth_callback(
    code: str | None = Query(None),
    error: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    settings = get_settings()
    admin_url = (settings.admin_frontend_url or settings.frontend_url).rstrip("/")
    if error or not code:
        return RedirectResponse(f"{admin_url}/settings?ebay_connected=0&reason={error or 'no_code'}")

    try:
        payload = await ebay_oauth.exchange_code_for_tokens(code)
        await ebay_oauth.store_tokens_from_exchange(db, payload)
    except ebay_oauth.EbayOAuthError:
        return RedirectResponse(f"{admin_url}/settings?ebay_connected=0&reason=exchange_failed")

    return RedirectResponse(f"{admin_url}/settings?ebay_connected=1")


@router.get("/status")
async def status(db: AsyncSession = Depends(get_db)):
    return await ebay_oauth.get_connection_status(db)


@router.post("/disconnect")
async def disconnect(db: AsyncSession = Depends(get_db)):
    await ebay_oauth.disconnect(db)
    return {"connected": False}
