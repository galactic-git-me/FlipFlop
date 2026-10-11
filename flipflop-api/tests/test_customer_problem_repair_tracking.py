from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.customer_problem import CustomerProblem
from app.models.customer_problem_shipment import CustomerProblemShipment
from app.models.customer import Customer
from app.models.manual_build import ManualBuild
from app.models.order import Order
from app.models.portal_access_grant import PortalAccessGrant
from app.models.shipment_tracking_event import ShipmentTrackingEvent
from app.routes.auth import get_current_user
from app.routes.admin_auth import get_current_admin
from app.schemas.customer_portal import (
    CustomerProblemOut,
    CustomerProblemStatusUpdate,
    CustomerRepairTrackingEventOut,
)
from app.services.portal_access import create_guest_portal_token


@pytest.fixture
async def tracking_client():
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
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def override_admin():
        return SimpleNamespace(id=23, name="Warranty Admin")

    async def override_customer():
        return SimpleNamespace(id=41, name="Portal Customer", email="buyer@example.com")

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_admin] = override_admin
    app.dependency_overrides[get_current_user] = override_customer
    try:
        yield TestClient(app), session_factory
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()


@pytest.mark.asyncio
async def test_signed_in_order_portal_exposes_repair_tracking_only_for_owned_order(tracking_client):
    client, session_factory = tracking_client
    async with session_factory() as db:
        customer = Customer(id=41, name="Portal Customer", email="buyer@example.com")
        other_customer = Customer(id=42, name="Other Customer", email="other@example.com")
        db.add_all([customer, other_customer])
        await db.flush()
        order = Order(
            order_id="FF-PORTAL-TRACKING-1",
            customer_id=customer.id,
            specs={"build_name": "Tracked Build"},
            customer_price=900,
            component_costs=700,
            overhead_amount=50,
        )
        other_order = Order(
            order_id="FF-PORTAL-TRACKING-2",
            customer_id=other_customer.id,
            specs={"build_name": "Other Build"},
            customer_price=900,
            component_costs=700,
            overhead_amount=50,
        )
        db.add_all([order, other_order])
        await db.flush()
        order_id = order.id
        other_order_id = other_order.id
        db.add(CustomerProblem(
            order_id=order.id,
            customer_id=customer.id,
            category="warranty",
            description="The system shuts down during sustained load.",
            status="return_in_transit",
            repair_tracking={
                "purpose": "customer_return",
                "carrier": "Example Courier",
                "tracking_number": "TRACK-ORDER-123",
                "tracking_url": "https://carrier.example/track/TRACK-ORDER-123",
            },
            repair_tracking_audit=[{"updated_by_admin_id": 23, "note": "internal audit"}],
        ))
        await db.commit()

    response = client.get(f"/api/orders/{order_id}/problems")
    assert response.status_code == 200
    case = response.json()[0]
    assert case["repair_tracking"]["tracking_number"] == "TRACK-ORDER-123"
    assert "repair_tracking_audit" not in case

    cross_order = client.get(f"/api/orders/{other_order_id}/problems")
    assert cross_order.status_code == 404


def test_customer_case_response_exposes_tracking_but_not_admin_audit():
    case = SimpleNamespace(
        id=7,
        order_id=12,
        manual_build_id=None,
        category="warranty",
        description="The system shuts down under load.",
        status="return_in_transit",
        evidence=[],
        repair_tracking={
            "purpose": "customer_return",
            "carrier": "Example Courier",
            "tracking_number": "TRACK-123",
            "tracking_url": "https://carrier.example/track/TRACK-123",
            "internal_admin_note": "never expose this value",
        },
        repair_tracking_audit=[{"updated_by_admin_id": 3, "note": "verified"}],
        created_at="2026-09-29T10:00:00",
        updated_at="2026-09-29T11:00:00",
    )

    response = CustomerProblemOut.model_validate(case)
    payload = response.model_dump()
    assert payload["repair_tracking"]["tracking_number"] == "TRACK-123"
    assert "internal_admin_note" not in payload["repair_tracking"]
    assert "repair_tracking_audit" not in payload

    unsafe = CustomerProblemOut.model_validate(SimpleNamespace(
        id=8,
        order_id=12,
        manual_build_id=None,
        category="warranty",
        description="A legacy record with an unsafe URL.",
        status="return_in_transit",
        evidence=[],
        repair_tracking={
            "purpose": "customer_return",
            "carrier": "Example Courier",
            "tracking_number": "TRACK-UNSAFE",
            "tracking_url": "https://buyer:secret@carrier.example/track/TRACK-UNSAFE",
        },
        repair_tracking_audit=[],
        created_at="2026-09-29T10:00:00",
        updated_at="2026-09-29T11:00:00",
    ))
    assert unsafe.repair_tracking.tracking_url is None

    overlong = CustomerProblemOut.model_validate(SimpleNamespace(
        id=9,
        order_id=12,
        manual_build_id=None,
        category="warranty",
        description="A legacy record with an overlong tracking URL.",
        status="return_in_transit",
        evidence=[],
        repair_tracking={
            "purpose": "customer_return",
            "carrier": "Example Courier",
            "tracking_number": "TRACK-LONG",
            "tracking_url": "https://carrier.example/" + "x" * 1100,
        },
        repair_tracking_audit=[],
        created_at="2026-09-29T10:00:00",
        updated_at="2026-09-29T11:00:00",
    ))
    assert overlong.repair_tracking.tracking_url is None
    event = CustomerRepairTrackingEventOut.model_validate({
        "status_code": "in_transit",
        "description": "Parcel in transit",
        "occurred_at": "2026-09-29T10:00:00",
        "tracking_url": "https://carrier.example/" + "x" * 1100,
    })
    assert event.tracking_url is None


def test_repair_tracking_contract_rejects_non_https_links():
    with pytest.raises(ValidationError):
        CustomerProblemStatusUpdate(
            status="return_in_transit",
            repair_tracking_purpose="customer_return",
            repair_carrier="Example Courier",
            repair_tracking_number="TRACK-123",
            repair_tracking_url="http://carrier.example/track/TRACK-123",
            repair_tracking_note="Verified against carrier receipt",
        )


def test_repair_tracking_contract_rejects_embedded_url_credentials():
    with pytest.raises(ValidationError, match="cannot contain embedded credentials"):
        CustomerProblemStatusUpdate(
            status="return_in_transit",
            repair_tracking_purpose="customer_return",
            repair_carrier="Example Courier",
            repair_tracking_number="TRACK-123",
            repair_tracking_url="https://buyer:secret@carrier.example/track/TRACK-123",
            repair_tracking_note="Verified against carrier receipt",
        )


@pytest.mark.asyncio
async def test_admin_repair_tracking_is_stage_bound_and_audited(tracking_client):
    client, session_factory = tracking_client
    async with session_factory() as db:
        build = ManualBuild(name="Warranty tracking test build")
        db.add(build)
        await db.flush()
        problem = CustomerProblem(
            manual_build_id=build.id,
            category="warranty",
            description="The PC powers off unexpectedly under sustained load.",
            status="approved",
        )
        db.add(problem)
        await db.commit()
        await db.refresh(problem)
        problem_id = problem.id
        support_problem = CustomerProblem(
            manual_build_id=build.id,
            category="technical_question",
            description="A question about the setup instructions.",
            status="received",
        )
        db.add(support_problem)
        await db.commit()
        await db.refresh(support_problem)
        support_problem_id = support_problem.id

    payload = {
        "status": "return_in_transit",
        "repair_tracking_purpose": "customer_return",
        "repair_carrier": "Parcel2Go",
        "repair_tracking_number": "TRACK-123",
        "repair_tracking_url": "https://carrier.example/track/TRACK-123",
        "repair_tracking_provider_reference": "P2G-REPAIR-LINE-23",
        "repair_tracking_note": "Verified against the purchased return label.",
    }
    wrong_stage = client.patch(
        f"/api/admin/customer-problems/{problem_id}",
        json={**payload, "status": "repair_in_progress"},
    )
    assert wrong_stage.status_code == 422
    wrong_category = client.patch(
        f"/api/admin/customer-problems/{support_problem_id}",
        json=payload,
    )
    assert wrong_category.status_code == 422

    response = client.patch(f"/api/admin/customer-problems/{problem_id}", json=payload)
    assert response.status_code == 200
    assert response.json()["repair_tracking"]["tracking_number"] == "TRACK-123"
    assert response.json()["repair_shipments"][0]["provider_reference"] == "P2G-REPAIR-LINE-23"
    assert "repair_tracking_audit" not in response.json()
    async with session_factory() as db:
        stored = await db.get(CustomerProblem, problem_id)
        assert stored.repair_tracking_audit[-1]["updated_by_admin_id"] == 23
        assert stored.repair_tracking_audit[-1]["note"] == payload["repair_tracking_note"]
        assert stored.repair_tracking_provider is None
        assert stored.repair_tracking_provider_reference is None
        shipment = (await db.execute(select(CustomerProblemShipment).where(
            CustomerProblemShipment.customer_problem_id == problem_id
        ))).scalar_one()
        assert shipment.purpose == "customer_return"
        assert shipment.provider_reference == "P2G-REPAIR-LINE-23"
        db.add(ShipmentTrackingEvent(
            customer_problem_shipment_id=shipment.id,
            provider="parcel2go",
            provider_event_id="repair-ref-lock-event",
            status_code="in_transit",
            description="Courier collected the parcel",
            occurred_at=datetime.utcnow(),
        ))
        await db.flush()
        grant = PortalAccessGrant(
            manual_build_id=stored.manual_build_id,
            contact_email="buyer@example.com",
            token_hash="a" * 64,
            channel="marketplace",
            expires_at=datetime.utcnow() + timedelta(days=30),
            claimed_at=datetime.utcnow(),
        )
        db.add(grant)
        await db.flush()
        guest_token = create_guest_portal_token(grant)
        await db.commit()

    locked_reference = client.patch(
        f"/api/admin/customer-problems/{problem_id}",
        json={**payload, "repair_tracking_provider_reference": "P2G-OTHER-LINE-99"},
    )
    assert locked_reference.status_code == 409

    customer_cases = client.get(
        "/api/orders/guest-portal/problems",
        headers={"Authorization": f"Bearer {guest_token}"},
    )
    assert customer_cases.status_code == 200
    portal_case = customer_cases.json()[0]
    assert portal_case["repair_tracking"]["tracking_number"] == "TRACK-123"
    assert portal_case["repair_shipments"][0]["purpose"] == "customer_return"
    assert "provider_reference" not in portal_case["repair_shipments"][0]
    assert "repair_tracking_provider_reference" not in portal_case
    assert "repair_tracking_audit" not in portal_case
