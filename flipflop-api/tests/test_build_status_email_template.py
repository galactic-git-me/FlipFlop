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
