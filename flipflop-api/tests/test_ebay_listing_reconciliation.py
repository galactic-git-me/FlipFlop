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
