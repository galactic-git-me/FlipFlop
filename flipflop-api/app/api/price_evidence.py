"""Product price evidence for the admin market-price explorer."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.gem_radar_cpk_listing_price import GemRadarCpkListingPrice
from app.models.gem_radar_cpk_market_price import GemRadarCpkMarketPrice
from app.models.gem_radar_observation import GemRadarListingObservation
from app.models.gem_radar_sold_observation import GemRadarSoldObservation

router = APIRouter(prefix="/price-evidence", tags=["price-evidence"])


def _product(row: GemRadarCpkMarketPrice) -> dict:
    label = " ".join(part for part in (row.brand, row.model) if part).strip() or row.cpk
    return {"cpk": row.cpk, "label": label, "brand": row.brand, "model": row.model,
            "category": row.category, "min_price": row.min_price, "median_price": row.median_price,
            "max_price": row.max_price, "listing_count": row.listing_count}


@router.get("/products")
async def list_products(q: str = Query(default=""), limit: int = Query(default=100, ge=1, le=500), db: AsyncSession = Depends(get_db)):
    term = q.strip()
    query = select(GemRadarCpkMarketPrice).order_by(GemRadarCpkMarketPrice.brand, GemRadarCpkMarketPrice.model).limit(limit)
    if term:
        like = f"%{term}%"
        query = query.where(or_(GemRadarCpkMarketPrice.cpk.ilike(like), GemRadarCpkMarketPrice.brand.ilike(like), GemRadarCpkMarketPrice.model.ilike(like)))
    rows = list((await db.execute(query)).scalars().all())
    return {"items": [_product(row) for row in rows]}


@router.get("/products/{cpk:path}")
async def product_evidence(cpk: str, db: AsyncSession = Depends(get_db)):
    market = (await db.execute(select(GemRadarCpkMarketPrice).where(GemRadarCpkMarketPrice.cpk == cpk))).scalar_one_or_none()
    active_prices = list((await db.execute(select(GemRadarCpkListingPrice).where(GemRadarCpkListingPrice.cpk == cpk).order_by(GemRadarCpkListingPrice.updated_at.desc()).limit(500))).scalars().all())
    sold = list((await db.execute(select(GemRadarSoldObservation).where(GemRadarSoldObservation.cpk == cpk).order_by(GemRadarSoldObservation.observed_at.desc()).limit(500))).scalars().all())
    observations = []
    for row in active_prices:
        obs = (await db.execute(select(GemRadarListingObservation).where(GemRadarListingObservation.listing_id == row.listing_id).order_by(GemRadarListingObservation.observed_at.desc()).limit(1))).scalar_one_or_none()
        observations.append({"kind": "active", "price": row.price, "observed_at": obs.observed_at.isoformat() if obs and obs.observed_at else row.updated_at.isoformat(), "source": obs.source if obs else None, "source_url": None, "title": obs.title if obs else row.listing_id})
    observations.extend({"kind": "sold", "price": row.price + (row.postage or 0), "observed_at": row.observed_at.isoformat() if row.observed_at else None, "source": "eBay sold", "source_url": row.source_url, "title": row.title or row.model or row.match_key} for row in sold)
    observations.sort(key=lambda item: item["observed_at"] or "", reverse=True)
    return {"product": _product(market) if market else {"cpk": cpk, "label": cpk}, "observations": observations}
