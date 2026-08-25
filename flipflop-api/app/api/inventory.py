from datetime import datetime
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from app.database import get_db
from app.models.inventory import InventoryItem
from app.models.inventory_allocation import InventoryAllocation
from app.models.build import Build
from app.models.manual_build import ManualBuild
from app.models.inventory_event import InventoryEvent
from app.schemas.inventory import InventoryItemIn, InventoryItemPartialIn, InventoryItemOut, AllocationInfo

router = APIRouter(prefix="/inventory", tags=["inventory"])


async def _build_item_with_allocations(item: InventoryItem, db: AsyncSession) -> dict:
    """Build inventory item response with allocation info."""
    # Query allocations for this item
    result = await db.execute(
        select(InventoryAllocation).where(InventoryAllocation.inventory_item_id == item.id)
    )
    allocations_records = result.scalars().all()

    # Build allocation info list and calculate total allocated
    allocations = [
        AllocationInfo(
            allocation_id=a.id,
            flip_id=a.flip_id,
            build_id=a.build_id,
            quantity_allocated=a.quantity_allocated
        )
        for a in allocations_records
    ]

    total_allocated = sum(a.quantity_allocated for a in allocations_records)
    quantity_unallocated = item.quantity - total_allocated

    # Convert item to dict and add allocation data
    item_dict = {
        "id": item.id,
        "component_name": item.component_name,
        "component_type": item.component_type,
        "quantity": item.quantity,
        "quantity_unallocated": quantity_unallocated,
        "base_price": item.base_price,
        "shipping_cost": item.shipping_cost,
        "discount_amount": item.discount_amount,
        "actual_cost": item.actual_cost,
        "purchase_date": item.purchase_date,
        "source": item.source,
        "notes": item.notes,
        "created_at": item.created_at,
        "allocations": allocations,
    }

    return item_dict


@router.get("/", response_model=list[InventoryItemOut])
async def list_inventory(
    component_type: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List all inventory items with allocation info, optionally filtered by component type."""
    q = select(InventoryItem).order_by(desc(InventoryItem.created_at))
    if component_type:
        q = q.where(InventoryItem.component_type == component_type)
    result = await db.execute(q)
    items = result.scalars().all()

    # Build response with allocation info for each item
    response = []
    for item in items:
        item_with_allocations = await _build_item_with_allocations(item, db)
        response.append(item_with_allocations)

    return response


@router.post("/", response_model=InventoryItemOut, status_code=201)
async def create_inventory_item(
    item: InventoryItemIn,
    db: AsyncSession = Depends(get_db),
):
    """Add a new inventory item."""
    new_item = InventoryItem(
        component_name=item.component_name,
        component_type=item.component_type,
        quantity=item.quantity,
        base_price=item.base_price,
        shipping_cost=item.shipping_cost,
        discount_amount=item.discount_amount,
        purchase_date=item.purchase_date or datetime.utcnow(),
        source=item.source,
        notes=item.notes,
    )
    db.add(new_item)
    await db.flush()
    db.add(InventoryEvent(
        inventory_item_id=new_item.id,
        event_type="purchased",
        quantity=new_item.quantity,
        detail={"source": new_item.source or "Manual inventory entry"},
    ))
    await db.refresh(new_item)
    return await _build_item_with_allocations(new_item, db)


# Static collection routes must be registered before /{item_id}; Starlette
# otherwise treats names such as "free-items" as an integer item id.
@router.get("/summary/stats")
async def inventory_stats_route(db: AsyncSession = Depends(get_db)):
    return await _inventory_stats(db)


@router.get("/free-items")
async def free_inventory_items_route(
    component_type: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await _free_inventory_items(component_type, db)


@router.get("/summary/health")
async def inventory_health_route(db: AsyncSession = Depends(get_db)):
    return await _inventory_health(db)


@router.get("/{item_id}", response_model=InventoryItemOut)
async def get_inventory_item(
    item_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get a single inventory item with allocation info."""
    result = await db.execute(select(InventoryItem).where(InventoryItem.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        from fastapi import HTTPException
        raise HTTPException(404, "Item not found")
    return await _build_item_with_allocations(item, db)


@router.patch("/{item_id}", response_model=InventoryItemOut)
async def update_inventory_item(
    item_id: int,
    item: InventoryItemPartialIn,
    db: AsyncSession = Depends(get_db),
):
    """Update an inventory item. Only provided fields are updated."""
    result = await db.execute(select(InventoryItem).where(InventoryItem.id == item_id))
    db_item = result.scalar_one_or_none()
    if not db_item:
        from fastapi import HTTPException
        raise HTTPException(404, "Item not found")

    # Only update fields that are explicitly provided (not None)
    if item.component_name is not None:
        db_item.component_name = item.component_name
    if item.component_type is not None:
        db_item.component_type = item.component_type
    if item.quantity is not None:
        db_item.quantity = item.quantity
    if item.base_price is not None:
        db_item.base_price = item.base_price
    if item.shipping_cost is not None:
        db_item.shipping_cost = item.shipping_cost
    if item.discount_amount is not None:
        db_item.discount_amount = item.discount_amount
    if item.purchase_date is not None:
        db_item.purchase_date = item.purchase_date
    if item.source is not None:
        db_item.source = item.source
    if item.notes is not None:
        db_item.notes = item.notes

    db_item.updated_at = datetime.utcnow()

    await db.flush()
    await db.refresh(db_item)
    return await _build_item_with_allocations(db_item, db)


@router.delete("/{item_id}", status_code=204)
async def delete_inventory_item(
    item_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Delete an inventory item."""
    result = await db.execute(select(InventoryItem).where(InventoryItem.id == item_id))
    db_item = result.scalar_one_or_none()
    if not db_item:
        from fastapi import HTTPException
        raise HTTPException(404, "Item not found")
    
    await db.delete(db_item)
    await db.commit()


@router.post("/bulk")
async def bulk_import_inventory(
    data: dict,
    db: AsyncSession = Depends(get_db),
):
    """Bulk import inventory items from JSON file.

    Expected format:
    {
        "items": [
            {
                "component_name": "RTX 4070",
                "component_type": "gpu",
                "quantity": 1,
                "base_price": 450.00,
                "shipping_cost": 10.00,
                "discount_amount": 0,
                "purchase_date": "2026-06-20",
                "source": "eBay",
                "notes": "Optional notes"
            }
        ]
    }
    """
    from fastapi import HTTPException

    if "items" not in data or not isinstance(data["items"], list):
        raise HTTPException(
            status_code=400,
            detail="Invalid format: expected {\"items\": [...]}"
        )

    items_data = data["items"]
    if not items_data:
        raise HTTPException(status_code=400, detail="No items provided")

    created_items = []
    errors = []

    for idx, item_data in enumerate(items_data):
        try:
            # Validate required fields
            required = ["component_name", "component_type", "quantity", "base_price", "purchase_date"]
            missing = [f for f in required if f not in item_data]
            if missing:
                errors.append(f"Item {idx}: Missing fields: {', '.join(missing)}")
                continue

            # Parse date
            purchase_date_str = item_data.get("purchase_date")
            if isinstance(purchase_date_str, str):
                try:
                    purchase_date = datetime.fromisoformat(purchase_date_str)
                except ValueError:
                    errors.append(f"Item {idx}: Invalid date format '{purchase_date_str}', use YYYY-MM-DD")
                    continue
            else:
                purchase_date = datetime.utcnow()

            # Create item
            new_item = InventoryItem(
                component_name=str(item_data["component_name"]),
                component_type=str(item_data["component_type"]),
                quantity=int(item_data["quantity"]),
                base_price=float(item_data["base_price"]),
                shipping_cost=float(item_data.get("shipping_cost", 0.0)),
                discount_amount=float(item_data.get("discount_amount", 0.0)),
                purchase_date=purchase_date,
                source=item_data.get("source"),
                notes=item_data.get("notes"),
            )
            db.add(new_item)
            created_items.append(new_item.component_name)

        except (ValueError, TypeError) as e:
            errors.append(f"Item {idx}: Invalid data - {str(e)}")
            continue

    if not created_items:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to create any items. Errors: {'; '.join(errors)}"
        )

    try:
        await db.commit()
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Database error: {str(e)}"
        )

    return {
        "created": len(created_items),
        "items": created_items,
        "errors": errors if errors else None,
    }


async def _inventory_stats(db: AsyncSession):
    """Get inventory statistics."""
    result = await db.execute(select(InventoryItem))
    items = result.scalars().all()

    total_cost = sum(item.actual_cost * item.quantity for item in items)
    total_qty = sum(item.quantity for item in items)
    by_type = {}

    for item in items:
        if item.component_type not in by_type:
            by_type[item.component_type] = {"qty": 0, "cost": 0}
        by_type[item.component_type]["qty"] += item.quantity
        by_type[item.component_type]["cost"] += item.actual_cost * item.quantity

    return {
        "total_items": len(items),
        "total_quantity": total_qty,
        "total_cost": total_cost,
        "by_type": by_type,
    }


async def _free_inventory_items(component_type: str | None, db: AsyncSession):
    """Free physical inventory, cheapest landed-cost item first."""
    item_query = select(InventoryItem)
    if component_type:
        item_query = item_query.where(InventoryItem.component_type == component_type)
    result = await db.execute(item_query)
    items = result.scalars().all()
    result = await db.execute(select(
        InventoryAllocation.inventory_item_id,
        func.sum(InventoryAllocation.quantity_allocated),
    ).group_by(InventoryAllocation.inventory_item_id))
    allocated = {item_id: int(quantity or 0) for item_id, quantity in result.all()}
    return sorted([
        {
            "id": item.id,
            "component_name": item.component_name,
            "component_type": item.component_type,
            "quantity_free": item.quantity - allocated.get(item.id, 0),
            "actual_cost": item.actual_cost,
            "source": item.source,
            "listing_url": item.listing_url,
            "purchase_date": item.purchase_date,
        }
        for item in items if item.quantity - allocated.get(item.id, 0) > 0
    ], key=lambda item: item["actual_cost"])


async def _inventory_health(db: AsyncSession):
    """Operational stock health across free, reserved and consumed units."""
    items_result = await db.execute(select(InventoryItem))
    items = items_result.scalars().all()
    allocations_result = await db.execute(
        select(InventoryAllocation, Build, ManualBuild)
        .join(Build, Build.id == InventoryAllocation.build_id, isouter=True)
        .join(ManualBuild, ManualBuild.id == Build.manual_build_id, isouter=True)
    )
    allocation_rows = allocations_result.all()
    allocated_by_item: dict[int, int] = {}
    reserved_units = consumed_units = 0
    reserved_value = consumed_value = 0.0
    item_by_id = {item.id: item for item in items}
    for allocation, _build, manual_build in allocation_rows:
        allocated_by_item[allocation.inventory_item_id] = allocated_by_item.get(allocation.inventory_item_id, 0) + allocation.quantity_allocated
        value = allocation.quantity_allocated * allocation.cost_per_unit_at_allocation
        if manual_build and manual_build.status == "in_progress":
            reserved_units += allocation.quantity_allocated
            reserved_value += value
        else:
            consumed_units += allocation.quantity_allocated
            consumed_value += value
    free_units = sum(max(0, item.quantity - allocated_by_item.get(item.id, 0)) for item in items)
    free_value = sum(max(0, item.quantity - allocated_by_item.get(item.id, 0)) * item.actual_cost for item in items)
    now = datetime.utcnow()
    stale = [
        {"id": item.id, "name": item.component_name, "days": (now - item.purchase_date).days,
         "value": max(0, item.quantity - allocated_by_item.get(item.id, 0)) * item.actual_cost}
        for item in items
        if item.quantity - allocated_by_item.get(item.id, 0) > 0 and (now - item.purchase_date).days >= 90
    ]
    free_by_type: dict[str, int] = {}
    for item in items:
        free_by_type[item.component_type] = free_by_type.get(item.component_type, 0) + max(0, item.quantity - allocated_by_item.get(item.id, 0))
    excess = [{"component_type": key, "free_units": value} for key, value in free_by_type.items() if value >= 3]
    builds_result = await db.execute(select(ManualBuild).where(
        ManualBuild.status == "in_progress", ManualBuild.is_archived.is_(False)
    ))
    active_builds = builds_result.scalars().all()
    blockers = []
    expected_profit = 0.0
    for build in active_builds:
        missing = [component.get("slot") for component in (build.components or []) if not component.get("purchased")]
        if missing:
            blockers.append({"build_id": build.id, "build_name": build.name, "missing": missing})
        if build.last_evaluation and build.total_cost is not None:
            expected_profit += max(0, float(build.last_evaluation.get("mid") or 0) - build.total_cost)
    return {
        "free_units": free_units,
        "reserved_units": reserved_units,
        "consumed_units": consumed_units,
        "free_value": round(free_value, 2),
        "reserved_value": round(reserved_value, 2),
        "consumed_value": round(consumed_value, 2),
        "stale_items": sorted(stale, key=lambda item: item["days"], reverse=True),
        "excess_stock": sorted(excess, key=lambda item: item["free_units"], reverse=True),
        "build_blockers": blockers,
        "expected_profit": round(expected_profit, 2),
    }
