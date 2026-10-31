"""Durable-by-reconciliation Google Merchant product and stock synchronizer."""
from __future__ import annotations

from datetime import datetime, timedelta

import structlog
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.channel_listing import ChannelListing
from app.models.listing_publish_event import ListingPublishEvent
from app.models.manual_build import ManualBuild
from app.models.product import Product, ProductStatus
from app.services.google_merchant_api import (
    GoogleMerchantAPI,
    GoogleMerchantError,
    product_input_for_build,
)

log = structlog.get_logger(__name__)


async def run_google_merchant_sync_job() -> dict[str, int | str]:
    """Reconcile Google product inputs against build and storefront reality.

    A hash check avoids routine writes. A 25-day refresh keeps Google's
    product data current before its 30-day expiration window. Sale withdrawals
    retry while pending; content/price/stock updates follow the latest build.
    """
    client = GoogleMerchantAPI()
    if not client.enabled_for_writes:
        return {"skipped": "Google Merchant writes are not configured or enabled."}

    updated = deleted = failed = 0
    now = datetime.utcnow()
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(ChannelListing).where(
                ChannelListing.channel == "google_shopping",
                ChannelListing.status.in_(["published", "sync_pending", "withdrawal_pending"]),
            ).order_by(ChannelListing.id)
        )).scalars().all()

        for row in rows:
            build = await db.get(ManualBuild, row.manual_build_id)
            if not build:
                row.status = "withdrawal_pending"
                try:
                    await client.delete_offer_id(f"FF-BUILD-{row.manual_build_id}")
                    row.status = "withdrawn"
                    row.withdrawn_at = row.withdrawn_at or now
                    row.last_recreate_status = "success"
                    row.last_recreate_message = "Google Merchant product input deleted; canonical build is unavailable."
                    deleted += 1
                except GoogleMerchantError as exc:
                    row.last_recreate_status = "failed"
                    row.last_recreate_message = str(exc)[:500]
                    failed += 1
                continue

            product = await db.get(Product, build.storefront_product_id) if build.storefront_product_id else None
            sold_or_withdrawn = (
                build.status == "sold"
                or not product
                or product.status in {ProductStatus.SOLD, ProductStatus.WITHDRAWN, ProductStatus.DRAFT}
            )
            if sold_or_withdrawn or row.status == "withdrawal_pending":
                try:
                    await client.delete_build(build)
                    row.status = "withdrawn"
                    row.withdrawn_at = row.withdrawn_at or now
                    row.last_recreate_status = "success"
                    row.last_recreate_message = "Google Merchant product input is deleted."
                    db.add(ListingPublishEvent(
                        channel_listing_id=row.id,
                        event_type="google_product_withdrawn",
                        message=row.last_recreate_message,
                        event_metadata={"build_id": build.id, "channel": row.channel, "at": now.isoformat(), "source": "reconciliation"},
                    ))
                    deleted += 1
                except GoogleMerchantError as exc:
                    row.status = "withdrawal_pending"
                    row.last_recreate_status = "failed"
                    row.last_recreate_message = str(exc)[:500]
                    failed += 1
                    log.error("google_merchant_sync.withdraw_failed", build_id=build.id, error=str(exc))
                continue

            availability = "OUT_OF_STOCK" if product.status == ProductStatus.RESERVED else "IN_STOCK"
            last_event = (await db.execute(
                select(ListingPublishEvent)
                .where(
                    ListingPublishEvent.channel_listing_id == row.id,
                    ListingPublishEvent.event_type.in_(["google_product_submitted", "google_product_updated"]),
                )
                .order_by(ListingPublishEvent.created_at.desc())
                .limit(1)
            )).scalars().first()
            last_meta = (last_event.event_metadata or {}) if last_event else {}
            try:
                payload, fingerprint = product_input_for_build(
                    build,
                    product.id,
                    client.settings,
                    last_meta.get("selected_images"),
                    availability,
                )
                fresh = bool(last_event and last_event.created_at and last_event.created_at >= now - timedelta(days=25))
                if row.status == "published" and last_meta.get("payload_hash") == fingerprint and fresh:
                    continue
                submission = await client.upsert_build(
                    build,
                    image_urls=last_meta.get("selected_images"),
                    availability=availability,
                )
                row.external_listing_id = submission.offer_id
                row.status = "published"
                row.published_at = row.published_at or now
                row.withdrawn_at = None
                row.last_recreate_status = "success"
                row.last_recreate_message = "Google Merchant product input is synchronized; eligibility is processed asynchronously."
                db.add(ListingPublishEvent(
                    channel_listing_id=row.id,
                    event_type="google_product_updated",
                    message=row.last_recreate_message,
                    event_metadata={
                        "offer_id": submission.offer_id,
                        "input_name": submission.input_name,
                        "listing_url": submission.product_url,
                        "payload_hash": submission.payload_hash,
                        "selected_images": payload["productAttributes"].get("imageLink") and [
                            payload["productAttributes"]["imageLink"],
                            *payload["productAttributes"].get("additionalImageLinks", []),
                        ],
                        "at": now.isoformat(),
                        "source": "reconciliation",
                    },
                ))
                updated += 1
            except GoogleMerchantError as exc:
                row.last_recreate_status = "failed"
                row.last_recreate_message = str(exc)[:500]
                row.status = "sync_pending" if exc.status_code is None or exc.status_code == 429 or (exc.status_code and exc.status_code >= 500) else "failed"
                failed += 1
                log.error("google_merchant_sync.upsert_failed", build_id=build.id, status=exc.status_code, error=str(exc))

        await db.commit()
    return {"updated": updated, "deleted": deleted, "failed": failed}
