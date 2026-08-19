from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta, date
from app.database import get_db
from app.models import Order, BuildCapacity, BuildCapacityOverride
from app.models.customer import Customer
from app.routes.auth import get_current_user
from app.routes.admin_auth import get_current_admin
from app.schemas.order import (
    CapacitySlotsOut,
    AdminOrderOut,
    AdminOrderUpdateIn,
    BuildCapacityOut,
    CapacityOverrideIn,
    MyOrderOut,
    MyOrderSlotOut,
)

router = APIRouter(prefix="/api/orders", tags=["orders"])


def _order_to_my_order_out(order: Order) -> MyOrderOut:
    specs = order.specs or {}
    carrier = (order.carrier or "").strip()
    tracking_url = None
    carrier_urls = {
        "royal_mail": "https://www.royalmail.com/track-your-item#/tracking-results/{}",
        "parcelforce": "https://www.parcelforce.com/track-trace?trackNumber={}",
        "dpd": "https://track.dpd.co.uk/parcels/{}",
        "ups": "https://www.ups.com/track?loc=en_GB&tracknum={}",
        "dhl": "https://www.dhl.com/gb-en/home/tracking/tracking-express.html?submit=1&tracking-id={}",
        "fedex": "https://www.fedex.com/fedextrack/?trknbr={}",
    }
    if order.tracking_number:
        template = carrier_urls.get(carrier.lower().replace(" ", "_"))
        tracking_url = template.format(order.tracking_number) if template else None
    return MyOrderOut(
        id=order.id,
        order_id=order.order_id,
        status=order.status.value if hasattr(order.status, "value") else str(order.status),
        customer_price=order.customer_price,
        component_costs=order.component_costs,
        slots=[MyOrderSlotOut(**s) for s in specs.get("slots", [])],
        case_name=specs.get("case_name"),
        case_price=specs.get("case_price", 0.0),
        chosen_week=specs.get("chosen_week"),
        promised_delivery_date=order.promised_delivery_date,
        actual_delivery_date=order.actual_delivery_date,
        estimated_delivery=order.estimated_delivery,
        shipped_at=order.shipped_at,
        delivered_at=order.delivered_at,
        tracking_number=order.tracking_number,
        carrier=carrier or None,
        tracking_url=tracking_url,
        live_tracking_available=False,
        created_at=order.created_at,
    )


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


@router.get("/me", response_model=list[MyOrderOut])
async def list_my_orders(
    customer: Customer = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """The logged-in customer's own orders — real fields only, no fabricated
    reference/playbook_name/etc."""
    result = await db.execute(
        select(Order)
        .where(Order.customer_id == customer.id)
        .order_by(Order.created_at.desc())
    )
    return [_order_to_my_order_out(o) for o in result.scalars().all()]


@router.get("/{order_id}", response_model=MyOrderOut)
async def get_my_order(
    order_id: int,
    customer: Customer = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """A single order — scoped to the requesting customer. Deliberately not
    a public by-reference lookup (the old one was schema-incompatible and
    would have leaked other customers' orders to anyone with a reference)."""
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order or order.customer_id != customer.id:
        raise HTTPException(status_code=404, detail="Order not found")
    return _order_to_my_order_out(order)


admin_router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(get_current_admin)])


@admin_router.get("/orders", response_model=list[AdminOrderOut])
async def list_orders(
    status: str = None,
    week: str = None,
    email: str = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """List orders with optional filtering"""
    query = select(Order)

    if status:
        query = query.where(Order.status == status)
    if week:
        query = query.where(Order.assigned_build_week == week)
    if email:
        query = query.where(Order.customer_email.ilike(f"%{email}%"))

    query = query.order_by(Order.created_at.desc()).offset(offset).limit(limit)

    result = await db.execute(query)
    return result.scalars().all()


@admin_router.patch("/orders/{order_id}", response_model=AdminOrderOut)
async def update_order(
    order_id: int,
    update: AdminOrderUpdateIn,
    db: AsyncSession = Depends(get_db),
):
    """Update order status or notes"""
    order_result = await db.execute(
        select(Order).where(Order.id == order_id)
    )
    order = order_result.scalar()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if update.status:
        order.status = update.status
    if update.note is not None:
        pass

    order.updated_at = datetime.utcnow()
    await db.commit()

    return order


@admin_router.get("/capacity", response_model=BuildCapacityOut)
async def get_capacity(db: AsyncSession = Depends(get_db)):
    """Get global default capacity"""
    capacity_result = await db.execute(select(BuildCapacity).limit(1))
    capacity = capacity_result.scalar()

    if not capacity:
        return BuildCapacityOut(default_per_week=3)

    return capacity


@admin_router.patch("/capacity/default")
async def update_capacity_default(
    default_per_week: int,
    db: AsyncSession = Depends(get_db),
):
    """Update global default capacity"""
    capacity_result = await db.execute(select(BuildCapacity).limit(1))
    capacity = capacity_result.scalar()

    if not capacity:
        capacity = BuildCapacity(default_per_week=default_per_week)
        db.add(capacity)
    else:
        capacity.default_per_week = default_per_week

    capacity.updated_at = datetime.utcnow()
    await db.commit()

    return BuildCapacityOut(default_per_week=capacity.default_per_week)


@admin_router.put("/capacity/overrides/{week}")
async def set_capacity_override(
    week: str,
    override: CapacityOverrideIn,
    db: AsyncSession = Depends(get_db),
):
    """Set or remove week override (null max_builds = week closed)"""
    override_result = await db.execute(
        select(BuildCapacityOverride).where(BuildCapacityOverride.week == week)
    )
    existing = override_result.scalar()

    if existing:
        existing.max_builds = override.max_builds
        existing.note = override.note
    else:
        existing = BuildCapacityOverride(
            week=week,
            max_builds=override.max_builds,
            note=override.note,
        )
        db.add(existing)

    await db.commit()

    return {
        "week": existing.week,
        "max_builds": existing.max_builds,
        "note": existing.note,
    }
