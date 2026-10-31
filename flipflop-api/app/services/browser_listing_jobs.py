"""Shared queue for operator publishing and scheduled Chrome relisting."""
from datetime import datetime, timedelta
from urllib.parse import urlparse
import re
from sqlalchemy import select
from app.models.browser_listing_job import BrowserListingJob
from app.models.channel_listing import ChannelListing
from app.models.listing_publish_event import ListingPublishEvent
from app.models.manual_build import ManualBuild
from app.models.app_settings import AppSettings

BROWSER_CHANNELS = {"onbuy", "facebook_catalog", "vinted"}
SELLER_URLS = {
    "onbuy": "https://seller.onbuy.com/",
    "facebook_catalog": "https://www.facebook.com/marketplace/you/selling",
    "vinted": "https://www.vinted.co.uk/member/items",
}
HOSTS = {"onbuy": {"onbuy.com"}, "facebook_catalog": {"facebook.com"},
         "vinted": {"vinted.co.uk"}}
PENDING = ("queued", "running", "blocked", "needs_review")
ITEM_PATHS = {"onbuy": r"~p\d+|/p/", "facebook_catalog": r"/marketplace/item/\d+",
              "vinted": r"/items/\d+"}


def validate_listing_url(channel: str, value: str) -> str:
    url = urlparse(value)
    host = (url.hostname or "").lower()
    domains = HOSTS.get(channel, set())
    if (url.scheme != "https" or url.username or url.password or url.port not in (None, 443)
            or not any(host == d or host.endswith("." + d) for d in domains)
            or not re.search(ITEM_PATHS.get(channel, r"(?!)"), url.path)):
        raise ValueError("A confirmed HTTPS listing URL on the selected vendor is required")
    return value


def seller_pack(build: ManualBuild, row: ChannelListing, image_urls: list[str] | None = None, *, allow_sold=False) -> dict:
    if (build.status == "sold" or build.is_archived) and not allow_sold:
        raise ValueError("Sold or archived builds cannot be listed")
    originals = [p["url"] for p in build.photos or [] if isinstance(p, dict) and p.get("url") and p.get("kind", "photo") == "photo"]
    if not build.generated_description or not build.generated_title or not build.ebay_price or build.ebay_price <= 0 or not originals:
        raise ValueError("Save the canonical title, description, listing price and product photographs first")
    from app.services.product_faqs import selected_faqs
    faqs = selected_faqs(build.id, build.selected_faq_ids, build.selected_faq_answer_overrides)
    title = build.generated_title.strip()
    if build.name.strip().lower() not in title.lower():
        title = f"{build.name.strip()} | {title}"[:80]
    return {"schema": "flipflop.seller-pack.v1", "build_id": build.id, "channel": row.channel,
        "seller_url": SELLER_URLS[row.channel], "previous_listing_id": row.external_listing_id,
        "previous_listing_url": row.listing_url,
        "listing": {"title": title, "description": build.generated_description, "faqs": faqs,
            "price": build.ebay_price, "currency": "GBP", "quantity": 1,
            "sku": f"FF-BUILD-{build.id}", "condition": build.ebay_condition or "Used",
            "specifications": build.generated_aspects or {}, "components": build.components or [],
            "images": image_urls or originals, "model_3d_url": build.model_3d_url,
            "shipping_cost": build.shipping_cost or 0, "return_days": build.return_days,
            "delivery_only": True, "collection_allowed": False, "pickup_allowed": False}}


async def enqueue_browser_job(db, build_id: int, channel: str, *, operation="publish", image_urls=None):
    if channel not in BROWSER_CHANNELS:
        raise ValueError("This channel uses its API publishing path")
    if operation not in {"publish", "update", "relist", "withdraw", "reconcile"}:
        raise ValueError("Unsupported browser listing operation")
    # Lock the build before finding/creating its channel identity; concurrent
    # double-clicks and scheduler ticks share this lock and the pending index.
    build = (await db.execute(select(ManualBuild).where(ManualBuild.id == build_id).with_for_update())).scalar_one_or_none()
    if not build:
        raise ValueError("Build not found")
    row = (await db.execute(select(ChannelListing).where(ChannelListing.manual_build_id == build_id,
        ChannelListing.channel == channel).order_by(ChannelListing.id.desc()))).scalars().first()
    if not row:
        settings = (await db.execute(select(AppSettings).where(AppSettings.name == "default"))).scalar_one_or_none()
        row = ChannelListing(manual_build_id=build_id, channel=channel, status="draft", recreate_count=0,
            recreate_enabled=bool(settings and settings.relist_enabled_default),
            recreate_interval_days=(settings.indirect_channel_recreate_interval_days or 7) if settings else 7)
        db.add(row)
        await db.flush()
    pending = (await db.execute(select(BrowserListingJob).where(
        BrowserListingJob.channel_listing_id == row.id, BrowserListingJob.status.in_(PENDING)))).scalar_one_or_none()
    if pending:
        if operation != "withdraw":
            return pending
        pending.status, pending.message = "blocked", "Superseded by a confirmed sale; withdrawal takes priority."
        pending.lease_token = pending.lease_until = None
        await db.flush()
    if operation == "withdraw":
        previous = (await db.execute(select(BrowserListingJob).where(
            BrowserListingJob.channel_listing_id == row.id,
            BrowserListingJob.status == "succeeded",
        ).order_by(BrowserListingJob.id.desc()).limit(1))).scalars().first()
        pack = dict(previous.payload) if previous else seller_pack(build, row, image_urls, allow_sold=True)
    else:
        pack = seller_pack(build, row, image_urls)
    if operation == "withdraw" and (not row.external_listing_id or not row.listing_url):
        raise ValueError("A confirmed vendor listing ID and URL are required for withdrawal")
    job = BrowserListingJob(channel_listing_id=row.id, operation=operation, status="queued", payload=pack)
    db.add(job)
    row.last_recreate_status = "queued"
    row.last_recreate_message = f"Queued for Codex to {operation} through Chrome."
    # Retain the due clock until verified completion. The pending-job index
    # prevents repeated scheduler ticks from producing duplicate work.
    db.add(ListingPublishEvent(channel_listing_id=row.id, event_type="browser_job_queued",
        message=row.last_recreate_message, event_metadata={"build_id": build_id, "channel": channel, "operation": operation}))
    await db.flush()
    return job


async def complete_browser_job(db, job, *, status, message, listing_url=None, external_id=None, evidence=None):
    row = await db.get(ChannelListing, job.channel_listing_id)
    build = await db.get(ManualBuild, row.manual_build_id)
    if status == "succeeded":
        if not external_id or not evidence or not evidence.get("verified_at") or not evidence.get("title"):
            raise ValueError("Confirmed vendor ID, URL and browser read-back evidence are required")
        validate_listing_url(row.channel, listing_url or "")
        if external_id not in (listing_url or ""):
            raise ValueError("Vendor identity must match the confirmed item URL")
        if evidence.get("url") != listing_url or evidence.get("title") != job.payload["listing"]["title"] or evidence.get("price") != job.payload["listing"]["price"]:
            raise ValueError("Browser evidence must match the canonical title, price and confirmed URL")
        if job.operation == "withdraw":
            if row.external_listing_id != job.payload.get("previous_listing_id") or row.listing_url != job.payload.get("previous_listing_url"):
                raise ValueError("Saved vendor listing identity changed; reconcile before withdrawal")
        elif seller_pack(build, row, job.payload["listing"]["images"]) != job.payload:
            raise ValueError("Saved listing changed; reconcile before confirming this job")
        now = datetime.utcnow()
        if job.operation == "reconcile":
            remote_state = (evidence or {}).get("remote_state")
            if remote_state not in {"active", "ended", "missing", "sold"}:
                raise ValueError("Seller-side reconciliation must confirm active, ended, missing or sold status")
            if remote_state == "sold":
                if not evidence.get("order_id") or not evidence.get("note") or external_id != row.external_listing_id:
                    raise ValueError("Confirm a seller order ID and note for the exact saved vendor item before marking it sold")
                row.status, row.withdrawn_at = "sold", now
                row.recreate_enabled = False
                row.next_recreate_at = None
                build.status = "sold"
                build.updated_at = now
                row.last_recreate_status = "success"
                row.last_recreate_message = "Vendor sale confirmed from the seller account. Other listings are being withdrawn."
                from app.services.cross_channel_guard import (
                    withdraw_google_for_sold_build,
                    withdraw_storefront_for_sold_build,
                    withdraw_ebay_for_sold_build,
                )
                from app.config import get_settings
                await withdraw_google_for_sold_build(build, db)
                await withdraw_storefront_for_sold_build(build, db)
                await withdraw_ebay_for_sold_build(build, get_settings().ebay_listing_environment)
            elif remote_state in {"ended", "missing"}:
                row.status = "ended"
                row.last_recreate_status = "success"
                row.last_recreate_message = "Vendor listing ended; scheduled relisting will create a new vendor listing ID."
                row.next_recreate_at = now if row.recreate_enabled else None
            else:
                row.status = "published"
                row.last_recreate_status = "success"
                row.last_recreate_message = "Vendor listing verified active."
        elif job.operation == "withdraw":
            if row.status not in {"published", "submitted", "withdrawal_pending"}:
                raise ValueError("Only a currently published vendor listing can be withdrawn")
            row.status, row.withdrawn_at = "withdrawn", now
            row.recreate_enabled = False
            row.next_recreate_at = None
            row.last_recreate_status = "success"
            row.last_recreate_message = "Vendor withdrawal confirmed by Chrome read-back."
        else:
            if build.status == "sold" or build.is_archived:
                raise ValueError("Build is no longer sellable; reconcile the vendor listing before completion")
            row.external_listing_id, row.listing_url = external_id, listing_url
            row.status, row.published_at, row.withdrawn_at = "published", now, None
            row.last_recreate_at = now
            row.last_recreate_status = "success"
            if job.operation == "relist":
                row.recreate_count = (row.recreate_count or 0) + 1
            row.next_recreate_at = now + timedelta(days=row.recreate_interval_days or 7) if row.recreate_enabled else None
    else:
        # Keep the last confirmed identity and due timestamp on failures.
        row.last_recreate_status = status
    row.last_recreate_message = message[:500]
    job.status, job.message = status, message[:500]
    job.lease_token, job.lease_until = None, None
    db.add(ListingPublishEvent(channel_listing_id=row.id, event_type="browser_job_" + status,
        message=message[:500], event_metadata={"job_id": job.id, "build_id": row.manual_build_id,
            "channel": row.channel, "listing_url": listing_url, "external_id": external_id, "evidence": evidence}))
