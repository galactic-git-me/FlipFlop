from types import SimpleNamespace

from app.services.ebay_sales_tracker import is_orphaned_local_manual_build


def test_legacy_listing_url_is_not_treated_as_orphaned():
    build = SimpleNamespace(
        status="listed",
        ebay_listing_id=None,
        ebay_listing_url="https://www.ebay.co.uk/itm/188817313509",
    )

    assert is_orphaned_local_manual_build(build) is False


def test_missing_id_and_url_is_treated_as_orphaned():
    build = SimpleNamespace(
        status="listed",
        ebay_listing_id=None,
        ebay_listing_url=None,
    )

    assert is_orphaned_local_manual_build(build) is True
