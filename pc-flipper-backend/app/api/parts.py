from collections import defaultdict
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


@router.get("/grouped", response_model=list[dict])
async def get_parts_grouped(
    category: PartCategory | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Return parts grouped by name, with cheapest price and all sources listed.
    Each group has: name, category, cheapest_price, cheapest_source, cheapest_url,
    all_prices (list of {source, price, url, condition}).
    """
    q = select(Part).where(Part.is_active == True)
    if category:
        q = q.where(Part.category == category)
    else:
        q = q.where(Part.category != PartCategory.case)
    q = q.order_by(Part.category, Part.name, Part.price)
    result = await db.execute(q)
    all_parts = result.scalars().all()

    # Group by normalized name (lowercase, strip trailing spaces/model variants)
    groups: dict[str, list] = defaultdict(list)
    for p in all_parts:
        # Normalize key: category + lowercase name
        key = f"{p.category}::{p.name.lower().strip()}"
        groups[key].append(p)

    output = []
    for key, parts in groups.items():
        # Find cheapest overall price across all sources
        priced = [p for p in parts if p.price is not None]
        if not priced:
            continue
        cheapest = min(priced, key=lambda p: p.price)
        output.append({
            "name": parts[0].name,
            "category": parts[0].category,
            "image_url": next((p.image_url for p in parts if p.image_url), None),
            "cheapest_price": cheapest.price,
            "cheapest_source": cheapest.source_site,
            "cheapest_url": cheapest.source_url,
            "price_used": next((p.price_used for p in parts if p.price_used), None),
            "price_refurb": next((p.price_refurb for p in parts if p.price_refurb), None),
            "price_new": next((p.price_new for p in parts if p.price_new), None),
            "last_price_update": max(
                (p.last_price_update for p in parts if p.last_price_update),
                default=None,
            ),
            "all_sources": [
                {
                    "source": p.source_site,
                    "price": p.price,
                    "url": p.source_url,
                    "condition": p.condition,
                }
                for p in sorted(priced, key=lambda p: p.price or 999)
            ],
        })

    output.sort(key=lambda g: (g["category"], g["cheapest_price"] or 999))
    return output


@router.get("/{part_id}", response_model=PartOut)
async def get_part(part_id: int, db: AsyncSession = Depends(get_db)):
    from fastapi import HTTPException
    part = await db.get(Part, part_id)
    if not part:
        raise HTTPException(404, "Part not found")
    return part


@router.post("/", response_model=PartOut, status_code=201)
async def create_part(body: PartCreate, db: AsyncSession = Depends(get_db)):
    part = Part(**body.model_dump())
    db.add(part)
    await db.flush()
    await db.refresh(part)
    return part
