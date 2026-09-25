"""Admin API for the curated-build playbook and catalogue subset."""
from datetime import datetime
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models.catalogue import CatalogueVariant, PlaybookSlot
from app.models.curated_build_segment import CuratedBuildSegment
from app.models.listing import Listing
from app.routes.admin_auth import get_current_admin

router = APIRouter(prefix="/curated-builds", tags=["curated-builds"], dependencies=[Depends(get_current_admin)])


class SegmentInput(BaseModel):
    customer_type: str = Field(min_length=1, max_length=120)
    budget_level: str = Field(min_length=1, max_length=80)
    budget_min: float | None = None
    budget_max: float | None = None
    components: dict[str, int] | None = None
    selling_price: float | None = None
    is_live: bool | None = None


def _segment_json(segment: CuratedBuildSegment) -> dict:
    return {
        "id": segment.id,
        "customer_type": segment.customer_type,
        "budget_level": segment.budget_level,
        "budget_min": segment.budget_min,
        "budget_max": segment.budget_max,
        "components": segment.components or {},
        "selling_price": segment.selling_price,
        "proposed_selling_price": segment.proposed_selling_price,
        "availability_status": segment.availability_status,
        "is_live": segment.is_live,
        "regeneration_status": segment.regeneration_status,
        "regeneration_request_id": segment.regeneration_request_id,
        "regeneration_error": segment.regeneration_error,
        "updated_at": segment.updated_at.isoformat() if segment.updated_at else None,
    }


async def _component_context(db: AsyncSession, ids: set[int]) -> dict[int, dict]:
    if not ids:
        return {}
    rows = (await db.execute(
        select(CatalogueVariant, Listing)
        .join(Listing, Listing.id == CatalogueVariant.listing_id)
        .join(PlaybookSlot, PlaybookSlot.id == CatalogueVariant.slot_id)
        .where(CatalogueVariant.id.in_(ids))
    )).all()
    return {
        variant.id: {
            "id": variant.id,
            "slot_type": slot.slot_type,
            "title": listing.title,
            "price": listing.price,
            "status": listing.status.value if hasattr(listing.status, "value") else listing.status,
            "last_seen_at": listing.last_seen_at.isoformat() if listing.last_seen_at else None,
            "image_url": listing.image_urls[0] if listing.image_urls else None,
            "url": listing.url,
            "curated_for_builds": variant.curated_for_builds,
        }
        for variant, listing, slot in rows
    }


@router.get("")
async def get_curated_builds(db: AsyncSession = Depends(get_db)):
    segments = (await db.execute(select(CuratedBuildSegment).order_by(
        CuratedBuildSegment.customer_type, CuratedBuildSegment.budget_min,
        CuratedBuildSegment.budget_level,
    ))).scalars().all()
    ids = {int(value) for segment in segments for value in (segment.components or {}).values() if str(value).isdigit()}
    context = await _component_context(db, ids)
    payload = []
    for segment in segments:
        row = _segment_json(segment)
        component_rows = {key: context.get(int(value)) for key, value in (segment.components or {}).items()}
        row["component_details"] = component_rows
        selected = [item for item in component_rows.values() if item]
        total = sum(item["price"] or 0 for item in selected)
        row["component_cost"] = round(total, 2)
        if segment.component_cost_snapshot is not None and segment.selling_price is not None:
            delta = total - segment.component_cost_snapshot
            if abs(delta) >= 0.01 and segment.proposed_selling_price is None:
                row["proposed_selling_price"] = round(max(0, segment.selling_price + delta), 2)
        row["availability_status"] = "out_of_stock" if any(item["status"] != "active" for item in selected) else "in_stock"
        if row["availability_status"] == "out_of_stock" and segment.is_live:
            segment.is_live = False
        payload.append(row)
    return {"segments": payload, "components": list((await _component_context(db, {
        row[0].id for row in (await db.execute(
            select(CatalogueVariant, Listing, PlaybookSlot)
            .join(Listing, Listing.id == CatalogueVariant.listing_id)
            .join(PlaybookSlot, PlaybookSlot.id == CatalogueVariant.slot_id)
            .where(CatalogueVariant.curated_for_builds.is_(True))
        )).all()
    })).values())}


@router.post("/segments")
async def upsert_segment(body: SegmentInput, db: AsyncSession = Depends(get_db)):
    segment = (await db.execute(select(CuratedBuildSegment).where(
        CuratedBuildSegment.customer_type == body.customer_type,
        CuratedBuildSegment.budget_level == body.budget_level,
    ))).scalar_one_or_none()
    if segment is None:
        segment = CuratedBuildSegment(customer_type=body.customer_type, budget_level=body.budget_level)
        db.add(segment)
    segment.budget_min = body.budget_min
    segment.budget_max = body.budget_max
    if body.components is not None:
        segment.components = body.components
    if body.selling_price is not None:
        segment.selling_price = body.selling_price
        ids = {int(value) for value in (body.components or segment.components or {}).values() if str(value).isdigit()}
        context = await _component_context(db, ids)
        segment.component_cost_snapshot = sum(item["price"] or 0 for item in context.values())
    if body.is_live is not None:
        segment.is_live = body.is_live
    await db.flush()
    return _segment_json(segment)


@router.patch("/variants/{variant_id}/curated")
async def set_curated_variant(variant_id: int, body: dict, db: AsyncSession = Depends(get_db)):
    variant = await db.get(CatalogueVariant, variant_id)
    if not variant:
        raise HTTPException(status_code=404, detail="Catalogue item not found")
    variant.curated_for_builds = bool(body.get("curated_for_builds"))
    variant.updated_at = datetime.utcnow().isoformat()
    return {"id": variant.id, "curated_for_builds": variant.curated_for_builds}


@router.post("/segments/{segment_id}/generate")
async def generate_segment(segment_id: int, db: AsyncSession = Depends(get_db)):
    segment = await db.get(CuratedBuildSegment, segment_id)
    if not segment:
        raise HTTPException(status_code=404, detail="Playbook segment not found")
    webhook_url = get_settings().hermes_curated_build_webhook_url
    if not webhook_url:
        raise HTTPException(status_code=503, detail="Hermes build webhook is not configured (HERMES_CURATED_BUILD_WEBHOOK_URL)")
    request_id = str(uuid4())
    payload = {
        "event": "curated_build.generate",
        "request_id": request_id,
        "segment": _segment_json(segment),
        "callback_url": get_settings().hermes_curated_build_callback_url or None,
    }
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(webhook_url, json=payload)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Hermes webhook request failed: {exc}") from exc
    segment.regeneration_status = "queued"
    segment.regeneration_request_id = request_id
    segment.regeneration_error = None
    return {"request_id": request_id, "status": "queued", "hermes_response": response.text[:1000]}


@router.post("/segments/{segment_id}/apply-price")
async def apply_proposed_price(segment_id: int, db: AsyncSession = Depends(get_db)):
    segment = await db.get(CuratedBuildSegment, segment_id)
    if not segment or segment.proposed_selling_price is None:
        raise HTTPException(status_code=409, detail="No proposed price is available")
    segment.selling_price = segment.proposed_selling_price
    segment.proposed_selling_price = None
    ids = {int(value) for value in (segment.components or {}).values() if str(value).isdigit()}
    context = await _component_context(db, ids)
    segment.component_cost_snapshot = sum(item["price"] or 0 for item in context.values())
    return _segment_json(segment)
