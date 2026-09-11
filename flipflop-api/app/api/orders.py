from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy import func, select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta, date
from app.database import get_db
from app.models import Order, BuildCapacity, BuildCapacityOverride, CustomerProblem, CXDocument, Capture3DAsset, Capture3DStatus, Product, Build
from app.models.manual_build import ManualBuild
from app.models.customer import Customer
from app.routes.auth import get_current_user
from app.routes.admin_auth import get_current_admin
from app.services.auth_service import get_customer_by_token
from app.services.admin_auth_service import get_admin_by_token
from app.services.product_faqs import selected_faqs
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

async def _portal_actor(authorization: str | None, db: AsyncSession):
    """Accept either the buyer JWT or the separate admin JWT.

    The short-lived preview token identifies the build; it is deliberately
    not itself a login credential.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Sign in to access this customer portal")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid authorization header format")
    token = parts[1]
    customer = await get_customer_by_token(db, token)
    if customer:
        return "customer", customer
    admin = await get_admin_by_token(db, token)
    if admin:
        return "admin", admin
    raise HTTPException(status_code=401, detail="Invalid or expired login")


@router.get("/portal-preview/{preview_token}")
async def get_portal_preview(
    preview_token: str,
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
):
    actor_type, actor = await _portal_actor(authorization, db)
    try:
        claims = jwt.decode(preview_token, get_settings().secret_key, algorithms=[get_settings().jwt_algorithm])
    except JWTError:
        raise HTTPException(status_code=401, detail="Preview expired or invalid")
    if claims.get("typ") != "portal_preview" or claims.get("scope") != "read":
        raise HTTPException(status_code=403, detail="Invalid preview scope")
    build_id = int(claims.get("build_id") or 0)
    order_id = int(claims.get("order_id") or 0)
    if build_id:
        build = (await db.execute(select(ManualBuild).where(ManualBuild.id == build_id))).scalar_one_or_none()
        if not build or build.status not in {"built", "listed", "sold"} or not build.model_3d_url:
            raise HTTPException(status_code=404, detail="Build portal not found")
        if actor_type != "admin":
            # A buyer can access a manual build only through the storefront
            # order that sold its linked product.
            buyer_order = (await db.execute(
                select(Order).join(Product, Product.sold_order_id == Order.id)
                .join(Build, Build.id == Product.build_id)
                .where(Build.manual_build_id == build.id, Order.customer_id == actor.id)
            )).scalar_one_or_none()
            if not buyer_order:
                raise HTTPException(status_code=404, detail="Build portal not found")
        return _manual_build_to_portal_out(build)

    if order_id:
        order = (await db.execute(select(Order).where(Order.id == order_id))).scalar_one_or_none()
        if order and (actor_type == "admin" or order.customer_id == actor.id):
            asset = (await db.execute(select(Capture3DAsset).where(Capture3DAsset.order_id == order.id))).scalar_one_or_none()
            return _order_to_my_order_out(order, asset)
    raise HTTPException(status_code=404, detail="Build portal not found")


def _manual_build_customer_hub(build: ManualBuild) -> dict:
    evidence = dict(build.evidence_data or {})
    performance = dict(evidence.get("performance_card") or {})
    evaluation = dict(build.last_evaluation or {})
    upgrades = evaluation.get("upgrade_plan") or evaluation.get("upgrades") or []
    if isinstance(upgrades, dict):
        upgrades = [upgrades]
    return {
        "build_name": build.generated_title or build.name,
        "hero_photo_url": build.hero_photo_url,
        "model": {"url": build.model_3d_url, "preview_image_url": build.hero_photo_url, "status": "published", "ar_ready": True},
        "performance": {
            "available": bool(performance),
            "data": performance,
            "message": "Measured results for this specific build." if performance else "Performance data will appear when benchmark results are published.",
        },
        "upgrade_plan": {
            "title": "Upgrade path",
            "intro": "Compatibility must be checked against the exact components in this build before any upgrade.",
            "items": upgrades,
        },
        "getting_started": [
            "Remove transit protection and check that all internal components are secure.",
            "Connect the display to the graphics card where one is fitted.",
            "Connect keyboard, mouse and network, then run Windows Update.",
            "Keep the packaging until the machine has been checked and accepted.",
        ],
        "troubleshooting": [
            {"title": "No display", "steps": ["Check power to the monitor and PC.", "Check the display cable is connected to the graphics card.", "Try the supplied cable and another monitor input."]},
            {"title": "No power", "steps": ["Check the rear PSU switch and wall socket.", "Reseat the mains cable.", "Do not open the PSU; contact support if the issue remains."]},
            {"title": "Network or audio issue", "steps": ["Run Windows Update and restart.", "Check the selected output device and network connection.", "Contact support with the exact symptom if it persists."]},
        ],
        "downloads": ([{"title": "Exact build 3D model (GLB)", "url": build.model_3d_url, "kind": "3d_model"}] if build.model_3d_url else []),
        "driver_note": "No build-specific driver bundle has been published. Use the component manufacturer's support page for the exact part shown in the specification.",
        "policies": {
            "returns": f"Returns are handled under the published {build.return_days}-day return policy for this listing, subject to its terms.",
            "warranty": "Your statutory consumer rights remain in force. Any additional warranty coverage is limited to what is stated in your order documents.",
            "delivery": f"Delivery is normally expected within {build.delivery_min_days}-{build.delivery_max_days} days after dispatch, subject to courier conditions.",
            "support": "Use the private support form in this portal and include the build ID and any error message.",
        },
        "faqs": selected_faqs(build.id, build.selected_faq_ids, build.selected_faq_answer_overrides),
    }


def _order_customer_hub(model_url: str | None, preview_image_url: str | None = None) -> dict:
    """Baseline hub for a normal customer order when no ManualBuild row is linked."""
    return {
        "model": {"url": model_url, "preview_image_url": preview_image_url, "status": "published" if model_url else "pending", "ar_ready": bool(model_url)},
        "performance": {"available": False, "data": {}, "message": "Benchmark data will appear here when it has been published for this build."},
        "upgrade_plan": {"title": "Upgrade path", "intro": "Compatibility must be checked against the exact components in this build before any upgrade.", "items": []},
        "getting_started": ["Remove transit protection and check that all internal components are secure.", "Connect the display to the graphics card where one is fitted.", "Connect keyboard, mouse and network, then run Windows Update.", "Keep the packaging until the machine has been checked and accepted."],
        "troubleshooting": [{"title": "No display", "steps": ["Check power to the monitor and PC.", "Check the display cable is connected to the graphics card.", "Contact support if the issue remains."]}],
        "downloads": ([{"title": "Exact build 3D model (GLB)", "url": model_url, "kind": "3d_model"}] if model_url else []),
        "driver_note": "No build-specific driver bundle has been published. Use the component manufacturer's support page for the exact part shown in the specification.",
        "policies": {"returns": "Returns are handled under the published order policy and its terms.", "warranty": "Your statutory consumer rights remain in force. Additional coverage is limited to your order documents.", "delivery": "Delivery updates are shown in the order tracking section.", "support": "Use the private support form in this portal."},
        "faqs": [],
    }


def _manual_build_to_portal_out(build: ManualBuild) -> MyOrderOut:
    """Represent a ready-to-ship build in the existing owner-portal contract."""
    components = list(build.components or [])
    case = next(
        (item for item in components if str(item.get("slot", "")).lower() in {"case", "chassis"}),
        None,
    )
    slots = [
        MyOrderSlotOut(
            slot_id=index,
            slot_type=str(item.get("slot") or "component"),
            variant_id=int(item.get("part_id") or 0),
            title=str(item.get("name") or "Component"),
            price=float(item.get("price_paid") or 0),
        )
        for index, item in enumerate(components, start=1)
        if item is not case
    ]
    asking_price = float(build.ebay_price or (build.last_evaluation or {}).get("mid") or 0)
    return MyOrderOut(
        id=build.id,
        order_id=f"BUILD-{build.id}",
        status=build.status,
        customer_price=asking_price,
        component_costs=float(build.total_cost or 0),
        slots=slots,
        case_name=str(case.get("name")) if case else None,
        case_price=float(case.get("price_paid") or 0) if case else 0.0,
        capture_3d={
            "status": "published",
            "optimized_asset_ref": build.model_3d_url,
            "preview_image_ref": build.hero_photo_url,
            "ar_ready": True,
        },
        model_3d_url=build.model_3d_url,
        customer_hub=_manual_build_customer_hub(build),
        created_at=build.created_at,
    )


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
    published_model_url = (
        capture_3d.optimized_asset_ref
        if capture_3d and capture_3d.status == Capture3DStatus.PUBLISHED and capture_3d.optimized_asset_ref
        else None
    )
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
        model_3d_url=published_model_url,
        customer_hub=_order_customer_hub(published_model_url, capture_3d.preview_image_ref if capture_3d else None),
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
        content_json=document.content_json if (document.status.value if hasattr(document.status, "value") else str(document.status)) == "ready" else None,
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
