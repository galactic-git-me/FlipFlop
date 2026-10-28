import pytest

from app.services import email_service
from app.services.email_service import render_build_status_email


def test_status_email_template_covers_build_and_courier_updates():
    subject, body = render_build_status_email(
        "Alex Buyer",
        "ORD-123",
        "qa",
        123,
    )
    assert subject == "Performance testing: ORD-123"
    assert "Alex Buyer" in body
    assert "ORD-123" in body
    assert "/my-builds/123" in body
    assert "performance and quality testing" in body

    courier_subject, courier_body = render_build_status_email(
        "Alex Buyer",
        "ORD-123",
        "shipped",
        123,
        carrier="DPD",
        tracking_number="DPD123",
        tracking_url="https://example.test/track/DPD123",
        estimated_delivery="2026-09-14",
        update_kind="courier",
    )
    assert courier_subject == "Courier update: ORD-123"
    assert "DPD" in courier_body
    assert "DPD123" in courier_body
    assert "2026-09-14" in courier_body


@pytest.mark.asyncio
async def test_case_email_includes_safe_repair_tracking_details(monkeypatch):
    captured = {}
    monkeypatch.setattr(email_service, "smtp_is_configured", lambda: True)
    monkeypatch.setattr(
        email_service,
        "_send",
        lambda message, reference: captured.update(message=message, reference=reference) or True,
    )

    sent = await email_service.send_customer_case_status_email(
        "buyer@example.com",
        "Alex Buyer",
        "CASE-44",
        "replacement_dispatched",
        123,
        repair_tracking={
            "purpose": "replacement",
            "carrier": "DPD & Sons",
            "tracking_number": "DPD-123",
            "tracking_url": "https://carrier.example/track/DPD-123?source=mail&safe=1",
        },
    )

    html_body = captured["message"].get_payload()[0].get_payload(decode=True).decode()
    assert sent is True
    assert captured["reference"] == "customer-case-CASE-44-replacement_dispatched"
    assert "DPD &amp; Sons" in html_body
    assert "DPD-123" in html_body
    assert "https://carrier.example/track/DPD-123?source=mail&amp;safe=1" in html_body


@pytest.mark.asyncio
async def test_case_email_omits_unsafe_repair_tracking_url(monkeypatch):
    captured = {}
    monkeypatch.setattr(email_service, "smtp_is_configured", lambda: True)
    monkeypatch.setattr(
        email_service,
        "_send",
        lambda message, reference: captured.update(message=message) or True,
    )

    await email_service.send_customer_case_status_email(
        "buyer@example.com",
        "Alex Buyer",
        "CASE-45",
        "return_in_transit",
        124,
        repair_tracking={
            "purpose": "customer_return",
            "carrier": "Example",
            "tracking_number": "TRACK-1",
            "tracking_url": "javascript:alert(1)",
        },
    )

    html_body = captured["message"].get_payload()[0].get_payload(decode=True).decode()
    assert "javascript:" not in html_body
    assert "Track with the carrier" not in html_body


@pytest.mark.asyncio
async def test_guest_portal_claim_email_escapes_content_and_uses_one_time_link(monkeypatch):
    from datetime import datetime

    captured = {}
    monkeypatch.setattr(email_service, "smtp_is_configured", lambda: True)
    monkeypatch.setattr(
        email_service,
        "_send",
        lambda message, reference: captured.update(message=message, reference=reference) or True,
    )

    sent = await email_service.send_guest_portal_claim_email(
        "verified@example.com",
        "Alex <Buyer>",
        "Build & Beyond",
        "https://shop.example/claim-build?token=secret%26opaque",
        datetime(2026, 10, 1),
        "FF-2026-0042",
    )

    html_body = captured["message"].get_payload()[0].get_payload(decode=True).decode()
    assert sent is True
    assert captured["message"]["To"] == "verified@example.com"
    assert captured["reference"] == "portal-claim-FF-2026-0042"
    assert "Alex &lt;Buyer&gt;" in html_body
    assert "Build &amp; Beyond" in html_body
    assert "https://shop.example/claim-build?token=secret%26opaque" in html_body
    assert "one-time link expires" in html_body
    assert "prevents email security scanners" in html_body


@pytest.mark.asyncio
async def test_dispatched_guest_portal_email_includes_claim_and_safe_tracking(monkeypatch):
    captured = {}
    monkeypatch.setattr(email_service, "smtp_is_configured", lambda: True)
    monkeypatch.setattr(
        email_service,
        "_send",
        lambda message, reference: captured.update(message=message, reference=reference) or True,
    )

    sent = await email_service.send_dispatched_guest_portal_email(
        "verified@example.com",
        "Alex <Buyer>",
        "Build & Beyond",
        "https://shop.example/claim-build?token=secret%26opaque",
        "2026-12-28T12:00:00",
        "FF-2026-0042",
        "DPD & Sons",
        "DPD-123",
        "https://carrier.example/track/DPD-123?source=mail&safe=1",
    )

    html_body = captured["message"].get_payload()[0].get_payload(decode=True).decode()
    assert sent is True
    assert captured["message"]["To"] == "verified@example.com"
    assert captured["reference"] == "portal-dispatch-FF-2026-0042"
    assert "Alex &lt;Buyer&gt;" in html_body
    assert "Build &amp; Beyond" in html_body
    assert "DPD &amp; Sons" in html_body
    assert "https://carrier.example/track/DPD-123?source=mail&amp;safe=1" in html_body
    assert "https://shop.example/claim-build?token=secret%26opaque" in html_body
    assert "prevents email security scanners" in html_body


@pytest.mark.asyncio
async def test_dispatched_guest_portal_email_omits_unsafe_tracking_url(monkeypatch):
    captured = {}
    monkeypatch.setattr(email_service, "smtp_is_configured", lambda: True)
    monkeypatch.setattr(
        email_service,
        "_send",
        lambda message, reference: captured.update(message=message) or True,
    )

    await email_service.send_dispatched_guest_portal_email(
        "verified@example.com",
        "Buyer",
        "Build",
        "https://shop.example/claim-build?token=opaque",
        "2026-12-28",
        "FF-2026-0043",
        "Courier",
        "TRACK-2",
        "javascript:alert(1)",
    )

    html_body = captured["message"].get_payload()[0].get_payload(decode=True).decode()
    assert "TRACK-2" in html_body
    assert "javascript:" not in html_body
