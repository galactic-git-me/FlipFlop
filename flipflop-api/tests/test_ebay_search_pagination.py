"""Regression coverage for extension-facing eBay pagination."""

from unittest.mock import AsyncMock, patch

import pytest

from app.api.gem_radar import ebay_search


@pytest.mark.asyncio
async def test_short_normalized_ebay_page_still_has_next_page() -> None:
    """Filtered results must not make a full raw eBay page look terminal."""
    listing = {
        "url": "https://www.ebay.co.uk/itm/123",
        "title": "AMD Ryzen Processor",
        "condition": "Used",
        "price": 100.0,
        "image_url": None,
    }
    normalized_page = [listing.copy() for _ in range(96)]

    with patch(
        "app.services.ebay_browse.search_active_listings",
        new=AsyncMock(return_value=normalized_page),
    ):
        result = await ebay_search(query="AMD CPU", page=1, limit=100, _=None)

    assert result["count"] == 96
    assert result["hasNextPage"] is True
