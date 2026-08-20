"""PC Case sourcing and 3D model management endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.case import Case

router = APIRouter(prefix="/cases", tags=["cases"])


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

    result = await db.execute(
        select(Case)
        .where(
            and_(
                Case.has_3d_model == False,
            )
        )
        .order_by(
            Case.bestseller_rank.asc().nullslast(),  # Bestseller rank first (null last)
            sql_case((Case.source_site == "Amazon", 0), else_=1),  # Amazon prioritized
            Case.price.asc(),  # Cheaper cases first
        )
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
            "status": c.status,
        }
        for c in cases
    ]


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


@router.get("/stats")
async def get_cases_stats(db: AsyncSession = Depends(get_db)):
    """Get sourcing statistics."""
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
