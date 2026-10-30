"""Desired channel state, canonical change detection, and confirmed-sale fanout."""
from datetime import datetime, timedelta
import hashlib
import json
import re
from sqlalchemy import select
from app.models.browser_listing_job import BrowserListingJob
from app.models.channel_listing import ChannelListing
from app.models.listing_publish_event import ListingPublishEvent
from app.models.manual_build import ManualBuild
from app.models.product import Product, ProductStatus, WithdrawalReason

ALIASES = {"ebay": "ebay_uk", "storefront": "flipflop_shop", "facebook": "facebook_catalog", "facebook_marketplace": "facebook_catalog"}
PENDING = ("queued", "running", "blocked", "needs_review")


def canonical_hash(build):
    fields = ("name", "generated_title", "generated_description", "ebay_price", "ebay_condition", "generated_aspects",
        "components", "photos", "hero_photo_url", "shipping_cost", "shipping_method", "return_days", "selected_faq_ids", "selected_faq_answer_overrides")
    data = {field: getattr(build, field, None) for field in fields}
    return hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()


async def enqueue_operation(db, build, row, operation):
    from app.services.browser_listing_jobs import BROWSER_CHANNELS, enqueue_browser_job
    pending = (await db.execute(select(BrowserListingJob).where(BrowserListingJob.channel_listing_id == row.id,
        BrowserListingJob.status.in_(PENDING)).with_for_update())).scalar_one_or_none()
    if pending:
        if pending.operation == "withdraw" or operation != "withdraw":
            return pending
        # A confirmed sale invalidates an in-flight publish/update lease.
        pending.status, pending.lease_token, pending.lease_until = "cancelled", None, None
        pending.message = "Superseded by withdrawal after a confirmed sale or archive."
        await db.flush()
    if row.channel in BROWSER_CHANNELS:
        job = await enqueue_browser_job(db, build.id, row.channel, operation=operation)
    else:
        job = BrowserListingJob(channel_listing_id=row.id, operation=operation, status="queued",
            payload={"build_id": build.id, "channel": row.channel, "canonical_hash": canonical_hash(build)})
        db.add(job)
        await db.flush()
    if operation == "withdraw":
        row.recreate_enabled, row.next_recreate_at, row.status = False, None, "withdrawal_pending"
    return job


async def withdraw_other_channels(db, build, source_channel=None):
    """Persist every withdrawal in the sale transaction; never claim remote success."""
    source_channel = ALIASES.get(source_channel, source_channel)
    build.relist_enabled, build.next_recreate_at, build.deferred_publish_at = False, None, None
    rows = (await db.execute(select(ChannelListing).where(ChannelListing.manual_build_id == build.id).order_by(ChannelListing.id))).scalars().all()
    now = datetime.utcnow()
    # Remove storefront stock in the same database transaction as the sale.
    if build.storefront_product_id:
        product = (await db.execute(select(Product).where(Product.id == build.storefront_product_id).with_for_update())).scalar_one_or_none()
        if product and product.status not in {ProductStatus.SOLD, ProductStatus.WITHDRAWN}:
            product.status, product.withdrawn_at = ProductStatus.WITHDRAWN, now
            product.withdrawal_reason = WithdrawalReason.SOLD_OTHER_CHANNEL
    for row in rows:
        row.recreate_enabled, row.next_recreate_at = False, None
        channel = ALIASES.get(row.channel, row.channel)
        if channel == source_channel or row.status == "sold" or (channel == "ebay_uk" and build.ebay_listing_status == "sold"):
            row.status = "sold"
            continue
        if channel == "flipflop_shop":
            row.status, row.withdrawn_at, row.last_checked_at = "withdrawn", now, now
            pending = (await db.execute(select(BrowserListingJob).where(BrowserListingJob.channel_listing_id == row.id,
                BrowserListingJob.status.in_(PENDING)))).scalars().all()
            for job in pending:
                job.status, job.lease_token, job.lease_until = "cancelled", None, None
            continue
        if row.status == "withdrawn" and row.last_checked_at:
            continue
        if row.external_listing_id or row.listing_url or row.status in {"publishing", "published", "withdrawal_pending"}:
            await enqueue_operation(db, build, row, "withdraw")
    await db.flush()


async def confirm_browser_observation(db, job, *, state, external_id=None, listing_url=None, evidence=None, order_id=None):
    from app.services.browser_listing_jobs import validate_listing_url
    row = await db.get(ChannelListing, job.channel_listing_id)
    build = (await db.execute(select(ManualBuild).where(ManualBuild.id == row.manual_build_id).with_for_update())).scalar_one()
    if not evidence or not evidence.get("verified_at") or not evidence.get("url") or not evidence.get("note"):
        raise ValueError("An observed seller-page result is required")
    if state == "sold" and (not order_id or not external_id or external_id != row.external_listing_id):
        raise ValueError("A confirmed seller order and the exact saved vendor item ID are required for a sale")
    now = datetime.utcnow()
    row.last_checked_at = now
    job.status, job.message, job.lease_token, job.lease_until = "succeeded", f"Seller account confirmed {state}.", None, None
    await db.flush()  # Release the pending index before scheduling follow-up work.
    if job.operation == "withdraw":
        if state not in {"ended", "missing", "sold"}:
            raise ValueError("The seller account must confirm the item is no longer offered for sale")
        row.status, row.withdrawn_at = "withdrawn", now
        row.recreate_enabled, row.next_recreate_at = False, None
    elif state == "sold":
        row.status = "sold"
        build.status, build.dispatch_status, build.updated_at = "sold", "awaiting_dispatch", now
        await withdraw_other_channels(db, build, row.channel)
        from app.services.getting_started_jobs import ensure_manual_build_job
        await ensure_manual_build_job(db, manual_build_id=build.id)
    elif state in {"ended", "missing"}:
        row.status = "ended"
        if row.recreate_enabled:
            row.next_recreate_at = now
    elif state == "active":
        if listing_url:
            validate_listing_url(row.channel, listing_url)
            row.listing_url = listing_url
        row.status = "published"
        if build.status == "sold" or build.is_archived:
            await withdraw_other_channels(db, build)
        elif evidence.get("price") is not None and float(evidence["price"]) != build.ebay_price:
            await enqueue_operation(db, build, row, "update")
    else:
        job.status, job.message = "needs_review", "Seller state is unverified; no sale or withdrawal was inferred."
    db.add(ListingPublishEvent(channel_listing_id=row.id, event_type="seller_state_confirmed",
        message=job.message, event_metadata={"job_id": job.id, "state": state, "order_id": order_id, "evidence": evidence}))


async def queue_email_checks(db, sale, body):
    """Emails trigger seller verification; titles/senders alone never prove a sale."""
    channel = ALIASES.get(sale.get("marketplace"), sale.get("marketplace"))
    if channel not in {"ebay_uk", "amazon", "onbuy", "facebook_catalog", "vinted"}:
        return []
    title = (sale.get("title") or "").strip().casefold()
    candidates = (await db.execute(select(ManualBuild).where(ManualBuild.status != "sold", ManualBuild.is_archived.is_(False)))).scalars().all()
    matched = [b for b in candidates if (b.ebay_listing_id and b.ebay_listing_id in body and channel == "ebay_uk")
        or re.search(r"\bFF-BUILD-" + str(b.id) + r"\b", body)
        or (title and title != "unknown" and title in {(b.generated_title or "").casefold(), (b.name or "").casefold()})]
    if len(matched) != 1:
        return []
    build = matched[0]
    row = (await db.execute(select(ChannelListing).where(ChannelListing.manual_build_id == build.id,
        ChannelListing.channel.in_([channel] + [key for key, value in ALIASES.items() if value == channel])).order_by(ChannelListing.id.desc()))).scalars().first()
    if not row:
        if channel != "ebay_uk" or not build.ebay_listing_id:
            return []
        row = ChannelListing(manual_build_id=build.id, channel=channel, status="published",
            external_listing_id=build.ebay_listing_id, listing_url=build.ebay_listing_url)
        db.add(row)
        await db.flush()
    return [await enqueue_operation(db, build, row, "sale_check")]
