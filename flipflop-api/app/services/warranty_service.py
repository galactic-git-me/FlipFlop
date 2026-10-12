from __future__ import annotations

from datetime import datetime
import math

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.manual_build import ManualBuild
from app.models.order import Order
from app.models.customer_problem import CustomerProblem
from app.models.alert_event import AlertEvent
from app.models.warranty import WarrantyClaim, WarrantyReserve

OPEN_CLAIM_STATUSES = {
    "open", "reviewing", "approved", "awaiting_customer_return",
    "return_in_transit", "received_for_inspection", "repair_in_progress",
    "waiting_for_parts", "replacement_ordered", "replacement_dispatched",
}
WARRANTY_CASE_CATEGORIES = {"warranty", "warranty_claim", "repair", "technical_fault"}
DEFAULT_RESERVE_PCT = 5.0


def _reserve_percentage(value: float | int | str | None) -> float:
    """Apply the 5% per-build reserve floor to every sale."""
    if value is None:
        return DEFAULT_RESERVE_PCT
    percentage = float(value)
    if not math.isfinite(percentage):
        raise ValueError("Warranty reserve percentage must be finite")
    return min(25.0, max(DEFAULT_RESERVE_PCT, percentage))


async def lock_warranty_sale_owner(
    db: AsyncSession,
    *,
    order_id: int | None = None,
    manual_build_id: int | None = None,
    skip_locked: bool = False,
) -> Order | ManualBuild | None:
    """Lock the owning sale row before inserting a case or locking its reserve."""
    if (order_id is None) == (manual_build_id is None):
        raise ValueError("Provide exactly one warranty sale owner")
    if order_id is not None:
        return (await db.execute(
            select(Order)
            .where(Order.id == order_id)
            .with_for_update(skip_locked=skip_locked)
            .execution_options(populate_existing=True)
        )).scalar_one_or_none()
    return (await db.execute(
        select(ManualBuild)
        .where(ManualBuild.id == manual_build_id)
        .with_for_update(skip_locked=skip_locked)
        .execution_options(populate_existing=True)
    )).scalar_one_or_none()


async def lock_warranty_owner_then_reserve(
    db: AsyncSession,
    reserve_id: int,
    *,
    skip_locked: bool = False,
) -> WarrantyReserve | None:
    """Lock a reserve's owning sale first, then reload and lock the reserve."""
    reference = (await db.execute(
        select(WarrantyReserve.order_id, WarrantyReserve.manual_build_id)
        .where(WarrantyReserve.id == reserve_id)
    )).one_or_none()
    if reference is None:
        return None
    owner = await lock_warranty_sale_owner(
        db,
        order_id=reference.order_id,
        manual_build_id=reference.manual_build_id,
        skip_locked=skip_locked,
    )
    if owner is None:
        return None
    return (await db.execute(
        select(WarrantyReserve)
        .where(WarrantyReserve.id == reserve_id)
        .with_for_update(skip_locked=skip_locked)
        .execution_options(populate_existing=True)
    )).scalar_one_or_none()


async def lock_warranty_reserve_then_claim(
    db: AsyncSession,
    claim_id: int,
) -> tuple[WarrantyReserve | None, WarrantyClaim | None]:
    """Lock a claim's reserve before the claim so all mutation paths serialize with release."""
    reference = await db.get(WarrantyClaim, claim_id)
    if reference is None:
        return None, None
    reserve = (await db.execute(
        select(WarrantyReserve)
        .where(WarrantyReserve.id == reference.reserve_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )).scalar_one_or_none()
    claim = (await db.execute(
        select(WarrantyClaim)
        .where(WarrantyClaim.id == claim_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )).scalar_one_or_none()
    return reserve, claim


def _unlinked_warranty_cases_query(*, order_id: int | None = None, manual_build_id: int | None = None):
    query = (
        select(CustomerProblem)
        .outerjoin(WarrantyClaim, WarrantyClaim.customer_problem_id == CustomerProblem.id)
        .where(
            WarrantyClaim.id.is_(None),
            func.lower(func.trim(CustomerProblem.category)).in_(WARRANTY_CASE_CATEGORIES),
        )
    )
    if order_id is not None:
        return query.where(CustomerProblem.order_id == order_id)
    return query.where(CustomerProblem.manual_build_id == manual_build_id)


def _attach_case_to_reserve(db: Session | AsyncSession, reserve: WarrantyReserve, problem: CustomerProblem) -> None:
    claim_status = {
        "received": "open",
        "reviewing": "reviewing",
        "claim_opened": "open",
        "approved": "approved",
        "awaiting_customer_return": "awaiting_customer_return",
        "return_in_transit": "return_in_transit",
        "received_for_inspection": "received_for_inspection",
        "repair_in_progress": "repair_in_progress",
        "waiting_for_parts": "waiting_for_parts",
        "replacement_ordered": "replacement_ordered",
        "replacement_dispatched": "replacement_dispatched",
        "resolved": "resolved",
        "rejected": "rejected",
        "closed": "closed",
    }.get(problem.status, "open")
    reserve_claim = WarrantyClaim(
        reserve_id=reserve.id,
        customer_problem_id=problem.id,
        issue_summary=problem.description,
        status=claim_status,
        resolved_at=datetime.utcnow() if claim_status in {"resolved", "rejected", "closed"} else None,
    )
    db.add(reserve_claim)
    # A reserve that was already released is not silently reopened. The claim
    # still remains attached for aftercare review and may concern statutory rights.
    if claim_status in OPEN_CLAIM_STATUSES and reserve.status != "released":
        reserve.status = "claim_open"
        reserve.eligible_at = None


def _attach_unlinked_cases_sync(db: Session, reserve: WarrantyReserve) -> None:
    query = _unlinked_warranty_cases_query(order_id=reserve.order_id) if reserve.order_id else _unlinked_warranty_cases_query(manual_build_id=reserve.manual_build_id)
    query = query.with_for_update(of=CustomerProblem)
    for problem in db.execute(query).scalars().all():
        _attach_case_to_reserve(db, reserve, problem)


async def _attach_unlinked_cases(db: AsyncSession, reserve: WarrantyReserve) -> None:
    query = _unlinked_warranty_cases_query(order_id=reserve.order_id) if reserve.order_id else _unlinked_warranty_cases_query(manual_build_id=reserve.manual_build_id)
    query = query.with_for_update(of=CustomerProblem)
    for problem in (await db.execute(query)).scalars().all():
        _attach_case_to_reserve(db, reserve, problem)


def warranty_expiry(started_at: datetime) -> datetime:
    """Return the same calendar date next year, handling 29 February."""
    try:
        return started_at.replace(year=started_at.year + 1)
    except ValueError:
        return started_at.replace(year=started_at.year + 1, day=28)


def public_warranty_summary(
    reserve: WarrantyReserve | None,
    *,
    started_at: datetime | None = None,
    now: datetime | None = None,
) -> dict:
    # Customer coverage starts on delivery independently of whether finance
    # has enough confirmed sale data to create its reserve ledger entry.
    if reserve is None:
        if started_at is None:
            return {
                "status": "not_started",
                "started_at": None,
                "expires_at": None,
                "is_active": False,
                "message": "Your 12-month FlipFlop warranty starts when delivery is confirmed.",
            }
        warranty_started_at = started_at
        warranty_expires_at = warranty_expiry(started_at)
    else:
        warranty_started_at = reserve.warranty_started_at
        warranty_expires_at = reserve.warranty_expires_at
    current = now or datetime.utcnow()
    if current < warranty_started_at:
        return {
            "status": "not_started",
            "started_at": warranty_started_at.isoformat(),
            "expires_at": warranty_expires_at.isoformat(),
            "is_active": False,
            "message": (
                "Your 12-month FlipFlop warranty starts on "
                f"{warranty_started_at.date().isoformat()}, when delivery is confirmed."
            ),
        }
    active = warranty_started_at <= current < warranty_expires_at
    return {
        "status": "active" if active else "expired",
        "started_at": warranty_started_at.isoformat(),
        "expires_at": warranty_expires_at.isoformat(),
        "is_active": active,
        "message": (
            f"Your FlipFlop warranty is active until {warranty_expires_at.date().isoformat()}."
            if active else
            "The 12-month FlipFlop warranty period has ended. Your statutory rights are unaffected."
        ),
    }


def ensure_order_reserve_sync(db: Session, order: Order, started_at: datetime) -> WarrantyReserve:
    # Lock the sale row before checking for its reserve. Locking a missing
    # reserve row cannot serialize two first-delivery/case transactions.
    db.execute(select(Order.id).where(Order.id == order.id).with_for_update()).scalar_one()
    existing = db.query(WarrantyReserve).filter(
        WarrantyReserve.order_id == order.id
    ).with_for_update().first()
    if existing:
        if started_at < existing.warranty_started_at:
            existing.warranty_started_at = started_at
            existing.warranty_expires_at = warranty_expiry(started_at)
            if existing.status != "released":
                existing.status = "held"
                existing.eligible_at = None
        _attach_unlinked_cases_sync(db, existing)
        return existing
    pct = _reserve_percentage((order.specs or {}).get("warranty_reserve_pct"))
    sale_value = max(0.0, float(order.customer_price or 0))
    reserve = WarrantyReserve(
        order_id=order.id,
        sale_value_gbp=sale_value,
        reserve_pct=pct,
        reserved_amount_gbp=round(sale_value * pct / 100, 2),
        warranty_started_at=started_at,
        warranty_expires_at=warranty_expiry(started_at),
    )
    db.add(reserve)
    db.flush()
    _attach_unlinked_cases_sync(db, reserve)
    return reserve


async def ensure_order_reserve(db: AsyncSession, order: Order, started_at: datetime) -> WarrantyReserve:
    # Lock the sale row first so concurrent first-delivery/case transactions
    # cannot both observe a missing reserve and race its unique constraint.
    (await db.execute(select(Order.id).where(Order.id == order.id).with_for_update())).scalar_one()
    # Existing reserve locking also serializes claim attachment with the
    # explicit admin release path.
    existing = (await db.execute(
        select(WarrantyReserve).where(WarrantyReserve.order_id == order.id).with_for_update()
    )).scalar_one_or_none()
    if existing:
        if started_at < existing.warranty_started_at:
            existing.warranty_started_at = started_at
            existing.warranty_expires_at = warranty_expiry(started_at)
            if existing.status != "released":
                existing.status = "held"
                existing.eligible_at = None
        await _attach_unlinked_cases(db, existing)
        return existing
    pct = _reserve_percentage((order.specs or {}).get("warranty_reserve_pct"))
    sale_value = max(0.0, float(order.customer_price or 0))
    reserve = WarrantyReserve(
        order_id=order.id,
        sale_value_gbp=sale_value,
        reserve_pct=pct,
        reserved_amount_gbp=round(sale_value * pct / 100, 2),
        warranty_started_at=started_at,
        warranty_expires_at=warranty_expiry(started_at),
    )
    db.add(reserve)
    await db.flush()
    await _attach_unlinked_cases(db, reserve)
    return reserve


async def ensure_manual_build_reserve(
    db: AsyncSession, build: ManualBuild, started_at: datetime
) -> WarrantyReserve | None:
    # As with orders, lock the parent build before checking for a possibly
    # absent reserve. This serializes concurrent first-delivery/case writes.
    (await db.execute(select(ManualBuild.id).where(ManualBuild.id == build.id).with_for_update())).scalar_one()
    # Keep the parent -> reserve lock order consistent with order reserves.
    existing = (await db.execute(
        select(WarrantyReserve).where(WarrantyReserve.manual_build_id == build.id).with_for_update()
    )).scalar_one_or_none()
    raw_sale_value = build.sale_price_actual
    try:
        sale_value = float(raw_sale_value) if raw_sale_value is not None else 0.0
    except (TypeError, ValueError):
        sale_value = 0.0
    sale_value_is_confirmed = math.isfinite(sale_value) and sale_value > 0
    if existing:
        if started_at < existing.warranty_started_at:
            existing.warranty_started_at = started_at
            existing.warranty_expires_at = warranty_expiry(started_at)
            if existing.status != "released":
                existing.status = "held"
                existing.eligible_at = None
        await _attach_unlinked_cases(db, existing)
        if sale_value_is_confirmed and existing.status != "released" and existing.sale_value_gbp != sale_value:
            existing.sale_value_gbp = sale_value
            existing.reserved_amount_gbp = round(sale_value * existing.reserve_pct / 100, 2)
        elif sale_value_is_confirmed and existing.status == "released" and existing.sale_value_gbp != sale_value:
            code = f"warranty_sale_value_changed_after_release_{build.id}"
            alerted = await db.scalar(select(AlertEvent.id).where(AlertEvent.code == code).limit(1))
            if alerted is None:
                db.add(AlertEvent(
                    code=code,
                    source="warranty",
                    severity="critical",
                    message=(
                        f"Build {build.id} actual sale value differs from its released warranty reserve. "
                        "Review the reserve ledger and released amount."
                    ),
                    link_url="/warranty-reserves",
                ))
        return existing
    if not sale_value_is_confirmed:
        code = f"warranty_sale_value_missing_{build.id}"
        alerted = await db.scalar(select(AlertEvent.id).where(AlertEvent.code == code).limit(1))
        if alerted is None:
            db.add(AlertEvent(
                code=code,
                source="warranty",
                severity="warning",
                message=(
                    f"Build {build.id} was delivered, but its confirmed sale value is missing or invalid. "
                    "Record the actual sale price so its warranty reserve can be created or verified."
                ),
                link_url="/warranty-reserves",
            ))
        return None
    pct = _reserve_percentage(build.warranty_reserve_pct)
    reserve = WarrantyReserve(
        manual_build_id=build.id,
        sale_value_gbp=sale_value,
        reserve_pct=pct,
        reserved_amount_gbp=round(sale_value * pct / 100, 2),
        warranty_started_at=started_at,
        warranty_expires_at=warranty_expiry(started_at),
    )
    db.add(reserve)
    await db.flush()
    await _attach_unlinked_cases(db, reserve)
    return reserve


async def recalculate_reserve_status(db: AsyncSession, reserve: WarrantyReserve, *, now: datetime | None = None) -> str:
    if reserve.status == "released":
        return reserve.status
    claims = (await db.execute(select(WarrantyClaim).where(WarrantyClaim.reserve_id == reserve.id))).scalars().all()
    reserve.allocated_claim_amount_gbp = round(sum(max(0.0, claim.approved_cost_gbp or 0) for claim in claims), 2)
    if any(claim.status in OPEN_CLAIM_STATUSES for claim in claims):
        reserve.status = "claim_open"
        reserve.eligible_at = None
    elif (now or datetime.utcnow()) >= reserve.warranty_expires_at:
        reserve.status = "eligible_for_release"
        reserve.eligible_at = reserve.eligible_at or (now or datetime.utcnow())
    else:
        reserve.status = "held"
        reserve.eligible_at = None
    return reserve.status
