"""Regression coverage for private, order-scoped Welcome Guide access.

These tests are authored but intentionally not executed until the platform
test strategy receives approval.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.routes import guides
from app.schemas.guide import WelcomeGuideRequest


@pytest.mark.asyncio
async def test_customer_can_access_only_their_own_order(monkeypatch):
    customer = SimpleNamespace(id=23)
    order = SimpleNamespace(id=9, customer_id=23)
    db = SimpleNamespace(get=AsyncMock(return_value=order))
    monkeypatch.setattr(guides, "get_customer_by_token", AsyncMock(return_value=customer))

    authorized_order, guest = await guides._authorized_order(9, "Bearer customer-token", db)

    assert authorized_order is order
    assert guest is False


@pytest.mark.asyncio
async def test_customer_token_cannot_access_another_customers_order(monkeypatch):
    customer = SimpleNamespace(id=23)
    order = SimpleNamespace(id=9, customer_id=24)
    db = SimpleNamespace(get=AsyncMock(return_value=order))
    monkeypatch.setattr(guides, "get_customer_by_token", AsyncMock(return_value=customer))

    with pytest.raises(HTTPException) as error:
        await guides._authorized_order(9, "Bearer customer-token", db)

    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_guest_token_is_limited_to_its_granted_order(monkeypatch):
    grant = SimpleNamespace(order_id=9)
    order = SimpleNamespace(id=9, customer_id=24)
    db = SimpleNamespace(get=AsyncMock(return_value=order))
    monkeypatch.setattr(guides, "get_customer_by_token", AsyncMock(return_value=None))
    monkeypatch.setattr(guides, "verify_guest_portal_token", AsyncMock(return_value=grant))

    authorized_order, guest = await guides._authorized_order(9, "Bearer guest-token", db)
    assert authorized_order is order
    assert guest is True

    with pytest.raises(HTTPException) as error:
        await guides._authorized_order(10, "Bearer guest-token", db)
    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_guest_token_cannot_generate_or_regenerate_guide(monkeypatch):
    monkeypatch.setattr(
        guides,
        "_authorized_order",
        AsyncMock(return_value=(SimpleNamespace(id=9), True)),
    )

    with pytest.raises(HTTPException) as error:
        await guides.generate_welcome_guide(
            9,
            WelcomeGuideRequest(regenerate=True),
            authorization="Bearer guest-token",
            db=SimpleNamespace(),
        )

    assert error.value.status_code == 403
