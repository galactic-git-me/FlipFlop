"""
Admin dashboard API routes for managing PC builds through their lifecycle.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from jose import jwt
from datetime import timezone
from app.config import get_settings
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
from typing import Optional
from pydantic import BaseModel
import json

from app.database import get_db
from app.models.order import Order, OrderStatus
from app.models.build import Build, BuildStatus, BuildType
from app.models.manual_build import ManualBuild
from app.models.getting_started_job import GettingStartedJob
from app.models.order_checklist import OrderChecklist
from app.models.order_photo import OrderPhoto
from app.models.customer import Customer
from app.models.shipment_tracking_event import ShipmentTrackingEvent
from app.models.product import Product, ProductType
from app.routes.admin_auth import get_current_admin
from app.services.email_service import send_shipment_update_email, send_order_status_email
from app.services.warranty_service import ensure_order_reserve

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(get_current_admin)])

@router.post("/orders/{order_id}/portal-preview")
def create_portal_preview(order_id: int, db: Session = Depends(get_db)):
    """Create a short-lived, read-only preview reference for one order.

    The token is intentionally scoped to this order and cannot authenticate as
    the customer. The storefront preview consumer must enforce the `preview`
    and `order_id` claims and disable all mutations.
    """
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    now = datetime.now(timezone.utc)
    settings = get_settings()
    token = jwt.encode({"typ": "portal_preview", "order_id": order.id, "scope": "read", "iat": now, "exp": now + timedelta(minutes=15)}, settings.secret_key, algorithm=settings.jwt_algorithm)
    return {"order_id": order.id, "token": token, "expires_at": (now + timedelta(minutes=15)).isoformat()}


# ─── Schemas ────────────────────────────────────────────────────────────────

class ChecklistItemResponse(BaseModel):
    item: str
    completed: bool
    notes: Optional[str] = None
    updated_at: Optional[datetime] = None


class OrderPhotoResponse(BaseModel):
    id: int
    stage: str
    photo_url: str
    notes: Optional[str] = None
    created_at: datetime


class OrderDetailResponse(BaseModel):
    id: int
    order_id: str
    customer_name: str
    customer_email: str
    status: str
    customer_price: float
    component_costs: float
    profit: Optional[float]
    promised_delivery_date: datetime
    actual_delivery_date: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    # Timing fields
    sourcing_started_at: Optional[datetime]
    sourcing_approved_at: Optional[datetime]
    building_started_at: Optional[datetime]
    building_completed_at: Optional[datetime]
    qa_started_at: Optional[datetime]
    qa_passed_at: Optional[datetime]
    shipped_at: Optional[datetime]
    delivered_at: Optional[datetime]
    # Shipping
    tracking_number: Optional[str]
    carrier: Optional[str]
    estimated_delivery: Optional[datetime]
    cancellation_requested_at: Optional[datetime] = None
    cancellation_status: Optional[str] = None
    refund_id: Optional[str] = None
    cancelled_at: Optional[datetime] = None
    benchmark_results: Optional[dict] = None
    change_request: Optional[dict] = None

    class Config:
        from_attributes = True


class OrderListResponse(BaseModel):
    id: int
    order_id: str
    customer_name: str
    status: str
    customer_price: float
    days_elapsed: int
    created_at: datetime

    class Config:
        from_attributes = True


class OrderStatusUpdateRequest(BaseModel):
    status: str  # 'awaiting_sourcing', 'parts_ordered', 'building', 'qa', 'ready_to_ship', 'shipped', 'completed'
    notes: Optional[str] = None


class OrderBenchmarkEvidenceUpdate(BaseModel):
    benchmark_results: dict
    confirm_measured_results: bool


def _ensure_order_dispatch_build(db: Session, order: Order, admin) -> ManualBuild:
    """Attach an order-owned preparation job to the shared physical dispatch workflow."""
    specs = dict(order.specs or {})
    benchmark_results = specs.get("benchmark_results")
    review = specs.get("benchmark_evidence_review")
    if (
        not isinstance(benchmark_results, dict)
        or not benchmark_results
        or not isinstance(review, dict)
        or review.get("confirmed_measured_results") is not True
    ):
        raise HTTPException(409, "Record the completed build's measured benchmark results before moving it to Ready to Ship")
    raw_slots = specs.get("slots")
    if not isinstance(raw_slots, list) or not raw_slots:
        raise HTTPException(409, "This order has no persisted component specification. Restore and verify the exact built components before dispatch preparation")
    if not specs.get("case_id") or not specs.get("case_name"):
        raise HTTPException(409, "This order has no verified case in its paid specification. Record the exact built case before dispatch preparation")

    component_rows = []
    for slot in raw_slots:
        if not isinstance(slot, dict) or not slot.get("title") or not slot.get("slot_type"):
            raise HTTPException(409, "The order component specification is incomplete; verify each component before dispatch preparation")
        component_rows.append({
            "slot": str(slot["slot_type"]),
            "name": str(slot["title"]),
            "variant_id": slot.get("variant_id"),
            "source": "paid_order_specification",
            "purchased": True,
        })
    delivery_address = dict(specs.get("delivery_address") or {})
    if delivery_address.get("full_name") and not delivery_address.get("contact_name"):
        delivery_address["contact_name"] = delivery_address["full_name"]
    if delivery_address.get("line1") and not delivery_address.get("address_line1"):
        delivery_address["address_line1"] = delivery_address["line1"]
    if delivery_address.get("line2") and not delivery_address.get("address_line2"):
        delivery_address["address_line2"] = delivery_address["line2"]
    if delivery_address.get("postcode") and not delivery_address.get("postal_code"):
        delivery_address["postal_code"] = delivery_address["postcode"]
    if delivery_address.get("country") and not delivery_address.get("country_code"):
        delivery_address["country_code"] = delivery_address["country"]
    if order.customer and order.customer.phone and not delivery_address.get("phone"):
        delivery_address["phone"] = order.customer.phone
    if specs.get("case_name"):
        component_rows.append({
            "slot": "PC Case",
            "name": str(specs["case_name"]),
            "variant_id": specs.get("case_id"),
            "source": "paid_order_specification",
            "purchased": True,
        })

    orchestration = db.query(Build).filter(Build.order_id == order.id).with_for_update().first()
    manual_build = db.query(ManualBuild).filter(ManualBuild.id == orchestration.manual_build_id).with_for_update().first() if orchestration and orchestration.manual_build_id else None
    if not manual_build:
        from app.models.playbook import Playbook
        playbook = db.query(Playbook).filter(Playbook.id == order.playbook_id).first() if order.playbook_id else None
        build_name = str(specs.get("build_name") or (f"{playbook.name} PC" if playbook else order.order_id))[:300]
        manual_build = ManualBuild(
            name=build_name,
            components=component_rows,
            total_cost=float(order.component_costs or 0),
            status="sold",
            customer_id=order.customer_id,
            customer_email=order.customer.email if order.customer else None,
            buyer_name=order.customer.name if order.customer else None,
            buyer_address_json=delivery_address or None,
            sale_price_actual=float(order.customer_price or 0),
            evidence_data={
                "fulfilment_type": specs.get("fulfilment_type", "made_by_you"),
                "order_id": order.id,
                "benchmark_results": benchmark_results,
                "playbook_assignment": {
                    "playbook_id": order.playbook_id,
                    "software_profile": specs.get("software_profile"),
                    "curated_build_id": specs.get("curated_build_id"),
                    "cell_name": specs.get("playbook_cell"),
                },
            },
        )
        db.add(manual_build)
        db.flush()
    else:
        manual_build.name = str(specs.get("build_name") or manual_build.name)[:300]
        manual_build.components = component_rows
        manual_build.total_cost = float(order.component_costs or 0)
        manual_build.status = "sold"
        manual_build.customer_id = order.customer_id
        manual_build.customer_email = order.customer.email if order.customer else manual_build.customer_email
        manual_build.buyer_name = order.customer.name if order.customer else manual_build.buyer_name
        manual_build.buyer_address_json = delivery_address or manual_build.buyer_address_json
        manual_build.sale_price_actual = float(order.customer_price or 0)
        manual_build.evidence_data = {
            **(manual_build.evidence_data or {}),
            "fulfilment_type": specs.get("fulfilment_type", "made_by_you"),
            "order_id": order.id,
            "benchmark_results": benchmark_results,
            "playbook_assignment": {
                "playbook_id": order.playbook_id,
                "software_profile": specs.get("software_profile"),
                "curated_build_id": specs.get("curated_build_id"),
                "cell_name": specs.get("playbook_cell"),
            },
        }

    if orchestration is None:
        orchestration = Build(
            build_type=BuildType.MADE_TO_ORDER,
            order_id=order.id,
            manual_build_id=manual_build.id,
            playbook_id=order.playbook_id,
            spec_json={"components": component_rows, "benchmark_results": benchmark_results},
            status=BuildStatus.FINALISED,
        )
        db.add(orchestration)
    else:
        orchestration.manual_build_id = manual_build.id
        orchestration.playbook_id = orchestration.playbook_id or order.playbook_id
        orchestration.spec_json = {"components": component_rows, "benchmark_results": benchmark_results}
        orchestration.status = BuildStatus.FINALISED

    job = db.query(GettingStartedJob).filter(GettingStartedJob.order_id == order.id).with_for_update().first()
    if job and job.manual_build_id not in (None, manual_build.id):
        raise HTTPException(409, "This order's Getting Ready job is already linked to another physical build")
    if job:
        job.manual_build_id = manual_build.id
        job.status = "awaiting_admin_review"
        job.checklist = {**(job.checklist or {}), "benchmark_results_recorded": True}
        job.updated_at = datetime.utcnow()
    else:
        from app.services.getting_started_jobs import DEFAULT_CHECKLIST, normalize_source_type
        selections = specs.get("software_package_ids") or []
        initial_checklist = {
            **DEFAULT_CHECKLIST,
            "components_ordered": True,
            "software_selection_submitted": isinstance(selections, list),
            "benchmark_results_recorded": True,
        }
        db.add(GettingStartedJob(
            order_id=order.id,
            manual_build_id=manual_build.id,
            customer_id=order.customer_id,
            playbook_id=order.playbook_id,
            source_type=normalize_source_type(str(specs.get("fulfilment_type") or "made_by_you")),
            status="awaiting_admin_review",
            checklist=initial_checklist,
            customer_software_selections=[value for value in selections if isinstance(value, str)],
        ))
    manual_build.evidence_data = {**(manual_build.evidence_data or {}), "benchmark_verified_by": getattr(admin, "email", None) or "admin", "benchmark_verified_at": datetime.utcnow().isoformat()}
    return manual_build


class ChecklistUpdateRequest(BaseModel):
    item: str
    completed: bool
    notes: Optional[str] = None


class ShippingUpdateRequest(BaseModel):
    tracking_number: str
    carrier: str
    estimated_delivery: datetime


class MetricsResponse(BaseModel):
    total_active: int
    orders_by_status: dict
    average_build_time_days: float
    late_orders: int
    customer_satisfaction_avg: Optional[float]


# ─── Endpoints ──────────────────────────────────────────────────────────────

@router.get("/order-priority")
async def list_order_priority(
    status: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Active orders sorted by delivery commitment and component readiness."""
    prebuilt = select(Product.id).where(
        Product.sold_order_id == Order.id,
        Product.product_type == ProductType.PREBUILT,
    ).exists()
    criteria = [
        Order.status.notin_((OrderStatus.SHIPPED, OrderStatus.COMPLETED, OrderStatus.CANCELLED)),
        Order.cancellation_requested_at.is_(None),
    ]
    if status:
        try:
            criteria.append(Order.status == OrderStatus(status))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Unknown order status") from exc

    total = await db.scalar(select(func.count(Order.id)).where(*criteria))
    result = await db.execute(
        select(Order, Customer.name, prebuilt.label("is_prebuilt"))
        .join(Customer, Customer.id == Order.customer_id)
        .where(*criteria)
    )
    now = datetime.utcnow()
    labels = ("prebuilt_fast_track", "prebuilt_standard", "build_fast_track", "build_normal", "build_flexible")
    rows = []
    for order, customer_name, is_prebuilt in result.all():
        specs = order.specs or {}
        mode = specs.get("delivery_mode")
        if is_prebuilt:
            rank = 0 if order.fast_track_selected else 1
        elif order.fast_track_selected:
            rank = 2
        elif mode == "flexible":
            rank = 4
        else:
            rank = 3
        # Every ordered component must arrive before a build can start.
        components = specs.get("ordered_components") or []
        arrival_dates = []
        if isinstance(components, list):
            for component in components:
                if not isinstance(component, dict) or component.get("received_at"):
                    continue
                try:
                    arrival = datetime.fromisoformat(component["expected_arrival_at"].replace("Z", "+00:00"))
                    if arrival.tzinfo is not None:
                        arrival = arrival.astimezone(timezone.utc).replace(tzinfo=None)
                    arrival_dates.append(arrival)
                except (KeyError, TypeError, ValueError):
                    arrival_dates = []
                    break
        ready_at = max(arrival_dates) if arrival_dates else None
        rows.append({
            "id": order.id,
            "order_id": order.order_id,
            "customer_name": customer_name,
            "status": order.status.value if isinstance(order.status, OrderStatus) else str(order.status),
            "customer_price": order.customer_price,
            "days_elapsed": max(0, (now - order.created_at).days),
            "created_at": order.created_at,
            "priority_kind": labels[rank],
            "priority_rank": rank + 1,
            "components_ready_at": ready_at,
        })
    rows.sort(key=lambda row: (
        row["priority_rank"],
        datetime.max if row["priority_rank"] > 2 and row["components_ready_at"] is None else (
            row["components_ready_at"] if row["priority_rank"] > 2 else datetime.min
        ),
        -row["customer_price"], row["created_at"], row["id"],
    ))
    return {
        "total": total or 0,
        "orders": rows[skip:skip + limit],
    }

@router.get("/orders")
async def list_orders(
    status: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    budget_min: Optional[float] = Query(None),
    budget_max: Optional[float] = Query(None),
    sort_by: str = Query("created_at"),
    skip: int = Query(0),
    limit: int = Query(50),
    db: Session = Depends(get_db)
):
    """List all orders with filtering and sorting."""
    query = db.query(Order, Customer).join(Customer)

    # Apply filters
    if status:
        # SQLAlchemy's Enum column is backed by the enum member on some
        # databases and by its stored name on others.  Convert the public
        # value (for example, ``awaiting_sourcing``) before filtering so the
        # dashboard behaves consistently with both SQLite and PostgreSQL.
        try:
            status_filter = OrderStatus(status)
        except ValueError:
            status_filter = status
        query = query.filter(Order.status == status_filter)

    if date_from:
        date_from_dt = datetime.fromisoformat(date_from)
        query = query.filter(Order.created_at >= date_from_dt)

    if date_to:
        date_to_dt = datetime.fromisoformat(date_to)
        query = query.filter(Order.created_at <= date_to_dt)

    if budget_min is not None:
        query = query.filter(Order.customer_price >= budget_min)

    if budget_max is not None:
        query = query.filter(Order.customer_price <= budget_max)

    # Apply sorting
    if sort_by == "status":
        query = query.order_by(Order.status)
    elif sort_by == "customer":
        query = query.order_by(Customer.name)
    elif sort_by == "price":
        query = query.order_by(Order.customer_price.desc())
    else:  # default: created_at
        query = query.order_by(Order.created_at.desc())

    # Count total for pagination
    total = query.count()

    # Paginate
    orders = query.offset(skip).limit(limit).all()

    # Format response
    order_list = []
    now = datetime.utcnow()
    for order, customer in orders:
        days_elapsed = (now - order.created_at).days
        order_list.append(OrderListResponse(
            id=order.id,
            order_id=order.order_id,
            customer_name=customer.name,
            status=order.status.value if isinstance(order.status, OrderStatus) else str(order.status),
            customer_price=order.customer_price,
            days_elapsed=days_elapsed,
            created_at=order.created_at
        ))

    return {
        "total": total,
        "orders": order_list
    }


@router.get("/orders/{order_id}")
async def get_order_detail(order_id: int, db: Session = Depends(get_db)):
    """Get single order with all details including checklists and photos."""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    customer = db.query(Customer).filter(Customer.id == order.customer_id).first()

    # Get checklists
    build_checklist = db.query(OrderChecklist).filter(
        OrderChecklist.order_id == order_id,
        OrderChecklist.section == "build"
    ).all()

    qa_checklist = db.query(OrderChecklist).filter(
        OrderChecklist.order_id == order_id,
        OrderChecklist.section == "qa"
    ).all()

    # Get photos
    photos = db.query(OrderPhoto).filter(OrderPhoto.order_id == order_id).all()

    order_detail = OrderDetailResponse(
        id=order.id,
        order_id=order.order_id,
        customer_name=customer.name if customer else "Unknown",
        customer_email=customer.email if customer else "Unknown",
        status=order.status.value if isinstance(order.status, OrderStatus) else str(order.status),
        customer_price=order.customer_price,
        component_costs=order.component_costs,
        profit=order.profit,
        promised_delivery_date=order.promised_delivery_date,
        actual_delivery_date=order.actual_delivery_date,
        created_at=order.created_at,
        updated_at=order.updated_at,
        sourcing_started_at=order.sourcing_started_at,
        sourcing_approved_at=order.sourcing_approved_at,
        building_started_at=order.building_started_at,
        building_completed_at=order.building_completed_at,
        qa_started_at=order.qa_started_at,
        qa_passed_at=order.qa_passed_at,
        shipped_at=order.shipped_at,
        delivered_at=order.delivered_at,
        tracking_number=order.tracking_number,
        carrier=order.carrier,
        estimated_delivery=order.estimated_delivery,
        cancellation_requested_at=order.cancellation_requested_at,
        cancellation_status=order.cancellation_status,
        refund_id=order.refund_id,
        cancelled_at=order.cancelled_at,
        benchmark_results=(order.specs or {}).get("benchmark_results"),
        change_request=order.change_request if isinstance(order.change_request, dict) else None,
    )

    return {
        "order": order_detail,
        "checklist": {
            "build": [
                ChecklistItemResponse(
                    item=item.item,
                    completed=item.completed,
                    notes=item.notes,
                    updated_at=item.updated_at
                ) for item in build_checklist
            ],
            "qa": [
                ChecklistItemResponse(
                    item=item.item,
                    completed=item.completed,
                    notes=item.notes,
                    updated_at=item.updated_at
                ) for item in qa_checklist
            ]
        },
        "photos": [
            OrderPhotoResponse(
                id=photo.id,
                stage=photo.stage,
                photo_url=photo.photo_url,
                notes=photo.notes,
                created_at=photo.created_at
            ) for photo in photos
        ]
    }


@router.put("/orders/{order_id}/build-evidence")
def save_order_benchmark_evidence(
    order_id: int,
    body: OrderBenchmarkEvidenceUpdate,
    admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    if not body.confirm_measured_results:
        raise HTTPException(409, "Confirm these are measured results from this physical build")
    results = body.benchmark_results
    if not isinstance(results, dict) or not results.get("test_date") or not results.get("test_setup") or not results.get("results"):
        raise HTTPException(422, "Include test_date, test_setup, and measured results")
    try:
        encoded = json.dumps(results, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as error:
        raise HTTPException(422, "Benchmark results must be valid JSON values") from error
    if len(encoded.encode("utf-8")) > 64 * 1024:
        raise HTTPException(413, "Benchmark evidence must be no larger than 64 KB")

    order = db.query(Order).filter(Order.id == order_id).with_for_update().first()
    if not order:
        raise HTTPException(404, "Order not found")
    if order.status in {OrderStatus.SHIPPED, OrderStatus.COMPLETED, OrderStatus.CANCELLED}:
        raise HTTPException(409, "Build evidence is locked after dispatch or cancellation")
    specs = dict(order.specs or {})
    specs["benchmark_results"] = results
    specs["benchmark_evidence_review"] = {
        "confirmed_measured_results": True,
        "reviewed_by": getattr(admin, "email", None) or "admin",
        "recorded_at": datetime.utcnow().isoformat(),
    }
    order.specs = specs
    order.updated_at = datetime.utcnow()
    db.commit()
    return {"success": True, "order_id": order.id, "benchmark_results": results}


@router.patch("/orders/{order_id}")
async def update_order_status(
    order_id: int,
    update: OrderStatusUpdateRequest,
    background_tasks: BackgroundTasks,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Update order status and set relevant timing fields."""
    # Serialize sourcing milestones with customer cancellation. The customer
    # cancellation endpoint locks this same row before recording its sourcing
    # hold, so only one transition can pass its eligibility check at a time.
    order = (await db.execute(
        select(Order).options(selectinload(Order.customer)).where(Order.id == order_id).with_for_update()
    )).scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    old_status = order.status
    now = datetime.utcnow()

    # Map string status to enum
    try:
        new_status = OrderStatus[update.status.upper()]
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Invalid status: {update.status}")

    if new_status == OrderStatus.CANCELLED:
        raise HTTPException(status_code=409, detail="Use the owner-verified cancellation and refund action; do not change cancellation status manually")
    if new_status == OrderStatus.COMPLETED and not order.delivered_at:
        raise HTTPException(status_code=409, detail="Order completion requires a confirmed delivery event")
    if order.status == OrderStatus.CANCELLED or order.cancellation_requested_at:
        raise HTTPException(status_code=409, detail="This order is cancelled or has a refund pending reconciliation")
    change_request_status = (order.change_request or {}).get("status") if isinstance(order.change_request, dict) else None
    if change_request_status in {"requested", "quote_ready", "customer_approved"} and new_status != OrderStatus.AWAITING_SOURCING:
        raise HTTPException(status_code=409, detail="Sourcing is paused while the customer build-change request is open")
    if new_status == OrderStatus.SHIPPED:
        raise HTTPException(status_code=409, detail="Use Dispatch Centre's booked-shipment handover action after evidence and insurance checks")

    if new_status == OrderStatus.READY_TO_SHIP:
        fulfilment_type = str((order.specs or {}).get("fulfilment_type") or "").lower().replace("-", "_")
        if fulfilment_type in {"curated", "curated_for_you", "custom", "made_by_you"} and order.status != OrderStatus.QA:
            raise HTTPException(409, "Curated and Made-by-you builds must complete QA before moving to Ready to Ship")
        await db.run_sync(lambda sync_db: _ensure_order_dispatch_build(sync_db, order, admin))

    order.status = new_status
    if new_status in {
        OrderStatus.PARTS_ORDERED,
        OrderStatus.BUILDING,
        OrderStatus.QA,
        OrderStatus.READY_TO_PACKAGE,
        OrderStatus.PACKAGING_IN_PROGRESS,
        OrderStatus.READY_TO_SHIP,
        OrderStatus.SHIPPED,
        OrderStatus.COMPLETED,
    }:
        getting_started_job = (await db.execute(
            select(GettingStartedJob).where(GettingStartedJob.order_id == order.id)
        )).scalar_one_or_none()
        if getting_started_job:
            getting_started_job.checklist = {
                **(getting_started_job.checklist or {}),
                "components_ordered": True,
            }
    if update.notes:
        order.notes = update.notes

    # Set timing fields based on status transitions
    if new_status == OrderStatus.PARTS_ORDERED and old_status == OrderStatus.AWAITING_SOURCING:
        order.sourcing_started_at = order.sourcing_started_at or now
        order.sourcing_approved_at = now
        order.building_started_at = now

    elif new_status == OrderStatus.BUILDING and old_status == OrderStatus.PARTS_ORDERED:
        order.building_started_at = order.building_started_at or now

    elif new_status == OrderStatus.QA and old_status == OrderStatus.BUILDING:
        order.building_completed_at = now
        order.qa_started_at = now

    elif new_status == OrderStatus.READY_TO_SHIP and old_status == OrderStatus.QA:
        order.qa_passed_at = now

    elif new_status == OrderStatus.SHIPPED:
        order.shipped_at = order.shipped_at or now
        existing_dispatch_event = (await db.execute(
            select(ShipmentTrackingEvent.id).where(
                ShipmentTrackingEvent.provider_event_id == f"admin-dispatch:{order.id}"
            )
        )).scalar_one_or_none()
        if not existing_dispatch_event:
            db.add(ShipmentTrackingEvent(
                order_id=order.id,
                provider=order.carrier or "operator",
                provider_event_id=f"admin-dispatch:{order.id}",
                status_code="dispatched",
                description="Your order has been handed to the courier.",
                material=True,
                occurred_at=order.shipped_at,
            ))

    elif new_status == OrderStatus.COMPLETED:
        order.delivered_at = order.delivered_at or now
        order.actual_delivery_date = order.actual_delivery_date or order.delivered_at
        await ensure_order_reserve(db, order, order.delivered_at)
        linked_build = (await db.execute(select(Build).where(
            Build.order_id == order.id,
            Build.manual_build_id.is_not(None),
        ))).scalar_one_or_none()
        if linked_build:
            physical_build = await db.get(ManualBuild, linked_build.manual_build_id)
            if physical_build:
                physical_build.delivered_at = physical_build.delivered_at or order.delivered_at
                physical_build.warranty_started_at = physical_build.warranty_started_at or order.delivered_at
                physical_build.dispatch_status = "delivered"
        existing_delivery_event = (await db.execute(
            select(ShipmentTrackingEvent.id).where(
                ShipmentTrackingEvent.provider_event_id == f"admin-delivered:{order.id}"
            )
        )).scalar_one_or_none()
        if not existing_delivery_event:
            db.add(ShipmentTrackingEvent(
                order_id=order.id,
                provider=order.carrier or "operator",
                provider_event_id=f"admin-delivered:{order.id}",
                status_code="delivered",
                description="Your courier delivery has been recorded as delivered.",
                material=True,
                occurred_at=order.delivered_at,
            ))

    await db.commit()
    await db.refresh(order)

    # Every customer-visible lifecycle transition gets the same branded,
    # centralised status email template.
    if old_status != new_status and order.customer:
        background_tasks.add_task(send_order_status_email, order.customer.email, order.customer.name, order.order_id, new_status.value, order.id)

    return {
        "status": "updated",
        "order_id": order.id,
        "new_status": new_status.value
    }


@router.post("/orders/{order_id}/checklist/{section}")
async def update_checklist_item(
    order_id: int,
    section: str,
    update: ChecklistUpdateRequest,
    db: Session = Depends(get_db)
):
    """Update or create a checklist item."""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if section not in ["build", "qa"]:
        raise HTTPException(status_code=400, detail="Section must be 'build' or 'qa'")

    checklist = db.query(OrderChecklist).filter(
        OrderChecklist.order_id == order_id,
        OrderChecklist.section == section,
        OrderChecklist.item == update.item
    ).first()

    if not checklist:
        checklist = OrderChecklist(
            order_id=order_id,
            section=section,
            item=update.item,
            completed=update.completed,
            notes=update.notes
        )
        db.add(checklist)
    else:
        checklist.completed = update.completed
        checklist.notes = update.notes
        checklist.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(checklist)

    return {
        "status": "updated",
        "order_id": order_id,
        "section": section,
        "item": update.item,
        "completed": checklist.completed
    }


@router.patch("/orders/{order_id}/shipping")
async def update_shipping(
    order_id: int,
    update: ShippingUpdateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Update shipping information."""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    shipping_changed = (
        order.tracking_number != update.tracking_number
        or order.carrier != update.carrier
        or order.estimated_delivery != update.estimated_delivery
    )
    order.tracking_number = update.tracking_number
    order.carrier = update.carrier
    order.estimated_delivery = update.estimated_delivery
    order.shipped_at = order.shipped_at or datetime.utcnow()

    db.commit()
    db.refresh(order)

    if shipping_changed and order.customer:
        carrier_urls = {"royal_mail": "https://www.royalmail.com/track-your-item#/tracking-results/{}", "parcelforce": "https://www.parcelforce.com/track-trace?trackNumber={}", "dpd": "https://track.dpd.co.uk/parcels/{}", "ups": "https://www.ups.com/track?loc=en_GB&tracknum={}", "dhl": "https://www.dhl.com/gb-en/home/tracking/tracking-express.html?submit=1&tracking-id={}"}
        template = carrier_urls.get((order.carrier or "").lower().replace(" ", "_"))
        tracking_url = template.format(order.tracking_number) if template and order.tracking_number else None
        background_tasks.add_task(send_shipment_update_email, order.customer.email, order.customer.name, order.order_id, order.carrier, order.tracking_number, tracking_url, order.estimated_delivery, order.id)

    return {
        "status": "updated",
        "order_id": order.id,
        "tracking_number": order.tracking_number,
        "carrier": order.carrier,
        "estimated_delivery": order.estimated_delivery
    }


@router.get("/metrics")
async def get_metrics(db: Session = Depends(get_db)):
    """Get dashboard KPIs."""
    # Active orders (not completed/delivered)
    active_count = db.query(func.count(Order.id)).filter(
        Order.status.in_([
            OrderStatus.AWAITING_SOURCING,
            OrderStatus.PARTS_ORDERED,
            OrderStatus.BUILDING,
            OrderStatus.QA,
            OrderStatus.READY_TO_SHIP,
            OrderStatus.SHIPPED
        ]),
        Order.cancellation_requested_at.is_(None),
    ).scalar() or 0

    # Orders by status
    by_status = db.query(Order.status, func.count(Order.id)).group_by(Order.status).all()
    orders_by_status = {
        s.value if isinstance(s, OrderStatus) else str(s): count
        for s, count in by_status
    }

    # Average build time (completed orders only)
    completed = db.query(Order).filter(
        Order.status == OrderStatus.COMPLETED,
        Order.delivered_at.is_not(None)
    ).all()

    avg_build_time = 0.0
    if completed:
        total_days = sum([
            (o.delivered_at - o.created_at).days
            for o in completed if o.delivered_at
        ])
        avg_build_time = round(total_days / len(completed), 1)

    # Late orders (created > 14 days ago but not completed)
    cutoff = datetime.utcnow() - timedelta(days=14)
    late_count = db.query(func.count(Order.id)).filter(
        Order.created_at <= cutoff,
        Order.status.notin_((OrderStatus.COMPLETED, OrderStatus.CANCELLED)),
        Order.cancellation_requested_at.is_(None),
    ).scalar() or 0

    # Average customer rating (delivered orders with ratings)
    avg_rating = db.query(func.avg(Order.rating)).filter(
        Order.status == OrderStatus.COMPLETED,
        Order.rating.is_not(None)
    ).scalar()

    return MetricsResponse(
        total_active=active_count,
        orders_by_status=orders_by_status,
        average_build_time_days=avg_build_time,
        late_orders=late_count,
        customer_satisfaction_avg=float(avg_rating) if avg_rating else None
    )
