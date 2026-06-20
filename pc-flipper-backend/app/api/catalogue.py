"""
Admin API router for catalogue management.

Prefix: /catalogue  (mounted at /api/catalogue/ in main.py)
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.catalogue import CaseCatalogue, CatalogueVariant, PlaybookSlot
from app.models.listing import Listing
from app.schemas.catalogue import (
    CaseCatalogueCreate,
    CaseCatalogueOut,
    CaseCatalogueUpdate,
    RejectBody,
)
from app.services.catalogue_service import approve_variant, reject_variant

router = APIRouter(prefix="/catalogue", tags=["catalogue"])


@router.get("/review-queue")
async def get_review_queue(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(CatalogueVariant, Listing, PlaybookSlot)
        .join(Listing, CatalogueVariant.listing_id == Listing.id)
        .join(PlaybookSlot, CatalogueVariant.slot_id == PlaybookSlot.id)
        .where(CatalogueVariant.status == "pending_review")
        .order_by(CatalogueVariant.auto_published_at.desc())
    )
    rows = result.all()
    return [
        {
            "id": v.id,
            "listing_id": v.listing_id,
            "listing_title": l.title,
            "listing_price": l.price,
            "gem_score": l.gem_score,
            "slot_id": v.slot_id,
            "slot_type": s.slot_type,
            "playbook_id": s.playbook_id,
            "tier": v.tier,
            "display_price": v.display_price,
            "auto_published_at": v.auto_published_at,
        }
        for v, l, s in rows
    ]


# IMPORTANT: approve-all MUST come before {variant_id}/approve — FastAPI matches
# routes in declaration order and "approve-all" would be swallowed by the
# {variant_id} pattern if declared second.
@router.post("/variants/approve-all")
async def approve_all_variants(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(CatalogueVariant).where(CatalogueVariant.status == "pending_review")
    )
    variants = result.scalars().all()
    now = datetime.utcnow().isoformat()
    for v in variants:
        v.status = "active"
        v.reviewed_at = now
        v.reviewed_by = "admin-bulk"
    await db.commit()
    return {"approved": len(variants)}


@router.post("/variants/{variant_id}/approve")
async def approve_one(variant_id: int, db: AsyncSession = Depends(get_db)):
    variant = await approve_variant(db, variant_id)
    if not variant:
        raise HTTPException(status_code=404, detail="Variant not found")
    return {"id": variant.id, "status": variant.status}


@router.post("/variants/{variant_id}/reject")
async def reject_one(variant_id: int, body: RejectBody, db: AsyncSession = Depends(get_db)):
    variant = await reject_variant(db, variant_id, reason=body.reason)
    if not variant:
        raise HTTPException(status_code=404, detail="Variant not found")
    return {"id": variant.id, "status": variant.status, "reject_reason": variant.reject_reason}


@router.get("/variants")
async def list_variants(
    status: Optional[str] = Query(None),
    playbook_id: Optional[int] = Query(None),
    slot_type: Optional[str] = Query(None),
    tier: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    q = (
        select(CatalogueVariant, Listing, PlaybookSlot)
        .join(Listing, CatalogueVariant.listing_id == Listing.id)
        .join(PlaybookSlot, CatalogueVariant.slot_id == PlaybookSlot.id)
    )
    if status:
        q = q.where(CatalogueVariant.status == status)
    if playbook_id:
        q = q.where(PlaybookSlot.playbook_id == playbook_id)
    if slot_type:
        q = q.where(PlaybookSlot.slot_type == slot_type)
    if tier:
        q = q.where(CatalogueVariant.tier == tier)
    result = await db.execute(q.order_by(CatalogueVariant.auto_published_at.desc()))
    rows = result.all()
    return [
        {
            "id": v.id,
            "listing_id": v.listing_id,
            "listing_title": l.title,
            "slot_type": s.slot_type,
            "playbook_id": s.playbook_id,
            "status": v.status,
            "tier": v.tier,
            "display_price": v.display_price,
            "gem_score": l.gem_score,
            "consecutive_misses": v.consecutive_misses,
            "last_seen_at": v.last_seen_at,
            "auto_published_at": v.auto_published_at,
            "reviewed_at": v.reviewed_at,
            "reject_reason": v.reject_reason,
        }
        for v, l, s in rows
    ]


@router.patch("/variants/{variant_id}/toggle-status")
async def toggle_variant_status(variant_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(CatalogueVariant).where(CatalogueVariant.id == variant_id)
    )
    variant = result.scalar_one_or_none()
    if not variant:
        raise HTTPException(status_code=404, detail="Variant not found")
    if variant.status not in ("active", "hidden"):
        raise HTTPException(status_code=400, detail="Can only toggle active or hidden variants")
    variant.status = "hidden" if variant.status == "active" else "active"
    await db.commit()
    return {"id": variant.id, "status": variant.status}


@router.get("/cases", response_model=list[CaseCatalogueOut])
async def list_cases(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(CaseCatalogue).order_by(CaseCatalogue.brand, CaseCatalogue.name)
    )
    return result.scalars().all()


@router.post("/cases", response_model=CaseCatalogueOut, status_code=201)
async def create_case(body: CaseCatalogueCreate, db: AsyncSession = Depends(get_db)):
    now = datetime.utcnow().isoformat()
    case = CaseCatalogue(**body.model_dump(), created_at=now, updated_at=now)
    db.add(case)
    await db.commit()
    await db.refresh(case)
    return case


@router.patch("/cases/{case_id}", response_model=CaseCatalogueOut)
async def update_case(case_id: int, body: CaseCatalogueUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(CaseCatalogue).where(CaseCatalogue.id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(case, field, value)
    case.updated_at = datetime.utcnow().isoformat()
    await db.commit()
    await db.refresh(case)
    return case


@router.get("/slots")
async def list_slots(
    playbook_id: Optional[int] = Query(None), db: AsyncSession = Depends(get_db)
):
    q = select(PlaybookSlot)
    if playbook_id:
        q = q.where(PlaybookSlot.playbook_id == playbook_id)
    result = await db.execute(q.order_by(PlaybookSlot.playbook_id, PlaybookSlot.slot_type))
    return [
        {
            "id": s.id,
            "playbook_id": s.playbook_id,
            "slot_type": s.slot_type,
            "is_customer_visible": s.is_customer_visible,
            "tier_names": s.tier_names,
            "score_band_budget": s.score_band_budget,
            "score_band_mid": s.score_band_mid,
            "score_band_high": s.score_band_high,
        }
        for s in result.scalars().all()
    ]


@router.patch("/slots/{slot_id}")
async def update_slot(slot_id: int, body: dict, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(PlaybookSlot).where(PlaybookSlot.id == slot_id))
    slot = result.scalar_one_or_none()
    if not slot:
        raise HTTPException(status_code=404, detail="Slot not found")
    allowed = {
        "is_customer_visible",
        "tier_names",
        "score_band_budget",
        "score_band_mid",
        "score_band_high",
    }
    for k, v in body.items():
        if k in allowed:
            setattr(slot, k, v)
    slot.updated_at = datetime.utcnow().isoformat()
    await db.commit()
    return {"id": slot.id, "slot_type": slot.slot_type, "updated": True}
