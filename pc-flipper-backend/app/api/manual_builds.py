import json
import re
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.manual_build import ManualBuild
from app.schemas.manual_build import (
    ManualBuildCreate, ManualBuildPatch, ManualBuildOut, ManualBuildSummary,
    EvaluationResult, EvaluationSuggestion,
)
from app.services import ai_service

router = APIRouter(prefix="/manual-builds", tags=["manual-builds"])


@router.post("/", response_model=ManualBuildOut, status_code=201)
async def create_build(body: ManualBuildCreate, db: AsyncSession = Depends(get_db)):
    build = ManualBuild(name=body.name, components=[], total_cost=None)
    db.add(build)
    await db.flush()
    await db.refresh(build)
    return build


@router.get("/", response_model=list[ManualBuildSummary])
async def list_builds(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ManualBuild).order_by(ManualBuild.updated_at.desc())
    )
    builds = result.scalars().all()
    return [
        ManualBuildSummary(
            id=b.id,
            name=b.name,
            total_cost=b.total_cost,
            component_count=len(b.components or []),
            updated_at=b.updated_at,
        )
        for b in builds
    ]


@router.get("/{build_id}", response_model=ManualBuildOut)
async def get_build(build_id: int, db: AsyncSession = Depends(get_db)):
    build = await db.get(ManualBuild, build_id)
    if not build:
        raise HTTPException(404, "Build not found")
    return build


@router.patch("/{build_id}", response_model=ManualBuildOut)
async def patch_build(build_id: int, body: ManualBuildPatch, db: AsyncSession = Depends(get_db)):
    build = await db.get(ManualBuild, build_id)
    if not build:
        raise HTTPException(404, "Build not found")
    if body.name is not None:
        build.name = body.name
    if body.components is not None:
        build.components = [c.model_dump() for c in body.components]
        build.total_cost = sum(c.price_paid for c in body.components)
    build.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(build)
    return build


@router.delete("/{build_id}", status_code=204)
async def delete_build(build_id: int, db: AsyncSession = Depends(get_db)):
    build = await db.get(ManualBuild, build_id)
    if not build:
        raise HTTPException(404, "Build not found")
    await db.delete(build)
