"""Prevents the same physical build from selling twice across eBay and the
FlipFlop.shop storefront — each ManualBuild represents one real, physical
unit, so a sale on either channel must immediately pull the listing from
the other.

Called from two places:
  - app/api/manual_builds.py's sync_ebay_order, once an eBay sale is confirmed
  - app/api/public_showcase.py's checkout-confirm, once a storefront sale is confirmed

Withdrawal failures are logged loudly but never raised past the caller —
the payment has already succeeded by the time either function runs, so a
failed cross-channel withdrawal must not block the sale that already
happened. It leaves a stale listing live instead, which is a real problem
but a much smaller one than losing a confirmed sale.
"""
from __future__ import annotations

import asyncio
from datetime import datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.manual_build import ManualBuild
from app.models.channel_listing import ChannelListing
from app.models.listing_publish_event import ListingPublishEvent
from app.models.product import Product, ProductStatus, SoldChannel, WithdrawalReason
from app.services.ebay_listing_withdraw import withdraw_listing_by_sku, EbayListingWithdrawError
from app.services.google_merchant_api import GoogleMerchantAPI, GoogleMerchantError

log = structlog.get_logger(__name__)


async def withdraw_ebay_for_sold_build(build: ManualBuild, environment: str) -> None:
    """Call once a build's storefront Product sale is confirmed — ends the
    matching live eBay listing, if any, so it can't also sell there."""
    if not build.ebay_sku:
        return
    try:
        await withdraw_listing_by_sku(build.ebay_sku, environment=environment)
        log.info("cross_channel_guard.ebay_withdrawn", build_id=build.id, sku=build.ebay_sku)
    except EbayListingWithdrawError as e:
        log.error(
            "cross_channel_guard.ebay_withdraw_failed",
            build_id=build.id, sku=build.ebay_sku, error=str(e),
        )


async def withdraw_storefront_for_sold_build(build: ManualBuild, db: AsyncSession) -> None:
    """Call once a build's eBay sale is confirmed (see sync_ebay_order) —
    withdraws the matching storefront Product listing, if any, so it can't
    also sell there."""
    if not build.storefront_product_id:
        return

    # FOR UPDATE closes the race with public_showcase.py's confirm_checkout,
    # which locks this same Product row before finalising a storefront sale —
    # whichever transaction gets here first wins, and the loser sees the
    # already-SOLD status once it acquires the lock.
    result = await db.execute(
        select(Product).where(Product.id == build.storefront_product_id).with_for_update()
    )
    product = result.scalar_one_or_none()
    if not product or product.status not in (ProductStatus.LISTED, ProductStatus.RESERVED):
        return

    product.status = ProductStatus.WITHDRAWN
    product.withdrawn_at = datetime.utcnow()
    product.withdrawal_reason = WithdrawalReason.SOLD_OTHER_CHANNEL
    product.sold_via_channel = SoldChannel.EBAY
    product.updated_at = datetime.utcnow()
    await db.flush()
    log.info("cross_channel_guard.storefront_withdrawn", build_id=build.id, product_id=product.id)


async def withdraw_google_for_sold_build(build: ManualBuild, db: AsyncSession) -> None:
    """Immediately remove the Merchant Center input and preserve retry state.

    The caller is already handling a confirmed sale, so provider failures must
    not unwind it. A pending row is reconciled by the periodic Merchant sync.
    """
    rows = (await db.execute(
        select(ChannelListing).where(
            ChannelListing.manual_build_id == build.id,
            ChannelListing.channel == "google_shopping",
            ChannelListing.external_listing_id.is_not(None),
        )
    )).scalars().all()
    if rows:
      client = GoogleMerchantAPI()
      for row in rows:
        now = datetime.utcnow()
        row.status = "withdrawal_pending"
        row.withdrawn_at = now
        try:
            await asyncio.wait_for(client.delete_build(build), timeout=6)
            row.status = "withdrawn"
            row.last_recreate_status = "success"
            row.last_recreate_message = "Google Merchant product input deleted after the build sold."
            event_type = "google_product_withdrawn"
            log.info("cross_channel_guard.google_merchant_withdrawn", build_id=build.id)
        except (GoogleMerchantError, asyncio.TimeoutError) as exc:
            row.last_recreate_status = "failed"
            row.last_recreate_message = f"Google Merchant withdrawal pending retry: {str(exc)[:420]}"
            event_type = "google_product_withdrawal_failed"
            log.error("cross_channel_guard.google_merchant_withdraw_failed", build_id=build.id, error=str(exc))
        db.add(ListingPublishEvent(
            channel_listing_id=row.id,
            event_type=event_type,
            message=row.last_recreate_message,
            event_metadata={"build_id": build.id, "channel": "google_shopping", "at": now.isoformat()},
        ))
    await queue_browser_withdrawals(build, db)
    await db.flush()


async def queue_browser_withdrawals(build: ManualBuild, db: AsyncSession) -> None:
    """Queue sold-build withdrawals for active Chrome-managed vendor listings."""
    from app.services.browser_listing_jobs import BROWSER_CHANNELS, enqueue_browser_job
    from app.services.channel_images import prepare_channel_urls

    rows = (await db.execute(select(ChannelListing).where(
        ChannelListing.manual_build_id == build.id,
        ChannelListing.channel.in_(BROWSER_CHANNELS),
        ChannelListing.status.in_(("published", "submitted", "withdrawal_pending")),
        ChannelListing.external_listing_id.is_not(None),
        ChannelListing.listing_url.is_not(None),
    ))).scalars().all()
    for row in rows:
        try:
            originals = [p["url"] for p in build.photos or [] if isinstance(p, dict) and p.get("url") and p.get("kind", "photo") == "photo"]
            images = await prepare_channel_urls(originals, row.channel)
            await enqueue_browser_job(db, build.id, row.channel, operation="withdraw", image_urls=images)
            row.status = "withdrawal_pending"
            row.recreate_enabled = False
            row.next_recreate_at = None
            row.last_recreate_message = "Sale confirmed. Waiting for Codex to end this vendor listing in Chrome."
            log.info("cross_channel_guard.browser_withdrawal_queued", build_id=build.id, channel=row.channel)
        except Exception as exc:
            log.error("cross_channel_guard.browser_withdrawal_queue_failed", build_id=build.id, channel=row.channel, error=str(exc))
