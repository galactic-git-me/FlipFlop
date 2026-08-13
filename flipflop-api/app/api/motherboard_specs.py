"""Admin API for the motherboard reference table (see app/models/motherboard_spec.py).

Endpoints:
  GET  /motherboard-specs                    list all (optionally filter by reviewed)
  POST /motherboard-specs/backfill           AI-extract a spec from a title, save unreviewed
  PATCH /motherboard-specs/{id}              admin edit / approve (sets reviewed=True)
  DELETE /motherboard-specs/{id}
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.motherboard_spec import MotherboardSpec
from app.models.admin_user import AdminUser
from app.schemas.motherboard_spec import (
    MotherboardSpecOut,
    MotherboardSpecBackfillRequest,
    MotherboardSpecUpdate,
)
from app.services.motherboard_spec_ai import extract_motherboard_spec
from app.routes.admin_auth import get_current_admin

router = APIRouter(prefix="/motherboard-specs", tags=["motherboard-specs"], dependencies=[Depends(get_current_admin)])


@router.get("", response_model=list[MotherboardSpecOut])
async def list_motherboard_specs(
    reviewed: bool | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> list[MotherboardSpec]:
    stmt = select(MotherboardSpec).order_by(MotherboardSpec.canonical_model)
    if reviewed is not None:
        stmt = stmt.where(MotherboardSpec.reviewed == reviewed)
    return (await db.execute(stmt)).scalars().all()


@router.post("/backfill", response_model=MotherboardSpecOut, status_code=201)
async def backfill_motherboard_spec(
    body: MotherboardSpecBackfillRequest,
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> MotherboardSpec:
    result = await extract_motherboard_spec(body.title)
    if result is None:
        raise HTTPException(status_code=502, detail="AI extraction failed — check ANTHROPIC_API_KEY and try again")
    if not result.recognised or not result.canonical_model:
        raise HTTPException(status_code=422, detail="Model not recognised with sufficient confidence — enter it manually instead")

    existing = (
        await db.execute(
            select(MotherboardSpec).where(MotherboardSpec.canonical_model == result.canonical_model)
        )
    ).scalar_one_or_none()

    if existing:
        raise HTTPException(status_code=409, detail=f"Already have a spec for {result.canonical_model}")

    spec = MotherboardSpec(
        canonical_model=result.canonical_model,
        brand=result.brand,
        socket=result.socket,
        chipset=result.chipset,
        ram_type=result.ram_type,
        ram_slots=result.ram_slots,
        max_ram_gb=result.max_ram_gb,
        pcie_x16_slots=result.pcie_x16_slots,
        m2_slots=result.m2_slots,
        sata_ports=result.sata_ports,
        form_factor=result.form_factor,
        wifi=result.wifi,
        source="ai_generated",
        ai_confidence=result.confidence,
        ai_reasoning=result.reasoning,
        reviewed=False,
        raw_ai_response=result.raw,
    )
    db.add(spec)
    await db.commit()
    await db.refresh(spec)
    return spec


@router.patch("/{spec_id}", response_model=MotherboardSpecOut)
async def update_motherboard_spec(
    spec_id: int,
    body: MotherboardSpecUpdate,
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> MotherboardSpec:
    spec = (
        await db.execute(select(MotherboardSpec).where(MotherboardSpec.id == spec_id))
    ).scalar_one_or_none()
    if not spec:
        raise HTTPException(status_code=404, detail="Not found")

    updates = body.model_dump(exclude_unset=True)
    was_reviewed_now = updates.get("reviewed") is True and not spec.reviewed
    for field, value in updates.items():
        setattr(spec, field, value)
    if was_reviewed_now:
        spec.reviewed_by = admin.email

    await db.commit()
    await db.refresh(spec)
    return spec


@router.delete("/{spec_id}", status_code=204)
async def delete_motherboard_spec(
    spec_id: int,
    db: AsyncSession = Depends(get_db),
) -> None:
    spec = (
        await db.execute(select(MotherboardSpec).where(MotherboardSpec.id == spec_id))
    ).scalar_one_or_none()
    if not spec:
        raise HTTPException(status_code=404, detail="Not found")
    await db.delete(spec)
    await db.commit()
