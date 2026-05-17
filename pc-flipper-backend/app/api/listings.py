from datetime import datetime
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.models.listing import Listing, ListingStatus, Classification
from app.schemas.listing import ListingOut, ListingFilter

router = APIRouter(prefix="/listings", tags=["listings"])


def _build_gem_explainer(listing: Listing) -> str:
    signals = listing.gem_signals or []
    top = ", ".join(signals[:3]) if signals else "baseline value opportunity"
    risks = []
    if listing.seller_type in {"private", None}:
        risks.append("private seller risk")
    if listing.listing_type == "auction":
        risks.append("auction final price can drift")
    if listing.resale_comp_count is not None and listing.resale_comp_count < 3:
        risks.append("limited sold comps")
    risk_text = f" Risks: {', '.join(risks)}." if risks else ""
    return f"Flagged for {top}.{risk_text}"


@router.get("/", response_model=list[ListingOut])
async def get_listings(
    classification: Classification | None = Query(None),
    status: ListingStatus | None = Query(ListingStatus.active),
    source_name: str | None = Query(None),
    min_profit: float | None = Query(None),
    max_price: float | None = Query(None),
    search: str | None = Query(None),
    first_seen_after: datetime | None = Query(None),
    limit: int = Query(50, le=1000),
    offset: int = Query(0),
    sort_by: str = Query("estimated_profit"),
    sort_desc: bool = Query(True),
    db: AsyncSession = Depends(get_db),
):
    q = select(Listing)

    if status:
        q = q.where(Listing.status == status)
    if classification:
        q = q.where(Listing.classification == classification)
    if source_name:
        q = q.where(Listing.source_name == source_name)
    if min_profit is not None:
        q = q.where(Listing.estimated_profit >= min_profit)
    if max_price is not None:
        q = q.where(Listing.price <= max_price)
    if search:
        q = q.where(Listing.title.ilike(f"%{search}%"))
    if first_seen_after is not None:
        q = q.where(Listing.first_seen_at >= first_seen_after)

    sort_col = getattr(Listing, sort_by, Listing.estimated_profit)
    q = q.order_by(sort_col.desc() if sort_desc else sort_col.asc())
    q = q.offset(offset).limit(limit)

    result = await db.execute(q)
    rows = result.scalars().all()
    out = []
    for r in rows:
        item = ListingOut.model_validate(r).model_dump()
        item["gem_explainer"] = _build_gem_explainer(r)
        out.append(item)
    return out


@router.get("/stats")
async def get_listing_stats(db: AsyncSession = Depends(get_db)):
    total = await db.scalar(select(func.count()).select_from(Listing))
    gems = await db.scalar(
        select(func.count()).select_from(Listing).where(
            Listing.classification.in_([Classification.amazing_gem, Classification.gem])
        )
    )
    avg_profit = await db.scalar(
        select(func.avg(Listing.estimated_profit)).where(
            Listing.classification.in_([Classification.amazing_gem, Classification.gem]),
            Listing.estimated_profit > 0,
        )
    )
    return {
        "total_listings": total,
        "gems_count": gems,
        "avg_profit": round(avg_profit or 0, 2),
    }


@router.get("/{listing_id}", response_model=ListingOut)
async def get_listing(listing_id: int, db: AsyncSession = Depends(get_db)):
    listing = await db.get(Listing, listing_id)
    if not listing:
        raise HTTPException(404, "Listing not found")
    item = ListingOut.model_validate(listing).model_dump()
    item["gem_explainer"] = _build_gem_explainer(listing)
    return item


@router.patch("/{listing_id}/status")
async def update_listing_status(
    listing_id: int,
    status: ListingStatus,
    db: AsyncSession = Depends(get_db),
):
    listing = await db.get(Listing, listing_id)
    if not listing:
        raise HTTPException(404, "Listing not found")
    listing.status = status
    return {"ok": True, "status": status}
