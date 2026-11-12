from decimal import Decimal

from app.services.commerce_pricing import (
    Condition, FulfilmentMode, SupplierOffer, estimate_delivery_working_days, supplier_allowed,
)
from app.services.commercial_quote_evidence import supplier_identity
from app.services.playbook_service import _supplier_fact_is_approvable


def _offer(days=7):
    return SupplierOffer(
        supplier="AliExpress", channel="retail", condition=Condition.NEW,
        item_gbp=Decimal("100"), delivery_gbp=Decimal("5"), fees_gbp=Decimal("0"),
        risk_gbp=Decimal("0"), observed_at="2026-11-12T12:00:00+00:00",
        stock_confirmed=True, approved=True, delivery_working_days=days,
        supplier_confidence=Decimal("1"),
    )


def test_aliexpress_is_flexible_only_even_when_a_listing_reports_fast_delivery():
    offer = _offer(days=1)
    assert not supplier_allowed(FulfilmentMode.PRIORITY, offer)
    assert not supplier_allowed(FulfilmentMode.STANDARD, offer)
    assert supplier_allowed(FulfilmentMode.FLEXIBLE, offer)


def test_aliexpress_fallback_arrival_is_seven_working_days():
    assert estimate_delivery_working_days("AliExpress", None) == (7, "vendor_default")
    assert estimate_delivery_working_days("AliExpress", 5) == (5, "listing_estimate")


def test_aliexpress_offer_requires_exact_extension_page_price_stock_and_postage_evidence():
    url = "https://www.aliexpress.com/item/1005001234567890.html"
    part = {"role": "cpu", "source_url": url}
    source = {
        "url": url, "source": "AliExpress", "evidence_source": "flipflopxtension",
        "fresh": True, "commercial_capture_verified": True, "active_listing": True,
        "condition": "new", "listing_type": "buy_it_now", "stock_status": "available",
        "stock_evidence": "In stock", "item_gbp": "100", "delivery_gbp": "5",
        "postage_verified": True,
        "marketplace_evidence": {
            "source_page_verified": True, "selected_price_stable": True,
            "selected_options_capture_complete": True, "availability_page_verified": True,
            "shipping_page_verified": True,
        },
    }
    assert supplier_identity("AliExpress", url) == "aliexpress"
    assert _supplier_fact_is_approvable(part, source)
    source["marketplace_evidence"]["shipping_page_verified"] = False
    assert not _supplier_fact_is_approvable(part, source)
    source["marketplace_evidence"]["shipping_page_verified"] = True
    source["evidence_source"] = "backend_scrape"
    assert not _supplier_fact_is_approvable(part, source)
