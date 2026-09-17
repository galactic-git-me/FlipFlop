"""Persistent per-channel recreate worker for cross-listings."""
from datetime import datetime, timedelta
import structlog
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.channel_listing import ChannelListing
from app.models.listing_publish_event import ListingPublishEvent
from app.models.manual_build import ManualBuild
from app.services.live_publisher import LivePublisher
from app.services.alerts import emit_alert

log = structlog.get_logger(__name__)


async def run_cross_listing_recreate_job() -> dict:
    now = datetime.utcnow()
    recreated = failed = 0
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(ChannelListing).where(
            ChannelListing.recreate_enabled.is_(True),
            ChannelListing.next_recreate_at.isnot(None),
            ChannelListing.next_recreate_at <= now,
            ChannelListing.status == "published",
        ))).scalars().all()
        for row in rows:
            build = await db.get(ManualBuild, row.manual_build_id)
            if not build or build.status == "sold":
                row.recreate_enabled = False
                row.last_recreate_status = "skipped"
                row.last_recreate_message = "Paused because the build is unavailable or sold."
                continue
            try:
                await LivePublisher.withdraw_from_channel(db, build.id, row.channel)
                db.add(ListingPublishEvent(channel_listing_id=row.id, event_type="recreate_ended", message=f"Ended {row.channel} before scheduled recreation.", event_metadata={"build_id": build.id, "channel": row.channel, "at": now.isoformat()}))
                result = await LivePublisher.publish_to_channel(db, build.id, row.channel)
                row.last_recreate_at = now
                row.recreate_count += 1
                row.last_recreate_status = "success" if result.success else "failed"
                row.last_recreate_message = result.message or result.error or "Recreate completed."
                row.next_recreate_at = now + timedelta(days=row.recreate_interval_days or 7)
                db.add(ListingPublishEvent(channel_listing_id=row.id, event_type="recreate_created" if result.success else "recreate_failed", message=row.last_recreate_message, event_metadata={"build_id": build.id, "channel": row.channel, "external_id": result.external_listing_id, "at": now.isoformat()}))
                await db.commit()
                await emit_alert(code="cross_listing_recreated" if result.success else "cross_listing_recreate_failed", source=row.channel, severity="info" if result.success else "critical", message=f"Cross-listing {('recreated' if result.success else 'recreate failed')} for Build {build.id} on {row.channel}: {row.last_recreate_message}", link_url="/cross-listing")
                recreated += int(result.success)
                failed += int(not result.success)
            except Exception as exc:
                await db.rollback()
                failed += 1
                log.exception("cross_listing_recreate.failed", build_id=row.manual_build_id, channel=row.channel, error=str(exc))
    return {"recreated": recreated, "failed": failed}
