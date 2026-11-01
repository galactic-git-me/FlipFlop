from datetime import datetime

from app.services.ebay_order_sync import _parse_order


def test_parse_order_retains_exact_ebay_ship_by_deadline():
    order = {
        "orderId": "12-34567-89012",
        "fulfillmentStartInstructions": [{
            "shippingStep": {
                "shipTo": {
                    "fullName": "Buyer",
                    "contactAddress": {"countryCode": "GB"},
                },
            },
        }],
        "lineItems": [{
            "lineItemId": "line-1",
            "legacyItemId": "listing-1",
            "lineItemFulfillmentInstructions": {
                "shipByDate": "2026-10-17T15:00:00.000Z",
            },
        }],
        "pricingSummary": {"total": {"value": "799.99", "currency": "GBP"}},
    }

    parsed = _parse_order(order, matching_legacy_item_id="listing-1")

    assert parsed is not None
    assert parsed.ship_by_date == datetime(2026, 10, 17, 15, 0)


def test_parse_order_keeps_ship_by_unknown_when_channel_omits_it():
    order = {
        "orderId": "12-34567-89012",
        "fulfillmentStartInstructions": [{
            "shippingStep": {"shipTo": {"fullName": "Buyer", "contactAddress": {}}},
        }],
        "lineItems": [{"lineItemId": "line-1"}],
        "pricingSummary": {"total": {"value": "799.99", "currency": "GBP"}},
    }

    parsed = _parse_order(order)

    assert parsed is not None
    assert parsed.ship_by_date is None
