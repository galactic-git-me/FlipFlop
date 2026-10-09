"""Regression coverage for Gem Radar API empty-market behaviour."""

from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from app.api import gem_radar


class _EmptyResult:
    def scalar_one_or_none(self):
        return None


@pytest.mark.asyncio
async def test_component_lookup_returns_empty_when_no_active_listing(monkeypatch):
    """A temporarily empty category is a normal dashboard state, not a 500."""
    monkeypatch.setattr(gem_radar, "get_active_buy_it_now_listing_ids", AsyncMock(return_value=[101]))
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_EmptyResult())

    result = await gem_radar._fetch_best_gem_for_category(db, "gpu", since=datetime.utcnow())

    assert result is None
    assert db.execute.await_count == 2
