"""Admin API for the curated-build playbook and catalogue subset."""
import json
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models.catalogue import CatalogueVariant, PlaybookSlot
from app.models.curated_build_segment import CuratedBuildSegment
from app.models.listing import Listing
from app.routes.admin_auth import get_current_admin

router = APIRouter(prefix="/curated-builds", tags=["curated-builds"], dependencies=[Depends(get_current_admin)])


@router.get("/draft-playbook")
async def draft_playbook():
    """Return the local planning draft without implying supplier approval."""
    path = Path(__file__).resolve().parents[3] / "tmp" / "curated-playbooks-v1-stub.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Draft playbook file is unavailable")
    return json.loads(path.read_text(encoding="utf-8"))


@router.get("/bestseller-catalogue")
async def bestseller_catalogue(db: AsyncSession = Depends(get_db)):
    """Every captured Amazon bestseller, with its own ASIN as a minimum match.

    The Amazon snapshot supplies product identity and rank. Marketplace prices
    remain separate from the Amazon observation and are never treated as an
    approved component or procurement quote.
    """
    rows = (await db.execute(text("""
        WITH latest AS (
            SELECT DISTINCT ON (category, asin)
                category, asin, title, url, image_url, rank, cpk, price,
                rating, review_count, captured_at
            FROM amazon_bestseller_observations
            ORDER BY category, asin, captured_at DESC
        )
        SELECT a.category, a.asin, a.title, a.url, a.image_url, a.rank,
            COALESCE(a.cpk, 'asin:' || a.asin) AS cpk, a.price,
            a.rating, a.review_count, a.captured_at,
            COALESCE(r.status, 'pending') AS review_status,
            COALESCE(m.listing_id, 'amazon-bestseller:' || a.asin) AS marketplace_listing_id,
            COALESCE(m.source, 'amazon') AS marketplace_source,
            COALESCE(m.title, a.title) AS marketplace_title,
            COALESCE(m.url, a.url) AS marketplace_url,
            COALESCE(m.image_url, a.image_url) AS marketplace_image_url,
            (m.listing_id IS NOT NULL AND m.image_url IS NULL) AS marketplace_image_is_reference,
            (m.listing_id IS NULL) AS marketplace_is_self_capture,
            COALESCE(m.delivered_price, a.price) AS marketplace_price,
            m.condition AS marketplace_condition,
            COALESCE(m.scored_at, a.captured_at) AS marketplace_seen_at
        FROM latest a
        LEFT JOIN LATERAL (
            SELECT s.listing_id, s.source, s.title,
                s.url, COALESCE(
                    CASE WHEN s.image_url ~* '^https?://' AND s.image_url NOT LIKE '%._RC' THEN s.image_url END,
                    o.image_url
                ) AS image_url,
                s.delivered_price, s.condition, s.scored_at
            FROM gem_radar_scored_listings s
            LEFT JOIN LATERAL (
                SELECT image_url FROM gem_radar_listing_observations
                WHERE listing_id = s.listing_id
                  AND image_url ~* '^https?://'
                  AND image_url NOT LIKE '%._RC'
                ORDER BY observed_at DESC, id DESC LIMIT 1
            ) o ON true
            WHERE (s.listing_id = a.asin OR (a.cpk IS NOT NULL AND s.cpk = a.cpk))
              AND s.delivered_price > 0
              AND s.category IN (
                CASE a.category WHEN 'storage' THEN 'ssd'
                    WHEN 'cooler' THEN 'cooling' ELSE a.category END,
                a.category
              )
            ORDER BY (s.listing_id = a.asin) DESC,
                (COALESCE(
                CASE WHEN s.image_url ~* '^https?://' AND s.image_url NOT LIKE '%._RC' THEN s.image_url END,
                o.image_url
            ) IS NOT NULL) DESC,
                s.scored_at DESC
            LIMIT 1
        ) m ON true
        LEFT JOIN curated_bestseller_reviews r
            ON r.category = a.category AND r.cpk = COALESCE(a.cpk, 'asin:' || a.asin)
        ORDER BY a.category, a.rank
    """))).mappings().all()
    return {"items": [dict(row) for row in rows]}


class BestsellerReviewInput(BaseModel):
    category: str = Field(min_length=1, max_length=40)
    cpk: str = Field(min_length=1, max_length=255)
    status: str


@router.put("/bestseller-catalogue/review")
async def review_bestseller(body: BestsellerReviewInput, db: AsyncSession = Depends(get_db)):
    if body.status not in {"approved", "rejected", "pending"}:
        raise HTTPException(status_code=422, detail="Invalid review status")
    exists = (await db.execute(text("""
        SELECT EXISTS (
            SELECT 1 FROM amazon_bestseller_observations a
            JOIN gem_radar_scored_listings s ON s.cpk = a.cpk
            WHERE a.category = :category AND a.cpk = :cpk
              AND s.delivered_price > 0
              AND s.category IN (
                  CASE a.category WHEN 'storage' THEN 'ssd'
                      WHEN 'cooler' THEN 'cooling' ELSE a.category END,
                  a.category
              )
        )
    """), {"category": body.category, "cpk": body.cpk})).scalar()
    if not exists:
        raise HTTPException(status_code=404, detail="Matched bestseller product not found")
    if body.status == "approved":
        has_image = (await db.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM amazon_bestseller_observations a
                WHERE a.category = :category AND a.cpk = :cpk
                  AND a.image_url ~* '^https?://'
                  AND a.image_url NOT LIKE '%._RC'
            ) OR EXISTS (
                SELECT 1 FROM gem_radar_scored_listings s
                WHERE s.cpk = :cpk AND s.delivered_price > 0
                  AND s.category IN (
                      CASE :category WHEN 'storage' THEN 'ssd'
                          WHEN 'cooler' THEN 'cooling' ELSE :category END,
                      :category
                  )
                  AND ((s.image_url ~* '^https?://' AND s.image_url NOT LIKE '%._RC') OR EXISTS (
                      SELECT 1 FROM gem_radar_listing_observations o
                      WHERE o.listing_id = s.listing_id
                        AND o.image_url ~* '^https?://'
                        AND o.image_url NOT LIKE '%._RC'
                  ))
            )
        """), {"category": body.category, "cpk": body.cpk})).scalar()
        if not has_image:
            raise HTTPException(status_code=409, detail="Capture a product picture before approving this match")
    if body.status == "pending":
        await db.execute(text("""
            DELETE FROM curated_bestseller_reviews
            WHERE category = :category AND cpk = :cpk
        """), {"category": body.category, "cpk": body.cpk})
    else:
        await db.execute(text("""
            INSERT INTO curated_bestseller_reviews (category, cpk, status, reviewed_at)
            VALUES (:category, :cpk, :status, now())
            ON CONFLICT (category, cpk) DO UPDATE
            SET status = EXCLUDED.status, reviewed_at = EXCLUDED.reviewed_at
        """), {"category": body.category, "cpk": body.cpk, "status": body.status})
    return {"category": body.category, "cpk": body.cpk, "review_status": body.status}


class SegmentInput(BaseModel):
    customer_type: str = Field(min_length=1, max_length=120)
    budget_level: str = Field(min_length=1, max_length=80)
    budget_min: float | None = None
    budget_max: float | None = None
    components: dict[str, int] | None = None
    selling_price: float | None = None
    is_live: bool | None = None


@router.get("/match-budget")
async def match_budget(customer_type: str, budget_gbp: float, db: AsyncSession = Depends(get_db)):
    if budget_gbp < 0:
        raise HTTPException(status_code=422, detail="Budget must be zero or greater")
    segments = (await db.execute(select(CuratedBuildSegment).where(
        CuratedBuildSegment.customer_type == customer_type,
        CuratedBuildSegment.budget_min.is_not(None),
    ))).scalars().all()
    matches = [s for s in segments if s.budget_min <= budget_gbp and (s.budget_max is None or budget_gbp < s.budget_max)]
    if len(matches) != 1:
        raise HTTPException(status_code=404, detail="No unique budget segment found for this customer type and amount")
    return _segment_json(matches[0])


SLOT_BESTSELLER_CATEGORY = {
    "cpu": "cpu", "gpu": "gpu", "motherboard": "motherboard",
    "ram": "ram", "storage": "storage", "psu": "psu",
    "cooling": "cooler", "case": "case",
}


def _segment_json(segment: CuratedBuildSegment) -> dict:
    return {
        "id": segment.id,
        "customer_type": segment.customer_type,
        "budget_level": segment.budget_level,
        "budget_min": segment.budget_min,
        "budget_max": segment.budget_max,
        "components": segment.components or {},
        "bestseller_components": segment.bestseller_components or {},
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
        select(CatalogueVariant, Listing, PlaybookSlot)
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
        assigned_count = len(segment.components or {})
        row["availability_status"] = "out_of_stock" if assigned_count == 0 or len(selected) != assigned_count or any(item["status"] != "active" for item in selected) else "in_stock"
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
    if body.budget_min is not None and body.budget_min < 0:
        raise HTTPException(status_code=422, detail="Minimum budget must be zero or greater")
    if body.budget_max is not None and (body.budget_min is None or body.budget_max <= body.budget_min):
        raise HTTPException(status_code=422, detail="Maximum budget must be greater than minimum budget")
    segment = (await db.execute(select(CuratedBuildSegment).where(
        CuratedBuildSegment.customer_type == body.customer_type,
        CuratedBuildSegment.budget_level == body.budget_level,
    ))).scalar_one_or_none()
    if body.budget_min is not None:
        peers = (await db.execute(select(CuratedBuildSegment).where(
            CuratedBuildSegment.customer_type == body.customer_type,
            CuratedBuildSegment.budget_min.is_not(None),
        ))).scalars().all()
        for peer in peers:
            if segment is not None and peer.id == segment.id:
                continue
            if (body.budget_max is None or peer.budget_min < body.budget_max) and (peer.budget_max is None or body.budget_min < peer.budget_max):
                raise HTTPException(status_code=409, detail=f"Budget range overlaps {peer.budget_level}")
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


class BestsellerComponentInput(BaseModel):
    slot: str
    cpk: str | None = None


@router.put("/segments/{segment_id}/bestseller-component")
async def set_segment_bestseller_component(
    segment_id: int, body: BestsellerComponentInput, db: AsyncSession = Depends(get_db)
):
    segment = await db.get(CuratedBuildSegment, segment_id)
    if not segment:
        raise HTTPException(status_code=404, detail="Playbook segment not found")
    category = SLOT_BESTSELLER_CATEGORY.get(body.slot)
    if not category:
        raise HTTPException(status_code=422, detail="Unknown build component slot")
    choices = dict(segment.bestseller_components or {})
    if body.cpk:
        eligible = (await db.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM amazon_bestseller_observations a
                JOIN gem_radar_scored_listings s ON s.cpk = a.cpk
                LEFT JOIN curated_bestseller_reviews r
                    ON r.category = a.category AND r.cpk = a.cpk
                WHERE a.category = :category AND a.cpk = :cpk
                  AND COALESCE(r.status, 'pending') <> 'rejected'
                  AND s.delivered_price > 0
                  AND s.category IN (
                      CASE a.category WHEN 'storage' THEN 'ssd'
                          WHEN 'cooler' THEN 'cooling' ELSE a.category END,
                      a.category
                  )
                  AND (a.image_url ~* '^https?://' OR
                       (s.image_url ~* '^https?://' AND s.image_url NOT LIKE '%._RC') OR EXISTS (
                      SELECT 1 FROM gem_radar_listing_observations o
                      WHERE o.listing_id = s.listing_id
                        AND o.image_url ~* '^https?://'
                        AND o.image_url NOT LIKE '%._RC'
                  ))
            )
        """), {"category": category, "cpk": body.cpk})).scalar()
        if not eligible:
            raise HTTPException(status_code=409, detail="This bestseller has no eligible marketplace match")
        choices[body.slot] = {"category": category, "cpk": body.cpk}
    else:
        choices.pop(body.slot, None)
    segment.bestseller_components = choices
    segment.is_live = False
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


@router.post("/segments/{segment_id}/publish")
async def publish_segment(segment_id: int, body: dict, db: AsyncSession = Depends(get_db)):
    segment = await db.get(CuratedBuildSegment, segment_id)
    if not segment:
        raise HTTPException(status_code=404, detail="Playbook segment not found")
    if not body.get("is_live", True):
        segment.is_live = False
        return _segment_json(segment)
    required = {"cpu", "gpu", "motherboard", "ram", "storage", "psu", "case"}
    selected = segment.components or {}
    if not required.issubset(selected):
        raise HTTPException(status_code=409, detail="Assign CPU, GPU, motherboard, RAM, storage, PSU and case before publishing")
    if segment.selling_price is None or segment.selling_price <= 0:
        raise HTTPException(status_code=409, detail="Set a valid selling price before publishing")
    ids = {int(value) for value in selected.values() if str(value).isdigit()}
    context = await _component_context(db, ids)
    if len(context) != len(ids) or any(not item["curated_for_builds"] or item["status"] != "active" for item in context.values()):
        raise HTTPException(status_code=409, detail="Every selected component must remain curated and currently available")
    segment.is_live = True
    segment.availability_status = "in_stock"
    return _segment_json(segment)
