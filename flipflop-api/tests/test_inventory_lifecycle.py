from datetime import datetime

import pytest
from sqlalchemy import select

from app.models import InventoryAllocation, InventoryEvent, InventoryItem, ManualBuild
from app.services.inventory_lifecycle import (
    apply_inventory_component,
    orchestration_build_for,
    record_consumption,
    release_manual_build_inventory,
)


@pytest.mark.asyncio
async def test_reserved_inventory_updates_build_at_actual_cost(db):
    manual_build = ManualBuild(name="Inventory-backed build", components=[], status="in_progress")
    item = InventoryItem(
        component_name="RTX 4070",
        component_type="gpu",
        quantity=1,
        base_price=390,
        shipping_cost=10,
        discount_amount=20,
        purchase_date=datetime.utcnow(),
    )
    db.add_all([manual_build, item])
    await db.flush()
    build = await orchestration_build_for(db, manual_build)
    db.add(InventoryAllocation(
        inventory_item_id=item.id,
        build_id=build.id,
        flip_id=None,
        quantity_allocated=1,
        cost_per_unit_at_allocation=item.actual_cost,
    ))
    apply_inventory_component(manual_build, item)
    await db.commit()

    assert manual_build.components[0]["slot"] == "GPU"
    assert manual_build.components[0]["inventory_item_id"] == item.id
    assert manual_build.components[0]["purchased"] is True
    assert manual_build.total_cost == 380


@pytest.mark.asyncio
async def test_release_returns_allocation_to_free_and_audits(db):
    manual_build = ManualBuild(name="Cancelled draft", components=[], status="in_progress")
    item = InventoryItem(component_name="CPU", component_type="cpu", quantity=1, base_price=100)
    db.add_all([manual_build, item])
    await db.flush()
    build = await orchestration_build_for(db, manual_build)
    db.add(InventoryAllocation(
        inventory_item_id=item.id, build_id=build.id, flip_id=None,
        quantity_allocated=1, cost_per_unit_at_allocation=100,
    ))
    await db.flush()

    assert await release_manual_build_inventory(db, manual_build, reason="test") == 1
    await db.commit()
    assert (await db.execute(select(InventoryAllocation))).scalars().all() == []
    event = (await db.execute(select(InventoryEvent))).scalar_one()
    assert event.event_type == "released"
    assert event.detail["reason"] == "test"


@pytest.mark.asyncio
async def test_marking_build_records_consumption_once(db):
    manual_build = ManualBuild(name="Completed build", components=[], status="built")
    item = InventoryItem(component_name="RAM", component_type="ram", quantity=1, base_price=50)
    db.add_all([manual_build, item])
    await db.flush()
    build = await orchestration_build_for(db, manual_build)
    db.add(InventoryAllocation(
        inventory_item_id=item.id, build_id=build.id, flip_id=None,
        quantity_allocated=1, cost_per_unit_at_allocation=50,
    ))
    await db.flush()

    await record_consumption(db, manual_build)
    await db.flush()
    await record_consumption(db, manual_build)
    await db.commit()
    events = (await db.execute(select(InventoryEvent).where(InventoryEvent.event_type == "consumed"))).scalars().all()
    assert len(events) == 1
