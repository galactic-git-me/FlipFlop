"""Build stage items API — checklist management during BUILD phase."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from datetime import datetime
from pydantic import BaseModel
from app.database import get_db
from app.models.build_stage_item import BuildStageItem, BuildStageItemSection
from app.models.build import Build, BuildStatus

router = APIRouter(prefix="/api/build-stage-items", tags=["build-stage-items"])


class BuildStageItemCreate(BaseModel):
    section: str
    item: str
    is_required: bool = True


class BuildStageItemUpdate(BaseModel):
    item: str | None = None
    is_required: bool | None = None
    completed: bool | None = None
    notes: str | None = None
    file_url: str | None = None


class BuildStageItemResponse(BaseModel):
    id: int
    build_id: int
    section: str
    item: str
    is_required: bool
    completed: bool
    completed_at: datetime | None
    notes: str | None
    file_url: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


@router.get("/builds/{build_id}", response_model=list[BuildStageItemResponse])
async def list_build_stage_items(
    build_id: int,
    section: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """List checklist items for a build, optionally filtered by section."""
    query = select(BuildStageItem).where(BuildStageItem.build_id == build_id)
    if section:
        query = query.where(BuildStageItem.section == section)
    query = query.order_by(BuildStageItem.section, BuildStageItem.id)

    result = await db.execute(query)
    return result.scalars().all()


@router.post("/builds/{build_id}/items", response_model=BuildStageItemResponse)
async def create_build_stage_item(
    build_id: int,
    item: BuildStageItemCreate,
    db: AsyncSession = Depends(get_db),
):
    """Add a new checklist item to a build."""
    build_result = await db.execute(select(Build).where(Build.id == build_id))
    if not build_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Build not found")

    db_item = BuildStageItem(
        build_id=build_id,
        section=item.section,
        item=item.item,
        is_required=item.is_required,
    )
    db.add(db_item)
    await db.commit()
    await db.refresh(db_item)
    return db_item


@router.patch("/items/{item_id}", response_model=BuildStageItemResponse)
async def update_build_stage_item(
    item_id: int,
    update: BuildStageItemUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a checklist item (mark complete, add notes, attach files)."""
    result = await db.execute(select(BuildStageItem).where(BuildStageItem.id == item_id))
    db_item = result.scalar_one_or_none()
    if not db_item:
        raise HTTPException(status_code=404, detail="Item not found")

    if update.item is not None:
        db_item.item = update.item
    if update.is_required is not None:
        db_item.is_required = update.is_required
    if update.completed is not None:
        db_item.completed = update.completed
        db_item.completed_at = datetime.utcnow() if update.completed else None
    if update.notes is not None:
        db_item.notes = update.notes
    if update.file_url is not None:
        db_item.file_url = update.file_url

    db_item.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(db_item)
    return db_item


@router.delete("/items/{item_id}")
async def delete_build_stage_item(
    item_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Delete a checklist item."""
    result = await db.execute(select(BuildStageItem).where(BuildStageItem.id == item_id))
    db_item = result.scalar_one_or_none()
    if not db_item:
        raise HTTPException(status_code=404, detail="Item not found")

    await db.delete(db_item)
    await db.commit()
    return {"deleted": True}


# Default checklist templates per section
DEFAULT_ITEMS = {
    "software": [
        {"item": "Install Windows OS", "is_required": True},
        {"item": "Install drivers", "is_required": True},
        {"item": "Install monitoring software", "is_required": False},
        {"item": "Run stress tests", "is_required": False},
    ],
    "model_3d": [
        {"item": "Capture 3D model (Capture3DAsset)", "is_required": False},
        {"item": "Generate 3D preview", "is_required": False},
    ],
    "pictures": [
        {"item": "Photograph build exterior", "is_required": True},
        {"item": "Photograph internals", "is_required": False},
        {"item": "Generate marketing photos", "is_required": True},
    ],
    "performance_tests": [
        {"item": "Run Cinebench CPU test", "is_required": False},
        {"item": "Run 3DMark GPU test", "is_required": False},
        {"item": "Verify temps under load", "is_required": True},
    ],
    "registration_plate": [
        {"item": "Create registration plate graphic", "is_required": True},
        {"item": "Print/attach registration plate", "is_required": True},
    ],
}


@router.post("/builds/{build_id}/seed-defaults")
async def seed_default_checklist(
    build_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Seed a build with default checklist items for all sections.

    Safe to call multiple times — only adds items that don't already exist.
    """
    build_result = await db.execute(select(Build).where(Build.id == build_id))
    if not build_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Build not found")

    added_count = 0
    for section, items in DEFAULT_ITEMS.items():
        for item_spec in items:
            # Check if this item already exists
            existing = await db.execute(
                select(BuildStageItem).where(
                    and_(
                        BuildStageItem.build_id == build_id,
                        BuildStageItem.section == section,
                        BuildStageItem.item == item_spec["item"],
                    )
                )
            )
            if not existing.scalar_one_or_none():
                db_item = BuildStageItem(
                    build_id=build_id,
                    section=section,
                    item=item_spec["item"],
                    is_required=item_spec.get("is_required", True),
                )
                db.add(db_item)
                added_count += 1

    await db.commit()
    return {"build_id": build_id, "added": added_count}
