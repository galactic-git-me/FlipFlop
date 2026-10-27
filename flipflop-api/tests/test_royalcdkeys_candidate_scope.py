import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services import royalcdkeys_catalogue_sync
from app.services.royalcdkeys_catalogue_sync import candidate_product_links


def test_candidate_discovery_includes_requested_products_and_excludes_untyped_windows():
    html = '''
      <a href="/en-gb/products/windows-11-home-oem">Windows 11 Home OEM CD Key</a>
      <a href="/en-gb/products/windows-11-key">Microsoft Windows 11 Pro Key</a>
      <a href="/en-gb/products/office-2024">Microsoft Office 2024 Professional Plus LTSC Key</a>
      <a href="/en-gb/products/google-ai-pro-18-month">Google AI Pro: Gemini Advanced - 18-Month Subscription Activation Link (NON-STACKABLE)</a>
      <a href="/en-gb/products/google-ai-pro-12-month">Google AI Pro: Gemini Advanced - 12-Month Subscription</a>
    '''

    candidates = candidate_product_links(html)

    assert [(item["category"], item["handle"]) for item in candidates] == [
        ("os", "windows-11-home-oem"),
        ("office", "office-2024"),
        ("ai_subscription", "google-ai-pro-18-month"),
    ]


def test_office_and_subscription_candidates_never_receive_a_windows_catalogue_category():
    html = '''
      <a href="/en-gb/products/office">Microsoft Office 2024 Home and Business PC Retail Key</a>
      <a href="/en-gb/products/google-ai">Google AI Pro: Gemini Advanced - 18-Month Subscription Activation Link</a>
    '''

    candidates = candidate_product_links(html)

    assert all(item["category"] != "os" for item in candidates)
    assert [item["category"] for item in candidates] == ["office", "ai_subscription"]


@pytest.mark.asyncio
async def test_exact_product_capture_uses_bounded_concurrency_and_preserves_order(monkeypatch):
    active = 0
    peak = 0

    async def fake_capture(_url):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0)
        active -= 1
        return {"status": "captured"}

    monkeypatch.setattr(royalcdkeys_catalogue_sync, "collect_product_capture", fake_capture)
    candidates = [{"url": f"https://royalcdkeys.com/en-gb/products/test-{i}", "index": i}
        for i in range(8)]

    results = await royalcdkeys_catalogue_sync._capture_candidates(candidates)

    assert peak == royalcdkeys_catalogue_sync.ROYALCDKEYS_CAPTURE_CONCURRENCY
    assert [candidate["index"] for candidate, _capture in results] == list(range(8))
    assert all(capture["status"] == "captured" for _candidate, capture in results)


@pytest.mark.asyncio
async def test_royalcdkeys_review_candidates_resolve_source_preview(monkeypatch):
    from app.services import playbook_service

    listing = SimpleNamespace(
        id=19,
        title="Windows 11 Home Retail",
        url="https://royalcdkeys.com/en-gb/products/windows-11-home-retail",
        image_urls=[],
        raw_specs={
            "royalcdkeys": {"category": "os"},
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

    candidates = await playbook_service.royalcdkeys_licence_candidates(Session())

    assert len(candidates) == 1
    assert candidates[0]["listing_id"] == 19
    assert candidates[0]["price_gbp"] == "29.99"
    assert candidates[0]["customer_offering_enabled"] is False
