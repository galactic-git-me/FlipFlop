"""PC Builder API - build creation, purchase planning, and analytics."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from datetime import datetime
from app.database import get_db
from app.models.pc_builder import PCBuild, PCBuildPurchasePlan, PCBuildStage
from app.models.build import Build, BuildType, BuildStatus
from app.services.ai_build_generator import generate_ai_builds, load_ai_builds
from pydantic import BaseModel

router = APIRouter(prefix="/api/pc-builder", tags=["pc-builder"])


@router.get("/ai-generated-builds")
async def get_ai_generated_builds():
    """Cached top-6 AI-generated Super Gem builds (see
    app.services.ai_build_generator), refreshed on a schedule. Instant read —
    does not call eBay on this request."""
    return load_ai_builds()


@router.post("/ai-generated-builds/refresh")
async def refresh_ai_generated_builds():
    """Manually trigger regeneration (hits eBay live — slow, ~10 validation
    lookups). Normally handled by the scheduled job instead."""
    return await generate_ai_builds()


class ComponentSelection(BaseModel):
    component_type: str
    listing_id: str | None = None
    title: str | None = None
    seller_name: str | None = None
    actual_price: float | None = None
    market_new_price: float | None = None
    market_used_price: float | None = None


class PCBuildCreate(BaseModel):
    name: str
    playbook_id: str
    playbook_tier: str
    components: list[ComponentSelection] | None = None
    estimated_total_cost: float = 0.0
    estimated_market_new_price: float | None = None
    estimated_market_used_price: float | None = None
    estimated_profit: float | None = None
    notes: str | None = None


class PCBuildUpdate(BaseModel):
    name: str | None = None
    components: list[ComponentSelection] | None = None
    estimated_total_cost: float | None = None
    estimated_market_new_price: float | None = None
    estimated_market_used_price: float | None = None
    estimated_profit: float | None = None
    notes: str | None = None


class PCBuildResponse(BaseModel):
    id: int
    name: str
    playbook_id: str
    playbook_tier: str
    stage: str
    status: str
    components: dict | None = None
    estimated_total_cost: float
    estimated_market_new_price: float | None
    estimated_market_used_price: float | None
    estimated_profit: float | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None

    class Config:
        from_attributes = True


@router.post("/builds", response_model=PCBuildResponse)
async def create_build(
    build: PCBuildCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new PC build (draft)."""
    components_data = []
    if build.components:
        components_data = [c.model_dump() if hasattr(c, 'model_dump') else c.dict() for c in build.components]

    db_build = PCBuild(
        name=build.name,
        playbook_id=build.playbook_id,
        playbook_tier=build.playbook_tier,
        status="draft",
        components={"components": components_data},
        estimated_total_cost=build.estimated_total_cost,
        estimated_market_new_price=build.estimated_market_new_price,
        estimated_market_used_price=build.estimated_market_used_price,
        estimated_profit=build.estimated_profit,
        notes=build.notes,
    )
    db.add(db_build)
    await db.commit()
    await db.refresh(db_build)
    return db_build


@router.get("/builds", response_model=list[PCBuildResponse])
async def list_builds(
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """List all PC builds (optionally filtered by status: draft/completed)."""
    query = select(PCBuild)
    if status:
        query = query.where(PCBuild.status == status)
    query = query.order_by(desc(PCBuild.updated_at))

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/builds/{build_id}", response_model=PCBuildResponse)
async def get_build(
    build_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific build."""
    result = await db.execute(select(PCBuild).where(PCBuild.id == build_id))
    build = result.scalar_one_or_none()
    if not build:
        raise HTTPException(status_code=404, detail="Build not found")
    return build


@router.patch("/builds/{build_id}", response_model=PCBuildResponse)
async def update_build(
    build_id: int,
    update: PCBuildUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a build."""
    result = await db.execute(select(PCBuild).where(PCBuild.id == build_id))
    build = result.scalar_one_or_none()
    if not build:
        raise HTTPException(status_code=404, detail="Build not found")

    if update.name is not None:
        build.name = update.name
    if update.components is not None:
        build.components = {"components": [c.dict() for c in update.components]}
    if update.estimated_total_cost is not None:
        build.estimated_total_cost = update.estimated_total_cost
    if update.estimated_market_new_price is not None:
        build.estimated_market_new_price = update.estimated_market_new_price
    if update.estimated_market_used_price is not None:
        build.estimated_market_used_price = update.estimated_market_used_price
    if update.estimated_profit is not None:
        build.estimated_profit = update.estimated_profit
    if update.notes is not None:
        build.notes = update.notes

    build.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(build)
    return build


@router.post("/builds/{build_id}/complete")
async def complete_build(
    build_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Mark a build as completed and create a purchase plan."""
    result = await db.execute(select(PCBuild).where(PCBuild.id == build_id))
    build = result.scalar_one_or_none()
    if not build:
        raise HTTPException(status_code=404, detail="Build not found")

    build.status = "completed"
    build.completed_at = datetime.utcnow()
    await db.commit()

    # Create purchase plan
    components = build.components.get("components", []) if build.components else []
    purchase_plan = PCBuildPurchasePlan(
        build_id=build.id,
        build_name=build.name,
        items={"items": components},
        estimated_total_cost=build.estimated_total_cost,
        estimated_resale_new=build.estimated_market_new_price,
        estimated_resale_used=build.estimated_market_used_price,
        estimated_profit=build.estimated_profit,
        items_total_count=len(components),
    )
    db.add(purchase_plan)
    await db.commit()
    await db.refresh(purchase_plan)

    return {"build_id": build.id, "purchase_plan_id": purchase_plan.id}


@router.post("/builds/{build_id}/start-build")
async def start_build(
    build_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Transition a PCBuild from design stage to build stage.

    Creates a shared Build orchestration record that links this PCBuild
    to the unified build fulfillment pipeline (inventory, checklist, final sale).

    Only allowed when:
    - PCBuild.stage == "design" (not already building or selling)
    - All required component slots are filled (components list not empty)
    """
    result = await db.execute(select(PCBuild).where(PCBuild.id == build_id))
    build = result.scalar_one_or_none()
    if not build:
        raise HTTPException(status_code=404, detail="Build not found")

    if build.stage != PCBuildStage.DESIGN:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot start build: stage is {build.stage.value}, not design",
        )

    components = build.components.get("components", []) if build.components else []
    if not components:
        raise HTTPException(
            status_code=400,
            detail="Cannot start build: no components selected",
        )

    orchestration_build = Build(
        build_type=BuildType.PREBUILT,
        pcbuild_id=build.id,
        playbook_id=build.playbook_id,
        spec_json=build.components,
        status=BuildStatus.PLANNING,
    )
    db.add(orchestration_build)
    await db.commit()
    await db.refresh(orchestration_build)

    build.stage = PCBuildStage.BUILD
    build.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(build)

    return {
        "pcbuild_id": build.id,
        "build_id": orchestration_build.id,
        "stage": build.stage.value,
    }


@router.get("/purchase-plans/{plan_id}")
async def get_purchase_plan(
    plan_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get a purchase plan."""
    result = await db.execute(
        select(PCBuildPurchasePlan).where(PCBuildPurchasePlan.id == plan_id)
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Purchase plan not found")
    return plan


@router.patch("/purchase-plans/{plan_id}/update-item")
async def update_purchase_item(
    plan_id: int,
    item_index: int,
    actual_price: float | None = None,
    purchased: bool | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Update a specific item in the purchase plan with actual price."""
    result = await db.execute(
        select(PCBuildPurchasePlan).where(PCBuildPurchasePlan.id == plan_id)
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Purchase plan not found")

    items = plan.items.get("items", [])
    if item_index < 0 or item_index >= len(items):
        raise HTTPException(status_code=400, detail="Invalid item index")

    if actual_price is not None:
        items[item_index]["actual_price"] = actual_price
    if purchased is not None:
        items[item_index]["purchased"] = purchased

    # Recalculate totals
    plan.items = {"items": items}
    actual_total = sum(
        item.get("actual_price", item.get("estimated_price", 0))
        for item in items
        if item.get("purchased", False)
    )
    plan.actual_total_cost = actual_total
    plan.items_purchased_count = sum(1 for item in items if item.get("purchased", False))

    # Update profit if resale prices exist
    if plan.estimated_resale_new or plan.estimated_resale_used:
        avg_resale = (
            (plan.estimated_resale_new or 0) + (plan.estimated_resale_used or 0)
        ) / 2
        plan.actual_profit = avg_resale - actual_total

    plan.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(plan)
    return plan


@router.get("/builds/needs-attention/count")
async def count_builds_needing_attention(
    db: AsyncSession = Depends(get_db),
):
    """Get count of Made-to-Order builds needing admin attention (new sales detected via email monitor)."""
    result = await db.execute(
        select(Build).where(Build.needs_attention == True)
    )
    builds = result.scalars().all()
    return {"count": len(builds), "build_ids": [b.id for b in builds]}
