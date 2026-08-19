from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta, date
from app.database import get_db
from app.models import Order, BuildCapacity, BuildCapacityOverride, CustomerProblem, CXDocument, Capture3DAsset, Capture3DStatus
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
from app.schemas.customer_portal import CustomerDocumentOut, CustomerProblemCreate, CustomerProblemOut, CustomerProblemStatusUpdate
from jose import jwt, JWTError
from app.config import get_settings

router = APIRouter(prefix="/api/orders", tags=["orders"])

@router.get("/portal-preview/{preview_token}")
async def get_portal_preview(preview_token: str, db: AsyncSession = Depends(get_db)):
    try:
        claims = jwt.decode(preview_token, get_settings().secret_key, algorithms=[get_settings().jwt_algorithm])
    except JWTError:
        raise HTTPException(status_code=401, detail="Preview expired or invalid")
    if claims.get("typ") != "portal_preview" or claims.get("scope") != "read":
        raise HTTPException(status_code=403, detail="Invalid preview scope")
    order = (await db.execute(select(Order).where(Order.id == int(claims.get("order_id", 0))))).scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    asset = (await db.execute(select(Capture3DAsset).where(Capture3DAsset.order_id == order.id))).scalar_one_or_none()
    return _order_to_my_order_out(order, asset)


def _order_to_my_order_out(order: Order, capture_3d: Capture3DAsset | None = None) -> MyOrderOut:
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
        capture_3d=(
            {"status": capture_3d.status.value if hasattr(capture_3d.status, "value") else str(capture_3d.status),
             "optimized_asset_ref": capture_3d.optimized_asset_ref,
             "preview_image_ref": capture_3d.preview_image_ref,
             "ar_ready": bool(capture_3d.ar_ready)}
            if capture_3d and capture_3d.status == Capture3DStatus.PUBLISHED and capture_3d.optimized_asset_ref else None
        ),
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
    orders = result.scalars().all()
    assets = (await db.execute(select(Capture3DAsset).where(Capture3DAsset.order_id.in_([o.id for o in orders])))).scalars().all() if orders else []
    assets_by_order = {asset.order_id: asset for asset in assets}
    return [_order_to_my_order_out(o, assets_by_order.get(o.id)) for o in orders]


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
    asset = (await db.execute(select(Capture3DAsset).where(Capture3DAsset.order_id == order.id))).scalar_one_or_none()
    return _order_to_my_order_out(order, asset)


async def _owned_order(order_id: int, customer: Customer, db: AsyncSession) -> Order:
    result = await db.execute(select(Order).where(Order.id == order_id, Order.customer_id == customer.id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.get("/{order_id}/documents", response_model=list[CustomerDocumentOut])
async def list_my_order_documents(
    order_id: int,
    customer: Customer = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return only generated documents belonging to the signed-in customer's order."""
    await _owned_order(order_id, customer, db)
    result = await db.execute(select(CXDocument).where(CXDocument.order_id == order_id).order_by(CXDocument.created_at.desc()))
    return [CustomerDocumentOut(
        id=document.id,
        document_type=document.document_type.value if hasattr(document.document_type, "value") else str(document.document_type),
        status=document.status.value if hasattr(document.status, "value") else str(document.status),
        version=document.version or 1,
        pdf_url=document.pdf_url,
        generated_at=document.generated_at,
    ) for document in result.scalars().all()]


@router.get("/{order_id}/problems", response_model=list[CustomerProblemOut])
async def list_my_order_problems(
    order_id: int,
    customer: Customer = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _owned_order(order_id, customer, db)
    result = await db.execute(select(CustomerProblem).where(CustomerProblem.order_id == order_id).order_by(CustomerProblem.created_at.desc()))
    return list(result.scalars().all())


@router.post("/{order_id}/problems", response_model=CustomerProblemOut, status_code=201)
async def create_my_order_problem(
    order_id: int,
    body: CustomerProblemCreate,
    customer: Customer = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _owned_order(order_id, customer, db)
    problem = CustomerProblem(order_id=order_id, customer_id=customer.id, category=body.category, description=body.description)
    db.add(problem)
    await db.flush()
    await db.refresh(problem)
    return problem


admin_router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(get_current_admin)])


@admin_router.get("/customer-problems", response_model=list[CustomerProblemOut])
async def list_customer_problems(
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(CustomerProblem).order_by(CustomerProblem.created_at.desc())
    if status:
        query = query.where(CustomerProblem.status == status)
    result = await db.execute(query)
    return list(result.scalars().all())


@admin_router.patch("/customer-problems/{problem_id}", response_model=CustomerProblemOut)
async def update_customer_problem(
    problem_id: int,
    body: CustomerProblemStatusUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(CustomerProblem).where(CustomerProblem.id == problem_id))
    problem = result.scalar_one_or_none()
    if not problem:
        raise HTTPException(status_code=404, detail="Problem report not found")
    problem.status = body.status
    await db.flush()
    await db.refresh(problem)
    return problem


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
