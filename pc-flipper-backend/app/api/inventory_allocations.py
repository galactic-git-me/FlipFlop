from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.inventory import InventoryItem
from app.models.inventory_allocation import InventoryAllocation
from app.models.flip import Flip
from app.schemas.inventory_allocation import InventoryAllocationIn, InventoryAllocationPartialIn, InventoryAllocationOut

router = APIRouter(prefix="/inventory-allocations", tags=["inventory-allocations"])


@router.post("/", response_model=InventoryAllocationOut, status_code=201)
async def create_allocation(
    allocation: InventoryAllocationIn,
    db: AsyncSession = Depends(get_db),
):
    """Create a new inventory allocation."""
    # Verify inventory_item_id exists
    result = await db.execute(select(InventoryItem).where(InventoryItem.id == allocation.inventory_item_id))
    inventory_item = result.scalar_one_or_none()
    if not inventory_item:
        raise HTTPException(404, f"Inventory item {allocation.inventory_item_id} not found")

    # Verify flip_id exists
    result = await db.execute(select(Flip).where(Flip.id == allocation.flip_id))
    flip = result.scalar_one_or_none()
    if not flip:
        raise HTTPException(404, f"Flip {allocation.flip_id} not found")

    # Verify quantity_allocated doesn't exceed unallocated inventory
    # First, get total allocated for this inventory item
    result = await db.execute(
        select(InventoryAllocation)
        .where(InventoryAllocation.inventory_item_id == allocation.inventory_item_id)
    )
    existing_allocations = result.scalars().all()
    total_allocated = sum(a.quantity_allocated for a in existing_allocations)
    unallocated = inventory_item.quantity - total_allocated

    if allocation.quantity_allocated > unallocated:
        raise HTTPException(
            400,
            f"Allocation quantity {allocation.quantity_allocated} exceeds unallocated inventory {unallocated}",
        )

    # Create allocation with cost_per_unit_at_allocation from inventory_item.actual_cost
    new_allocation = InventoryAllocation(
        inventory_item_id=allocation.inventory_item_id,
        flip_id=allocation.flip_id,
        quantity_allocated=allocation.quantity_allocated,
        cost_per_unit_at_allocation=inventory_item.actual_cost,
        notes=allocation.notes,
    )
    db.add(new_allocation)
    await db.flush()
    await db.refresh(new_allocation)
    return new_allocation


@router.get("/", response_model=list[InventoryAllocationOut])
async def list_allocations(
    flip_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List all allocations, optionally filtered by flip_id."""
    q = select(InventoryAllocation)
    if flip_id is not None:
        q = q.where(InventoryAllocation.flip_id == flip_id)
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/{allocation_id}", response_model=InventoryAllocationOut)
async def get_allocation(
    allocation_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get a single allocation by ID."""
    result = await db.execute(select(InventoryAllocation).where(InventoryAllocation.id == allocation_id))
    allocation = result.scalar_one_or_none()
    if not allocation:
        raise HTTPException(404, f"Allocation {allocation_id} not found")
    return allocation


@router.patch("/{allocation_id}", response_model=InventoryAllocationOut)
async def update_allocation(
    allocation_id: int,
    allocation_update: InventoryAllocationPartialIn,
    db: AsyncSession = Depends(get_db),
):
    """Update an allocation. Only provided fields are updated."""
    result = await db.execute(select(InventoryAllocation).where(InventoryAllocation.id == allocation_id))
    db_allocation = result.scalar_one_or_none()
    if not db_allocation:
        raise HTTPException(404, f"Allocation {allocation_id} not found")

    # Validate inventory_item_id if provided
    if allocation_update.inventory_item_id is not None:
        result = await db.execute(select(InventoryItem).where(InventoryItem.id == allocation_update.inventory_item_id))
        if not result.scalar_one_or_none():
            raise HTTPException(404, f"Inventory item {allocation_update.inventory_item_id} not found")

    # Validate flip_id if provided
    if allocation_update.flip_id is not None:
        result = await db.execute(select(Flip).where(Flip.id == allocation_update.flip_id))
        if not result.scalar_one_or_none():
            raise HTTPException(404, f"Flip {allocation_update.flip_id} not found")

    # Update only provided fields
    if allocation_update.inventory_item_id is not None:
        db_allocation.inventory_item_id = allocation_update.inventory_item_id
    if allocation_update.flip_id is not None:
        db_allocation.flip_id = allocation_update.flip_id
    if allocation_update.quantity_allocated is not None:
        # Revalidate quantity if changed
        inventory_item = await db.execute(
            select(InventoryItem).where(InventoryItem.id == db_allocation.inventory_item_id)
        )
        inv_item = inventory_item.scalar_one_or_none()
        if inv_item:
            # Get total allocated for this inventory item (excluding current allocation)
            result = await db.execute(
                select(InventoryAllocation)
                .where(InventoryAllocation.inventory_item_id == db_allocation.inventory_item_id)
                .where(InventoryAllocation.id != allocation_id)
            )
            existing_allocations = result.scalars().all()
            total_allocated = sum(a.quantity_allocated for a in existing_allocations)
            unallocated = inv_item.quantity - total_allocated

            if allocation_update.quantity_allocated > unallocated:
                raise HTTPException(
                    400,
                    f"Allocation quantity {allocation_update.quantity_allocated} exceeds unallocated inventory {unallocated}",
                )
        db_allocation.quantity_allocated = allocation_update.quantity_allocated
    if allocation_update.notes is not None:
        db_allocation.notes = allocation_update.notes

    db_allocation.updated_at = datetime.utcnow()

    await db.flush()
    await db.refresh(db_allocation)
    return db_allocation


@router.delete("/{allocation_id}", status_code=204)
async def delete_allocation(
    allocation_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Delete an allocation."""
    result = await db.execute(select(InventoryAllocation).where(InventoryAllocation.id == allocation_id))
    db_allocation = result.scalar_one_or_none()
    if not db_allocation:
        raise HTTPException(404, f"Allocation {allocation_id} not found")

    await db.delete(db_allocation)
    await db.commit()
