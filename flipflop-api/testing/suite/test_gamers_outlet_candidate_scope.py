from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services import playbook_product_capture
from app.services.playbook_product_capture import supported_product_url


def test_gamers_outlet_url_support_is_exact_and_secure():
    assert supported_product_url("https://www.gamers-outlet.net/en/buy-windows-11-home-oem-cd-key")
    assert not supported_product_url("https://www.gamers-outlet.net/en/")
    assert not supported_product_url("http://www.gamers-outlet.net/en/buy-windows-11-home-oem-cd-key")

@pytest.mark.asyncio
async def test_gamers_outlet_exact_product_url_uses_gamers_outlet_capture(monkeypatch):
    expected = {"status": "captured", "item_gbp": "29.99"}
    capture = AsyncMock(return_value=expected)
    monkeypatch.setattr(playbook_product_capture, "_collect_gamers_outlet_capture", capture)

    result = await playbook_product_capture.collect_product_capture(
        "https://www.gamers-outlet.net/en/buy-windows-11-home-oem-cd-key"
    )

    assert result == expected
    capture.assert_awaited_once_with(
        "https://www.gamers-outlet.net/en/buy-windows-11-home-oem-cd-key",
        browser_runtime=None,
    )


@pytest.mark.asyncio
async def test_gamers_outlet_review_candidates_resolve_source_preview(monkeypatch):
    from app.services import playbook_service

    listing = SimpleNamespace(
        id=19,
        source_name="Gamers Outlet",
        title="Windows 11 Home Retail",
        url="https://www.gamers-outlet.net/en/buy-windows-11-home-retail",
        image_urls=[],
        raw_specs={
            "gamers_outlet": {"category": "os"},
            "playbook_product_capture": {"status": "captured", "digital_product": True},
        },
    )

    class Result:
        def scalars(self):
            return self

        def all(self):
            return [listing]

    class VariantResult:
        def all(self):
            return []

    class Session:
        calls = 0

        async def execute(self, _statement):
            self.calls += 1
            return Result() if self.calls == 1 else VariantResult()

    monkeypatch.setattr(playbook_service, "source_preview", AsyncMock(return_value={
        "item_gbp": "29.99", "fresh": True, "stock_status": "available",
        "stock_evidence": "Exact supplier page says in stock",
        "licence_review_fingerprint": "a" * 64, "licence_source_reviewed": False,
        "product_properties": {},
    }))

    candidates = await playbook_service.gamers_outlet_licence_candidates(Session())

    assert len(candidates) == 1
    assert candidates[0]["listing_id"] == 19
    assert candidates[0]["price_gbp"] == "29.99"
    assert candidates[0]["customer_offering_enabled"] is False
