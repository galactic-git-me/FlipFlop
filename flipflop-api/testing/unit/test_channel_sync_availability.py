from types import SimpleNamespace

import pytest

from app.services.channel_sync import (
    build_is_unavailable,
    confirm_browser_observation,
    record_relisted_channel,
)


@pytest.mark.asyncio
async def test_confirmed_sale_is_unavailable_while_ebay_withdrawal_is_pending():
    build = SimpleNamespace(status="sold", ebay_listing_status="active", is_archived=False,
                            storefront_product_id=None)

    assert await build_is_unavailable(None, build) is True


@pytest.mark.asyncio
async def test_confirmed_relist_restores_build_availability():
    build = SimpleNamespace(status="listed", ebay_listing_status="active", is_archived=False,
                            storefront_product_id=None)

    assert await build_is_unavailable(None, build) is False


@pytest.mark.asyncio
async def test_active_browser_listing_for_sold_build_queues_withdrawal_even_if_ebay_status_active(monkeypatch):
    from unittest.mock import AsyncMock, Mock

    row = SimpleNamespace(
        id=44,
        manual_build_id=9,
        channel="facebook_catalog",
        external_listing_id="fb-listing-1",
        listing_url="https://www.facebook.com/marketplace/item/1",
        status="published",
        recreate_enabled=True,
        next_recreate_at=None,
    )
    build = SimpleNamespace(
        id=9,
        status="sold",
        ebay_listing_status="active",
        is_archived=False,
        ebay_price=100,
        storefront_product_id=None,
    )
    job = SimpleNamespace(
        id=55,
        channel_listing_id=row.id,
        operation="observe",
        status="running",
        message=None,
        lease_token="lease",
        lease_until=None,
    )
    db = SimpleNamespace(
        get=AsyncMock(return_value=row),
        execute=AsyncMock(return_value=SimpleNamespace(scalar_one=lambda: build)),
        flush=AsyncMock(),
        add=Mock(),
    )
    withdraw = AsyncMock()
    update = AsyncMock()
    monkeypatch.setattr("app.services.channel_sync.withdraw_other_channels", withdraw)
    monkeypatch.setattr("app.services.channel_sync.enqueue_operation", update)

    await confirm_browser_observation(
        db,
        job,
        state="active",
        evidence={"verified_at": "now", "url": row.listing_url, "note": "seller page checked", "price": 120},
    )

    withdraw.assert_awaited_once_with(db, build)
    update.assert_not_awaited()


@pytest.mark.asyncio
async def test_original_active_ebay_listing_cannot_be_recorded_as_a_relist():
    build = SimpleNamespace(ebay_listing_id="original-listing")

    with pytest.raises(ValueError, match="original listing"):
        await record_relisted_channel(
            None,
            build,
            channel="ebay_uk",
            external_listing_id="original-listing",
            listing_url="https://www.ebay.co.uk/itm/original-listing",
            source="admin_reconciliation",
        )


@pytest.mark.asyncio
async def test_running_withdrawal_rejects_relist_before_creating_replacement_row():
    old_row = SimpleNamespace(id=10)
    running_withdrawal = SimpleNamespace(status="running")

    class FakeDb:
        def __init__(self):
            self.results = [
                SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [old_row])),
                SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [running_withdrawal])),
            ]
            self.added = []
            self.flush_count = 0

        async def execute(self, _statement):
            return self.results.pop(0)

        def add(self, value):
            self.added.append(value)

        async def flush(self):
            self.flush_count += 1

    db = FakeDb()
    build = SimpleNamespace(id=1, ebay_listing_id="original-listing")

    with pytest.raises(ValueError, match="withdrawal is already running"):
        await record_relisted_channel(
            db,
            build,
            channel="ebay_uk",
            external_listing_id="replacement-listing",
            listing_url="https://www.ebay.co.uk/itm/replacement-listing",
            source="admin_reconciliation",
        )

    assert len(db.results) == 0
    assert db.added == []
    assert db.flush_count == 0
