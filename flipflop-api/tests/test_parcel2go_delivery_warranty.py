"""Unexecuted integration coverage for delivered events and warranty start."""

import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.build import Build, BuildStatus, BuildType
from app.models.customer import Customer
from app.models.customer_problem import CustomerProblem
from app.models.customer_problem_shipment import CustomerProblemShipment
from app.models.manual_build import ManualBuild
from app.models.order import Order, OrderStatus
from app.models.shipment_tracking_event import ShipmentTrackingEvent
from app.models.warranty import WarrantyReserve
from app.routes import webhooks
from app.services import parcel2go_notifications
from app.api.orders import _customer_problem_outputs

notify_parcel2go_tracking_event_impl = webhooks._notify_parcel2go_tracking_event


@pytest.fixture
async def delivery_webhook_client(monkeypatch):
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    secret = "test-parcel2go-webhook-secret"
    monkeypatch.setattr(webhooks, "get_settings", lambda: SimpleNamespace(parcel2go_webhook_secret=secret))
    monkeypatch.setattr(webhooks, "_notify_parcel2go_tracking_event", AsyncMock(return_value=True))
    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app), session_factory, secret
    finally:
        app.dependency_overrides.pop(get_db, None)
        await engine.dispose()


def _signed_event(secret: str, *, event_id: str, occurred_at: datetime) -> dict:
    envelope_time = datetime.now(timezone.utc).replace(microsecond=0)
    timestamp = envelope_time.strftime("%Y-%m-%d %H:%M:%S")
    event_type = "tracking"
    signature = hmac.new(
        secret.encode(), f"{event_id}:{timestamp}:{event_type}".encode(), hashlib.sha256
    ).hexdigest()
    return {
        "Id": event_id,
        "Timestamp": envelope_time.isoformat(),
        "Type": event_type,
        "Signature": signature,
        "Payload": {
            "OrderLineId": "P2G-DELIVERY-LINE-1",
            "TrackingStage": "delivered",
            "StatusDescription": "Delivered to recipient",
            "Timestamp": occurred_at.replace(tzinfo=timezone.utc).isoformat(),
        },
    }


@pytest.mark.asyncio
async def test_delivery_and_late_earlier_delivery_event_start_one_backdated_warranty(
    delivery_webhook_client,
):
    client, session_factory, secret = delivery_webhook_client
    async with session_factory() as db:
        customer = Customer(id=701, name="Portal Buyer", email="buyer@example.com")
        order = Order(
            order_id="FF-P2G-WARRANTY-1",
            customer_id=customer.id,
            specs={"build_name": "Atlas Test Build"},
            customer_price=1000,
            component_costs=800,
            overhead_amount=50,
            status=OrderStatus.SHIPPED,
        )
        build_record = ManualBuild(
            name="Atlas Test Build",
            status="sold",
            parcel2go_order_line_id="P2G-DELIVERY-LINE-1",
            sale_price_actual=1000,
            warranty_reserve_pct=5,
        )
        db.add_all([customer, order, build_record])
        await db.flush()
        db.add(Build(
            build_type=BuildType.PREBUILT,
            order_id=order.id,
            manual_build_id=build_record.id,
            status=BuildStatus.FINALISED,
            spec_json={"build_name": "Atlas Test Build"},
        ))
        await db.commit()
        manual_build_id = build_record.id
        order_id = order.id

    first_delivery = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0) - timedelta(hours=3)
    earlier_delivery = first_delivery - timedelta(hours=2)
    first = client.post(
        "/api/webhooks/parcel2go",
        json=_signed_event(secret, event_id="delivery-event-1", occurred_at=first_delivery),
    )
    assert first.status_code == 200
    assert first.json()["status"] == "processed"

    second = client.post(
        "/api/webhooks/parcel2go",
        json=_signed_event(secret, event_id="delivery-event-2", occurred_at=earlier_delivery),
    )
    assert second.status_code == 200

    duplicate = client.post(
        "/api/webhooks/parcel2go",
        json=_signed_event(secret, event_id="delivery-event-2", occurred_at=earlier_delivery),
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["status"] == "duplicate"

    async with session_factory() as db:
        order = await db.get(Order, order_id)
        build_record = await db.get(ManualBuild, manual_build_id)
        reserve = (await db.execute(select(WarrantyReserve).where(
            WarrantyReserve.order_id == order_id
        ))).scalar_one()
        event_count = (await db.execute(select(func.count()).select_from(ShipmentTrackingEvent))).scalar_one()

        assert order.delivered_at == earlier_delivery
        assert order.actual_delivery_date == earlier_delivery
        assert order.status == OrderStatus.COMPLETED
        assert build_record.delivered_at == earlier_delivery
        assert build_record.warranty_started_at == earlier_delivery
        assert build_record.dispatch_status == "delivered"
        assert reserve.warranty_started_at == earlier_delivery
        assert reserve.warranty_expires_at == earlier_delivery.replace(year=earlier_delivery.year + 1)
        assert reserve.reserved_amount_gbp == 50
        assert event_count == 2


@pytest.mark.asyncio
async def test_marketplace_delivery_starts_build_scoped_warranty_without_creating_order(
    delivery_webhook_client,
):
    client, session_factory, secret = delivery_webhook_client
    async with session_factory() as db:
        build_record = ManualBuild(
            name="Marketplace Atlas",
            status="sold",
            parcel2go_order_line_id="P2G-DELIVERY-LINE-1",
            sale_price_actual=800,
            warranty_reserve_pct=5,
        )
        db.add(build_record)
        await db.commit()
        manual_build_id = build_record.id

    delivered_at = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0) - timedelta(minutes=30)
    response = client.post(
        "/api/webhooks/parcel2go",
        json=_signed_event(secret, event_id="marketplace-delivery-event", occurred_at=delivered_at),
    )
    assert response.status_code == 200

    async with session_factory() as db:
        build_record = await db.get(ManualBuild, manual_build_id)
        reserve = (await db.execute(select(WarrantyReserve).where(
            WarrantyReserve.manual_build_id == manual_build_id
        ))).scalar_one()
        event = (await db.execute(select(ShipmentTrackingEvent))).scalar_one()

        assert reserve.order_id is None
        assert reserve.warranty_started_at == delivered_at
        assert reserve.reserved_amount_gbp == 40
        assert build_record.delivered_at == delivered_at
        assert build_record.warranty_started_at == delivered_at
        assert event.order_id is None
        assert event.manual_build_id == manual_build_id


@pytest.mark.asyncio
async def test_future_provider_delivery_timestamp_cannot_postpone_warranty_start(
    delivery_webhook_client,
):
    client, session_factory, secret = delivery_webhook_client
    async with session_factory() as db:
        build_record = ManualBuild(
            name="Future Timestamp Atlas",
            status="sold",
            parcel2go_order_line_id="P2G-DELIVERY-LINE-1",
            sale_price_actual=800,
            warranty_reserve_pct=5,
        )
        db.add(build_record)
        await db.commit()
        manual_build_id = build_record.id

    before_received_at = datetime.now(timezone.utc).replace(tzinfo=None)
    future_stage_at = datetime.now(timezone.utc) + timedelta(days=1)
    response = client.post(
        "/api/webhooks/parcel2go",
        json=_signed_event(secret, event_id="future-delivery-event", occurred_at=future_stage_at),
    )
    after_received_at = datetime.now(timezone.utc).replace(tzinfo=None)
    assert response.status_code == 200

    async with session_factory() as db:
        build_record = await db.get(ManualBuild, manual_build_id)
        reserve = (await db.execute(select(WarrantyReserve).where(
            WarrantyReserve.manual_build_id == manual_build_id
        ))).scalar_one()
        event = (await db.execute(select(ShipmentTrackingEvent))).scalar_one()

        assert before_received_at <= build_record.delivered_at <= after_received_at
        assert reserve.warranty_started_at == build_record.delivered_at
        assert event.occurred_at == build_record.delivered_at


@pytest.mark.asyncio
async def test_repair_return_webhook_updates_case_timeline_without_restarting_build_warranty(
    delivery_webhook_client,
):
    client, session_factory, secret = delivery_webhook_client
    async with session_factory() as db:
        customer = Customer(id=703, name="Repair Buyer", email="repair@example.com")
        order = Order(
            order_id="FF-REPAIR-TRACKING-1",
            customer_id=customer.id,
            specs={"build_name": "Repair Build"},
            customer_price=1200,
            component_costs=900,
            overhead_amount=75,
            status=OrderStatus.COMPLETED,
        )
        db.add_all([customer, order])
        await db.flush()
        problem = CustomerProblem(
            order_id=order.id,
            customer_id=customer.id,
            category="warranty_claim",
            description="The PC restarts under a sustained workload.",
            status="return_in_transit",
            repair_tracking={
                "purpose": "customer_return",
                "carrier": "Parcel2Go",
                "tracking_number": "P2G-RETURN-TRACK-1",
                "tracking_url": "https://carrier.example/track/P2G-RETURN-TRACK-1",
            },
        )
        db.add(problem)
        await db.flush()
        shipment = CustomerProblemShipment(
            customer_problem_id=problem.id,
            purpose="customer_return",
            carrier="Parcel2Go",
            tracking_number="P2G-RETURN-TRACK-1",
            tracking_url="https://carrier.example/track/P2G-RETURN-TRACK-1",
            provider="parcel2go",
            provider_reference="P2G-REPAIR-LINE-1",
        )
        db.add(shipment)
        await db.commit()
        problem_id = problem.id
        order_id = order.id
        shipment_id = shipment.id

    delivered_at = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0) - timedelta(minutes=20)
    payload = _signed_event(secret, event_id="repair-return-delivered", occurred_at=delivered_at)
    payload["Payload"]["OrderLineId"] = "P2G-REPAIR-LINE-1"
    payload["Payload"]["StatusDescription"] = "Repair return delivered to FlipFlop"
    response = client.post("/api/webhooks/parcel2go", json=payload)

    assert response.status_code == 200
    duplicate = client.post("/api/webhooks/parcel2go", json=payload)
    assert duplicate.status_code == 200
    assert duplicate.json()["status"] == "duplicate"
    async with session_factory() as db:
        problem = await db.get(CustomerProblem, problem_id)
        order = await db.get(Order, order_id)
        event = (await db.execute(select(ShipmentTrackingEvent))).scalar_one()
        portal_case = (await _customer_problem_outputs(db, [problem]))[0]

        assert problem.status == "received_for_inspection"
        assert problem.repair_tracking["latest_status_code"] == "delivered"
        assert event.customer_problem_id is None
        assert event.customer_problem_shipment_id == shipment_id
        assert event.order_id is None and event.manual_build_id is None
        assert event.occurred_at == delivered_at
        assert order.status == OrderStatus.COMPLETED
        assert portal_case.repair_shipments[0].events[0].description == "Repair return delivered to FlipFlop"
        assert portal_case.repair_shipments[0].events[0].occurred_at == delivered_at
        assert "repair_tracking_provider_reference" not in portal_case.model_dump()
        assert await db.scalar(select(func.count()).select_from(WarrantyReserve)) == 0
        assert await db.scalar(select(func.count()).select_from(ShipmentTrackingEvent)) == 1


@pytest.mark.asyncio
async def test_repair_case_retains_separate_inbound_and_outbound_tracking_timelines(
    delivery_webhook_client,
):
    client, session_factory, secret = delivery_webhook_client
    async with session_factory() as db:
        customer = Customer(id=705, name="Two Leg Buyer", email="two-leg@example.com")
        order = Order(
            order_id="FF-REPAIR-TWO-LEGS",
            customer_id=customer.id,
            specs={"build_name": "Two Leg Repair"},
            customer_price=1250,
            component_costs=950,
            overhead_amount=70,
            status=OrderStatus.COMPLETED,
        )
        db.add_all([customer, order])
        await db.flush()
        problem = CustomerProblem(
            order_id=order.id,
            customer_id=customer.id,
            category="warranty_claim",
            description="The PC shuts down unexpectedly under load.",
            status="return_in_transit",
        )
        db.add(problem)
        await db.flush()
        inbound = CustomerProblemShipment(
            customer_problem_id=problem.id,
            purpose="customer_return",
            carrier="Parcel2Go",
            tracking_number="INBOUND-1",
            tracking_url="https://carrier.example/inbound-1",
            provider="parcel2go",
            provider_reference="P2G-INBOUND-LINE-1",
        )
        outbound = CustomerProblemShipment(
            customer_problem_id=problem.id,
            purpose="replacement",
            carrier="Parcel2Go",
            tracking_number="OUTBOUND-1",
            tracking_url="https://carrier.example/outbound-1",
            provider="parcel2go",
            provider_reference="P2G-OUTBOUND-LINE-1",
        )
        db.add_all([inbound, outbound])
        await db.commit()
        problem_id = problem.id

    inbound_time = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0) - timedelta(minutes=15)
    inbound_payload = _signed_event(secret, event_id="two-leg-inbound-delivered", occurred_at=inbound_time)
    inbound_payload["Payload"]["OrderLineId"] = "P2G-INBOUND-LINE-1"
    inbound_payload["Payload"]["StatusDescription"] = "Returned PC delivered to FlipFlop"
    assert client.post("/api/webhooks/parcel2go", json=inbound_payload).status_code == 200

    async with session_factory() as db:
        problem = await db.get(CustomerProblem, problem_id)
        problem.status = "replacement_dispatched"
        await db.commit()

    outbound_time = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0) - timedelta(minutes=5)
    outbound_payload = _signed_event(secret, event_id="two-leg-outbound-delivered", occurred_at=outbound_time)
    outbound_payload["Payload"]["OrderLineId"] = "P2G-OUTBOUND-LINE-1"
    outbound_payload["Payload"]["StatusDescription"] = "Repaired PC delivered to customer"
    assert client.post("/api/webhooks/parcel2go", json=outbound_payload).status_code == 200

    async with session_factory() as db:
        problem = await db.get(CustomerProblem, problem_id)
        portal_case = (await _customer_problem_outputs(db, [problem]))[0]
        events = (await db.execute(select(ShipmentTrackingEvent))).scalars().all()
        assert problem.status == "replacement_dispatched"
        assert len(events) == 2
        assert len(portal_case.repair_shipments) == 2
        inbound_view, outbound_view = portal_case.repair_shipments
        assert inbound_view.purpose == "customer_return"
        assert [event.description for event in inbound_view.events] == ["Returned PC delivered to FlipFlop"]
        assert inbound_view.events[0].occurred_at == inbound_time
        assert outbound_view.purpose == "replacement"
        assert [event.description for event in outbound_view.events] == ["Repaired PC delivered to customer"]
        assert outbound_view.events[0].occurred_at == outbound_time
        assert "provider_reference" not in inbound_view.model_dump()
        assert "provider_reference" not in outbound_view.model_dump()


@pytest.mark.asyncio
async def test_delivered_direct_repair_return_email_retries_until_confirmed(
    delivery_webhook_client, monkeypatch,
):
    _, session_factory, _ = delivery_webhook_client
    async with session_factory() as db:
        customer = Customer(id=704, name="Repair Email Buyer", email="repair-email@example.com")
        order = Order(
            order_id="FF-REPAIR-EMAIL-1",
            customer_id=customer.id,
            specs={"build_name": "Repair Email Build"},
            customer_price=1100,
            component_costs=850,
            overhead_amount=60,
        )
        db.add_all([customer, order])
        await db.flush()
        problem = CustomerProblem(
            order_id=order.id,
            customer_id=customer.id,
            category="warranty_claim",
            description="The display output intermittently stops working.",
            status="received_for_inspection",
            repair_tracking={
                "purpose": "customer_return",
                "carrier": "Parcel2Go",
                "tracking_number": "P2G-RETURN-EMAIL-1",
                "tracking_url": "https://carrier.example/track/P2G-RETURN-EMAIL-1",
            },
        )
        db.add(problem)
        await db.flush()
        shipment = CustomerProblemShipment(
            customer_problem_id=problem.id,
            purpose="customer_return",
            carrier="Parcel2Go",
            tracking_number="P2G-RETURN-EMAIL-1",
            tracking_url="https://carrier.example/track/P2G-RETURN-EMAIL-1",
            provider="parcel2go",
            provider_reference="P2G-EMAIL-LINE-1",
        )
        db.add(shipment)
        await db.flush()
        event = ShipmentTrackingEvent(
            customer_problem_shipment_id=shipment.id,
            provider="parcel2go",
            provider_event_id="repair-return-email-event",
            status_code="delivered",
            description="Return delivered to FlipFlop",
            material=True,
            occurred_at=datetime.utcnow(),
        )
        db.add(event)
        await db.commit()
        event_id = event.id

    email_sender = AsyncMock(return_value=False)
    monkeypatch.setattr(parcel2go_notifications, "send_customer_case_status_email", email_sender)
    async with session_factory() as db:
        event = await db.get(ShipmentTrackingEvent, event_id)
        assert await notify_parcel2go_tracking_event_impl(db, event) is False
        assert event.customer_notified_at is None

    email_sender.return_value = True
    async with session_factory() as db:
        event = await db.get(ShipmentTrackingEvent, event_id)
        assert await notify_parcel2go_tracking_event_impl(db, event) is True
        assert event.customer_notified_at is not None
    assert email_sender.await_count == 2


@pytest.mark.asyncio
async def test_delivered_repair_shipment_notifies_direct_customer_without_resolving_case(
    delivery_webhook_client, monkeypatch,
):
    _, session_factory, _ = delivery_webhook_client
    async with session_factory() as db:
        customer = Customer(id=706, name="Replacement Buyer", email="replacement@example.com")
        order = Order(
            order_id="FF-REPAIR-REPLACEMENT-1",
            customer_id=customer.id,
            specs={"build_name": "Replacement Build"},
            customer_price=1100,
            component_costs=850,
            overhead_amount=60,
        )
        db.add_all([customer, order])
        await db.flush()
        problem = CustomerProblem(
            order_id=order.id,
            customer_id=customer.id,
            category="warranty_claim",
            description="The replacement system has been dispatched.",
            status="replacement_dispatched",
        )
        db.add(problem)
        await db.flush()
        shipment = CustomerProblemShipment(
            customer_problem_id=problem.id,
            purpose="replacement",
            carrier="Parcel2Go",
            tracking_number="P2G-REPLACEMENT-1",
            tracking_url="https://carrier.example/track/P2G-REPLACEMENT-1",
            provider="parcel2go",
            provider_reference="P2G-REPLACEMENT-LINE-1",
        )
        db.add(shipment)
        await db.flush()
        event = ShipmentTrackingEvent(
            customer_problem_shipment_id=shipment.id,
            provider="parcel2go",
            provider_event_id="repair-replacement-delivered-event",
            status_code="delivered",
            description="Replacement delivered to customer",
            material=True,
            occurred_at=datetime.utcnow(),
        )
        db.add(event)
        await db.commit()
        problem_id = problem.id
        event_id = event.id

    email_sender = AsyncMock(return_value=True)
    monkeypatch.setattr(parcel2go_notifications, "send_customer_case_status_email", email_sender)
    async with session_factory() as db:
        event = await db.get(ShipmentTrackingEvent, event_id)
        assert await notify_parcel2go_tracking_event_impl(db, event) is True
    assert email_sender.await_args.args[3] == "replacement_delivered"
    async with session_factory() as db:
        problem = await db.get(CustomerProblem, problem_id)
        event = await db.get(ShipmentTrackingEvent, event_id)
        assert problem.status == "replacement_dispatched"
        assert event.customer_notified_at is not None
