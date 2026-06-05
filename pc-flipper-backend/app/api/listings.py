from datetime import datetime
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.models.listing import Listing, ListingStatus, Classification
from app.schemas.listing import ListingOut, ListingFilter

router = APIRouter(prefix="/listings", tags=["listings"])

_CLAUDE_VERDICTS = {"GEM", "GOOD", "MAYBE", "REJECT"}


def _build_gem_explainer(listing: Listing) -> str:
    # Prefer Claude's reasoning when available
    if listing.claude_reasoning:
        verdict_label = f"[{listing.claude_verdict}] " if listing.claude_verdict else ""
        risk_text = f" Risk: {listing.claude_main_risk}" if listing.claude_main_risk else ""
        return f"{verdict_label}{listing.claude_reasoning}{risk_text}"
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
    claude_verdict: str | None = Query(None),
    status: ListingStatus | None = Query(ListingStatus.active),
    source_name: str | None = Query(None),
    min_profit: float | None = Query(None),
    max_price: float | None = Query(None),
    search: str | None = Query(None),
    first_seen_after: datetime | None = Query(None),
    claude_judged_only: bool = Query(False),
    limit: int = Query(50, le=1000),
    offset: int = Query(0),
    sort_by: str = Query("gem_score"),
    sort_desc: bool = Query(True),
    db: AsyncSession = Depends(get_db),
):
    q = select(Listing)

    if status:
        q = q.where(Listing.status == status)
    if classification:
        q = q.where(Listing.classification == classification)
    if claude_verdict and claude_verdict.upper() in _CLAUDE_VERDICTS:
        q = q.where(Listing.claude_verdict == claude_verdict.upper())
    if source_name:
        q = q.where(Listing.source_name == source_name)
    if min_profit is not None:
        # Use Claude expected profit when available, fall back to estimated
        q = q.where(
            (Listing.claude_expected_profit >= min_profit) |
            ((Listing.claude_expected_profit == None) & (Listing.estimated_profit >= min_profit))
        )
    if max_price is not None:
        q = q.where(Listing.price <= max_price)
    if search:
        q = q.where(Listing.title.ilike(f"%{search}%"))
    if first_seen_after is not None:
        q = q.where(Listing.first_seen_at >= first_seen_after)
    if claude_judged_only:
        q = q.where(Listing.claude_judged_at != None)

    sort_col = getattr(Listing, sort_by, Listing.gem_score)
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

    # Claude verdicts (authoritative when available)
    claude_gems = await db.scalar(
        select(func.count()).select_from(Listing).where(
            Listing.claude_verdict.in_(["GEM", "GOOD"])
        )
    )
    claude_judged = await db.scalar(
        select(func.count()).select_from(Listing).where(
            Listing.claude_judged_at != None
        )
    )
    avg_claude_profit = await db.scalar(
        select(func.avg(Listing.claude_expected_profit)).where(
            Listing.claude_verdict.in_(["GEM", "GOOD"]),
            Listing.claude_expected_profit > 0,
        )
    )

    # Rule-based fallback counts (listings not yet judged by Claude)
    rule_gems = await db.scalar(
        select(func.count()).select_from(Listing).where(
            Listing.classification.in_([Classification.amazing_gem, Classification.gem]),
            Listing.claude_judged_at == None,
        )
    )
    avg_rule_profit = await db.scalar(
        select(func.avg(Listing.estimated_profit)).where(
            Listing.classification.in_([Classification.amazing_gem, Classification.gem]),
            Listing.claude_judged_at == None,
            Listing.estimated_profit > 0,
        )
    )

    gems_count = (claude_gems or 0) + (rule_gems or 0)
    avg_profit = avg_claude_profit or avg_rule_profit or 0

    return {
        "total_listings": total,
        "gems_count": gems_count,
        "avg_profit": round(avg_profit, 2),
        "claude_judged_count": claude_judged or 0,
        "claude_gems_count": claude_gems or 0,
        "rule_based_gems_count": rule_gems or 0,
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


@router.post("/{listing_id}/re-evaluate")
async def re_evaluate_listing(listing_id: int, db: AsyncSession = Depends(get_db)):
    """Force a Claude re-evaluation of this listing (clears previous verdict first)."""
    from app.services.claude_eval_queue import enqueue_for_claude
    listing = await db.get(Listing, listing_id)
    if not listing:
        raise HTTPException(404, "Listing not found")
    listing.claude_judged_at = None  # allow re-evaluation
    await db.commit()
    enqueue_for_claude(listing_id)
    return {"ok": True, "queued": True, "listing_id": listing_id}


@router.post("/queue-for-claude")
async def queue_unjudged_for_claude(
    limit: int = Query(500, le=5000),
    db: AsyncSession = Depends(get_db),
):
    """
    Queue up to `limit` active listings that haven't been Claude-evaluated yet.
    Use this to backfill Claude verdicts for your existing catalogue.
    """
    from app.services.claude_eval_queue import enqueue_for_claude, should_queue_for_claude, queue_size
    result = await db.execute(
        select(Listing)
        .where(
            Listing.claude_judged_at == None,
            Listing.status == ListingStatus.active,
        )
        .order_by(Listing.gem_score.desc())
        .limit(limit)
    )
    listings = result.scalars().all()
    queued = 0
    for listing in listings:
        if should_queue_for_claude(listing):
            if enqueue_for_claude(listing.id):
                queued += 1
    return {
        "ok": True,
        "queued": queued,
        "total_candidates": len(listings),
        "queue_size": queue_size(),
    }
