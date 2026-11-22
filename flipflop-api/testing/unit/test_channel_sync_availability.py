from types import SimpleNamespace

import pytest

from app.services.channel_sync import build_is_unavailable, record_relisted_channel


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
