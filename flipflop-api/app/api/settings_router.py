"""Global app settings — single row keyed name='default'."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.app_settings import AppSettings

router = APIRouter(prefix="/settings", tags=["settings"])


class SettingsUpdate(BaseModel):
    max_concurrent_flips: int | None = None
    default_sell_platform: str | None = None
    auto_buy_autonomous: bool | None = None
    auto_buy_daily_limit: int | None = None
    ollama_base_url: str | None = None
    ollama_model: str | None = None
    openrouter_api_key: str | None = None
    openrouter_primary_model: str | None = None
    ebay_app_id: str | None = None
    image_gen_enabled: bool | None = None
    image_gen_provider: str | None = None
    handling_time_days: int | None = None
    returns_accepted: bool | None = None
    returns_window_days: int | None = None
    free_shipping_enabled: bool | None = None
    local_pickup_enabled: bool | None = None
    listing_type_default: str | None = None


@router.get("/")
async def get_settings(db: AsyncSession = Depends(get_db)):
    settings = await _get_or_create(db)
    return _to_dict(settings)


@router.put("/")
async def update_settings(body: SettingsUpdate, db: AsyncSession = Depends(get_db)):
    settings = await _get_or_create(db)
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(settings, field, value)
    await db.flush()
    await db.refresh(settings)

    # Propagate to live config cache so ai_service picks up changes without restart
    from app.config import get_settings as get_cfg
    cfg = get_cfg()
    if body.openrouter_api_key:
        cfg.openrouter_api_key = body.openrouter_api_key
    if body.ollama_model:
        cfg.ollama_model = body.ollama_model
    if body.ollama_base_url:
        cfg.ollama_base_url = body.ollama_base_url
    if body.openrouter_primary_model:
        cfg.openrouter_primary_model = body.openrouter_primary_model

    return _to_dict(settings)


async def _get_or_create(db: AsyncSession) -> AppSettings:
    result = await db.execute(select(AppSettings).where(AppSettings.name == "default"))
    settings = result.scalar_one_or_none()
    if not settings:
        settings = AppSettings(name="default")
        db.add(settings)
        await db.flush()
        await db.refresh(settings)
    return settings


def _to_dict(s: AppSettings) -> dict:
    return {
        "max_concurrent_flips": s.max_concurrent_flips,
        "default_sell_platform": s.default_sell_platform,
        "auto_buy_autonomous": s.auto_buy_autonomous,
        "auto_buy_daily_limit": s.auto_buy_daily_limit,
        "ollama_base_url": s.ollama_base_url,
        "ollama_model": s.ollama_model,
        "openrouter_api_key": "***" if s.openrouter_api_key else "",
        "openrouter_primary_model": s.openrouter_primary_model,
        "ebay_app_id": "***" if s.ebay_app_id else "",
        "image_gen_enabled": s.image_gen_enabled,
        "image_gen_provider": s.image_gen_provider,
        "handling_time_days": s.handling_time_days,
        "returns_accepted": s.returns_accepted,
        "returns_window_days": s.returns_window_days,
        "free_shipping_enabled": s.free_shipping_enabled,
        "local_pickup_enabled": s.local_pickup_enabled,
        "listing_type_default": s.listing_type_default,
    }
