"""Admin API endpoints for curated builds management."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from datetime import datetime
import json
from pathlib import Path

from app.database import get_db
from app.models.curated_build import CuratedBuild

router = APIRouter(prefix="/curated-builds", tags=["curated-builds"])


class CuratedBuildCreate(BaseModel):
    definition_id: str
    segment: str
    tier: str
    name: str
    description: str
    use: str
    components: dict
    estimated_price_gbp: Optional[float] = None
    components_cost: Optional[float] = None
    markup_percentage: float = 25.0
    display_order: int = 0
    is_featured: bool = False
    notes: Optional[str] = None


class CuratedBuildUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    use: Optional[str] = None
    estimated_price_gbp: Optional[float] = None
    components_cost: Optional[float] = None
    markup_percentage: Optional[float] = None
    display_order: Optional[int] = None
    is_featured: Optional[bool] = None
    is_available: Optional[bool] = None
    availability_notes: Optional[str] = None
    notes: Optional[str] = None


class CuratedBuildOut(BaseModel):
    id: int
    definition_id: str
    segment: str
    tier: str
    name: str
    description: str
    use: str
    components: dict
    estimated_price_gbp: Optional[float]
    components_cost: Optional[float]
    markup_percentage: float
    is_published: bool
    published_at: Optional[datetime]
    display_order: int
    is_featured: bool
    is_available: bool
    availability_notes: Optional[str]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


@router.get("/definitions")
async def get_curated_build_definitions():
    """Get all curated build definitions from the JSON file."""
    definitions_path = Path(__file__).resolve().parents[2] / 'data/curated_build_definitions.json'
    definitions = json.loads(definitions_path.read_text(encoding='utf-8'))
    return definitions


@router.post("", response_model=CuratedBuildOut)
async def create_curated_build(build: CuratedBuildCreate, db: AsyncSession = Depends(get_db)):
    """Create a new curated build from a definition."""
    # Check if definition_id already exists
    existing = (await db.execute(
        select(CuratedBuild).where(CuratedBuild.definition_id == build.definition_id)
    )).scalar_one_or_none()
    
    if existing:
        raise HTTPException(status_code=409, detail="Curated build with this definition_id already exists")
    
    new_build = CuratedBuild(**build.model_dump())
    db.add(new_build)
    await db.commit()
    await db.refresh(new_build)
    return new_build


@router.get("", response_model=list[CuratedBuildOut])
async def list_curated_builds(
    published_only: bool = False,
    segment: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """List all curated builds with optional filtering."""
    query = select(CuratedBuild)
    
    if published_only:
        query = query.where(CuratedBuild.is_published == True)
    
    if segment:
        query = query.where(CuratedBuild.segment == segment)
    
    query = query.order_by(CuratedBuild.display_order, CuratedBuild.created_at.desc())
    
    result = await db.execute(query)
    builds = result.scalars().all()
    return builds


@router.get("/{build_id}", response_model=CuratedBuildOut)
async def get_curated_build(build_id: int, db: AsyncSession = Depends(get_db)):
    """Get a single curated build by ID."""
    build = (await db.execute(
        select(CuratedBuild).where(CuratedBuild.id == build_id)
    )).scalar_one_or_none()
    
    if not build:
        raise HTTPException(status_code=404, detail="Curated build not found")
    
    return build


@router.patch("/{build_id}", response_model=CuratedBuildOut)
async def update_curated_build(
    build_id: int,
    updates: CuratedBuildUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update a curated build."""
    build = (await db.execute(
        select(CuratedBuild).where(CuratedBuild.id == build_id)
    )).scalar_one_or_none()
    
    if not build:
        raise HTTPException(status_code=404, detail="Curated build not found")
    
    for field, value in updates.model_dump(exclude_unset=True).items():
        setattr(build, field, value)
    
    build.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(build)
    return build


@router.post("/{build_id}/publish", response_model=CuratedBuildOut)
async def publish_curated_build(build_id: int, db: AsyncSession = Depends(get_db)):
    """Publish a curated build to make it visible on the storefront."""
    build = (await db.execute(
        select(CuratedBuild).where(CuratedBuild.id == build_id)
    )).scalar_one_or_none()
    
    if not build:
        raise HTTPException(status_code=404, detail="Curated build not found")
    
    build.is_published = True
    build.published_at = datetime.utcnow()
    build.updated_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(build)
    return build


@router.post("/{build_id}/unpublish", response_model=CuratedBuildOut)
async def unpublish_curated_build(build_id: int, db: AsyncSession = Depends(get_db)):
    """Unpublish a curated build to hide it from the storefront."""
    build = (await db.execute(
        select(CuratedBuild).where(CuratedBuild.id == build_id)
    )).scalar_one_or_none()
    
    if not build:
        raise HTTPException(status_code=404, detail="Curated build not found")
    
    build.is_published = False
    build.updated_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(build)
    return build


@router.delete("/{build_id}")
async def delete_curated_build(build_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a curated build."""
    build = (await db.execute(
        select(CuratedBuild).where(CuratedBuild.id == build_id)
    )).scalar_one_or_none()
    
    if not build:
        raise HTTPException(status_code=404, detail="Curated build not found")
    
    await db.delete(build)
    await db.commit()
    return {"message": "Curated build deleted successfully"}


@router.post("/sync-from-definitions")
async def sync_curated_builds_from_definitions(db: AsyncSession = Depends(get_db)):
    """
    Sync curated builds from the definitions JSON file.
    Creates new builds for definitions that don't exist yet.
    """
    definitions_path = Path(__file__).resolve().parents[2] / 'data/curated_build_definitions.json'
    definitions = json.loads(definitions_path.read_text(encoding='utf-8'))
    
    created_count = 0
    skipped_count = 0
    
    for build_def in definitions.get('builds', []):
        definition_id = build_def['id']
        
        # Check if already exists
        existing = (await db.execute(
            select(CuratedBuild).where(CuratedBuild.definition_id == definition_id)
        )).scalar_one_or_none()
        
        if existing:
            skipped_count += 1
            continue
        
        # Create new build
        new_build = CuratedBuild(
            definition_id=definition_id,
            segment=build_def['segment'],
            tier=build_def['tier'],
            name=build_def['name'],
            description=build_def['description'],
            use=build_def['use'],
            components=build_def['components'],
            is_published=False,
            display_order=0
        )
        
        db.add(new_build)
        created_count += 1
    
    await db.commit()
    
    return {
        "message": "Sync completed",
        "created": created_count,
        "skipped": skipped_count
    }
