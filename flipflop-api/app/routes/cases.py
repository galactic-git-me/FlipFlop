"""PC Case sourcing and 3D model management endpoints."""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, and_, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.case import Case

router = APIRouter(prefix="/cases", tags=["cases"])

SOURCING_STAGES = (
    "manufacturer_3d",
    "third_party_3d",
    "product_images",
    "youtube_video",
    "meshy_generation",
    "validation",
)

CASE_MESHY_PHOTO_REQUIREMENTS = (
    "chassis_empty",
    "included_rgb_fans_installed",
    "rgb_illuminated",
    "no_text_overlay",
    "no_dimension_overlay",
    "no_exploded_view",
    "same_chassis_configuration",
)


def _priority_payload(case: Case) -> dict:
    return {
        "id": case.id,
        "name": case.name,
        "brand": case.brand,
        "model": case.model,
        "price": case.price_new or case.price or 0,
        "source_site": case.source_site,
        "source_url": case.source_url,
        "image_url": case.image_url,
        "bestseller_rank": case.bestseller_rank,
        "priority_3d_rank": case.priority_3d_rank,
        "priority_3d_batch": case.priority_3d_batch,
        "priority_3d_frozen_at": case.priority_3d_frozen_at.isoformat() if case.priority_3d_frozen_at else None,
        "rating": case.rating,
        "review_count": case.review_count,
        "sales_velocity": case.sales_velocity,
        "keywords": case.keywords or [],
        "form_factors": case.form_factors or [],
        "status": case.status,
        "sourcing_3d_evidence": case.sourcing_3d_evidence or {},
    }


@router.post("/priority-for-3d/freeze")
async def freeze_top_30_3d_campaign(db: AsyncSession = Depends(get_db)):
    """Freeze the current top 30 into three stable ten-case work batches."""
    from sqlalchemy import case as sql_case

    existing = (
        await db.execute(
            select(Case).where(Case.priority_3d_rank.isnot(None)).order_by(Case.priority_3d_rank)
        )
    ).scalars().all()
    if existing:
        return {"frozen": False, "reason": "campaign_already_frozen", "cases": [_priority_payload(case) for case in existing]}

    ranked = (
        await db.execute(
            select(Case)
            .where(Case.has_3d_model == False)  # noqa: E712
            .order_by(
                Case.bestseller_rank.asc().nullslast(),
                sql_case((Case.source_site == "Amazon", 0), else_=1),
                Case.price.asc(),
                Case.id,
            )
            .limit(30)
            .with_for_update(skip_locked=True)
        )
    ).scalars().all()
    frozen_at = datetime.utcnow()
    for index, case in enumerate(ranked, start=1):
        case.priority_3d_rank = index
        case.priority_3d_batch = ((index - 1) // 10) + 1
        case.priority_3d_frozen_at = frozen_at
        case.sourcing_3d_evidence = {
            "schema_version": 1,
            "stages": {stage: {"status": "not_started", "attempts": []} for stage in SOURCING_STAGES},
        }
    await db.commit()
    return {"frozen": True, "cases": [_priority_payload(case) for case in ranked]}


class SourcingEvidencePatch(BaseModel):
    stage: str
    status: str = Field(pattern="^(not_started|searching|found|not_found|blocked|complete)$")
    attempt: dict | None = None


@router.patch("/{case_id}/3d-sourcing")
async def update_3d_sourcing_evidence(
    case_id: int,
    body: SourcingEvidencePatch,
    db: AsyncSession = Depends(get_db),
):
    if body.stage not in SOURCING_STAGES:
        raise HTTPException(status_code=422, detail=f"Unknown sourcing stage '{body.stage}'")
    if body.stage == "product_images" and body.status == "complete":
        assessments = (body.attempt or {}).get("image_assessments") or []
        eligible = [
            item for item in assessments
            if isinstance(item, dict)
            and isinstance(item.get("url"), str)
            and all(item.get(field) is True for field in CASE_MESHY_PHOTO_REQUIREMENTS)
        ]
        if not eligible:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Product-image acquisition cannot be completed until at least one photo shows the same empty "
                    "chassis with its included RGB fans installed and illuminated, without text, dimensions, or an exploded view."
                ),
            )
    case = (await db.execute(select(Case).where(Case.id == case_id))).scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    evidence = dict(case.sourcing_3d_evidence or {"schema_version": 1, "stages": {}})
    stages = dict(evidence.get("stages") or {})
    stage = dict(stages.get(body.stage) or {"attempts": []})
    attempts = list(stage.get("attempts") or [])
    if body.attempt is not None:
        attempts.append({**body.attempt, "recorded_at": datetime.utcnow().isoformat()})
    stage.update({"status": body.status, "attempts": attempts, "updated_at": datetime.utcnow().isoformat()})
    stages[body.stage] = stage
    evidence["stages"] = stages
    case.sourcing_3d_evidence = evidence
    case.status = "sourcing" if body.status not in ("complete", "blocked") else case.status
    await db.commit()
    return _priority_payload(case)


@router.get("/priority-for-3d")
async def get_cases_priority_for_3d(
    limit: int = 30,
    db: AsyncSession = Depends(get_db),
):
    """
    Get PC cases prioritized for 3D model creation.
    Sorted by Amazon bestseller rank (most popular first), then by source + price.
    Returns only cases without 3D models yet.
    """
    from sqlalchemy import case as sql_case

    frozen_exists = (await db.execute(select(func.count()).select_from(Case).where(Case.priority_3d_rank.isnot(None)))).scalar_one()
    priority_filter = (
        and_(Case.has_3d_model == False, Case.priority_3d_rank.isnot(None))
        if frozen_exists
        else Case.has_3d_model == False
    )
    result = await db.execute(
        select(Case)
        .where(priority_filter)
        .order_by(
            Case.priority_3d_rank.asc().nullslast() if frozen_exists else Case.bestseller_rank.asc().nullslast(),
            sql_case((Case.source_site == "Amazon", 0), else_=1),  # Amazon prioritized
            Case.price.asc(),  # Cheaper cases first
        )
        .limit(limit)
    )
    cases = result.scalars().all()

    return [_priority_payload(case) for case in cases]


@router.get("/with-3d-models")
async def get_cases_with_3d_models(
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """
    Get cases that have 3D models ready.
    Use for website/builder display.
    """
    result = await db.execute(
        select(Case)
        .where(
            and_(
                Case.has_3d_model == True,
            )
        )
        .order_by(Case.bestseller_rank.asc().nullslast())
        .limit(limit)
    )
    cases = result.scalars().all()

    return [
        {
            "id": c.id,
            "name": c.name,
            "brand": c.brand,
            "model": c.model,
            "price": c.price_new or c.price or 0,
            "source_site": c.source_site,
            "image_url": c.image_url,
            "bestseller_rank": c.bestseller_rank,
            "rating": c.rating,
            "review_count": c.review_count,
            "sales_velocity": c.sales_velocity,
            "keywords": c.keywords or [],
            "form_factors": c.form_factors or [],
            "model_3d_url": c.model_3d_url,
            "has_3d_model": True,
        }
        for c in cases
    ]


@router.get("/gallery")
async def get_gallery_cases(
    limit: int = 32,
    sort_by: str = "reviews",
    db: AsyncSession = Depends(get_db),
):
    """
    Get cases for the 3D review gallery.
    Sorted by: has_3d_model first, then by sort_by (reviews, rating, price, name).
    """
    from sqlalchemy import case as sql_case, desc

    # Build order clause: 3D models first, then by selected sort
    order_clauses = [
        sql_case((Case.has_3d_model == True, 0), else_=1),  # 3D models first
    ]

    if sort_by == "reviews":
        order_clauses.append(desc(Case.review_count))
    elif sort_by == "rating":
        order_clauses.append(desc(Case.rating))
    elif sort_by == "price":
        order_clauses.append(Case.price.asc())
    elif sort_by == "name":
        order_clauses.append(Case.name.asc())
    else:
        order_clauses.append(desc(Case.review_count))

    result = await db.execute(
        select(Case)
        .order_by(*order_clauses)
        .limit(limit)
    )
    cases = result.scalars().all()

    return [
        {
            "id": c.id,
            "name": c.name,
            "brand": c.brand,
            "model": c.model,
            "price": c.price_new or c.price or 0,
            "source_site": c.source_site,
            "image_url": c.image_url,
            "rating": c.rating or 0,
            "review_count": c.review_count or 0,
            "form_factors": c.form_factors or [],
            "keywords": c.keywords or [],
            "has_3d_model": c.has_3d_model,
            "model_3d_url": c.model_3d_url,
            "status": "has-model" if c.has_3d_model else "reference-only",
        }
        for c in cases
    ]


@router.get("/stats")
async def get_cases_stats(db: AsyncSession = Depends(get_db)):
    """Get sourcing statistics."""
    from sqlalchemy import Integer

    result = await db.execute(
        select(
            func.count().label("total"),
            func.sum((Case.has_3d_model == True).cast(Integer)).label("with_model"),
        ).select_from(Case)
    )
    row = result.first()
    return {
        "total_cases": row.total or 0,
        "with_3d_model": row.with_model or 0,
        "pending_3d_models": (row.total or 0) - (row.with_model or 0),
    }
