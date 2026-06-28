import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.companion_service import (
    build_system_prompt,
    parse_search_args,
    format_listing_result,
)


def test_build_system_prompt_contains_snapshot():
    snapshot = "Total: 100 | Gems: 12 | Last scan: 5m ago"
    prompt = build_system_prompt(snapshot, "listings")
    assert "100" in prompt
    assert "12" in prompt
    assert "listings" in prompt.lower()


def test_parse_search_args_extracts_query():
    args = {"query": "rtx 3060", "max_price": 200}
    result = parse_search_args(args)
    assert result["query"] == "rtx 3060"
    assert result["max_price"] == 200.0


def test_parse_search_args_defaults():
    result = parse_search_args({"query": "gaming pc"})
    assert result["max_price"] is None
    assert result["classification"] is None


def test_format_listing_result():
    listing = MagicMock()
    listing.id = 1
    listing.title = "Gaming PC i7 RTX 3060"
    listing.price = 149.0
    listing.classification = MagicMock(value="gem")
    listing.gem_score = 81.0
    listing.source_name = "eBay"
    listing.url = "https://ebay.com/itm/123"
    listing.gpu = "RTX 3060"
    listing.cpu = "i7-10700"
    listing.ram_gb = 16
    result = format_listing_result(listing)
    assert result["title"] == "Gaming PC i7 RTX 3060"
    assert result["price"] == 149.0
    assert result["classification"] == "gem"
    assert result["score"] == 81.0
