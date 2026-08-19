"""
Admin dashboard API routes for managing PC builds through their lifecycle.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import select, func, and_, or_
from datetime import datetime, timedelta
from typing import Optional, List
from pydantic import BaseModel

from app.database import get_db
from app.models.order import Order, OrderStatus
from app.models.order_checklist import OrderChecklist
from app.models.order_photo import OrderPhoto
from app.models.customer import Customer
from app.routes.admin_auth import get_current_admin
from app.services.email_service import send_shipment_update_email

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(get_current_admin)])


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
        query = query.filter(Order.status == status)

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
        estimated_delivery=order.estimated_delivery
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


@router.patch("/orders/{order_id}")
async def update_order_status(
    order_id: int,
    update: OrderStatusUpdateRequest,
    db: Session = Depends(get_db)
):
    """Update order status and set relevant timing fields."""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    old_status = order.status
    now = datetime.utcnow()

    # Map string status to enum
    try:
        new_status = OrderStatus[update.status.upper()]
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Invalid status: {update.status}")

    order.status = new_status
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

    elif new_status == OrderStatus.COMPLETED:
        order.delivered_at = now
        order.actual_delivery_date = now

    db.commit()
    db.refresh(order)

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

    first_shipment_update = order.shipped_at is None
    order.tracking_number = update.tracking_number
    order.carrier = update.carrier
    order.estimated_delivery = update.estimated_delivery
    order.shipped_at = order.shipped_at or datetime.utcnow()

    db.commit()
    db.refresh(order)

    if first_shipment_update and order.customer:
        carrier_urls = {"royal_mail": "https://www.royalmail.com/track-your-item#/tracking-results/{}", "parcelforce": "https://www.parcelforce.com/track-trace?trackNumber={}", "dpd": "https://track.dpd.co.uk/parcels/{}", "ups": "https://www.ups.com/track?loc=en_GB&tracknum={}", "dhl": "https://www.dhl.com/gb-en/home/tracking/tracking-express.html?submit=1&tracking-id={}"}
        template = carrier_urls.get((order.carrier or "").lower().replace(" ", "_"))
        tracking_url = template.format(order.tracking_number) if template and order.tracking_number else None
        background_tasks.add_task(send_shipment_update_email, order.customer.email, order.customer.name, order.order_id, order.carrier, order.tracking_number, tracking_url, order.estimated_delivery)

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
        ])
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
        Order.delivered_at != None
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
        Order.status != OrderStatus.COMPLETED
    ).scalar() or 0

    # Average customer rating (delivered orders with ratings)
    avg_rating = db.query(func.avg(Order.rating)).filter(
        Order.status == OrderStatus.COMPLETED,
        Order.rating != None
    ).scalar()

    return MetricsResponse(
        total_active=active_count,
        orders_by_status=orders_by_status,
        average_build_time_days=avg_build_time,
        late_orders=late_count,
        customer_satisfaction_avg=float(avg_rating) if avg_rating else None
    )
