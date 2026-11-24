from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import asyncio

import pytest

from app.services.ebay_listing_reconciliation import classify_ebay_listing_state


def test_active_listing_stays_active():
    assert classify_ebay_listing_state({"listing_status": "Active", "quantity_sold": 0}, order_found=False) == "active"


def test_completed_listing_with_sale_is_sold():
    assert classify_ebay_listing_state({"listing_status": "Completed", "quantity_sold": 1}, order_found=False) == "sold"


def test_completed_listing_without_sale_is_ended_early():
    assert classify_ebay_listing_state({"listing_status": "Completed", "quantity_sold": 0}, order_found=False) == "ended"


def test_confirmed_cancellation_overrides_ebay_historical_quantity_sold():
    assert classify_ebay_listing_state(
        {"listing_status": "Completed", "quantity_sold": 1},
        order_found=False,
        cancelled_order=True,
    ) == "ended"


def test_confirmed_order_overrides_stale_active_listing_snapshot():
    assert classify_ebay_listing_state(
        {"listing_status": "Active", "quantity_sold": 0},
        order_found=True,
    ) == "sold"


def test_order_proves_sale_even_if_item_has_disappeared():
    assert classify_ebay_listing_state(None, order_found=True) == "sold"


def test_api_failure_is_unknown_not_permission_to_relist():
    assert classify_ebay_listing_state(None, order_found=False) == "unknown"


def test_inaccessible_old_listing_without_sale_is_missing():
    assert classify_ebay_listing_state(
        None, order_found=False, confirmed_unavailable=True
    ) == "missing"


def test_sale_takes_precedence_over_inaccessible_old_listing():
    assert classify_ebay_listing_state(
        None, order_found=True, confirmed_unavailable=True
    ) == "sold"


def test_active_relisted_offer_is_discovered_for_previously_sold_build(monkeypatch):
    from app.services.ebay_listing_reconciliation import reconcile_manual_build_listing

    build = SimpleNamespace(
        id=2, status="sold", ebay_listing_id="198786792744", ebay_listing_status="sold",
        ebay_listing_status_checked_at=None, ebay_listing_end_reason="sold",
        ebay_sku="FF-BUILD-2", ebay_order_id="05-15450-52548", dispatch_status="awaiting_dispatch",
    )
    db = AsyncMock()
    db.execute = AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: None))
    db.execute.return_value = SimpleNamespace(scalar_one_or_none=lambda: None)
    relisted = AsyncMock()
    monkeypatch.setattr("app.config.get_settings", lambda: SimpleNamespace(ebay_listing_environment="production"))
    monkeypatch.setattr("app.services.ebay_token_manager.get_valid_ebay_access_token", AsyncMock(return_value="token"))
    monkeypatch.setattr("app.services.ebay_relisted_listing.find_active_listing_for_sku", AsyncMock(return_value={
        "listing_id": "199000000001", "listing_url": "https://www.ebay.co.uk/itm/199000000001",
    }))
    monkeypatch.setattr("app.services.channel_sync.record_relisted_channel", relisted)

    state = asyncio.run(reconcile_manual_build_listing(build, db, force=True))

    assert state == "active"
    relisted.assert_awaited_once_with(db, build, channel="ebay_uk", external_listing_id="199000000001",
        listing_url="https://www.ebay.co.uk/itm/199000000001", source="ebay_inventory_api")


@pytest.mark.asyncio
async def test_active_original_listing_stays_sold_and_is_reported_for_withdrawal(monkeypatch):
    from app.services.ebay_listing_reconciliation import reconcile_manual_build_listing

    listing_id = "198786792744"
    build = SimpleNamespace(
        id=2, status="sold", ebay_listing_id=listing_id, ebay_listing_status="sold",
        ebay_listing_status_checked_at=None, ebay_listing_end_reason="sold",
        ebay_sku="FF-BUILD-2", ebay_order_id="05-15450-52548", dispatch_status="awaiting_dispatch",
    )
    db = AsyncMock()
    relisted = AsyncMock()
    db.execute = AsyncMock(return_value=SimpleNamespace(all=lambda: []))
    monkeypatch.setattr("app.config.get_settings", lambda: SimpleNamespace(ebay_listing_environment="production"))
    monkeypatch.setattr("app.services.ebay_token_manager.get_valid_ebay_access_token", AsyncMock(return_value="token"))
    monkeypatch.setattr("app.services.ebay_order_sync.get_order_refund_state", AsyncMock(return_value={
        "cancel_state": "NONE", "refunds": [], "refund_signature": "",
    }))
    monkeypatch.setattr("app.services.ebay_relisted_listing.find_active_listing_for_sku", AsyncMock(return_value={
        "listing_id": listing_id, "listing_url": f"https://www.ebay.co.uk/itm/{listing_id}",
    }))
    monkeypatch.setattr("app.services.channel_sync.record_relisted_channel", relisted)
    monkeypatch.setattr("app.services.ebay_trading_api.get_item_status", AsyncMock(return_value={
        "listing_status": "Active", "quantity_sold": 0,
    }))

    state = await reconcile_manual_build_listing(build, db, force=True)

    assert state == "active"
    assert build.status == "sold"
    relisted.assert_not_awaited()
    db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_cancelled_order_remains_cancelled_after_build_reopens(monkeypatch):
    from app.services.ebay_listing_reconciliation import reconcile_manual_build_listing

    order_id = "05-15450-52548"
    channel_row = SimpleNamespace(id=82, status="sold")
    query_result = SimpleNamespace(
        scalar_one_or_none=lambda: None,
        scalars=lambda: SimpleNamespace(first=lambda: channel_row, all=lambda: [channel_row]),
    )
    db = AsyncMock()
    db.add = MagicMock()
    db.execute.return_value = query_result
    build = SimpleNamespace(
        id=27,
        status="built",
        ebay_listing_id="198786792744",
        ebay_listing_status="ended",
        ebay_listing_status_checked_at=None,
        ebay_listing_end_reason="order_cancelled",
        ebay_order_id=order_id,
        ebay_sku="FF-BUILD-27",
        dispatch_status="not_started",
    )
    cancelled_order = SimpleNamespace(order_id=order_id)
    cancellation = AsyncMock(return_value={"cancel_state": "CANCELED"})
    cancellation_inventory = AsyncMock()
    order_lookup = AsyncMock(return_value=cancelled_order)

    monkeypatch.setattr("app.config.get_settings", lambda: SimpleNamespace(ebay_listing_environment="production"))
    monkeypatch.setattr("app.services.ebay_token_manager.get_valid_ebay_access_token", AsyncMock(return_value="token"))
    monkeypatch.setattr("app.services.ebay_trading_api.get_item_status", AsyncMock(return_value={
        "listing_status": "Completed", "quantity_sold": 1,
    }))
    monkeypatch.setattr("app.services.ebay_order_sync.get_order_refund_state", cancellation)
    monkeypatch.setattr("app.services.ebay_order_sync.find_order_for_listing", order_lookup)
    monkeypatch.setattr("app.services.inventory_lifecycle.record_sale_cancellation", cancellation_inventory)

    state = await reconcile_manual_build_listing(build, db, force=True)

    assert state == "ended"
    assert build.status == "built"
    assert build.ebay_listing_end_reason == "order_cancelled"
    cancellation.assert_awaited_once_with(order_id, environment="production", db=db)
    order_lookup.assert_awaited_once()
    cancellation_inventory.assert_awaited_once_with(db, build, source="ebay_order_api")


@pytest.mark.asyncio
async def test_cross_channel_sale_does_not_use_ebay_active_offer_as_relist(monkeypatch):
    from app.services.ebay_listing_reconciliation import reconcile_manual_build_listing

    build = SimpleNamespace(
        id=3, status="sold", ebay_listing_id="198786792745", ebay_listing_status="active",
        ebay_listing_status_checked_at=None, ebay_listing_end_reason=None,
        ebay_sku="FF-BUILD-3", ebay_order_id=None, dispatch_status="awaiting_dispatch",
    )
    db = AsyncMock()
    discover = AsyncMock(return_value={
        "listing_id": "198786792745", "listing_url": "https://www.ebay.co.uk/itm/198786792745",
    })
    monkeypatch.setattr("app.config.get_settings", lambda: SimpleNamespace(ebay_listing_environment="production"))
    monkeypatch.setattr("app.services.ebay_token_manager.get_valid_ebay_access_token", AsyncMock(return_value="token"))
    monkeypatch.setattr("app.services.ebay_relisted_listing.find_active_listing_for_sku", discover)
    monkeypatch.setattr("app.services.ebay_trading_api.get_item_status", AsyncMock(return_value={
        "listing_status": "Active", "quantity_sold": 0,
    }))

    state = await reconcile_manual_build_listing(build, db, force=True)

    assert state == "active"
    assert build.status == "sold"
    discover.assert_not_awaited()


@pytest.mark.asyncio
async def test_error_17_without_matching_order_authorizes_fresh_listing():
    from app.services.ebay_listing_reconciliation import reconcile_manual_build_listing
    from app.services.ebay_order_sync import EbayOrderSyncError
    from app.services.ebay_trading_api import EbayTradingApiError

    build = SimpleNamespace(
        id=2,
        status="listed",
        ebay_listing_id="188817313509",
        ebay_listing_status=None,
        ebay_listing_status_checked_at=None,
        ebay_listing_end_reason=None,
        ebay_order_id=None,
    )
    db = AsyncMock()
    get_item_error = EbayTradingApiError("GetItem", [], "Failure")
    get_item_error.error_codes = {"17"}

    with patch("app.config.get_settings", return_value=SimpleNamespace(ebay_listing_environment="production")), \
         patch("app.services.ebay_token_manager.get_valid_ebay_access_token", new=AsyncMock(return_value="token")), \
         patch("app.services.ebay_trading_api.get_item_status", new=AsyncMock(side_effect=get_item_error)), \
         patch("app.services.ebay_order_sync.find_order_for_listing", new=AsyncMock(return_value=None)):
        state = await reconcile_manual_build_listing(build, db, force=True)

    assert state == "missing"
    assert build.status == "built"
    assert build.ebay_listing_end_reason == "missing_from_ebay"
    db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_error_17_stays_unknown_if_order_lookup_fails():
    from app.services.ebay_listing_reconciliation import reconcile_manual_build_listing
    from app.services.ebay_order_sync import EbayOrderSyncError
    from app.services.ebay_trading_api import EbayTradingApiError

    build = SimpleNamespace(
        id=2,
        status="listed",
        ebay_listing_id="188817313509",
        ebay_listing_status=None,
        ebay_listing_status_checked_at=None,
        ebay_listing_end_reason=None,
        ebay_order_id=None,
    )
    db = AsyncMock()
    get_item_error = EbayTradingApiError("GetItem", [], "Failure")
    get_item_error.error_codes = {"17"}

    with patch("app.config.get_settings", return_value=SimpleNamespace(ebay_listing_environment="production")), \
         patch("app.services.ebay_token_manager.get_valid_ebay_access_token", new=AsyncMock(return_value="token")), \
         patch("app.services.ebay_trading_api.get_item_status", new=AsyncMock(side_effect=get_item_error)), \
         patch("app.services.ebay_order_sync.find_order_for_listing", new=AsyncMock(side_effect=EbayOrderSyncError("offline"))):
        state = await reconcile_manual_build_listing(build, db, force=True)

    assert state == "unknown"


@pytest.mark.asyncio
@pytest.mark.parametrize(("existing_order_id", "initial_dispatch_status", "expected_dispatch_status"), [
    (None, "not_started", "awaiting_dispatch"),
    ("05-15450-52548", "dispatched", "dispatched"),
])
async def test_paid_order_records_sale_provenance_and_queues_dispatch(
    monkeypatch, existing_order_id, initial_dispatch_status, expected_dispatch_status,
):
    from app.services.ebay_listing_reconciliation import reconcile_manual_build_listing

    build = SimpleNamespace(
        id=12,
        status="listed",
        ebay_listing_id="198786792744",
        ebay_listing_url="https://www.ebay.co.uk/itm/198786792744",
        ebay_listing_status="active",
        ebay_listing_status_checked_at=None,
        ebay_listing_end_reason=None,
        ebay_order_id=existing_order_id,
        sale_price_actual=None,
        dispatch_status=initial_dispatch_status,
        ebay_sku="FF-BUILD-12",
        warranty_started_at=None,
        delivered_at=None,
        storefront_product_id=None,
        status_marker=None,
    )
    db = AsyncMock()
    result = SimpleNamespace(scalar_one_or_none=lambda: SimpleNamespace(ebay_seller_username="flip_7417"))
    db.execute = AsyncMock(return_value=result)
    order = SimpleNamespace(order_id="05-15450-52548", sale_price=1400.0)
    sale_event = AsyncMock()

    monkeypatch.setattr("app.config.get_settings", lambda: SimpleNamespace(ebay_listing_environment="production"))
    monkeypatch.setattr("app.services.ebay_token_manager.get_valid_ebay_access_token", AsyncMock(return_value="token"))
    monkeypatch.setattr("app.services.ebay_order_sync.get_order_refund_state", AsyncMock(return_value={
        "cancel_state": "NONE", "refunds": [], "refund_signature": "",
    }))
    monkeypatch.setattr("app.services.ebay_trading_api.get_item_status", AsyncMock(return_value={"listing_status": "Completed", "quantity_sold": 1}))
    monkeypatch.setattr("app.services.ebay_order_sync.find_order_for_listing", AsyncMock(return_value=order))
    monkeypatch.setattr("app.services.channel_sync.record_confirmed_sale", sale_event)
    monkeypatch.setattr("app.services.getting_started_jobs.ensure_manual_build_job", AsyncMock())
    monkeypatch.setattr("app.services.inventory_lifecycle.record_sale", AsyncMock())
    monkeypatch.setattr("app.services.cross_channel_guard.withdraw_storefront_for_sold_build", AsyncMock())

    state = await reconcile_manual_build_listing(build, db, force=True)

    assert state == "sold"
    assert build.ebay_order_id == order.order_id
    assert build.sale_price_actual == 1400.0
    assert build.dispatch_status == expected_dispatch_status
    sale_event.assert_awaited_once_with(
        db,
        build,
        channel="ebay_uk",
        order_id=order.order_id,
        sale_price=1400.0,
        source="ebay_fulfillment_order_api",
        account="flip_7417",
    )
