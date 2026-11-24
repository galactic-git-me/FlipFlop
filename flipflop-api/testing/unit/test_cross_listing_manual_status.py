from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest


@pytest.mark.asyncio
async def test_marking_relisted_ebay_item_live_clears_old_end_reason():
    from app.api.cross_listing import ManualChannelStatusIn, set_channel_status

    old_url = "https://www.ebay.co.uk/itm/198786792744"
    new_url = "https://www.ebay.co.uk/itm/198815946965"
    build = SimpleNamespace(
        id=2,
        status="built",
        dispatch_status="awaiting_dispatch",
        ebay_listing_status="ended",
        ebay_listing_status_checked_at=None,
        ebay_listing_url=old_url,
        ebay_listing_id="198786792744",
        ebay_listing_end_reason="order_cancelled",
        sale_price_actual=1400.0,
    )
    listing = SimpleNamespace(
        id=2,
        status="ended",
        listing_url=old_url,
        external_listing_id="198786792744",
        published_at=None,
        withdrawn_at=None,
        last_checked_at=None,
    )
    build_result = SimpleNamespace(scalar_one_or_none=lambda: build)
    listing_result = SimpleNamespace(scalars=lambda: SimpleNamespace(first=lambda: listing))
    db = AsyncMock()
    db.execute.side_effect = [build_result, listing_result]
    db.add = Mock()

    result = await set_channel_status(
        2,
        "ebay_uk",
        ManualChannelStatusIn(
            status="live",
            reason="Verified active replacement listing",
            listing_url=new_url,
            external_id="198815946965",
        ),
        db,
    )

    assert result["status"] == "live"
    assert build.status == "listed"
    assert build.ebay_listing_status == "active"
    assert build.ebay_listing_end_reason is None
    assert build.ebay_listing_id == "198815946965"
    assert listing.status == "published"
    assert listing.external_listing_id == "198815946965"
    db.add.assert_called_once()
    db.commit.assert_awaited_once()
