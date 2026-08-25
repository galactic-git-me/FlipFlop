from __future__ import annotations

import csv
import io
from collections import defaultdict
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.build import Build
from app.models.inventory import InventoryItem
from app.models.inventory_allocation import InventoryAllocation
from app.models.inventory_event import InventoryEvent
from app.models.inventory_unit import InventoryReorderRule, InventoryUnit
from app.models.manual_build import ManualBuild
from app.services.inventory_compatibility import TYPE_TO_SLOT, check_component

router = APIRouter(prefix="/inventory-intelligence", tags=["inventory-intelligence"])

ACTIVE_UNIT_STATUSES = {"free", "reserved"}
EXCEPTION_STATUSES = {"quarantined", "faulty", "returned", "spares", "written_off"}
UNIT_STATUSES = {
    "ordered", "dispatched", "delivered", "inspection", "free", "reserved", "consumed",
    "quarantined", "faulty", "returned", "spares", "written_off", "sold",
}


class UnitPatch(BaseModel):
    serial_number: str | None = None
    condition_grade: str | None = None
    status: str | None = None
    storage_location: str | None = None
    warranty_expires_at: datetime | None = None
    test_results: dict | None = None
    photos: list[str] | None = None
    exception_reason: str | None = None
    writeoff_amount: float | None = Field(default=None, ge=0)


class ReorderRuleIn(BaseModel):
    component_type: str
    minimum_free: int = Field(ge=0)
    maximum_free: int = Field(ge=0)
    target_free: int = Field(ge=0)
    notes: str | None = None


def _unit_dict(unit: InventoryUnit) -> dict:
    return {
        "id": unit.id, "inventory_item_id": unit.inventory_item_id, "unit_number": unit.unit_number,
        "serial_number": unit.serial_number, "condition_grade": unit.condition_grade, "status": unit.status,
        "storage_location": unit.storage_location, "warranty_expires_at": unit.warranty_expires_at,
        "test_results": unit.test_results or {}, "photos": unit.photos or [],
        "exception_reason": unit.exception_reason, "writeoff_amount": unit.writeoff_amount,
        "received_at": unit.received_at, "inspected_at": unit.inspected_at,
        "created_at": unit.created_at, "updated_at": unit.updated_at,
    }


async def _ensure_units(db: AsyncSession, item: InventoryItem) -> list[InventoryUnit]:
    result = await db.execute(select(InventoryUnit).where(InventoryUnit.inventory_item_id == item.id).order_by(InventoryUnit.unit_number))
    units = list(result.scalars().all())
    existing_numbers = {unit.unit_number for unit in units}
    initial_status = "ordered" if item.purchase_status in {"PURCHASED", "ORDERED"} and item.reconciliation_status == "PENDING" else "free"
    for number in range(1, item.quantity + 1):
        if number not in existing_numbers:
            unit = InventoryUnit(inventory_item_id=item.id, unit_number=number, status=initial_status)
            db.add(unit)
            units.append(unit)
    if len(units) < item.quantity:
        await db.flush()
    return sorted(units, key=lambda unit: unit.unit_number)


async def _allocation_counts(db: AsyncSession) -> dict[int, int]:
    result = await db.execute(select(
        InventoryAllocation.inventory_item_id, func.sum(InventoryAllocation.quantity_allocated)
    ).group_by(InventoryAllocation.inventory_item_id))
    return {item_id: int(quantity or 0) for item_id, quantity in result.all()}


@router.get("/items/{item_id}/units")
async def list_units(item_id: int, db: AsyncSession = Depends(get_db)):
    item = await db.get(InventoryItem, item_id)
    if not item:
        raise HTTPException(404, "Inventory item not found")
    units = await _ensure_units(db, item)
    await db.commit()
    return [_unit_dict(unit) for unit in units]


@router.patch("/units/{unit_id}")
async def update_unit(unit_id: int, body: UnitPatch, db: AsyncSession = Depends(get_db)):
    unit = await db.get(InventoryUnit, unit_id)
    if not unit:
        raise HTTPException(404, "Inventory unit not found")
    updates = body.model_dump(exclude_unset=True)
    if "status" in updates and updates["status"] not in UNIT_STATUSES:
        raise HTTPException(400, f"Unsupported stock status: {updates['status']}")
    previous_status = unit.status
    for field, value in updates.items():
        setattr(unit, field, value)
    now = datetime.utcnow()
    if unit.status in {"delivered", "inspection", "free"} and unit.received_at is None:
        unit.received_at = now
    if unit.status == "free" and unit.inspected_at is None:
        unit.inspected_at = now
    unit.updated_at = now
    if previous_status != unit.status:
        db.add(InventoryEvent(
            inventory_item_id=unit.inventory_item_id,
            event_type=unit.status,
            quantity=1,
            detail={"unit_id": unit.id, "from": previous_status, "reason": unit.exception_reason},
        ))
    await db.commit()
    await db.refresh(unit)
    return _unit_dict(unit)


@router.get("/units/{unit_id}/label")
async def unit_label(unit_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(InventoryUnit, InventoryItem).join(
        InventoryItem, InventoryItem.id == InventoryUnit.inventory_item_id
    ).where(InventoryUnit.id == unit_id))
    row = result.one_or_none()
    if not row:
        raise HTTPException(404, "Inventory unit not found")
    unit, item = row
    return {
        "unit_id": unit.id, "sku": f"FF-INV-{item.id:06d}-{unit.unit_number:02d}",
        "component_name": item.component_name, "serial_number": unit.serial_number,
        "location": unit.storage_location, "qr_payload": f"/inventory?unit={unit.id}",
    }


@router.get("/builds/{manual_build_id}/candidates")
async def build_inventory_candidates(manual_build_id: int, db: AsyncSession = Depends(get_db)):
    build = await db.get(ManualBuild, manual_build_id)
    if not build:
        raise HTTPException(404, "Build not found")
    allocations = await _allocation_counts(db)
    result = await db.execute(select(InventoryItem))
    response = []
    for item in result.scalars().all():
        free = item.quantity - allocations.get(item.id, 0)
        if free <= 0:
            continue
        compatibility = check_component(build.components or [], item.component_type, item.component_name)
        response.append({
            "id": item.id, "component_name": item.component_name, "component_type": item.component_type,
            "slot": TYPE_TO_SLOT.get(item.component_type, item.component_type.title()), "quantity_free": free,
            "actual_cost": item.actual_cost, "source": item.source, "compatible": compatibility.compatible,
            "confidence": compatibility.confidence, "reasons": compatibility.reasons,
            "warnings": compatibility.warnings,
        })
    return sorted(response, key=lambda item: (not item["compatible"], item["actual_cost"]))


@router.get("/reorder-rules")
async def reorder_rules(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(InventoryReorderRule).order_by(InventoryReorderRule.component_type))
    return result.scalars().all()


@router.put("/reorder-rules/{component_type}")
async def upsert_reorder_rule(component_type: str, body: ReorderRuleIn, db: AsyncSession = Depends(get_db)):
    if body.minimum_free > body.target_free or body.target_free > body.maximum_free:
        raise HTTPException(400, "Targets must satisfy minimum ≤ target ≤ maximum")
    result = await db.execute(select(InventoryReorderRule).where(InventoryReorderRule.component_type == component_type))
    rule = result.scalar_one_or_none()
    if rule is None:
        rule = InventoryReorderRule(component_type=component_type)
        db.add(rule)
    rule.minimum_free = body.minimum_free
    rule.maximum_free = body.maximum_free
    rule.target_free = body.target_free
    rule.notes = body.notes
    await db.commit()
    await db.refresh(rule)
    return rule


@router.get("/forecast")
async def stock_forecast(days: int = Query(30, ge=7, le=180), db: AsyncSession = Depends(get_db)):
    allocations = await _allocation_counts(db)
    result = await db.execute(select(InventoryItem))
    items = result.scalars().all()
    free_by_type: dict[str, int] = defaultdict(int)
    cost_by_type: dict[str, list[float]] = defaultdict(list)
    for item in items:
        free_by_type[item.component_type] += max(0, item.quantity - allocations.get(item.id, 0))
        cost_by_type[item.component_type].append(item.actual_cost)
    since = datetime.utcnow() - timedelta(days=90)
    events = await db.execute(select(InventoryEvent).where(
        InventoryEvent.event_type.in_(["consumed", "sold"]), InventoryEvent.created_at >= since
    ))
    velocity: dict[str, int] = defaultdict(int)
    for event in events.scalars().all():
        item = next((candidate for candidate in items if candidate.id == event.inventory_item_id), None)
        if item:
            velocity[item.component_type] += event.quantity
    rules_result = await db.execute(select(InventoryReorderRule))
    rules = {rule.component_type: rule for rule in rules_result.scalars().all()}
    all_types = sorted(set(free_by_type) | set(rules))
    rows = []
    for component_type in all_types:
        monthly_usage = velocity.get(component_type, 0) / 3
        projected_usage = monthly_usage * days / 30
        projected_free = max(0, free_by_type.get(component_type, 0) - projected_usage)
        rule = rules.get(component_type)
        target = rule.target_free if rule else 1
        recommendation = "buy" if projected_free < (rule.minimum_free if rule else 0) else "liquidate" if rule and free_by_type.get(component_type, 0) > rule.maximum_free else "hold"
        units = max(0, int(round(target - projected_free))) if recommendation == "buy" else max(0, free_by_type.get(component_type, 0) - target) if recommendation == "liquidate" else 0
        average_cost = sum(cost_by_type.get(component_type, [0])) / max(1, len(cost_by_type.get(component_type, [])))
        rows.append({
            "component_type": component_type, "free_now": free_by_type.get(component_type, 0),
            "monthly_usage": round(monthly_usage, 2), "projected_free": round(projected_free, 2),
            "recommendation": recommendation, "units": units,
            "estimated_capital": round(units * average_cost, 2) if recommendation == "buy" else 0,
        })
    return {"horizon_days": days, "rows": rows, "capital_required": round(sum(row["estimated_capital"] for row in rows), 2)}


@router.get("/sourcing-adjustments")
async def sourcing_adjustments(db: AsyncSession = Depends(get_db)):
    forecast = await stock_forecast(30, db)
    result = []
    for row in forecast["rows"]:
        adjustment = 15 if row["recommendation"] == "buy" else -12 if row["recommendation"] == "liquidate" else 0
        reason = "Restock or unblock builds" if adjustment > 0 else "Excess free stock; avoid duplicates" if adjustment < 0 else "Stock level is balanced"
        result.append({**row, "deal_score_adjustment": adjustment, "reason": reason})
    return result


@router.get("/build-opportunities")
async def build_opportunities(db: AsyncSession = Depends(get_db)):
    allocations = await _allocation_counts(db)
    result = await db.execute(select(InventoryItem))
    grouped: dict[str, list[InventoryItem]] = defaultdict(list)
    for item in result.scalars().all():
        if item.quantity - allocations.get(item.id, 0) > 0:
            grouped[item.component_type].append(item)
    for candidates in grouped.values():
        candidates.sort(key=lambda item: item.actual_cost)
    required = ["cpu", "motherboard", "ram", "gpu", "ssd", "psu", "case", "cooler"]
    chosen: dict[str, InventoryItem] = {}
    warnings: list[str] = []
    for component_type in required:
        for item in grouped.get(component_type, []):
            compatibility = check_component([
                {"slot": TYPE_TO_SLOT[key], "name": value.component_name} for key, value in chosen.items()
            ], component_type, item.component_name)
            if compatibility.compatible:
                chosen[component_type] = item
                warnings.extend(compatibility.warnings)
                break
    missing = [component_type for component_type in required if component_type not in chosen]
    completion = len(chosen) / len(required)
    total_cost = sum(item.actual_cost for item in chosen.values())
    return [{
        "name": "Best build from owned stock", "completion_pct": round(completion * 100),
        "ready": not missing, "missing": missing, "owned_cost": round(total_cost, 2),
        "additional_spend_estimate": round(sum(
            (sum(candidate.actual_cost for candidate in grouped.get(component_type, [])) / len(grouped[component_type]))
            if grouped.get(component_type) else 0 for component_type in missing
        ), 2),
        "components": [{"inventory_item_id": item.id, "component_type": key, "name": item.component_name, "cost": item.actual_cost} for key, item in chosen.items()],
        "warnings": sorted(set(warnings)),
    }]


@router.get("/accounting-export.csv")
async def accounting_export(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(InventoryItem).order_by(InventoryItem.purchase_date))
    items = result.scalars().all()
    allocations = await _allocation_counts(db)
    units_result = await db.execute(select(InventoryUnit))
    units_by_item: dict[int, list[InventoryUnit]] = defaultdict(list)
    for unit in units_result.scalars().all():
        units_by_item[unit.inventory_item_id].append(unit)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["inventory_id", "purchase_date", "component", "type", "source", "quantity", "unit_cost_gbp", "total_cost_gbp", "allocated_units", "free_units", "writeoffs_gbp", "stock_value_gbp"])
    for item in items:
        allocated = allocations.get(item.id, 0)
        writeoffs = sum(unit.writeoff_amount or (item.actual_cost if unit.status == "written_off" else 0) for unit in units_by_item.get(item.id, []))
        free = max(0, item.quantity - allocated)
        writer.writerow([item.id, item.purchase_date.isoformat(), item.component_name, item.component_type, item.source or "", item.quantity, f"{item.actual_cost:.2f}", f"{item.total_landed_cost:.2f}", allocated, free, f"{writeoffs:.2f}", f"{free * item.actual_cost:.2f}"])
    output.seek(0)
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=flipflop-inventory-accounting.csv"})
