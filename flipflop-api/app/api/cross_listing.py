from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import require_operator
from app.database import get_db
from app.models.channel_listing import ChannelListing
from app.models.listing_publish_event import ListingPublishEvent
from app.models.app_settings import AppSettings
from app.services.alerts import emit_alert
from app.services.amazon_sp_api import AmazonSPAPI, AmazonSPAPIError
from app.models.manual_build import ManualBuild

router = APIRouter(prefix="/cross-listing", tags=["cross-listing"], dependencies=[Depends(require_operator)])
INDIRECT_CHANNELS = {"onbuy", "amazon", "facebook_catalog", "vinted"}


class RecreateScheduleIn(BaseModel):
    build_id: int
    channel: str = Field(min_length=2, max_length=30)
    interval_days: int = Field(ge=1, le=365)
    enabled: bool = True


class CodexHandoffResultIn(BaseModel):
    success: bool
    message: str = Field(min_length=1, max_length=500)
    external_listing_id: str | None = Field(default=None, max_length=120)
    listing_url: str | None = Field(default=None, max_length=500)


class IndirectChannelSettingsIn(BaseModel):
    interval_days: int = Field(ge=1, le=365)


class AmazonPublishIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=4000)
    bullet_points: list[str] = Field(default_factory=list, max_length=8)
    price: float = Field(gt=0)
    quantity: int = Field(ge=0, le=999)
    condition: str = Field(min_length=1, max_length=60)
    images: list[str] = Field(min_length=1, max_length=12)
    sku: str | None = Field(default=None, max_length=80)


async def _app_settings(db: AsyncSession) -> AppSettings:
    settings = (await db.execute(select(AppSettings).where(AppSettings.name == "default"))).scalar_one_or_none()
    if not settings:
        settings = AppSettings(name="default")
        db.add(settings)
        await db.flush()
    return settings


@router.get("/settings")
async def get_cross_listing_settings(db: AsyncSession = Depends(get_db)):
    settings = await _app_settings(db)
    return {"indirect_channel_recreate_interval_days": settings.indirect_channel_recreate_interval_days or 7}


@router.get("/amazon/status")
async def amazon_status():
    """Check the seller-authorized SP-API connection without exposing secrets."""
    client = AmazonSPAPI()
    if not client.configured:
        return {"connected": False, "configured": False, "message": "Amazon credentials are not configured on the API service."}
    try:
        result = await client.status()
        result["configured"] = True
        if not result["marketplace_found"]:
            result["connected"] = False
            result["message"] = "The seller is authorized, but the configured marketplace is not enabled for this account."
        return result
    except AmazonSPAPIError as exc:
        return {"connected": False, "configured": True, "message": str(exc), "status_code": exc.status_code}


@router.post("/amazon/publish/{build_id}")
async def publish_amazon(build_id: int, body: AmazonPublishIn, db: AsyncSession = Depends(get_db)):
    """Create/update the Amazon listing for a reviewed canonical build."""
    build = await db.get(ManualBuild, build_id)
    if not build:
        raise HTTPException(status_code=404, detail="Build not found")
    if build.status == "sold" or body.quantity == 0:
        raise HTTPException(status_code=409, detail="Sold or zero-quantity builds cannot be listed on Amazon")

    sku = body.sku or f"FF-BUILD-{build_id}"
    client = AmazonSPAPI()
    if not client.configured:
        raise HTTPException(status_code=503, detail="Amazon SP-API is not configured on the API service")
    channel_listing = (await db.execute(
        select(ChannelListing)
        .where(ChannelListing.manual_build_id == build_id, ChannelListing.channel == "amazon")
        .order_by(ChannelListing.created_at.desc())
    )).scalars().first()
    if not channel_listing:
        channel_listing = ChannelListing(manual_build_id=build_id, channel="amazon", status="publishing")
        db.add(channel_listing)
        await db.flush()

    try:
        result = await client.upsert_listing(
            sku=sku,
            title=body.title,
            description=body.description,
            bullet_points=body.bullet_points,
            price=body.price,
            quantity=body.quantity,
            condition=body.condition,
            images=body.images,
        )
        issues = result.get("issues") or []
        accepted = str(result.get("status", "")).upper() in {"ACCEPTED", "VALID"} and not issues
        channel_listing.status = "published" if accepted else "failed"
        channel_listing.external_listing_id = sku
        channel_listing.published_at = datetime.utcnow() if accepted else None
        message = "Amazon accepted the listing submission." if accepted else "Amazon returned listing requirements or validation issues."
        db.add(ListingPublishEvent(channel_listing_id=channel_listing.id, event_type="published" if accepted else "publish_failed", message=message, event_metadata={"sku": sku, "response": result}))
        await db.commit()
        return {"success": accepted, "status": channel_listing.status, "sku": sku, "listing_url": None, "response": result, "message": message}
    except AmazonSPAPIError as exc:
        channel_listing.status = "failed"
        channel_listing.last_recreate_status = "failed"
        channel_listing.last_recreate_message = str(exc)[:500]
        db.add(ListingPublishEvent(channel_listing_id=channel_listing.id, event_type="publish_failed", message=str(exc)[:500], event_metadata={"sku": sku, "details": exc.details}))
        await db.commit()
        raise HTTPException(status_code=502, detail={"message": str(exc), "details": exc.details})


@router.put("/settings")
async def save_cross_listing_settings(body: IndirectChannelSettingsIn, db: AsyncSession = Depends(get_db)):
    settings = await _app_settings(db)
    settings.indirect_channel_recreate_interval_days = body.interval_days
    rows = (await db.execute(select(ChannelListing).where(ChannelListing.channel.in_(INDIRECT_CHANNELS)))).scalars().all()
    now = datetime.utcnow()
    for row in rows:
        row.recreate_interval_days = body.interval_days
        if row.recreate_enabled:
            row.next_recreate_at = now + timedelta(days=body.interval_days)
    await db.commit()
    return {"indirect_channel_recreate_interval_days": body.interval_days}


@router.get("/schedules")
async def list_schedules(build_id: int | None = Query(None), db: AsyncSession = Depends(get_db)):
    query = select(ChannelListing).order_by(ChannelListing.channel)
    if build_id is not None:
        query = query.where(ChannelListing.manual_build_id == build_id)
    rows = (await db.execute(query)).scalars().all()
    return [_schedule(row) for row in rows]


@router.put("/schedules")
async def save_schedule(body: RecreateScheduleIn, db: AsyncSession = Depends(get_db)):
    interval_days = body.interval_days
    if body.channel in INDIRECT_CHANNELS:
        settings = await _app_settings(db)
        interval_days = settings.indirect_channel_recreate_interval_days or 7
    row = (await db.execute(select(ChannelListing).where(ChannelListing.manual_build_id == body.build_id, ChannelListing.channel == body.channel).order_by(ChannelListing.created_at.desc()))).scalars().first()
    if not row:
        row = ChannelListing(manual_build_id=body.build_id, channel=body.channel, status="published")
        db.add(row)
    row.recreate_enabled = body.enabled
    row.recreate_interval_days = interval_days
    row.next_recreate_at = datetime.utcnow() + timedelta(days=interval_days) if body.enabled else None
    row.last_recreate_status = "scheduled" if body.enabled else "paused"
    row.last_recreate_message = f"Recreate every {interval_days} day(s)."
    await db.commit()
    await db.refresh(row)
    return _schedule(row)


@router.get("/actions")
async def list_actions(build_id: int | None = Query(None), limit: int = Query(100, ge=1, le=500), db: AsyncSession = Depends(get_db)):
    query = select(ListingPublishEvent, ChannelListing.channel, ChannelListing.manual_build_id).join(ChannelListing, ChannelListing.id == ListingPublishEvent.channel_listing_id).order_by(ListingPublishEvent.created_at.desc()).limit(limit)
    if build_id is not None:
        query = query.where(ChannelListing.manual_build_id == build_id)
    rows = (await db.execute(query)).all()
    return [{"id": event.id, "build_id": row_build_id, "channel": channel, "event_type": event.event_type, "message": event.message, "metadata": event.event_metadata, "created_at": event.created_at.isoformat() if event.created_at else None} for event, channel, row_build_id in rows]


@router.post("/actions/{event_id}/codex-result")
async def record_codex_result(event_id: int, body: CodexHandoffResultIn, db: AsyncSession = Depends(get_db)):
    event = await db.get(ListingPublishEvent, event_id)
    if not event or event.event_type != "recreate_handoff_required":
        raise HTTPException(status_code=404, detail="Codex relisting handoff not found")
    row = await db.get(ChannelListing, event.channel_listing_id)
    if not row:
        raise HTTPException(status_code=404, detail="Channel listing not found")
    now = datetime.utcnow()
    row.last_recreate_at = now
    row.last_recreate_status = "success" if body.success else "failed"
    row.last_recreate_message = body.message
    row.status = "published" if body.success else "withdrawn"
    if body.success:
        row.external_listing_id = body.external_listing_id
        row.published_at = now
        row.withdrawn_at = None
        row.next_recreate_at = now + timedelta(days=row.recreate_interval_days or 7) if row.recreate_enabled else None
    else:
        row.next_recreate_at = None
    db.add(ListingPublishEvent(
        channel_listing_id=row.id,
        event_type="recreate_created" if body.success else "recreate_failed",
        message=body.message,
        event_metadata={"build_id": row.manual_build_id, "channel": row.channel, "external_id": body.external_listing_id, "listing_url": body.listing_url, "via": "codex_browser_assist", "at": now.isoformat()},
    ))
    await db.commit()
    await emit_alert(
        code="cross_listing_recreated" if body.success else "cross_listing_recreate_failed",
        source=row.channel,
        severity="info" if body.success else "critical",
        message=f"Codex relisting {'completed' if body.success else 'failed'} for Build {row.manual_build_id} on {row.channel}: {body.message}",
        link_url="/cross-listing",
    )
    return {"ok": True, "schedule": _schedule(row)}


def _schedule(row: ChannelListing) -> dict:
    return {"id": row.id, "build_id": row.manual_build_id, "channel": row.channel, "status": row.status,
            "external_listing_id": row.external_listing_id,
            "published_at": row.published_at.isoformat() if row.published_at else None,
            "withdrawn_at": row.withdrawn_at.isoformat() if row.withdrawn_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            "recreate_enabled": row.recreate_enabled, "interval_days": row.recreate_interval_days,
            "next_recreate_at": row.next_recreate_at.isoformat() if row.next_recreate_at else None,
            "last_recreate_at": row.last_recreate_at.isoformat() if row.last_recreate_at else None,
            "recreate_count": row.recreate_count, "last_recreate_status": row.last_recreate_status,
            "last_recreate_message": row.last_recreate_message}
