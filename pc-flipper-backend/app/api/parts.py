from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.part import Part, PartCategory, PartCondition
from app.schemas.part import PartOut, PartCreate

router = APIRouter(prefix="/parts", tags=["parts"])


@router.get("/", response_model=list[PartOut])
async def get_parts(
    category: PartCategory | None = Query(None),
    condition: PartCondition | None = Query(None),
    theme: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    q = select(Part).where(Part.is_active == True)
    if category:
        q = q.where(Part.category == category)
    if condition:
        q = q.where(Part.condition == condition)
    if theme:
        q = q.where(Part.theme == theme)
    # Exclude cases from the general parts list unless explicitly requested
    if not category:
        q = q.where(Part.category != PartCategory.case)
    q = q.order_by(Part.category, Part.price)
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/cases", response_model=list[PartOut])
async def get_cases(
    theme: str | None = Query(None),
    source_site: str | None = Query(None),
    max_price: float | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    q = select(Part).where(Part.is_active == True, Part.category == PartCategory.case)
    if theme:
        q = q.where(Part.theme == theme)
    if source_site:
        q = q.where(Part.source_site == source_site)
    if max_price:
        q = q.where(Part.price <= max_price)
    q = q.order_by(Part.price)
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/themes", response_model=list[str])
async def get_case_themes(db: AsyncSession = Depends(get_db)):
    from sqlalchemy import distinct
    result = await db.execute(
        select(distinct(Part.theme)).where(
            Part.category == PartCategory.case,
            Part.theme != None,
            Part.is_active == True,
        )
    )
    return [r for r in result.scalars().all() if r]


@router.post("/", response_model=PartOut, status_code=201)
async def create_part(body: PartCreate, db: AsyncSession = Depends(get_db)):
    part = Part(**body.model_dump())
    db.add(part)
    await db.flush()
    await db.refresh(part)
    return part
