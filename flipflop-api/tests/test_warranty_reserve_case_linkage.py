"""Unexecuted coverage for support cases linked to delivery-time reserves."""

from datetime import datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.alert_event import AlertEvent
from app.models.customer_problem import CustomerProblem
from app.models.manual_build import ManualBuild
from app.models.order import Order
from app.models.warranty import WarrantyClaim, WarrantyReserve
from app.services.warranty_service import (
    _reserve_percentage,
    ensure_order_reserve,
    ensure_order_reserve_sync,
    ensure_manual_build_reserve,
    lock_warranty_reserve_then_claim,
    lock_warranty_owner_then_reserve,
    warranty_expiry,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, 5.0), (0, 5.0), (2.5, 5.0), (5, 5.0), (8.5, 8.5), (30, 25.0)],
)
def test_reserve_percentage_enforces_floor_and_ceiling(value, expected):
    assert _reserve_percentage(value) == expected


@pytest.mark.parametrize("value", ["nan", "inf", "-inf"])
def test_reserve_percentage_rejects_non_finite_values(value):
    with pytest.raises(ValueError, match="finite"):
        _reserve_percentage(value)


def test_warranty_expiry_preserves_delivery_time_across_leap_day():
    assert warranty_expiry(datetime(2024, 2, 29, 14, 30)) == datetime(2025, 2, 28, 14, 30)


@pytest.mark.asyncio
async def test_warranty_lock_helper_requests_reserve_lock_before_claim_lock():
    class Result:
        def __init__(self, value):
            self.value = value

        def scalar_one_or_none(self):
            return self.value

    class RecordingSession:
        def __init__(self):
            self.statements = []

        async def get(self, model, _claim_id):
            assert model is WarrantyClaim
            return SimpleNamespace(id=7, reserve_id=19)

        async def execute(self, statement):
            self.statements.append(statement)
            model = statement.column_descriptions[0]["entity"]
            return Result(SimpleNamespace(id=19) if model is WarrantyReserve else SimpleNamespace(id=7))

    db = RecordingSession()
    reserve, claim = await lock_warranty_reserve_then_claim(db, 7)

    assert reserve.id == 19
    assert claim.id == 7
    assert [statement.column_descriptions[0]["entity"] for statement in db.statements] == [
        WarrantyReserve,
        WarrantyClaim,
    ]
    compiled = [str(statement.compile(dialect=postgresql.dialect())).casefold() for statement in db.statements]
    assert all(" for update" in statement for statement in compiled)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("owner_model", "order_id", "manual_build_id"),
    [(Order, 23, None), (ManualBuild, None, 23)],
)
async def test_reserve_release_helper_locks_sale_owner_before_reserve(
    owner_model, order_id, manual_build_id,
):
    class Result:
        def __init__(self, value):
            self.value = value

        def one_or_none(self):
            return self.value

        def scalar_one_or_none(self):
            return self.value

    owner = SimpleNamespace(id=23)
    reserve = SimpleNamespace(id=19)

    class RecordingSession:
        def __init__(self):
            self.statements = []

        async def execute(self, statement):
            self.statements.append(statement)
            if len(self.statements) == 1:
                return Result(SimpleNamespace(order_id=order_id, manual_build_id=manual_build_id))
            if statement.column_descriptions[0]["entity"] is owner_model:
                return Result(owner)
            return Result(reserve)

    db = RecordingSession()
    locked_reserve = await lock_warranty_owner_then_reserve(db, 19)

    assert locked_reserve is reserve
    assert db.statements[1].column_descriptions[0]["entity"] is owner_model
    assert db.statements[2].column_descriptions[0]["entity"] is WarrantyReserve
    compiled = [str(statement.compile(dialect=postgresql.dialect())).casefold() for statement in db.statements]
    assert " for update" not in compiled[0]
    assert " for update" in compiled[1]
    assert " for update" in compiled[2]


async def _order_with_customer(db: AsyncSession) -> Order:
    customer = Customer(email="reserve@example.com", name="Reserve Test")
    db.add(customer)
    await db.flush()
    order = Order(
        order_id="FF-RESERVE-CASE-TEST",
        customer_id=customer.id,
        specs={},
        customer_price=1000,
        component_costs=800,
        overhead_amount=50,
    )
    db.add(order)
    await db.flush()
    return order


@pytest.mark.asyncio
async def test_manual_build_reserve_requires_confirmed_sale_value_and_reconciles_later(db: AsyncSession):
    build = ManualBuild(
        name="Marketplace build",
        status="sold",
        ebay_price=1000,
        sale_price_actual=None,
    )
    db.add(build)
    await db.flush()

    started_at = datetime(2026, 9, 29, 12)
    assert await ensure_manual_build_reserve(db, build, started_at) is None
    assert await db.scalar(select(func.count()).select_from(WarrantyReserve)) == 0
    alert = await db.scalar(select(AlertEvent).where(AlertEvent.code == f"warranty_sale_value_missing_{build.id}"))
    assert alert is not None

    build.sale_price_actual = 800
    reserve = await ensure_manual_build_reserve(db, build, started_at)
    assert reserve is not None
    assert reserve.sale_value_gbp == 800
    assert reserve.reserved_amount_gbp == 40

    build.sale_price_actual = 850
    updated = await ensure_manual_build_reserve(db, build, started_at)
    assert updated is reserve
    assert reserve.sale_value_gbp == 850
    assert reserve.reserved_amount_gbp == 42.5


@pytest.mark.asyncio
async def test_open_pre_delivery_warranty_case_attaches_and_holds_new_reserve(db: AsyncSession):
    order = await _order_with_customer(db)
    problem = CustomerProblem(
        order_id=order.id,
        category="technical_fault",
        description="The system shuts down during normal use.",
        status="received",
    )
    db.add(problem)
    await db.flush()

    started_at = datetime(2026, 9, 29, 12)
    reserve = await ensure_order_reserve(db, order, started_at)
    repeated_reserve = await ensure_order_reserve(db, order, started_at)
    claims = (await db.execute(
        select(WarrantyClaim).where(WarrantyClaim.customer_problem_id == problem.id)
    )).scalars().all()

    assert repeated_reserve.id == reserve.id
    assert len(claims) == 1
    assert claims[0].reserve_id == reserve.id
    assert claims[0].status == "open"
    assert reserve.status == "claim_open"
    assert reserve.eligible_at is None


@pytest.mark.asyncio
async def test_order_reserve_enforces_five_percent_minimum(db: AsyncSession):
    order = await _order_with_customer(db)
    order.specs = {"warranty_reserve_pct": 0}

    reserve = await ensure_order_reserve(db, order, datetime(2026, 9, 29, 12))

    assert reserve.reserve_pct == 5
    assert reserve.reserved_amount_gbp == 50


@pytest.mark.asyncio
async def test_non_warranty_support_case_does_not_attach_to_or_hold_reserve(db: AsyncSession):
    order = await _order_with_customer(db)
    problem = CustomerProblem(
        order_id=order.id,
        category="delivery_missing",
        description="The courier has not delivered the parcel.",
        status="received",
    )
    db.add(problem)
    await db.flush()

    reserve = await ensure_order_reserve(db, order, datetime(2026, 9, 29, 12))
    claims = (await db.execute(
        select(WarrantyClaim).where(WarrantyClaim.customer_problem_id == problem.id)
    )).scalars().all()

    assert claims == []
    assert reserve.status == "held"


def test_sync_delivery_reserve_reconciliation_is_idempotent_and_attaches_cases(db: Session):
    customer = Customer(email="sync-reserve@example.com", name="Sync Reserve Test")
    db.add(customer)
    db.flush()
    order = Order(
        order_id="FF-SYNC-RESERVE-TEST",
        customer_id=customer.id,
        specs={},
        customer_price=900,
        component_costs=700,
        overhead_amount=50,
    )
    db.add(order)
    db.flush()
    problem = CustomerProblem(
        order_id=order.id,
        category="repair",
        description="The build does not start reliably.",
        status="received",
    )
    db.add(problem)
    db.flush()

    started_at = datetime(2026, 9, 29, 12)
    reserve = ensure_order_reserve_sync(db, order, started_at)
    retried = ensure_order_reserve_sync(db, order, started_at)

    assert retried.id == reserve.id
    claim = db.execute(
        select(WarrantyClaim).where(WarrantyClaim.customer_problem_id == problem.id)
    ).scalar_one()
    assert claim.reserve_id == reserve.id
    assert reserve.status == "claim_open"
