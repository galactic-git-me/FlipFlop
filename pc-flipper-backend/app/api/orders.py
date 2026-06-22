from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy import func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta, date
from app.database import get_db
from app.models import Order, BuildCapacity, BuildCapacityOverride
from app.schemas.order import (
    CapacitySlotsOut,
    OrderCheckoutRequest,
    OrderCheckoutResponse,
    OrderConfirmationOut,
)
from app.services.stripe_service import create_checkout_session
import random
import string

router = APIRouter(prefix="/api/orders", tags=["orders"])


async def generate_unique_reference(db: AsyncSession) -> str:
    """Generate unique order reference in format FF-YYYY-NNNNN"""
    max_attempts = 10
    for _ in range(max_attempts):
        year = date.today().year
        random_suffix = "".join(random.choices(string.digits, k=5))
        reference = f"FF-{year}-{random_suffix}"

        existing = await db.execute(
            select(Order).where(Order.reference == reference)
        )
        if not existing.scalar():
            return reference

    raise RuntimeError("Could not generate unique reference after max attempts")


def get_iso_week(dt: date) -> str:
    """Returns ISO week string format: YYYY-Www"""
    iso_calendar = dt.isocalendar()
    return f"{iso_calendar[0]}-W{iso_calendar[1]:02d}"


def parse_iso_week(week_str: str) -> date:
    """Parses ISO week string to Monday of that week"""
    year, week = week_str.split("-W")
    d = datetime.strptime(f"{year}-W{int(week)}-1", "%Y-W%W-%w")
    return d.date()


async def count_business_days_until(from_date: date, to_date: date) -> int:
    """Count business days (Mon-Fri) between from_date (exclusive) and to_date (inclusive)"""
    count = 0
    current = from_date + timedelta(days=1)
    while current <= to_date:
        if current.weekday() < 5:
            count += 1
        current += timedelta(days=1)
    return count


@router.get("/slots", response_model=list[CapacitySlotsOut])
async def get_available_slots(db: AsyncSession = Depends(get_db)):
    """
    Returns next 8 weeks with available build slots.
    Excludes weeks within 5 business days.
    Excludes weeks with 0 available capacity.
    """
    today = date.today()

    capacity_result = await db.execute(select(BuildCapacity).limit(1))
    build_capacity = capacity_result.scalar()
    if not build_capacity:
        default_capacity = 3
    else:
        default_capacity = build_capacity.default_per_week

    result = []

    for i in range(16):
        current_date = today + timedelta(weeks=i)
        week_start = current_date - timedelta(days=current_date.weekday())
        week_str = get_iso_week(week_start)

        business_days_until = await count_business_days_until(today, week_start)
        if business_days_until < 5:
            continue

        override_result = await db.execute(
            select(BuildCapacityOverride).where(BuildCapacityOverride.week == week_str)
        )
        override = override_result.scalar()

        if override and override.max_builds is None:
            continue

        capacity = override.max_builds if override else default_capacity

        booked_result = await db.execute(
            select(func.count(Order.id)).where(
                and_(
                    Order.assigned_build_week == week_str,
                    Order.status.in_(["confirmed", "building", "shipped"]),
                )
            )
        )
        booked_count = booked_result.scalar() or 0

        available = max(0, capacity - booked_count)

        if available > 0:
            result.append(
                CapacitySlotsOut(
                    week=week_str,
                    week_start=week_start.isoformat(),
                    available=available,
                    capacity=capacity,
                )
            )

        if len(result) >= 8:
            break

    return result


@router.post("/checkout", response_model=OrderCheckoutResponse)
async def create_checkout(
    request: OrderCheckoutRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create order and return Stripe checkout URL"""
    week_str = request.chosen_week
    week_start = parse_iso_week(week_str)

    capacity_result = await db.execute(select(BuildCapacity).limit(1))
    build_capacity = capacity_result.scalar()
    default_capacity = build_capacity.default_per_week if build_capacity else 3

    override_result = await db.execute(
        select(BuildCapacityOverride).where(BuildCapacityOverride.week == week_str)
    )
    override = override_result.scalar()

    if override and override.max_builds is None:
        raise HTTPException(status_code=409, detail="Week is closed")

    capacity = override.max_builds if override else default_capacity

    booked_result = await db.execute(
        select(func.count(Order.id)).where(
            and_(
                Order.assigned_build_week == week_str,
                Order.status.in_(["confirmed", "building", "shipped"]),
            )
        )
    )
    booked_count = booked_result.scalar() or 0

    if booked_count >= capacity:
        raise HTTPException(status_code=409, detail="Week is fully booked")

    reference = await generate_unique_reference(db)

    subtotal = sum(
        slot_data.get("display_price", 0)
        for slot_type, slot_data in request.build_config.items()
        if slot_type != "case" and isinstance(slot_data, dict)
    )
    if "case" in request.build_config:
        subtotal += request.build_config["case"].get("rrp", 0)

    tax = 0.0
    total = subtotal + tax

    order = Order(
        reference=reference,
        playbook_id=request.playbook_id,
        playbook_name="",
        build_config=request.build_config,
        customer_name=request.customer_name,
        customer_email=request.customer_email,
        delivery_address=request.delivery_address.dict(),
        subtotal_gbp=subtotal,
        tax_gbp=tax,
        total_gbp=total,
        status="pending_payment",
    )
    db.add(order)
    await db.flush()

    try:
        stripe_url = create_checkout_session(
            order_reference=reference,
            build_config=request.build_config,
            customer_email=request.customer_email,
            total_gbp=total,
            success_url=f"http://andromeda-ts:3001/order/{reference}",
            cancel_url=f"http://andromeda-ts:3001/configure/gaming-rig",
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Stripe error: {str(e)}")

    order.stripe_session_id = stripe_url.split("session_id=")[-1] if "session_id=" in stripe_url else ""
    await db.commit()

    return OrderCheckoutResponse(reference=reference, stripe_url=stripe_url)
