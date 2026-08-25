from datetime import datetime
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from app.database import get_db
from app.models.inventory import InventoryItem
from app.models.inventory_allocation import InventoryAllocation
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
    await db.refresh(new_item)
    return await _build_item_with_allocations(new_item, db)


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


@router.get("/summary/stats")
async def inventory_stats(db: AsyncSession = Depends(get_db)):
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
