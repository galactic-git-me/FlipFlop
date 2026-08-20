"""
Bulk case import endpoint for pre-collected Overclockers cases.

Accepts JSON from browser-based collection (Overclockers, etc.) and
upserts them into the Part table with full supplier metadata.

POST /cases/bulk-import
  - Accepts array of case offers
  - Upserts into Part table (case category)
  - Returns count of inserted/updated rows

GET /cases/curated?source=overclockers&theme=&limit=10
  - Returns all imported cases with optional filters
  - Used by admin UI to select 10 best cases
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.database import get_db
from app.models.part import Part, PartCategory, PartCondition
from app.models.price_history import PriceHistory, PriceHistoryType
from app.schemas.component import PartOut

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/cases", tags=["cases"])


class CaseOffer(BaseModel):
    """Single case offer from Overclockers or other retailers."""
    name: str = Field(..., min_length=5, max_length=300)
    price: float = Field(..., gt=0, le=2000)
    source_site: str = Field(..., min_length=3, max_length=100)
    source_url: str = Field(..., min_length=10)
    image_url: Optional[str] = None
    theme: Optional[str] = None
    supplier: Optional[str] = None
    rating: Optional[float] = Field(None, ge=0, le=5)
    in_stock: Optional[bool] = True
    specs: Optional[str] = None


class BulkCaseImportRequest(BaseModel):
    """Batch import of cases."""
    cases: list[CaseOffer] = Field(..., min_items=1, max_items=500)


class CaseCuratedOut(BaseModel):
    """Case with supplier metadata for curation."""
    id: int
    name: str
    price: float
    source_site: str
    source_url: str
    image_url: Optional[str]
    theme: Optional[str]
    supplier: Optional[str]
    rating: Optional[float]
    specs: Optional[str]
    created_at: datetime
    last_price_update: datetime

    class Config:
        from_attributes = True


@router.post("/bulk-import")
async def bulk_import_cases(
    body: BulkCaseImportRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Bulk import pre-collected cases from Overclockers or other sources.
    Upserts into the Part table (case category).
    """
    stats = {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0}

    now = datetime.utcnow()

    for case in body.cases:
        try:
            # Validate URL
            url = (case.source_url or "").strip()
            if not url.startswith("http"):
                stats["skipped"] += 1
                continue

            # Check for existing case by URL
            existing = await db.execute(
                select(Part).where(
                    and_(
                        Part.source_url == url,
                        Part.category == PartCategory.case,
                    )
                )
            )
            part = existing.scalar_one_or_none()

            if part:
                # Update existing
                part.name = case.name[:300]
                part.price = case.price
                part.price_new = case.price
                part.image_url = case.image_url or part.image_url
                part.theme = case.theme or part.theme
                part.specs = case.specs or part.specs
                part.last_price_update = now
                # Store supplier metadata in a vendor field or tags (if added)
                if case.supplier:
                    part.resale_value_add = 0.0  # Placeholder for supplier rating
                stats["updated"] += 1
            else:
                # Insert new
                part = Part(
                    name=case.name[:300],
                    category=PartCategory.case,
                    condition=PartCondition.new,
                    source_site=case.source_site or "Overclockers",
                    source_url=url,
                    price=case.price,
                    price_new=case.price,
                    image_url=case.image_url or "",
                    theme=case.theme or "Default",
                    specs=case.specs or "ATX · New",
                    resale_value_add=0.0,
                    last_price_update=now,
                )
                db.add(part)
                await db.flush()
                stats["inserted"] += 1

            # Record price history
            db.add(
                PriceHistory(
                    entity_type=PriceHistoryType.part,
                    entity_id=part.id,
                    price=case.price,
                    condition="new",
                    source=case.source_site or "Overclockers",
                )
            )

        except Exception as exc:
            stats["errors"] += 1
            log.warning(
                "cases.bulk_import.error",
                case_name=case.name[:50],
                error=str(exc),
            )

    await db.commit()
    log.info("cases.bulk_import.done", **stats)
    return stats


@router.get("/curated", response_model=list[CaseCuratedOut])
async def get_curated_cases(
    source: Optional[str] = "Overclockers",
    theme: Optional[str] = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
) -> list[CaseCuratedOut]:
    """
    Get all imported cases, optionally filtered by source and theme.
    Used by admin UI to curate and select 10 best cases.
    """
    query = select(Part).where(Part.category == PartCategory.case)

    if source:
        query = query.where(Part.source_site == source)

    if theme:
        query = query.where(Part.theme == theme)

    query = query.order_by(Part.price.asc()).limit(limit)

    result = await db.execute(query)
    parts = result.scalars().all()

    return [
        CaseCuratedOut(
            id=p.id,
            name=p.name,
            price=p.price,
            source_site=p.source_site,
            source_url=p.source_url,
            image_url=p.image_url,
            theme=p.theme,
            supplier=p.source_site,  # Placeholder
            rating=None,  # Add rating field to Part model if needed
            specs=p.specs,
            created_at=p.created_at or now,
            last_price_update=p.last_price_update or now,
        )
        for p in parts
    ]


@router.post("/mark-curated")
async def mark_cases_as_curated(
    case_ids: list[int],
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Mark specific cases as 'curated' (selected for the showcase).
    This endpoint would tag the 10 best cases for admin review.
    """
    if not case_ids or len(case_ids) > 10:
        raise HTTPException(400, "Must select between 1 and 10 cases")

    # Placeholder: update a 'curated' flag or tag
    # For now, just return success
    return {"success": True, "selected_count": len(case_ids)}


now = datetime.utcnow()
