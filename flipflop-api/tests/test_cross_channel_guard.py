"""Deterministic coverage for sold-build withdrawal handoffs."""

import pytest
from sqlalchemy import select
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.models.channel_listing import ChannelListing
from app.models.listing_publish_event import ListingPublishEvent
from app.models.manual_build import ManualBuild
from app.models.product import Product, ProductStatus, ProductType, WithdrawalReason
from app.api.cross_listing import ManualHandoffResultIn, record_manual_handoff_result
from app.services.amazon_sp_api import AmazonSPAPIError
from app.services.google_merchant_api import GoogleMerchantError
from app.services import cross_channel_guard


@pytest.mark.asyncio
async def test_sale_queues_one_codex_unlist_handoff_per_live_manual_channel(db):
    build = ManualBuild(name="Synthetic sold build", status="sold")
    db.add(build)
    await db.flush()

    for channel in ("onbuy", "facebook_catalog", "vinted"):
        db.add(ChannelListing(
            manual_build_id=build.id,
            channel=channel,
            status="published",
            external_listing_id=f"synthetic-{channel}",
        ))
    await db.flush()

    await cross_channel_guard.queue_manual_vendor_unlist_handoffs(build, db)
    await db.flush()

    events = (await db.execute(select(ListingPublishEvent))).scalars().all()
    assert len(events) == 3
    assert {event.event_metadata["channel"] for event in events} == {
        "onbuy", "facebook_catalog", "vinted",
    }
    assert all(event.event_type == "manual_unlist_handoff_required" for event in events)
    assert all(event.event_metadata["operation"] == "unlist" for event in events)
    assert all(event.event_metadata["reason"] == "sold_other_channel" for event in events)

    # Reprocessing the same sale while the Codex tasks are pending is safe.
    await cross_channel_guard.queue_manual_vendor_unlist_handoffs(build, db)
    await db.flush()
    events = (await db.execute(select(ListingPublishEvent))).scalars().all()
    assert len(events) == 3

    for event in events:
        result = await record_manual_handoff_result(
            event.id,
            ManualHandoffResultIn(
                success=True,
                message="Synthetic Codex task ended the seller listing.",
            ),
            db,
        )
        assert result["status"] == "withdrawn"

    listings = (await db.execute(select(ChannelListing))).scalars().all()
    assert len(listings) == 3
    assert all(row.status == "withdrawn" for row in listings)


@pytest.mark.asyncio
async def test_sold_build_withdraws_amazon_and_google_and_clears_relist_timers(db):
    build = ManualBuild(name="Synthetic sold build", status="sold")
    db.add(build)
    await db.flush()
    listings = [
        ChannelListing(
            manual_build_id=build.id,
            channel=channel,
            status="published",
            external_listing_id=f"synthetic-{channel}",
            recreate_enabled=True,
            recreate_interval_days=7,
        )
        for channel in ("amazon", "google_shopping")
    ]
    db.add_all(listings)
    await db.flush()

    amazon = SimpleNamespace(configured=True, delete_listing=AsyncMock())
    google = SimpleNamespace(configured=True, delete_product=AsyncMock())
    with patch.object(cross_channel_guard, "AmazonSPAPI", return_value=amazon), patch.object(
        cross_channel_guard, "GoogleMerchantAPI", return_value=google
    ):
        await cross_channel_guard.withdraw_amazon_for_sold_build(build, db)
        await cross_channel_guard.withdraw_google_for_sold_build(build, db)

    assert amazon.delete_listing.await_count == 1
    assert google.delete_product.await_count == 1
    assert all(row.status == "withdrawn" for row in listings)
    assert all(row.next_recreate_at is None for row in listings)
    events = (await db.execute(select(ListingPublishEvent))).scalars().all()
    assert {event.event_metadata["reason"] for event in events} == {"sold_other_channel"}


@pytest.mark.asyncio
async def test_failed_api_withdrawals_remain_visible_as_live_and_record_errors(db):
    build = ManualBuild(name="Synthetic sold build", status="sold")
    db.add(build)
    await db.flush()
    listings = [
        ChannelListing(manual_build_id=build.id, channel="amazon", status="published"),
        ChannelListing(manual_build_id=build.id, channel="google_shopping", status="published"),
    ]
    db.add_all(listings)
    await db.flush()

    amazon = SimpleNamespace(
        configured=True,
        delete_listing=AsyncMock(side_effect=AmazonSPAPIError("provider unavailable", status_code=503)),
    )
    google = SimpleNamespace(
        configured=True,
        delete_product=AsyncMock(side_effect=GoogleMerchantError("provider unavailable", status_code=503)),
    )
    with patch.object(cross_channel_guard, "AmazonSPAPI", return_value=amazon), patch.object(
        cross_channel_guard, "GoogleMerchantAPI", return_value=google
    ):
        await cross_channel_guard.withdraw_amazon_for_sold_build(build, db)
        await cross_channel_guard.withdraw_google_for_sold_build(build, db)

    assert all(row.status == "published" for row in listings)
    events = (await db.execute(select(ListingPublishEvent))).scalars().all()
    assert {event.event_type for event in events} == {"withdraw_failed"}
    assert {event.event_metadata["status_code"] for event in events} == {503}


@pytest.mark.asyncio
async def test_sold_ebay_build_withdraws_live_storefront_product(db):
    product = Product(
        product_type=ProductType.PREBUILT,
        title="Synthetic storefront listing",
        status=ProductStatus.LISTED,
    )
    db.add(product)
    await db.flush()
    build = ManualBuild(
        name="Synthetic sold build",
        status="sold",
        storefront_product_id=product.id,
    )
    db.add(build)
    await db.flush()

    await cross_channel_guard.withdraw_storefront_for_sold_build(build, db)

    assert product.status == ProductStatus.WITHDRAWN
    assert product.withdrawal_reason == WithdrawalReason.SOLD_OTHER_CHANNEL


@pytest.mark.asyncio
async def test_storefront_sale_ends_the_live_ebay_listing_before_marking_build_sold(db):
    build = ManualBuild(
        name="Synthetic listed build",
        status="listed",
        ebay_sku="synthetic-ebay-sku",
    )

    with patch.object(
        cross_channel_guard,
        "withdraw_listing_by_sku",
        new=AsyncMock(),
    ) as withdraw:
        await cross_channel_guard.withdraw_ebay_for_sold_build(build, "sandbox")

    withdraw.assert_awaited_once_with("synthetic-ebay-sku", environment="sandbox")
