from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.services.warranty_service import public_warranty_summary, warranty_expiry


def _reserve(started_at: datetime):
    return SimpleNamespace(
        warranty_started_at=started_at,
        warranty_expires_at=warranty_expiry(started_at),
    )


def test_no_reserve_means_warranty_has_not_started():
    summary = public_warranty_summary(None, now=datetime(2026, 9, 29))
    assert summary["status"] == "not_started"
    assert summary["started_at"] is None


def test_recorded_delivery_starts_customer_warranty_without_financial_reserve():
    delivered = datetime(2026, 9, 20, 14, 30)
    summary = public_warranty_summary(
        None,
        started_at=delivered,
        now=datetime(2026, 9, 29, 12),
    )

    assert summary["status"] == "active"
    assert summary["is_active"] is True
    assert summary["started_at"] == delivered.isoformat()
    assert summary["expires_at"] == warranty_expiry(delivered).isoformat()


def test_marketplace_build_portal_uses_recorded_delivery_when_reserve_is_deferred(monkeypatch):
    from app.api import orders as orders_api

    delivered = datetime(2026, 9, 20, 14, 30)
    build = SimpleNamespace(
        id=12,
        generated_title=None,
        name="Atlas",
        hero_photo_url=None,
        model_3d_url=None,
        evidence_data={},
        last_evaluation={},
        warranty_started_at=delivered,
        delivered_at=delivered,
        selected_faq_ids=[],
        selected_faq_answer_overrides={},
        delivery_min_days=1,
        delivery_max_days=3,
    )
    monkeypatch.setattr(orders_api, "selected_faqs", lambda *_args: [])

    hub = orders_api._manual_build_customer_hub(build, warranty_reserve=None)

    assert hub["warranty"]["status"] == "active"
    assert hub["warranty"]["started_at"] == delivered.isoformat()


def test_future_delivery_date_is_not_misreported_as_expired():
    current = datetime(2026, 9, 29, 12)
    summary = public_warranty_summary(_reserve(current + timedelta(days=2)), now=current)
    assert summary["status"] == "not_started"
    assert summary["is_active"] is False
    assert "2026-10-01" in summary["message"]


def test_warranty_is_active_from_delivery_until_expiry_boundary():
    started = datetime(2025, 9, 29, 12)
    summary = public_warranty_summary(_reserve(started), now=started)
    assert summary["status"] == "active"
    assert summary["is_active"] is True


def test_expired_commercial_warranty_preserves_statutory_rights_message():
    started = datetime(2025, 9, 29, 12)
    summary = public_warranty_summary(
        _reserve(started), now=warranty_expiry(started) + timedelta(seconds=1)
    )
    assert summary["status"] == "expired"
    assert summary["is_active"] is False
    assert "statutory rights are unaffected" in summary["message"]


@pytest.mark.asyncio
async def test_build_portal_prefers_the_linked_order_warranty_reserve():
    from app.api.orders import _manual_build_portal_warranty_reserve

    product = SimpleNamespace(sold_order_id=81)
    order_reserve = SimpleNamespace(id=1, order_id=81)
    db = SimpleNamespace(
        get=AsyncMock(return_value=product),
        execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: order_reserve)),
    )
    build = SimpleNamespace(id=12, storefront_product_id=5)

    result = await _manual_build_portal_warranty_reserve(db, build)

    assert result is order_reserve
    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_build_portal_falls_back_to_build_reserve_when_sale_reserve_is_missing():
    from app.api.orders import _manual_build_portal_warranty_reserve

    product = SimpleNamespace(sold_order_id=82)
    build_reserve = SimpleNamespace(id=2, manual_build_id=13)
    results = [
        SimpleNamespace(scalar_one_or_none=lambda: None),
        SimpleNamespace(scalar_one_or_none=lambda: build_reserve),
    ]
    db = SimpleNamespace(
        get=AsyncMock(return_value=product),
        execute=AsyncMock(side_effect=results),
    )
    build = SimpleNamespace(id=13, storefront_product_id=6)

    result = await _manual_build_portal_warranty_reserve(db, build)

    assert result is build_reserve
    assert db.execute.await_count == 2


@pytest.mark.asyncio
async def test_sold_build_preview_uses_order_portal_tracking_and_reserve(monkeypatch):
    from app.api import orders as orders_api

    order = SimpleNamespace(id=81, customer_id=9)
    build = SimpleNamespace(id=12)
    job = SimpleNamespace(id=4)
    order_reserve = SimpleNamespace(id=1, order_id=81)
    events = [SimpleNamespace(id=5, order_id=81)]
    results = [
        SimpleNamespace(scalar_one_or_none=lambda: order),
        SimpleNamespace(scalar_one_or_none=lambda: None),
        SimpleNamespace(scalar_one_or_none=lambda: job),
        SimpleNamespace(scalar_one_or_none=lambda: order_reserve),
        SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: events)),
    ]
    db = SimpleNamespace(execute=AsyncMock(side_effect=results))
    response = object()
    render_order = Mock(return_value=response)
    monkeypatch.setattr(orders_api, "_portal_actor", AsyncMock(return_value=("admin", SimpleNamespace(id=1))))
    monkeypatch.setattr(orders_api.jwt, "decode", lambda *_args, **_kwargs: {
        "typ": "portal_preview", "scope": "read", "build_id": 12, "order_id": 81,
    })
    monkeypatch.setattr(orders_api, "_manual_build_sold_on_order", AsyncMock(return_value=build))
    monkeypatch.setattr(orders_api, "_order_to_my_order_out", render_order)

    result = await orders_api.get_portal_preview("preview-token", "Bearer admin", db)

    assert result is response
    render_order.assert_called_once_with(order, None, build, job, order_reserve, events)
