from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.services.ebay_listing_reconciliation import classify_ebay_listing_state


def test_active_listing_stays_active():
    assert classify_ebay_listing_state({"listing_status": "Active", "quantity_sold": 0}, order_found=False) == "active"


def test_completed_listing_with_sale_is_sold():
    assert classify_ebay_listing_state({"listing_status": "Completed", "quantity_sold": 1}, order_found=False) == "sold"


def test_completed_listing_without_sale_is_ended_early():
    assert classify_ebay_listing_state({"listing_status": "Completed", "quantity_sold": 0}, order_found=False) == "ended"


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
