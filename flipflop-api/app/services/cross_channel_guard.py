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

from datetime import datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.manual_build import ManualBuild
from app.models.product import Product, ProductStatus, SoldChannel, WithdrawalReason
from app.services.ebay_listing_withdraw import withdraw_listing_by_sku, EbayListingWithdrawError

log = structlog.get_logger(__name__)


async def withdraw_ebay_for_sold_build(build: ManualBuild, environment: str) -> None:
    """Call once a build's storefront Product sale is confirmed — ends the
    matching live eBay listing, if any, so it can't also sell there."""
    if not build.ebay_sku or build.status == "sold":
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
