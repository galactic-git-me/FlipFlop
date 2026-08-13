"""
Admin Performance & Margin dashboard — Algorithm Playbook rows 16, 37, 38.
Cross-build/store-wide utilities, not scoped to a single build's page.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services import performance_dashboard

router = APIRouter(prefix="/admin/performance", tags=["admin-performance"])


@router.get("/summary")
async def get_summary(days: int = Query(90, ge=1, le=365), db: AsyncSession = Depends(get_db)):
    return await performance_dashboard.get_revenue_margin_summary(db, days=days)


@router.get("/seller-standards")
async def get_seller_standards(db: AsyncSession = Depends(get_db)):
    return await performance_dashboard.get_seller_performance_metrics(db)


@router.get("/keyword-research")
async def keyword_research(query: str = Query(..., min_length=2)):
    return await performance_dashboard.search_title_keywords(query)
