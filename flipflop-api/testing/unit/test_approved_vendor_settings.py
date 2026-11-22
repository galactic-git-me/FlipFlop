import pytest

from app.api.settings_router import normalize_approved_vendors


def test_vendor_names_are_trimmed_and_case_insensitive_duplicates_removed():
    assert normalize_approved_vendors([" eBay UK ", "ebay uk", " Box.co.uk  ", "Box.co.uk"]) == ["eBay UK", "Box.co.uk"]


def test_empty_vendor_name_is_rejected():
    with pytest.raises(ValueError, match="cannot be empty"):
        normalize_approved_vendors(["  "])


def test_vendor_name_limit_is_enforced():
    with pytest.raises(ValueError, match="120 characters"):
        normalize_approved_vendors(["x" * 121])
