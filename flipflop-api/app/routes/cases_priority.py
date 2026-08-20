"""
API endpoint to get prioritized cases for 3D model creation.
Returns cases ranked by Amazon bestseller ranking (most popular first).
"""
from fastapi import APIRouter, Depends
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.part import Part, PartCategory

router = APIRouter(prefix="/cases", tags=["cases"])


@router.get("/priority-for-3d")
async def get_cases_priority_for_3d(
    limit: int = 30,
    db: AsyncSession = Depends(get_db),
):
    """
    Get cases prioritized for 3D model creation.
    Sorted by Amazon bestseller rank (if available), then by source + price.
    Returns only cases without 3D models yet.
    """
    from sqlalchemy import case as sql_case

    result = await db.execute(
        select(Part)
        .where(
            and_(
                Part.category == PartCategory.case,
                Part.has_3d_model == False,
            )
        )
        .order_by(
            Part.bestseller_rank.asc().nullslast(),  # Bestseller rank first (null last)
            sql_case((Part.source_site == "Amazon", 0), else_=1),  # Amazon prioritized
            Part.price.asc(),  # Cheaper cases first
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
        select(Part)
        .where(
            and_(
                Part.category == PartCategory.case,
                Part.has_3d_model == True,
            )
        )
        .order_by(Part.bestseller_rank.asc())
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
            "has_3d_model": True,
        }
        for c in cases
    ]
