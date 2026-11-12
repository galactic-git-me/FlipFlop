from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.api.marketplace_sourcing import SourcingListingInput, fingerprint


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
