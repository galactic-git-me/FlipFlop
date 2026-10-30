"""Reconcile inventory, push canonical edits and execute durable API jobs."""
from datetime import datetime, timedelta
import os
import secrets
import structlog
from sqlalchemy import select, or_, case
from app.database import AsyncSessionLocal
from app.models.browser_listing_job import BrowserListingJob
from app.models.channel_listing import ChannelListing
from app.models.listing_publish_event import ListingPublishEvent
from app.models.manual_build import ManualBuild
from app.models.app_settings import AppSettings
from app.services.browser_listing_jobs import BROWSER_CHANNELS
from app.services.channel_sync import ALIASES, canonical_hash, build_is_unavailable, enqueue_operation, withdraw_other_channels

log = structlog.get_logger(__name__)
_amazon_order_cache = (None, {})


async def plan_sync(db):
    now = datetime.utcnow()
    ids = (await db.execute(select(ManualBuild.id).where(or_(ManualBuild.ebay_listing_id.isnot(None),
        ManualBuild.storefront_product_id.isnot(None), ManualBuild.id.in_(select(ChannelListing.manual_build_id)))))).scalars().all()
    planned = 0
    for build_id in ids:
        build = (await db.execute(select(ManualBuild).where(ManualBuild.id == build_id).with_for_update(skip_locked=True))).scalar_one_or_none()
        if not build:
            continue
        rows = (await db.execute(select(ChannelListing).where(ChannelListing.manual_build_id == build.id))).scalars().all()
        for channel, external_id, url in [("ebay_uk", build.ebay_listing_id, build.ebay_listing_url),
                ("flipflop_shop", build.storefront_product_id, f"https://www.theflipflop.shop/ready-to-ship/{build.storefront_product_id}")]:
            if external_id and not any(ALIASES.get(r.channel, r.channel) == channel for r in rows):
                row = ChannelListing(manual_build_id=build.id, channel=channel, external_listing_id=str(external_id), listing_url=url, status="published")
                db.add(row)
                await db.flush()
                rows.append(row)
        if await build_is_unavailable(db, build):
            await withdraw_other_channels(db, build)
            continue
        fingerprint = canonical_hash(build)
        for row in rows:
            if row.status not in {"published", "submitted"}:
                continue
            channel = ALIASES.get(row.channel, row.channel)
            if channel == "google_shopping":
                # Merchant Center is distribution, not a checkout/order source.
                check_minutes = max(15, int(os.getenv("CROSS_LISTING_BROWSER_POLL_MINUTES", "15")))
            else:
                check_minutes = max(5, int(os.getenv("CROSS_LISTING_BROWSER_POLL_MINUTES", "15"))) if channel in BROWSER_CHANNELS else 5
            operation = "update" if row.last_payload_hash != fingerprint and row.status == "published" else "inspect"
            if operation == "inspect" and row.last_checked_at and row.last_checked_at > now - timedelta(minutes=check_minutes):
                continue
            try:
                await enqueue_operation(db, build, row, operation)
                planned += 1
            except ValueError as exc:
                row.last_recreate_status, row.last_recreate_message = "blocked", str(exc)[:500]
        await db.flush()
    return planned


async def execute_api_job(db, job, row, build):
    global _amazon_order_cache
    channel = ALIASES.get(row.channel, row.channel)
    now = datetime.utcnow()
    if job.operation != "withdraw" and await build_is_unavailable(db, build):
        job.status, job.message = "cancelled", "Build sold or archived; publication/update cancelled."
        await withdraw_other_channels(db, build)
        return
    if job.operation == "withdraw":
        if channel == "ebay_uk":
            from app.services.ebay_listing_reconciliation import reconcile_manual_build_listing
            state = await reconcile_manual_build_listing(build, db, force=True)
            if state == "active":
                from app.api.manual_builds import end_ebay_listing
                await end_ebay_listing(build.id, db)
                state = await reconcile_manual_build_listing(build, db, force=True)
            if state not in {"ended", "missing", "sold"}:
                raise ValueError("eBay withdrawal is not yet confirmed")
        elif channel == "amazon":
            from app.services.amazon_sp_api import AmazonSPAPI
            if not await AmazonSPAPI().withdraw_listing(sku=row.external_listing_id or f"FF-BUILD-{build.id}"):
                raise ValueError("Amazon accepted withdrawal but the item remains buyable")
        else:
            raise ValueError("No API withdrawal adapter is configured")
        row.status, row.withdrawn_at, row.last_checked_at = "withdrawn", now, now
        row.recreate_enabled, row.next_recreate_at = False, None
    elif job.operation in {"inspect", "sale_check"}:
        if channel == "ebay_uk":
            from app.services.ebay_listing_reconciliation import reconcile_manual_build_listing
            state = await reconcile_manual_build_listing(build, db, force=True)
            row.status = {"active": "published", "sold": "sold", "ended": "ended", "missing": "ended"}.get(state, row.status)
            if state not in {"active", "sold", "ended", "missing"}:
                raise ValueError("eBay state is unverified; sale and availability were not inferred")
            if state == "sold":
                await withdraw_other_channels(db, build, channel)
        elif channel == "amazon":
            from app.services.amazon_sp_api import AmazonSPAPI
            from app.api.cross_listing import _amazon_asin
            client = AmazonSPAPI()
            timestamp, orders = _amazon_order_cache
            if timestamp is None or timestamp < now - timedelta(minutes=5):
                orders = await client.paid_orders_by_sku()
                _amazon_order_cache = (now, orders)
            sku = row.external_listing_id or f"FF-BUILD-{build.id}"
            if sku in orders:
                build.status, build.dispatch_status, row.status = "sold", "awaiting_dispatch", "sold"
                await withdraw_other_channels(db, build, channel)
                db.add(ListingPublishEvent(channel_listing_id=row.id, event_type="sale_confirmed", message="Amazon confirmed a paid order for the exact seller SKU.", event_metadata={"order_id": orders[sku]}))
            else:
                item = await client.get_listing(sku=sku)
                if any("BUYABLE" in (s.get("status") or []) for s in item.get("summaries", [])):
                    row.status = "published"
                    asin = _amazon_asin(item)
                    if asin:
                        row.listing_url = f"https://www.amazon.co.uk/dp/{asin}"
                elif row.status == "published":
                    row.status = "ended"  # Unavailable is not proof of sale.
        elif channel == "flipflop_shop":
            from app.models.product import Product, ProductStatus
            product = await db.get(Product, build.storefront_product_id) if build.storefront_product_id else None
            if product and product.status == ProductStatus.SOLD:
                build.status, row.status = "sold", "sold"
                await withdraw_other_channels(db, build, channel)
            elif not product or product.status == ProductStatus.WITHDRAWN:
                row.status = "ended"
        row.last_checked_at = now
        if row.status == "ended" and row.recreate_enabled:
            row.next_recreate_at = now
    elif job.operation == "update":
        if channel == "ebay_uk":
            from app.api.manual_builds import post_to_ebay
            from app.schemas.manual_build import PostToEbayRequest
            result = await post_to_ebay(build.id, PostToEbayRequest(price=build.ebay_price, condition=build.ebay_condition or "USED_EXCELLENT", publish=True), db)
            if not result.success:
                raise ValueError("eBay did not confirm the canonical update")
        elif channel == "flipflop_shop":
            from app.api.manual_builds import list_on_storefront, ListOnStorefrontRequest
            await list_on_storefront(build.id, ListOnStorefrontRequest(price=build.ebay_price), db)
        elif channel == "amazon":
            from app.api.cross_listing import publish_amazon, AmazonPublishIn
            result = await publish_amazon(build.id, AmazonPublishIn(title=build.generated_title or build.name,
                description=build.generated_description or "", bullet_points=[], price=build.ebay_price or 0, quantity=1,
                condition=build.ebay_condition or "used_like_new", images=[p["url"] for p in build.photos or [] if isinstance(p, dict) and p.get("url") and p.get("kind", "photo") == "photo"]), db)
            if result.get("status") == "submitted":
                job.status, job.message, job.lease_token, job.lease_until = "succeeded", "Amazon accepted the canonical update; live availability remains pending verification.", None, None
                row.last_checked_at = now
                return
            if result.get("status") != "published":
                raise ValueError("Amazon canonical update is not yet confirmed live")
        row.last_payload_hash, row.last_checked_at = canonical_hash(build), now
    job.status, job.message, job.lease_token, job.lease_until = "succeeded", f"API confirmed {job.operation}.", None, None
    db.add(ListingPublishEvent(channel_listing_id=row.id, event_type="channel_sync_completed", message=job.message,
        event_metadata={"job_id": job.id, "operation": job.operation, "listing_url": row.listing_url}))


async def run_channel_sync_job():
    planned = succeeded = failed = 0
    async with AsyncSessionLocal() as db:
        planned = await plan_sync(db)
        await db.commit()
        queued = (await db.execute(select(BrowserListingJob.id, BrowserListingJob.payload).where(
            BrowserListingJob.status == "queued", BrowserListingJob.available_at <= datetime.utcnow(),
            BrowserListingJob.payload["channel"].as_string().not_in(BROWSER_CHANNELS))
            .order_by(case((BrowserListingJob.operation == "withdraw", 0), else_=1), BrowserListingJob.id).limit(20))).all()
        for job_id, payload in queued:
            try:
                # Match the build-before-job lock order used by sale fanout.
                build = (await db.execute(select(ManualBuild).where(ManualBuild.id == payload["build_id"]).with_for_update(skip_locked=True))).scalar_one_or_none()
                if not build:
                    continue
                job = (await db.execute(select(BrowserListingJob).where(BrowserListingJob.id == job_id,
                    BrowserListingJob.status == "queued").with_for_update(skip_locked=True))).scalar_one_or_none()
                if not job:
                    continue
                row = await db.get(ChannelListing, job.channel_listing_id)
                job.status, job.lease_token, job.lease_until = "running", secrets.token_hex(32), datetime.utcnow() + timedelta(minutes=5)
                await execute_api_job(db, job, row, build)
                await db.commit()
                succeeded += 1
            except Exception:
                await db.rollback()
                failed += 1
                job = await db.get(BrowserListingJob, job_id)
                if not job or job.status in {"succeeded", "cancelled"}:
                    continue
                job.attempt_count = (job.attempt_count or 0) + 1
                job.status = "queued" if job.operation == "withdraw" and job.attempt_count < 10 else "blocked"
                job.available_at = datetime.utcnow() + timedelta(minutes=min(60, 2 ** job.attempt_count))
                job.lease_token, job.lease_until = None, None
                job.message = "Vendor operation failed or is unverified. Withdrawal will retry with backoff." if job.status == "queued" else "Vendor operation requires review; no remote success was assumed."
                await db.commit()
                log.exception("channel_sync.failed", job_id=job_id)
    return {"planned": planned, "succeeded": succeeded, "failed": failed}
