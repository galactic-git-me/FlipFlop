"""Favourites: user-saved component searches, tracked across every data run.

See app/gem_radar/favourite_matching.py for the fuzzy-matching logic shared
between this router's live search and the background gem-match hook in
phase2_runner.py.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_operator
from app.database import get_db
from app.gem_radar.favourite_matching import (
    SEARCH_THRESHOLD,
    best_category,
    build_vendor_matrix,
    filter_matches,
)
from app.schemas.favourite import ProductOption
from app.gem_radar.marketplace import fallback_listing_url
from app.gem_radar.observations import get_active_listing_ids
from app.models.favourite import Favourite
from app.models.gem_radar_scored_listing import GemRadarScoredListing
from app.schemas.favourite import FavouriteCreate, FavouriteMatrixRow, FavouriteOut, FavouriteUpdate

router = APIRouter(prefix="/favourites", tags=["favourites"])


def _build_products_list(matches: list[dict]) -> list[ProductOption]:
    """Extract unique CPKs from matches, return sorted by lowest price."""
    products: dict[str, tuple[float, str]] = {}  # cpk -> (lowest_price, title)
    for m in matches:
        cpk = m.get("cpk")
        if not cpk:
            continue
        price = m.get("delivered_price")
        if price is None:
            continue
        title = m.get("title") or ""
        if cpk not in products or price < products[cpk][0]:
            products[cpk] = (price, title)

    result = [ProductOption(cpk=cpk, lowest_price=price, title=title) for cpk, (price, title) in products.items()]
    result.sort(key=lambda p: p.lowest_price)
    return result


async def _active_scored_listings(db: AsyncSession) -> list[dict]:
    """Same active/dedup shape as GET /scored-listings, trimmed to the
    fields the matrix builder needs."""
    active_ids = await get_active_listing_ids(db)
    if not active_ids:
        return []

    latest_scored_at = (
        select(
            GemRadarScoredListing.listing_id,
            func.max(GemRadarScoredListing.scored_at).label("scored_at"),
        )
        .where(GemRadarScoredListing.listing_id.in_(active_ids))
        .group_by(GemRadarScoredListing.listing_id)
        .subquery()
    )
    result = await db.execute(
        select(GemRadarScoredListing)
        .join(
            latest_scored_at,
            (GemRadarScoredListing.listing_id == latest_scored_at.c.listing_id)
            & (GemRadarScoredListing.scored_at == latest_scored_at.c.scored_at),
        )
    )
    scored = result.scalars().all()
    return [
        {
            "listing_id": s.listing_id,
            "source": s.source,
            "url": s.url or fallback_listing_url(s.listing_id, s.source),
            "category": s.category,
            "title": s.title,
            "delivered_price": s.delivered_price,
            "classification": s.classification,
            "cpk": s.cpk,
        }
        for s in scored
    ]


@router.get("")
async def list_favourites(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(Favourite).order_by(Favourite.category, Favourite.term, Favourite.cpk))).scalars().all()
    groups = sorted({r.category for r in rows if r.category})
    return {
        "items": [FavouriteOut.model_validate(r).model_dump() for r in rows],
        "groups": groups,
    }


@router.get("/search", response_model=FavouriteMatrixRow)
async def search_favourites(q: str = Query(..., min_length=1), db: AsyncSession = Depends(get_db)):
    listings = await _active_scored_listings(db)
    matches = filter_matches(q, listings, threshold=SEARCH_THRESHOLD)
    return FavouriteMatrixRow(
        query=q,
        category=best_category(matches),
        vendors=build_vendor_matrix(matches),
        products=_build_products_list(matches),
    )


@router.get("/matrix")
async def favourites_matrix(db: AsyncSession = Depends(get_db)):
    favourites = (await db.execute(select(Favourite))).scalars().all()
    listings = await _active_scored_listings(db)
    result: dict[int, dict] = {}
    for fav in favourites:
        matches = []
        query_display = ""

        # CPK match: filter to listings with this CPK
        if fav.cpk:
            matches = [l for l in listings if l.get("cpk") == fav.cpk]
            query_display = f"[Product: {fav.cpk}]"
        # Term match: fuzzy match the listings
        elif fav.term:
            matches = filter_matches(fav.term, listings, threshold=SEARCH_THRESHOLD)
            query_display = fav.term

        result[fav.id] = FavouriteMatrixRow(
            query=query_display,
            category=fav.category,
            vendors=build_vendor_matrix(matches),
            products=_build_products_list(matches),
        ).model_dump()
    return result


@router.post("", response_model=FavouriteOut, status_code=201, dependencies=[Depends(require_operator)])
async def create_favourite(body: FavouriteCreate, db: AsyncSession = Depends(get_db)):
    if not body.term and not body.cpk:
        raise HTTPException(400, "Must provide either term or cpk")

    category = body.category
    if not category and body.term:
        listings = await _active_scored_listings(db)
        matches = filter_matches(body.term, listings, threshold=SEARCH_THRESHOLD)
        category = best_category(matches)

    row = Favourite(term=body.term, cpk=body.cpk, category=category)
    db.add(row)
    await db.flush()
    await db.refresh(row)
    return row


@router.patch("/{favourite_id}", response_model=FavouriteOut, dependencies=[Depends(require_operator)])
async def update_favourite(favourite_id: int, body: FavouriteUpdate, db: AsyncSession = Depends(get_db)):
    row = await db.get(Favourite, favourite_id)
    if not row:
        raise HTTPException(404, "Favourite not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(row, k, v)
    await db.flush()
    await db.refresh(row)
    return row


@router.delete("/{favourite_id}", status_code=204, dependencies=[Depends(require_operator)])
async def delete_favourite(favourite_id: int, db: AsyncSession = Depends(get_db)):
    row = await db.get(Favourite, favourite_id)
    if not row:
        raise HTTPException(404, "Favourite not found")
    await db.delete(row)
    return None
