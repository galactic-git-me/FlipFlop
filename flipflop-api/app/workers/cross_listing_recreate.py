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

# These destinations do not have a server-side publishing adapter. They are
# deliberately routed to the Codex browser-assist handoff instead of being
# reported as successfully automated.
MANUAL_CODEX_CHANNELS = {"onbuy", "amazon", "facebook_catalog", "vinted"}
INTERNAL_CHANNEL_NAMES = {"ebay_uk": "ebay", "flipflop_shop": "storefront"}


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
                if row.channel in MANUAL_CODEX_CHANNELS:
                    row.last_recreate_at = now
                    row.recreate_count += 1
                    row.last_recreate_status = "awaiting_codex"
                    row.last_recreate_message = "Codex handoff required: end the current listing and create a brand-new listing from the listing pack."
                    # Do not repeatedly create the same task every five
                    # minutes. The operator can reschedule after completion.
                    row.next_recreate_at = None
                    db.add(ListingPublishEvent(
                        channel_listing_id=row.id,
                        event_type="recreate_handoff_required",
                        message=row.last_recreate_message,
                        event_metadata={"build_id": build.id, "channel": row.channel, "requires_browser_assist": True, "at": now.isoformat()},
                    ))
                    await db.commit()
                    await emit_alert(
                        code="cross_listing_codex_handoff",
                        source=row.channel,
                        severity="warning",
                        message=f"Codex handoff required for Build {build.id} on {row.channel}: end the current listing and create a new one.",
                        link_url="/cross-listing",
                    )
                    continue

                internal_channel = INTERNAL_CHANNEL_NAMES.get(row.channel, row.channel)
                await LivePublisher.withdraw_from_channel(db, build.id, internal_channel)
                db.add(ListingPublishEvent(channel_listing_id=row.id, event_type="recreate_ended", message=f"Ended {row.channel} before scheduled recreation.", event_metadata={"build_id": build.id, "channel": row.channel, "at": now.isoformat()}))
                result = await LivePublisher.publish_to_channel(db, build.id, internal_channel)
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
