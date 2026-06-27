from datetime import datetime
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.database import get_db
from app.models.inventory import InventoryItem
from app.schemas.inventory import InventoryItemIn, InventoryItemOut

router = APIRouter(prefix="/inventory", tags=["inventory"])


@router.get("/", response_model=list[InventoryItemOut])
async def list_inventory(
    component_type: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List all inventory items, optionally filtered by component type."""
    q = select(InventoryItem).order_by(desc(InventoryItem.created_at))
    if component_type:
        q = q.where(InventoryItem.component_type == component_type)
    result = await db.execute(q)
    return result.scalars().all()


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
    return new_item


@router.get("/{item_id}", response_model=InventoryItemOut)
async def get_inventory_item(
    item_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get a single inventory item."""
    result = await db.execute(select(InventoryItem).where(InventoryItem.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        from fastapi import HTTPException
        raise HTTPException(404, "Item not found")
    return item


@router.patch("/{item_id}", response_model=InventoryItemOut)
async def update_inventory_item(
    item_id: int,
    item: InventoryItemIn,
    db: AsyncSession = Depends(get_db),
):
    """Update an inventory item."""
    result = await db.execute(select(InventoryItem).where(InventoryItem.id == item_id))
    db_item = result.scalar_one_or_none()
    if not db_item:
        from fastapi import HTTPException
        raise HTTPException(404, "Item not found")

    db_item.component_name = item.component_name
    db_item.component_type = item.component_type
    db_item.quantity = item.quantity
    db_item.base_price = item.base_price
    db_item.shipping_cost = item.shipping_cost
    db_item.discount_amount = item.discount_amount
    db_item.purchase_date = item.purchase_date or db_item.purchase_date
    db_item.source = item.source
    db_item.notes = item.notes
    db_item.updated_at = datetime.utcnow()

    await db.flush()
    await db.refresh(db_item)
    return db_item


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
