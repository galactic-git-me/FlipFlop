"""Global app settings — single row keyed name='default'."""
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.app_settings import AppSettings
from app.models.channel_listing import ChannelListing
from app.models.manual_build import ManualBuild
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from app.routes.admin_auth import get_current_admin
from app.models.component_manual import ComponentManual
from urllib.parse import urlparse
import hashlib
from app.services.component_manual_library import normalize_manual_key
from app.services.ai_setup_offers import normalise_ai_setup_offers, validate_ai_setup_offers
from app.services.getting_started_guide import normalize_guide_text
from app.services.business_details import BusinessDetails, read_business_details, save_business_details

router = APIRouter(prefix="/settings", tags=["settings"])
public_router = APIRouter(prefix="/public", tags=["public-business-details"])
storefront_public_router = APIRouter(prefix="/public", tags=["public-storefront-settings"])

DEFAULT_TRUST_MESSAGES = [
    {"title": "🛡️ Trust & Protection 🛡️", "text": "Buy with confidence! Free UK delivery, 28-day returns, 12-month flipflop warranty and insured shipping. We've got you covered!", "audience": "all", "expires_at": None, "enabled": True, "priority": False},
    {"title": "🖥️ Three Ways to Buy 🖥️", "text": "Your PC. Your rules! Choose Ready-to-Go, Curated-for-You or Built-by-You. Your perfect machine starts here!", "audience": "all", "expires_at": None, "enabled": True},
    {"title": "⚡ Delivery Flexibility ⚡", "text": "Need speed or want savings? Fast Track, Standard or Flexible delivery. You choose the pace, we'll handle the rest!", "audience": "all", "expires_at": None, "enabled": True},
    {"title": "🎨 Personalisation & 3D Builder 🎨", "text": "Don't just buy a PC. Make it yours! Customise every detail and see your dream machine come alive in our 3D builder!", "audience": "all", "expires_at": None, "enabled": True},
    {"title": "🔧 Upgrade Your Existing PC 🔧", "text": "Love your PC but crave more power? Keep the good bits, upgrade what matters and give it a stunning new look!", "audience": "all", "expires_at": None, "enabled": True},
    {"title": "💳 Flexible Payments 💳", "text": "Big performance. Smaller payments! Spread the cost or pay later with eligible checkout options.", "audience": "all", "expires_at": None, "enabled": True},
    {"title": "🔍 Transparency & Value 🔍", "text": "No mystery parts. No nasty surprises! Know exactly what's inside, what it costs and why it's worth every penny!", "audience": "all", "expires_at": None, "enabled": True},
    {"title": "❤️ After-Sales Support ❤️", "text": "Our commitment doesn't end at checkout! Real support, a 12-month warranty and help long after the unboxing!", "audience": "all", "expires_at": None, "enabled": True},
    {"title": "🔥 Buy Today & Save 50% 🔥", "text": "Save 50% when you buy today!", "audience": "all", "expires_at": None, "enabled": True},
]


def _parse_expiry_datetime(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


@storefront_public_router.get("/storefront-messages")
async def public_storefront_messages(db: AsyncSession = Depends(get_db)):
    settings = await _get_or_create(db)
    messages = settings.storefront_trust_messages or DEFAULT_TRUST_MESSAGES
    return {
        "messages": [
            {
                **message,
                "enabled": message.get("enabled", True),
                "priority": message.get("priority", False),
                "display_mode": "fixed" if message.get("priority", False) else "rotating",
            }
            for message in messages[:10]
            if message.get("enabled", True)
            and (message.get("expires_at") is None or (_parse_expiry_datetime(message["expires_at"]) or datetime.min.replace(tzinfo=timezone.utc)) > datetime.now(timezone.utc))
        ],
    }


@router.get('/business-details', dependencies=[Depends(get_current_admin)])
async def business_details_settings():
    return read_business_details().model_dump()


@router.put('/business-details', dependencies=[Depends(get_current_admin)])
async def update_business_details_settings(body: BusinessDetails):
    return save_business_details(body).model_dump()


@public_router.get('/business-details')
async def public_business_details():
    return read_business_details().model_dump()

GETTING_STARTED_GUIDE_PATH = Path(__file__).resolve().parents[2] / "data" / "getting-started-guide.md"
GETTING_STARTED_GUIDE_LIMIT = 1_000_000
COMPONENT_MANUAL_LIMIT = 25_000_000
COMPONENT_MANUAL_LIBRARY_PATH = Path(__file__).resolve().parents[2] / "data" / "getting-ready-packages" / "manual-library"


@router.get("/component-manuals", dependencies=[Depends(get_current_admin)])
async def list_component_manuals(db: AsyncSession = Depends(get_db)):
    manuals = (await db.execute(select(ComponentManual).order_by(ComponentManual.component_name, ComponentManual.id))).scalars().all()
    return {"items": [{
        "id": item.id, "component_key": item.component_key, "component_name": item.component_name,
        "source_url": item.source_url, "filename": item.filename, "sha256": item.sha256,
        "size_bytes": item.size_bytes, "is_active": item.is_active,
    } for item in manuals]}


@router.post("/component-manuals", status_code=201, dependencies=[Depends(get_current_admin)])
async def upload_component_manual(
    component_key: str = Form(..., min_length=8, max_length=240),
    component_name: str = Form(..., min_length=2, max_length=300),
    source_url: str = Form(..., max_length=1000),
    confirm_official_source: bool = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Add an administrator-curated official PDF to the reusable manual cache."""
    if not confirm_official_source:
        raise HTTPException(409, "Confirm that this manual came from the component manufacturer's official support source")
    parsed = urlparse(source_url.strip())
    if parsed.scheme != "https" or not parsed.hostname:
        raise HTTPException(422, "Manual source must be an HTTPS manufacturer support URL")
    if Path(file.filename or "").suffix.lower() != ".pdf":
        raise HTTPException(415, "Upload a PDF component manual")
    content = await file.read(COMPONENT_MANUAL_LIMIT + 1)
    if len(content) < 8 or len(content) > COMPONENT_MANUAL_LIMIT:
        raise HTTPException(413, "Manual PDF must be between 8 bytes and 25 MB")
    if not content.startswith(b"%PDF-"):
        raise HTTPException(415, "The uploaded file does not have a valid PDF header")

    raw_key = " ".join(component_key.split())
    normalized_key = normalize_manual_key(raw_key)
    if len(normalized_key) < 8:
        raise HTTPException(422, "The exact model key must contain at least eight letters or numbers")
    digest = hashlib.sha256(content).hexdigest()
    storage_key = f"manual-library/{digest}.pdf"
    root = COMPONENT_MANUAL_LIBRARY_PATH.resolve()
    destination = (root / f"{digest}.pdf").resolve()
    if root not in destination.parents:
        raise HTTPException(422, "Invalid manual storage path")
    if not destination.exists():
        root.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(".pdf.tmp")
        temporary.write_bytes(content)
        temporary.replace(destination)

    existing = (await db.execute(select(ComponentManual).where(ComponentManual.component_key == normalized_key).with_for_update())).scalar_one_or_none()
    if existing:
        existing.component_name = component_name.strip()
        existing.source_url = source_url.strip()
        existing.storage_key = storage_key
        existing.filename = Path(file.filename or "component-manual.pdf").name[:255]
        existing.sha256 = digest
        existing.size_bytes = len(content)
        existing.is_active = True
        existing.updated_at = datetime.utcnow()
        item = existing
    else:
        item = ComponentManual(
            component_key=normalized_key,
            component_name=component_name.strip(),
            source_url=source_url.strip(),
            storage_key=storage_key,
            filename=Path(file.filename or "component-manual.pdf").name[:255],
            sha256=digest,
            size_bytes=len(content),
            is_active=True,
        )
        db.add(item)
    await db.flush()
    return {
        "storefront_trust_messages": s.storefront_trust_messages or DEFAULT_TRUST_MESSAGES,
        "storefront_trust_message_seconds": s.storefront_trust_message_seconds or 6,
        "id": item.id, "component_key": item.component_key, "component_name": item.component_name,
        "source_url": item.source_url, "filename": item.filename, "sha256": item.sha256,
        "size_bytes": item.size_bytes, "is_active": item.is_active,
    }


@router.patch("/component-manuals/{manual_id}/active", dependencies=[Depends(get_current_admin)])
async def set_component_manual_active(manual_id: int, active: bool, db: AsyncSession = Depends(get_db)):
    item = (await db.execute(select(ComponentManual).where(ComponentManual.id == manual_id).with_for_update())).scalar_one_or_none()
    if not item:
        raise HTTPException(404, "Component manual not found")
    item.is_active = active
    item.updated_at = datetime.utcnow()
    await db.flush()
    return {"id": item.id, "is_active": item.is_active}


@router.get("/getting-started-guide", dependencies=[Depends(get_current_admin)])
async def getting_started_guide_status():
    if not GETTING_STARTED_GUIDE_PATH.is_file():
        return {"uploaded": False, "filename": None, "sha256": None}
    content = GETTING_STARTED_GUIDE_PATH.read_bytes()
    return {
        "uploaded": True,
        "filename": "getting-started-guide.md",
        "sha256": sha256(content).hexdigest(),
        "size_bytes": len(content),
    }


@router.put("/getting-started-guide", dependencies=[Depends(get_current_admin)])
async def upload_getting_started_guide(file: UploadFile = File(...)):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".md", ".txt"}:
        raise HTTPException(415, "Upload a plain-text .md or .txt guide")
    content = await file.read(GETTING_STARTED_GUIDE_LIMIT + 1)
    if not content or len(content) > GETTING_STARTED_GUIDE_LIMIT:
        raise HTTPException(413, "Guide must be between 1 byte and 1 MB")
    try:
        decoded = content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise HTTPException(422, "Guide must be UTF-8 text") from error
    normalized = normalize_guide_text(decoded)
    if normalized is None:
        raise HTTPException(422, "Guide cannot be empty")
    GETTING_STARTED_GUIDE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = GETTING_STARTED_GUIDE_PATH.with_suffix(".md.tmp")
    with temporary_path.open("w", encoding="utf-8", newline="\n") as guide_file:
        guide_file.write(normalized)
    temporary_path.replace(GETTING_STARTED_GUIDE_PATH)
    saved = GETTING_STARTED_GUIDE_PATH.read_bytes()
    return {
        "uploaded": True,
        "filename": "getting-started-guide.md",
        "sha256": sha256(saved).hexdigest(),
        "size_bytes": len(saved),
    }

# These values are supplied per runtime by the service environment. Keep the
# request fields for old clients, but never save them to app_settings.
ENV_BACKED_SETTINGS = {
    "ollama_base_url",
    "ollama_model",
    "openrouter_api_key",
    "openrouter_primary_model",
    "ebay_app_id",
    "image_gen_provider",
}


class SettingsUpdate(BaseModel):
    storefront_trust_messages: list[dict] | None = None
    storefront_trust_message_seconds: int | None = Field(default=None, ge=2, le=30)
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
    relist_interval_days: int | None = None
    relist_enabled_default: bool | None = None
    speedy_delivery_price_gbp: float | None = None
    standard_curated_custom_days: int | None = None
    speedy_curated_custom_days: int | None = None
    flexible_curated_custom_days: int | None = None
    standard_prebuilt_days: int | None = None
    speedy_prebuilt_cutoff_hour: int | None = None
    gem_radar_scan_interval_minutes: int | None = None
    gem_radar_consecutive_misses_before_inactive: int | None = None
    gem_radar_scrape_artifacts_hours: int | None = None
    gem_radar_preserve_watched_evidence: bool | None = None
    deal_market_price_source: str | None = None
    deal_super_gem_threshold_pct: float | None = None
    deal_gem_threshold_pct: float | None = None
    deal_ok_deal_threshold_pct: float | None = None
    deal_average_deal_threshold_pct: float | None = None
    opportunity_super_profit_gbp: float | None = None
    opportunity_super_roi_pct: float | None = None
    opportunity_super_confidence: float | None = None
    opportunity_super_liquidity: float | None = None
    opportunity_super_score: float | None = None
    opportunity_super_market_discount_pct: float | None = None
    opportunity_gem_profit_gbp: float | None = None
    opportunity_gem_roi_pct: float | None = None
    opportunity_gem_confidence: float | None = None
    opportunity_gem_liquidity: float | None = None
    opportunity_gem_score: float | None = None
    opportunity_gem_market_discount_pct: float | None = None
    opportunity_delivery_fallback_gbp: float | None = None
    opportunity_ebay_fee_pct: float | None = None
    opportunity_packaging_gbp: float | None = None
    opportunity_testing_refurbishment_gbp: float | None = None
    opportunity_returns_warranty_pct: float | None = None
    opportunity_minimum_sold_comps: int | None = None
    opportunity_minimum_source_diversity: int | None = None
    opportunity_weight_economic_pct: float | None = None
    opportunity_weight_desirability_pct: float | None = None
    opportunity_weight_market_confidence_pct: float | None = None
    opportunity_weight_risk_safety_pct: float | None = None
    opportunity_weight_liquidity_pct: float | None = None


class AISetupOfferConfig(BaseModel):
    id: str = Field(min_length=1, max_length=80)
    enabled: bool
    price_gbp: float | None = Field(default=None, gt=0, le=5000)


class AISetupOffersUpdate(BaseModel):
    offers: list[AISetupOfferConfig]
    confirm_commercial_scope_review: bool = False


@router.get("/ai-setup-offers", dependencies=[Depends(get_current_admin)])
async def get_ai_setup_offer_settings(db: AsyncSession = Depends(get_db)):
    settings = await _get_or_create(db)
    return {"offers": normalise_ai_setup_offers(settings.ai_setup_offers)}


@router.put("/ai-setup-offers", dependencies=[Depends(get_current_admin)])
async def update_ai_setup_offer_settings(
    body: AISetupOffersUpdate,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    settings = await _get_or_create(db)
    try:
        validated = validate_ai_setup_offers([item.model_dump() for item in body.offers])
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    if any(item["enabled"] for item in validated) and not body.confirm_commercial_scope_review:
        raise HTTPException(409, "Confirm review of the offer scope, model/application licensing, customer data and account needs, ongoing charges, support boundary and refund terms before enabling sales")
    reviewed_at = datetime.utcnow().isoformat() if body.confirm_commercial_scope_review else None
    settings.ai_setup_offers = [
        {
            **item,
            "commercial_scope_reviewed": bool(item["enabled"] and body.confirm_commercial_scope_review),
            "commercial_scope_reviewed_at": reviewed_at if item["enabled"] and body.confirm_commercial_scope_review else None,
            "commercial_scope_reviewed_by": getattr(admin, "email", None) or "admin" if item["enabled"] and body.confirm_commercial_scope_review else None,
        }
        for item in validated
    ]
    await db.flush()
    return {"offers": normalise_ai_setup_offers(settings.ai_setup_offers)}


@router.get("/")
async def get_settings(db: AsyncSession = Depends(get_db)):
    settings = await _get_or_create(db)
    return _to_dict(settings)


@router.put("/")
async def update_settings(body: SettingsUpdate, db: AsyncSession = Depends(get_db)):
    settings = await _get_or_create(db)
    # API credentials, providers and model endpoints are runtime configuration,
    # never user preferences. Ignore legacy fields so DB rows cannot shadow env.
    values = body.model_dump(exclude_none=True, exclude=ENV_BACKED_SETTINGS)
    if "storefront_trust_messages" in values:
        messages = values["storefront_trust_messages"]
        allowed_audiences = {"all", "new_users", "returning_users"}
        if not isinstance(messages, list) or len(messages) > 10 or any(not isinstance(item, dict) or not isinstance(item.get("title", ""), str) or len(item.get("title", "")) > 100 or not isinstance(item.get("text"), str) or not item["text"].strip() or len(item["text"]) > 240 or item.get("audience") not in allowed_audiences or ("enabled" in item and not isinstance(item["enabled"], bool)) or ("priority" in item and not isinstance(item["priority"], bool)) or (item.get("expires_at") is not None and (not isinstance(item["expires_at"], str) or _parse_expiry_datetime(item["expires_at"]) is None)) for item in messages):
            raise HTTPException(422, "Configure up to 10 non-empty messages with audience all, new_users or returning_users")
        values["storefront_trust_messages"] = [{"title": item.get("title", "").strip(), "text": item["text"].strip(), "audience": item["audience"], "expires_at": item.get("expires_at"), "enabled": item.get("enabled", True), "priority": item.get("priority", False)} for item in messages]
    for field, value in values.items():
        setattr(settings, field, value)
    if body.relist_interval_days is not None:
        interval = max(1, body.relist_interval_days)
        now = datetime.utcnow()
        schedules = (
            await db.execute(
                select(ChannelListing).where(ChannelListing.recreate_enabled.is_(True))
            )
        ).scalars().all()
        for schedule in schedules:
            schedule.recreate_interval_days = interval
            if schedule.published_at:
                schedule.next_recreate_at = schedule.published_at + timedelta(days=interval)
            else:
                schedule.next_recreate_at = now + timedelta(days=interval)
        builds = (
            await db.execute(
                select(ManualBuild).where(
                    ManualBuild.relist_enabled.is_(True),
                    ManualBuild.listed_at.isnot(None),
                )
            )
        ).scalars().all()
        for build in builds:
            build.next_recreate_at = build.listed_at + timedelta(days=interval)
    await db.flush()
    await db.refresh(settings)

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
    from app.config import get_settings as get_cfg

    cfg = get_cfg()
    return {
        "max_concurrent_flips": s.max_concurrent_flips,
        "default_sell_platform": s.default_sell_platform,
        "auto_buy_autonomous": s.auto_buy_autonomous,
        "auto_buy_daily_limit": s.auto_buy_daily_limit,
        "ollama_base_url": cfg.ollama_base_url,
        "ollama_model": cfg.ollama_model,
        "openrouter_api_key": "***" if cfg.openrouter_api_key else "",
        "openrouter_primary_model": cfg.openrouter_primary_model,
        "llm_model_hierarchy": [
            {"tier": "primary", "provider": cfg.llm_primary_provider, "model": cfg.llm_primary_model},
            {"tier": "secondary", "provider": cfg.llm_secondary_provider,
             "model": cfg.llm_secondary_model or "google/gemma-4-31b-it:free"},
            {"tier": "tertiary", "provider": cfg.llm_tertiary_provider, "model": cfg.llm_tertiary_model},
        ],
        "ebay_app_id": "***" if cfg.ebay_app_id else "",
        "image_gen_enabled": s.image_gen_enabled,
        "image_gen_provider": cfg.image_gen_provider,
        "handling_time_days": s.handling_time_days,
        "returns_accepted": s.returns_accepted,
        "returns_window_days": s.returns_window_days,
        "free_shipping_enabled": s.free_shipping_enabled,
        "local_pickup_enabled": s.local_pickup_enabled,
        "listing_type_default": s.listing_type_default,
        "relist_interval_days": s.relist_interval_days or 7,
        "relist_enabled_default": s.relist_enabled_default,
        "speedy_delivery_price_gbp": s.speedy_delivery_price_gbp,
        "standard_curated_custom_days": s.standard_curated_custom_days,
        "speedy_curated_custom_days": s.speedy_curated_custom_days,
        "flexible_curated_custom_days": s.flexible_curated_custom_days,
        "standard_prebuilt_days": s.standard_prebuilt_days,
        "speedy_prebuilt_cutoff_hour": s.speedy_prebuilt_cutoff_hour,
        "gem_radar_scan_interval_minutes": s.gem_radar_scan_interval_minutes,
        "gem_radar_consecutive_misses_before_inactive": s.gem_radar_consecutive_misses_before_inactive,
        "gem_radar_scrape_artifacts_hours": s.gem_radar_scrape_artifacts_hours,
        "gem_radar_preserve_watched_evidence": s.gem_radar_preserve_watched_evidence,
        "deal_market_price_source": s.deal_market_price_source,
        "deal_super_gem_threshold_pct": s.deal_super_gem_threshold_pct,
        "deal_gem_threshold_pct": s.deal_gem_threshold_pct,
        "deal_ok_deal_threshold_pct": s.deal_ok_deal_threshold_pct,
        "deal_average_deal_threshold_pct": s.deal_average_deal_threshold_pct,
        "opportunity_super_profit_gbp": s.opportunity_super_profit_gbp,
        "opportunity_super_roi_pct": s.opportunity_super_roi_pct,
        "opportunity_super_confidence": s.opportunity_super_confidence,
        "opportunity_super_liquidity": s.opportunity_super_liquidity,
        "opportunity_super_score": s.opportunity_super_score,
        "opportunity_super_market_discount_pct": s.opportunity_super_market_discount_pct,
        "opportunity_gem_profit_gbp": s.opportunity_gem_profit_gbp,
        "opportunity_gem_roi_pct": s.opportunity_gem_roi_pct,
        "opportunity_gem_confidence": s.opportunity_gem_confidence,
        "opportunity_gem_liquidity": s.opportunity_gem_liquidity,
        "opportunity_gem_score": s.opportunity_gem_score,
        "opportunity_gem_market_discount_pct": s.opportunity_gem_market_discount_pct,
        "opportunity_delivery_fallback_gbp": s.opportunity_delivery_fallback_gbp,
        "opportunity_ebay_fee_pct": s.opportunity_ebay_fee_pct,
        "opportunity_packaging_gbp": s.opportunity_packaging_gbp,
        "opportunity_testing_refurbishment_gbp": s.opportunity_testing_refurbishment_gbp,
        "opportunity_returns_warranty_pct": s.opportunity_returns_warranty_pct,
        "opportunity_minimum_sold_comps": s.opportunity_minimum_sold_comps,
        "opportunity_minimum_source_diversity": s.opportunity_minimum_source_diversity,
        "opportunity_weight_economic_pct": s.opportunity_weight_economic_pct,
        "opportunity_weight_desirability_pct": s.opportunity_weight_desirability_pct,
        "opportunity_weight_market_confidence_pct": s.opportunity_weight_market_confidence_pct,
        "opportunity_weight_risk_safety_pct": s.opportunity_weight_risk_safety_pct,
        "opportunity_weight_liquidity_pct": s.opportunity_weight_liquidity_pct,
    }
