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


def seller_pack(build: ManualBuild, row: ChannelListing, image_urls: list[str] | None = None, *, operation="publish") -> dict:
    read_only = operation in {"inspect", "sale_check", "withdraw"}
    if not read_only and (build.status == "sold" or build.is_archived):
        raise ValueError("Sold or archived builds cannot be listed")
    originals = [p["url"] for p in build.photos or [] if isinstance(p, dict) and p.get("url") and p.get("kind", "photo") == "photo"]
    if not read_only and (not build.generated_description or not build.generated_title or not build.ebay_price or build.ebay_price <= 0 or not originals):
        raise ValueError("Save the canonical title, description, listing price and product photographs first")
    from app.services.product_faqs import selected_faqs
    faqs = selected_faqs(build.id, build.selected_faq_ids, build.selected_faq_answer_overrides)
    title = (build.generated_title or build.name).strip()
    if build.name.strip().lower() not in title.lower():
        title = f"{build.name.strip()} | {title}"[:80]
    from app.services.channel_sync import canonical_hash
    return {"schema": "flipflop.seller-pack.v1", "build_id": build.id, "channel": row.channel, "canonical_hash": canonical_hash(build),
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
        return pending
    if image_urls is None and operation not in {"inspect", "sale_check", "withdraw"}:
        from app.services.channel_images import prepare_channel_urls
        image_urls = await prepare_channel_urls([p["url"] for p in build.photos or []
            if isinstance(p, dict) and p.get("url") and p.get("kind", "photo") == "photo"], channel)
    pack = seller_pack(build, row, image_urls, operation=operation)
    job = BrowserListingJob(channel_listing_id=row.id, operation=operation, status="queued", payload=pack)
    db.add(job)
    row.last_recreate_status = "queued"
    row.last_recreate_message = f"Queued for Codex Chrome: {operation}."
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
        if seller_pack(build, row, job.payload["listing"]["images"], operation=job.operation) != job.payload:
            raise ValueError("Saved listing changed; reconcile before confirming this job")
        if build.status == "sold" or build.is_archived:
            raise ValueError("Build is no longer sellable; reconcile the vendor listing before completion")
        now = datetime.utcnow()
        row.external_listing_id, row.listing_url = external_id, listing_url
        row.status, row.published_at, row.withdrawn_at = "published", now, None
        row.last_payload_hash, row.last_checked_at = job.payload.get("canonical_hash"), now
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
