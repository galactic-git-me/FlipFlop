from datetime import datetime, timedelta
from types import SimpleNamespace

from app.services.alerts import _latest_unresolved_refund_requests


def _email_event(event_type, received_at, *, build_id=7, order_id=None):
    payload = {"order_id": order_id} if order_id else {}
    return SimpleNamespace(
        event_type=event_type,
        manual_build_id=build_id,
        received_at=received_at,
        payload=payload,
    )


def test_old_resolution_does_not_hide_a_later_request_for_the_same_order():
    first_request_at = datetime(2026, 1, 1, 9)
    resolved_at = first_request_at + timedelta(hours=1)
    new_request_at = resolved_at + timedelta(hours=1)
    old_request = _email_event("refund_requested", first_request_at, order_id="order-1")
    old_resolution = _email_event("refund_issued", resolved_at, order_id="order-1")
    new_request = _email_event("refund_requested", new_request_at, order_id="order-1")

    unresolved = _latest_unresolved_refund_requests(
        [new_request, old_request], [old_resolution],
    )

    assert unresolved == {7: new_request}


def test_only_a_later_resolution_for_the_matching_order_closes_the_request():
    requested_at = datetime(2026, 1, 1, 9)
    request = _email_event("refund_requested", requested_at, order_id="order-1")
    wrong_order_resolution = _email_event(
        "refund_issued", requested_at + timedelta(hours=1), order_id="order-2",
    )
    matching_resolution = _email_event(
        "return_closed", requested_at + timedelta(hours=2), order_id="order-1",
    )

    assert _latest_unresolved_refund_requests([request], [wrong_order_resolution]) == {7: request}
    assert _latest_unresolved_refund_requests([request], [matching_resolution]) == {}
