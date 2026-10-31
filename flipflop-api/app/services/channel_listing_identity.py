"""Persist identities returned by real API publications for the shared UI."""
from datetime import datetime, timedelta
from sqlalchemy import select
from app.models.channel_listing import ChannelListing
from app.models.listing_publish_event import ListingPublishEvent


async def save_confirmed_identity(db, build, channel, external_id, listing_url):
    aliases = {"ebay_uk": ["ebay", "ebay_uk"], "flipflop_shop": ["storefront", "flipflop_shop"]}.get(channel, [channel])
    row = (await db.execute(select(ChannelListing).where(ChannelListing.manual_build_id == build.id,
        ChannelListing.channel.in_(aliases)).order_by(ChannelListing.id.desc()))).scalars().first()
    if not row:
        row = ChannelListing(manual_build_id=build.id, channel=channel,
            recreate_enabled=bool(build.relist_enabled), recreate_interval_days=7, recreate_count=0)
        db.add(row)
        await db.flush()
    row.external_listing_id, row.listing_url, row.status = str(external_id), listing_url, "published"
    row.published_at = row.published_at or datetime.utcnow()
    row.withdrawn_at = None
    if row.recreate_enabled and row.next_recreate_at is None:
        row.next_recreate_at = build.next_recreate_at or row.published_at + timedelta(days=row.recreate_interval_days or 7)
    db.add(ListingPublishEvent(channel_listing_id=row.id, event_type="identity_confirmed",
        message="Confirmed through the channel API.", event_metadata={"build_id": build.id,
            "channel": channel, "external_id": str(external_id), "listing_url": listing_url}))
    await db.flush()
