from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import require_operator
from app.database import get_db
from app.models.channel_listing import ChannelListing
from app.models.listing_publish_event import ListingPublishEvent

router = APIRouter(prefix="/cross-listing", tags=["cross-listing"], dependencies=[Depends(require_operator)])


class RecreateScheduleIn(BaseModel):
    build_id: int
    channel: str = Field(min_length=2, max_length=30)
    interval_days: int = Field(ge=1, le=365)
    enabled: bool = True


@router.get("/schedules")
async def list_schedules(build_id: int | None = Query(None), db: AsyncSession = Depends(get_db)):
    query = select(ChannelListing).order_by(ChannelListing.channel)
    if build_id is not None:
        query = query.where(ChannelListing.manual_build_id == build_id)
    rows = (await db.execute(query)).scalars().all()
    return [_schedule(row) for row in rows]


@router.put("/schedules")
async def save_schedule(body: RecreateScheduleIn, db: AsyncSession = Depends(get_db)):
    row = (await db.execute(select(ChannelListing).where(ChannelListing.manual_build_id == body.build_id, ChannelListing.channel == body.channel).order_by(ChannelListing.created_at.desc()))).scalars().first()
    if not row:
        row = ChannelListing(manual_build_id=body.build_id, channel=body.channel, status="published")
        db.add(row)
    row.recreate_enabled = body.enabled
    row.recreate_interval_days = body.interval_days
    row.next_recreate_at = datetime.utcnow() + timedelta(days=body.interval_days) if body.enabled else None
    row.last_recreate_status = "scheduled" if body.enabled else "paused"
    row.last_recreate_message = f"Recreate every {body.interval_days} day(s)."
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


def _schedule(row: ChannelListing) -> dict:
    return {"id": row.id, "build_id": row.manual_build_id, "channel": row.channel, "status": row.status,
            "recreate_enabled": row.recreate_enabled, "interval_days": row.recreate_interval_days,
            "next_recreate_at": row.next_recreate_at.isoformat() if row.next_recreate_at else None,
            "last_recreate_at": row.last_recreate_at.isoformat() if row.last_recreate_at else None,
            "recreate_count": row.recreate_count, "last_recreate_status": row.last_recreate_status,
            "last_recreate_message": row.last_recreate_message}
