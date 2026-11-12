from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.api.marketplace_sourcing import (
    OfferVariantInput, SourcingListingInput, effective_bundle_status,
    effective_variant_status, fingerprint,
)


def test_extension_listing_contract_accepts_aliexpress_evidence():
    listing = SourcingListingInput(
        marketplace="aliexpress",
        marketplace_listing_id="1005001234567890",
        title="CPU motherboard bundle",
        url="https://www.aliexpress.com/item/1005001234567890.html",
        discovered_at=datetime.now(timezone.utc),
        bundle_candidate=True,
        applied_filters={"status": "unverified"},
    )
    assert listing.marketplace == "aliexpress"
    assert listing.bundle_candidate is True


def test_marketplace_url_must_match_selected_vendor():
    with pytest.raises(ValidationError, match="host does not match marketplace"):
        SourcingListingInput(
            marketplace="aliexpress",
            marketplace_listing_id="123",
            title="CPU",
            url="https://example.com/item/123",
            discovered_at=datetime.now(timezone.utc),
        )


def test_temu_is_not_an_enabled_source():
    with pytest.raises(ValidationError, match="unsupported marketplace"):
        SourcingListingInput(
            marketplace="temu",
            marketplace_listing_id="123",
            title="CPU",
            url="https://www.temu.com/item/123",
            discovered_at=datetime.now(timezone.utc),
        )


def test_variant_fingerprint_is_independent_of_object_key_order():
    assert fingerprint({"RAM": "32GB", "DDR": "DDR5"}) == fingerprint({"DDR": "DDR5", "RAM": "32GB"})


def variant(**overrides):
    values = {
        "item_price": "180.00", "currency": "GBP", "verification_status": "verified",
        "observed_at": datetime.now(timezone.utc),
        "source_url": "https://www.aliexpress.com/item/123.html",
        "selected_options": {"Package": "CPU + board"},
        "evidence": {"source_page_verified": True, "selected_price_stable": True,
                     "variant_controls_detected": True, "selected_options_capture_complete": True},
    }
    return OfferVariantInput(**{**values, **overrides})


def test_variant_requires_product_page_and_stable_selected_price_evidence():
    assert effective_variant_status(variant()) == "verified"
    assert effective_variant_status(variant(evidence={"source_page_verified": True})) == "needs_verification"
    assert effective_variant_status(variant(selected_options={})) == "needs_verification"


def test_bundle_requires_exact_contents_before_it_is_trusted():
    assert effective_bundle_status(variant(), "verified") == "needs_verification"
    bundle_variant = variant(
        bundle_components=[{"canonical_part_key": "cpu-5600", "quantity": 1}],
        evidence={"source_page_verified": True, "selected_price_stable": True,
                  "bundle_contents_verified": True},
    )
    assert effective_bundle_status(bundle_variant, "verified") == "verified"
