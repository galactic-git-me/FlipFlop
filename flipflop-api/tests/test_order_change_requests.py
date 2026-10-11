from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.customer import Customer
from app.models.getting_started_job import GettingStartedJob
from app.models.order import Order, OrderStatus
from app.routes.auth import get_current_user
from app.routes.admin_auth import get_current_admin
from app.api import orders as orders_api


@pytest.fixture
async def change_request_client(monkeypatch):
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as db:
        customer = Customer(id=901, name="Change Request Buyer", email="change@example.test")
        db.add(customer)
        await db.flush()
        order = Order(
            order_id="FF-CHANGE-REQUEST-901",
            customer_id=customer.id,
            specs={"components": [{"slot": "CPU", "name": "Original CPU"}]},
            customer_price=900,
            component_costs=700,
            overhead_amount=50,
            status=OrderStatus.AWAITING_SOURCING,
            stripe_payment_intent_id="pi_change_request_901",
        )
        db.add(order)
        await db.commit()
        order_id = order.id

    async def override_db():
        async with session_factory() as db:
            yield db

    async def override_customer():
        return SimpleNamespace(id=901, name="Change Request Buyer", email="change@example.test")

    async def override_admin():
        return SimpleNamespace(id=42, name="Admin", email="admin@example.test")

    monkeypatch.setattr(orders_api, "send_order_status_email", AsyncMock(return_value=True))
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_customer
    app.dependency_overrides[get_current_admin] = override_admin
    try:
        yield TestClient(app), session_factory, order_id
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()


@pytest.mark.asyncio
async def test_change_request_pauses_sourcing_and_quote_is_customer_visible(change_request_client):
    client, session_factory, order_id = change_request_client
    requested = client.post(
        f"/api/orders/{order_id}/change-requests",
        json={"request_text": "Please replace the processor with the next model up if it remains compatible."},
    )
    assert requested.status_code == 201
    assert requested.json()["change_request"]["status"] == "requested"

    sourcing = client.patch(
        f"/api/orders/{order_id}",
        json={"status": "parts_ordered"},
    )
    assert sourcing.status_code == 409
    assert "sourcing is paused" in sourcing.json()["detail"].lower()

    quote = client.patch(
        f"/api/admin/orders/{order_id}/change-request",
        json={
            "action": "quote",
            "customer_message": "We can make this change for the revised total shown below.",
            "proposed_specs": {"components": [{"slot": "CPU", "name": "Proposed CPU"}]},
            "proposed_customer_price": 975,
            "internal_note": "Price checked against supplier quote Q-901.",
        },
    )
    assert quote.status_code == 200
    assert quote.json()["change_request"]["status"] == "quote_ready"

    portal = client.get(f"/api/orders/{order_id}")
    assert portal.status_code == 200
    change = portal.json()["change_request"]
    assert change["status"] == "quote_ready"
    assert change["proposed_customer_price"] == 975
    assert "internal_note" not in change

    response = client.post(
        f"/api/orders/{order_id}/change-requests/respond",
        json={"decision": "accept_quote"},
    )
    assert response.status_code == 422
    async with session_factory() as db:
        persisted = await db.get(Order, order_id)
        assert persisted.status == OrderStatus.AWAITING_SOURCING
        assert persisted.specs["components"][0]["name"] == "Original CPU"
        assert persisted.customer_price == 900
        assert persisted.change_request["status"] == "quote_ready"


@pytest.mark.asyncio
async def test_ready_to_ship_order_cannot_open_a_pre_sourcing_change_request(change_request_client):
    client, session_factory, order_id = change_request_client
    async with session_factory() as db:
        db.add(GettingStartedJob(
            order_id=order_id,
            customer_id=901,
            source_type="ready_to_ship",
            status="awaiting_admin_review",
            checklist={"components_ordered": True},
        ))
        await db.commit()

    response = client.post(
        f"/api/orders/{order_id}/change-requests",
        json={"request_text": "Please change the graphics card before you send the PC."},
    )
    assert response.status_code == 409
    assert "ready-to-ship" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_declining_revised_quote_preserves_original_order_and_releases_sourcing_hold(change_request_client):
    client, session_factory, order_id = change_request_client
    request = client.post(
        f"/api/orders/{order_id}/change-requests",
        json={"request_text": "Please replace the processor with the next model up if it remains compatible."},
    )
    assert request.status_code == 201

    quote = client.patch(
        f"/api/admin/orders/{order_id}/change-request",
        json={
            "action": "quote",
            "customer_message": "We can make this change for the revised total shown below.",
            "proposed_specs": {"components": [{"slot": "CPU", "name": "Proposed CPU"}]},
            "proposed_customer_price": 975,
        },
    )
    assert quote.status_code == 200

    response = client.post(
        f"/api/orders/{order_id}/change-requests/respond",
        json={"decision": "decline_quote"},
    )
    assert response.status_code == 200
    assert response.json()["change_request"]["status"] == "declined"

    sourcing = client.patch(f"/api/orders/{order_id}", json={"status": "parts_ordered"})
    assert sourcing.status_code == 200
    async with session_factory() as db:
        persisted = await db.get(Order, order_id)
        assert persisted.status == OrderStatus.PARTS_ORDERED
        assert persisted.specs["components"][0]["name"] == "Original CPU"
        assert persisted.customer_price == 900
