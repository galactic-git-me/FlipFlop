"""Run persisted schedules through real channel APIs or durable Chrome jobs."""
from datetime import datetime, timedelta
import structlog
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.channel_listing import ChannelListing
from app.models.listing_publish_event import ListingPublishEvent
from app.models.manual_build import ManualBuild
from app.services.browser_listing_jobs import BROWSER_CHANNELS, enqueue_browser_job

log = structlog.get_logger(__name__)
MANUAL_CODEX_CHANNELS = BROWSER_CHANNELS


async def run_cross_listing_recreate_job() -> dict:
    now = datetime.utcnow()
    recreated = failed = queued = 0
    async with AsyncSessionLocal() as db:
        ids = (await db.execute(select(ChannelListing.id).where(
            ChannelListing.recreate_enabled.is_(True), ChannelListing.next_recreate_at <= now,
            ChannelListing.status.in_(["published", "ended", "withdrawn", "submitted"])))) .scalars().all()
        for listing_id in ids:
            try:
                row = (await db.execute(select(ChannelListing).where(ChannelListing.id == listing_id)
                    .with_for_update(skip_locked=True))).scalar_one_or_none()
                if not row or not row.next_recreate_at or row.next_recreate_at > now:
                    continue
                build = await db.get(ManualBuild, row.manual_build_id)
                if not build or build.status == "sold" or build.is_archived:
                    row.recreate_enabled = False
                    row.last_recreate_status = "skipped"
                    row.last_recreate_message = "Build is sold or unavailable."
                    await db.commit()
                    continue
                if row.channel in BROWSER_CHANNELS:
                    from app.services.channel_images import prepare_channel_urls
                    images = await prepare_channel_urls([p["url"] for p in build.photos or []
                        if isinstance(p, dict) and p.get("url") and p.get("kind", "photo") == "photo"], row.channel)
                    await enqueue_browser_job(db, build.id, row.channel, operation="relist", image_urls=images)
                    await db.commit()
                    queued += 1
                    continue
                if row.channel in {"ebay", "ebay_uk"}:
                    # The eBay lifecycle worker owns its reconciliation and clock.
                    continue
                if row.channel == "amazon":
                    from app.api.cross_listing import publish_amazon, AmazonPublishIn
                    result = await publish_amazon(build.id, AmazonPublishIn(
                        title=build.generated_title or build.name, description=build.generated_description or "",
                        bullet_points=[], price=build.ebay_price or 0, quantity=1,
                        condition=build.ebay_condition or "used_like_new", images=[p["url"] for p in build.photos or []
                            if isinstance(p, dict) and p.get("url") and p.get("kind", "photo") == "photo"]), db)
                    if not result.get("success") or result.get("status") != "published":
                        raise ValueError(result.get("message", "Amazon did not confirm publishing"))
                    row.listing_url = result.get("listing_url")
                elif row.channel in {"storefront", "flipflop_shop"}:
                    from app.api.manual_builds import list_on_storefront, ListOnStorefrontRequest
                    result = await list_on_storefront(build.id, ListOnStorefrontRequest(price=build.ebay_price), db)
                    row.external_listing_id = str(result.product_id)
                    row.listing_url = "https://www.theflipflop.shop" + result.storefront_url
                else:
                    raise ValueError("No publishing adapter is configured for this channel")
                row.status = "published"
                row.last_recreate_at, row.last_recreate_status = now, "success"
                row.last_recreate_message = "Confirmed through the channel API."
                row.recreate_count = (row.recreate_count or 0) + 1
                row.next_recreate_at = now + timedelta(days=row.recreate_interval_days or 7)
                db.add(ListingPublishEvent(channel_listing_id=row.id, event_type="recreate_created",
                    message=row.last_recreate_message, event_metadata={"listing_url": row.listing_url}))
                await db.commit()
                recreated += 1
            except Exception:
                await db.rollback()
                failed += 1
                log.exception("cross_listing_recreate.failed", listing_id=listing_id)
    return {"recreated": recreated, "failed": failed, "queued": queued}
