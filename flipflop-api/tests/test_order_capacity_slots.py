"""The public slot count uses the current paid-order and hold records."""
from datetime import date, datetime, timedelta, timezone

import pytest

from app.api.orders import get_available_slots, get_iso_week
from app.models.build_capacity import BuildCapacity
from app.models.commerce_evidence import (
    PriceQuoteSnapshot, WorkshopCapacityEvidence, WorkshopCapacityReservation,
)
from app.models.customer import Customer
from app.models.order import Order, OrderStatus


@pytest.mark.asyncio
async def test_slots_subtract_paid_order_and_active_hold(db):
    now = datetime.now(timezone.utc)
    future = date.today() + timedelta(days=14)
    monday = future - timedelta(days=future.weekday())
    week = get_iso_week(monday)

    customer = Customer(email="slots@example.test", name="Slot Customer")
    db.add(customer)
    await db.flush()
    db.add_all([
        BuildCapacity(default_per_week=3),
        Order(
            order_id="slots-paid-order", customer_id=customer.id,
            specs={"chosen_week": week}, customer_price=1000,
            component_costs=700, overhead_amount=100,
            status=OrderStatus.AWAITING_SOURCING,
        ),
    ])
    evidence = WorkshopCapacityEvidence(
        build_week=week, available_builds=3, observed_at=now,
        evidence_source="test", evidence_ref="test-week", captured_by_admin_id=1,
    )
    quote = PriceQuoteSnapshot(
        product_key="test-build", status="offerable", evidence_json={},
        decision_json={"offerable": True}, created_by_admin_id=1,
    )
    db.add_all([evidence, quote])
    await db.flush()
    db.add(WorkshopCapacityReservation(
        quote_snapshot_id=quote.id, capacity_evidence_id=evidence.id,
        build_week=week, status="held", expires_at=now + timedelta(minutes=15),
        created_by_admin_id=1,
    ))
    await db.flush()

    slots = await get_available_slots(db)
    selected = next(slot for slot in slots if slot.week == week)
    assert selected.capacity == 3
    assert selected.available == 1


@pytest.mark.asyncio
async def test_slots_require_current_workshop_evidence(db):
    db.add(BuildCapacity(default_per_week=3))
    await db.flush()

    assert await get_available_slots(db) == []
