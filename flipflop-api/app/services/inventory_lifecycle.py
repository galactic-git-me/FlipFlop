from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.build import Build, BuildStatus, BuildType
from app.models.inventory_allocation import InventoryAllocation
from app.models.inventory_event import InventoryEvent
from app.models.inventory_unit import InventoryUnit
from app.models.manual_build import ManualBuild


SLOT_BY_COMPONENT_TYPE = {
    "cpu": "CPU",
    "gpu": "GPU",
    "ram": "RAM",
    "motherboard": "Motherboard",
    "ssd": "Storage",
    "storage": "Storage",
    "psu": "PSU",
    "case": "PC Case",
    "cooler": "CPU Cooler",
    "fan": "Case Fans",
    "os": "Operating System",
}


async def orchestration_build_for(
    db: AsyncSession, manual_build: ManualBuild, *, create: bool = True
) -> Build | None:
    result = await db.execute(select(Build).where(Build.manual_build_id == manual_build.id))
    build = result.scalar_one_or_none()
    if build is None and create:
        build = Build(
            build_type=BuildType.PREBUILT,
            manual_build_id=manual_build.id,
            spec_json=manual_build.components or [],
            status=BuildStatus.PLANNING,
        )
        db.add(build)
        await db.flush()
    return build


def add_event(
    db: AsyncSession,
    *,
    inventory_item_id: int,
    event_type: str,
    quantity: int,
    manual_build_id: int | None = None,
    detail: dict | None = None,
) -> None:
    db.add(InventoryEvent(
        inventory_item_id=inventory_item_id,
        manual_build_id=manual_build_id,
        event_type=event_type,
        quantity=quantity,
        detail=detail or {},
    ))


def apply_inventory_component(manual_build: ManualBuild, item, quantity: int = 1) -> None:
    """Make the draft component list and physical allocation agree."""
    slot = SLOT_BY_COMPONENT_TYPE.get(item.component_type.lower(), item.component_type.replace("_", " ").title())
    component = {
        "slot": slot,
        "name": item.component_name,
        "price_paid": item.actual_cost * quantity,
        "source": "manual",
        "listing_url": item.listing_url,
        "image_url": None,
        "purchased": True,
        "inventory_item_id": item.id,
    }
    components = list(manual_build.components or [])
    matching_index = next((index for index, existing in enumerate(components) if existing.get("slot") == slot), None)
    if matching_index is None:
        components.append(component)
    else:
        components[matching_index] = component
    manual_build.components = components
    manual_build.total_cost = sum(float(existing.get("price_paid") or 0) for existing in components)


async def release_manual_build_inventory(
    db: AsyncSession, manual_build: ManualBuild, *, reason: str
) -> int:
    build = await orchestration_build_for(db, manual_build, create=False)
    if build is None:
        return 0
    result = await db.execute(
        select(InventoryAllocation).where(InventoryAllocation.build_id == build.id)
    )
    allocations = result.scalars().all()
    for allocation in allocations:
        add_event(
            db,
            inventory_item_id=allocation.inventory_item_id,
            manual_build_id=manual_build.id,
            event_type="released",
            quantity=allocation.quantity_allocated,
            detail={"reason": reason, "allocation_id": allocation.id},
        )
        unit_result = await db.execute(select(InventoryUnit).where(
            InventoryUnit.inventory_item_id == allocation.inventory_item_id,
            InventoryUnit.status == "reserved",
        ).order_by(InventoryUnit.unit_number))
        unit = unit_result.scalars().first()
        if unit:
            unit.status = "free"
        await db.delete(allocation)
    return len(allocations)


async def record_consumption(db: AsyncSession, manual_build: ManualBuild) -> int:
    build = await orchestration_build_for(db, manual_build, create=False)
    if build is None:
        return 0
    build.status = BuildStatus.FINALISED
    result = await db.execute(
        select(InventoryAllocation).where(InventoryAllocation.build_id == build.id)
    )
    allocations = result.scalars().all()
    for allocation in allocations:
        existing = await db.execute(select(InventoryEvent.id).where(
            InventoryEvent.inventory_item_id == allocation.inventory_item_id,
            InventoryEvent.manual_build_id == manual_build.id,
            InventoryEvent.event_type == "consumed",
        ))
        if existing.scalar_one_or_none() is not None:
            continue
        add_event(
            db,
            inventory_item_id=allocation.inventory_item_id,
            manual_build_id=manual_build.id,
            event_type="consumed",
            quantity=allocation.quantity_allocated,
            detail={"allocation_id": allocation.id},
        )
        unit_result = await db.execute(select(InventoryUnit).where(
            InventoryUnit.inventory_item_id == allocation.inventory_item_id,
            InventoryUnit.status == "reserved",
        ).order_by(InventoryUnit.unit_number))
        unit = unit_result.scalars().first()
        if unit:
            unit.status = "consumed"
    return len(allocations)


async def record_sale(db: AsyncSession, manual_build: ManualBuild, sale_price: float | None) -> int:
    build = await orchestration_build_for(db, manual_build, create=False)
    if build is None:
        return 0
    result = await db.execute(
        select(InventoryAllocation).where(InventoryAllocation.build_id == build.id)
    )
    allocations = result.scalars().all()
    for allocation in allocations:
        existing = await db.execute(select(InventoryEvent.id).where(
            InventoryEvent.inventory_item_id == allocation.inventory_item_id,
            InventoryEvent.manual_build_id == manual_build.id,
            InventoryEvent.event_type == "sold",
        ))
        if existing.scalar_one_or_none() is not None:
            continue
        add_event(
            db,
            inventory_item_id=allocation.inventory_item_id,
            manual_build_id=manual_build.id,
            event_type="sold",
            quantity=allocation.quantity_allocated,
            detail={"sale_price": sale_price},
        )
        unit_result = await db.execute(select(InventoryUnit).where(
            InventoryUnit.inventory_item_id == allocation.inventory_item_id,
            InventoryUnit.status.in_(["consumed", "reserved"]),
        ).order_by(InventoryUnit.unit_number))
        unit = unit_result.scalars().first()
        if unit:
            unit.status = "sold"
    return len(allocations)
