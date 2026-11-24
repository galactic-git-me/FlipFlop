from unittest.mock import AsyncMock

import pytest

from app.api import curated_availability


@pytest.mark.asyncio
async def test_public_build_availability_uses_cached_vendor_data(monkeypatch):
    get_bom = AsyncMock(return_value={"build_id": "FF-GVG-01", "is_available": True})

    class FakeService:
        def __init__(self, db):
            pass

        get_build_bom_with_availability = get_bom

    monkeypatch.setattr(curated_availability, "CuratedAvailabilityService", FakeService)

    result = await curated_availability.get_build_availability("FF-GVG-01", db=object())

    assert result["is_available"] is True
    get_bom.assert_awaited_once_with("FF-GVG-01", check_live=False)
