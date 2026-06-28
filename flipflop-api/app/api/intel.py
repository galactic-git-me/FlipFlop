"""
Intelligence & learning endpoints.
Reads from flip_intelligence table to surface profit patterns and AI recommendations.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from app.database import get_db
from app.models.flip_intelligence import FlipIntelligence
from app.models.flip import Flip
from app.models.outcome_event import RetrainCheckpoint
from app.services import ai_service
from app.services.retraining_pipeline import (
    list_model_versions,
    list_training_runs,
    promote_model_version,
    rollback_to_previous_active,
    run_retraining_if_ready,
)
from app.api.deps import require_operator

router = APIRouter(prefix="/intel", tags=["intel"])


@router.get("/summary")
async def get_summary(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(
        func.count(FlipIntelligence.id).label("total_flips"),
        func.sum(FlipIntelligence.profit).label("total_profit"),
        func.avg(FlipIntelligence.profit).label("avg_profit"),
        func.avg(FlipIntelligence.roi_pct).label("avg_roi_pct"),
        func.avg(FlipIntelligence.days_to_sell).label("avg_days_to_sell"),
    ))
    row = result.one()

    best_source = await _best_by(db, FlipIntelligence.source_site)
    best_cpu = await _best_by(db, FlipIntelligence.cpu_tier)

    return {
        "total_flips": row.total_flips or 0,
        "total_profit": float(row.total_profit or 0),
        "avg_profit": float(row.avg_profit or 0),
        "avg_roi_pct": float(row.avg_roi_pct or 0),
        "avg_days_to_sell": float(row.avg_days_to_sell or 0),
        "best_source": best_source,
        "best_cpu_tier": best_cpu,
    }


@router.get("/by-source")
async def by_source(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(
            FlipIntelligence.source_site.label("source"),
            func.count(FlipIntelligence.id).label("count"),
            func.avg(FlipIntelligence.profit).label("avg_profit"),
            func.sum(FlipIntelligence.profit).label("total_profit"),
        )
        .group_by(FlipIntelligence.source_site)
        .order_by(desc(func.avg(FlipIntelligence.profit)))
    )
    return [
        {"source": r.source, "count": r.count, "avg_profit": float(r.avg_profit), "total_profit": float(r.total_profit)}
        for r in result.all()
    ]


@router.get("/by-cpu")
async def by_cpu(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(
            FlipIntelligence.cpu_tier.label("cpu_tier"),
            func.count(FlipIntelligence.id).label("count"),
            func.avg(FlipIntelligence.profit).label("avg_profit"),
        )
        .where(FlipIntelligence.cpu_tier.is_not(None))
        .group_by(FlipIntelligence.cpu_tier)
        .order_by(desc(func.avg(FlipIntelligence.profit)))
    )
    return [
        {"cpu_tier": r.cpu_tier, "count": r.count, "avg_profit": float(r.avg_profit)}
        for r in result.all()
    ]


@router.get("/by-platform")
async def by_platform(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(
            FlipIntelligence.sell_platform.label("platform"),
            func.count(FlipIntelligence.id).label("count"),
            func.avg(FlipIntelligence.profit).label("avg_profit"),
        )
        .group_by(FlipIntelligence.sell_platform)
        .order_by(desc(func.avg(FlipIntelligence.profit)))
    )
    return [
        {"platform": r.platform, "count": r.count, "avg_profit": float(r.avg_profit)}
        for r in result.all()
    ]


@router.get("/history")
async def history(limit: int = 20, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(FlipIntelligence)
        .order_by(desc(FlipIntelligence.created_at))
        .limit(limit)
    )
    rows = result.scalars().all()
    return [
        {
            "id": r.id,
            "flip_id": r.flip_id,
            "buy_price": r.buy_price,
            "sell_price": r.sell_price,
            "profit": r.profit,
            "roi_pct": r.roi_pct,
            "days_to_sell": r.days_to_sell,
            "source_site": r.source_site,
            "cpu_tier": r.cpu_tier or "Unknown",
            "sell_platform": r.sell_platform,
            "case_theme": r.case_theme,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


@router.get("/recommendations")
async def recommendations(db: AsyncSession = Depends(get_db)):
    """AI-powered recommendations based on historical flip data."""
    result = await db.execute(select(FlipIntelligence).order_by(desc(FlipIntelligence.created_at)).limit(50))
    records = result.scalars().all()

    if len(records) < 3:
        return [{"insight": "Not enough data yet", "action": "Complete more flips to unlock AI recommendations", "confidence": 0.3}]

    # Build summary for Hermes
    total = len(records)
    avg_profit = sum(r.profit for r in records) / total
    source_profits: dict[str, list[float]] = {}
    cpu_profits: dict[str, list[float]] = {}
    platform_profits: dict[str, list[float]] = {}
    themed_profits = [r.profit for r in records if r.case_theme]
    unthemed_profits = [r.profit for r in records if not r.case_theme]

    for r in records:
        source_profits.setdefault(r.source_site, []).append(r.profit)
        if r.cpu_tier:
            cpu_profits.setdefault(r.cpu_tier, []).append(r.profit)
        platform_profits.setdefault(r.sell_platform, []).append(r.profit)

    best_source = max(source_profits, key=lambda k: sum(source_profits[k]) / len(source_profits[k])) if source_profits else None
    best_cpu = max(cpu_profits, key=lambda k: sum(cpu_profits[k]) / len(cpu_profits[k])) if cpu_profits else None
    best_platform = max(platform_profits, key=lambda k: sum(platform_profits[k]) / len(platform_profits[k])) if platform_profits else None
    themed_avg = sum(themed_profits) / len(themed_profits) if themed_profits else None
    unthemed_avg = sum(unthemed_profits) / len(unthemed_profits) if unthemed_profits else None

    # Build rule-based recommendations (fast, no AI call needed for common patterns)
    recs = []

    if best_source:
        best_src_avg = sum(source_profits[best_source]) / len(source_profits[best_source])
        if best_src_avg > avg_profit * 1.2:
            recs.append({
                "insight": f"{best_source} produces {((best_src_avg/avg_profit)-1)*100:.0f}% higher profit than average across your flips",
                "action": f"Prioritise {best_source} for sourcing — focus more scan time here",
                "confidence": min(0.9, 0.6 + len(source_profits[best_source]) * 0.05),
            })

    if best_cpu:
        best_cpu_avg = sum(cpu_profits[best_cpu]) / len(cpu_profits[best_cpu])
        if best_cpu_avg > avg_profit * 1.15:
            recs.append({
                "insight": f"{best_cpu} units yield the highest margins in your portfolio",
                "action": f"Increase max price ceiling for {best_cpu} units — they justify the premium",
                "confidence": min(0.85, 0.55 + len(cpu_profits[best_cpu]) * 0.06),
            })

    if best_platform:
        best_plat_avg = sum(platform_profits[best_platform]) / len(platform_profits[best_platform])
        if best_plat_avg > avg_profit * 1.1:
            recs.append({
                "insight": f"{best_platform.capitalize()} delivers the best net profit after fees in your history",
                "action": f"Default all new listings to {best_platform.capitalize()} first",
                "confidence": 0.75,
            })

    if themed_avg and unthemed_avg and themed_avg > unthemed_avg * 1.15:
        recs.append({
            "insight": f"Sci-fi themed builds average £{themed_avg:.0f} vs £{unthemed_avg:.0f} unthemed — a {((themed_avg/unthemed_avg)-1)*100:.0f}% premium",
            "action": "Always add a themed case to builds with strong CPU — the margin more than covers the case cost",
            "confidence": 0.8,
        })

    avg_days = sum(r.days_to_sell for r in records) / total
    if avg_days > 14:
        recs.append({
            "insight": f"Average time-to-sell is {avg_days:.0f} days — listings may be overpriced or poorly titled",
            "action": "Use Hermes to regenerate listing titles and price 5% below current suggested resale",
            "confidence": 0.7,
        })

    # Learning loop: compare realized profits to original forecast at flip selection.
    flip_ids = [r.flip_id for r in records if r.flip_id]
    if flip_ids:
        flips_result = await db.execute(
            select(Flip.id, Flip.initial_estimated_profit, Flip.actual_profit)
            .where(Flip.id.in_(flip_ids), Flip.actual_profit.is_not(None))
        )
        deltas = []
        abs_pct_errors = []
        for row in flips_result.all():
            if row.initial_estimated_profit is None:
                continue
            actual = float(row.actual_profit or 0)
            forecast = float(row.initial_estimated_profit)
            delta = actual - forecast
            deltas.append(delta)
            if abs(actual) > 1:
                abs_pct_errors.append(abs(delta) / abs(actual))

        if len(deltas) >= 3:
            avg_delta = sum(deltas) / len(deltas)
            mean_abs_pct_error = (sum(abs_pct_errors) / len(abs_pct_errors)) if abs_pct_errors else 0.0
            if avg_delta < -40:
                recs.append({
                    "insight": f"Recent flips are averaging £{abs(avg_delta):.0f} below forecasted profit",
                    "action": "Tighten sourcing guardrails: require higher gem score or +£50 profit buffer before committing.",
                    "confidence": min(0.85, 0.55 + len(deltas) * 0.04),
                })
            elif avg_delta > 40:
                recs.append({
                    "insight": f"Recent flips are averaging £{avg_delta:.0f} above initial forecasts",
                    "action": "You can safely widen search criteria slightly to capture more volume.",
                    "confidence": min(0.85, 0.55 + len(deltas) * 0.04),
                })

            if mean_abs_pct_error > 0.35:
                recs.append({
                    "insight": f"Forecast variance is high ({mean_abs_pct_error * 100:.0f}% average absolute error)",
                    "action": "Prioritise listings with stronger sold-comp depth and avoid sparse-spec auctions.",
                    "confidence": 0.7,
                })

    if not recs:
        recs.append({
            "insight": f"Consistent performance across {total} flips with £{avg_profit:.0f} average profit",
            "action": "Increase max concurrent flips from 1 — your data shows reliable margins",
            "confidence": 0.65,
        })

    return recs[:5]


async def _best_by(db: AsyncSession, column) -> str | None:
    result = await db.execute(
        select(column, func.avg(FlipIntelligence.profit).label("avg_p"))
        .where(column.is_not(None))
        .group_by(column)
        .order_by(desc("avg_p"))
        .limit(1)
    )
    row = result.one_or_none()
    return str(row[0]) if row else None


@router.get("/retrain-status")
async def retrain_status(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(RetrainCheckpoint).where(RetrainCheckpoint.name == "policy")
    )
    row = result.scalar_one_or_none()
    if row is None:
        return {
            "checkpoint": "policy",
            "sold_flips_since": 0,
            "retrain_ready": False,
            "last_flip_id": 0,
            "updated_at": None,
        }
    return {
        "checkpoint": row.name,
        "sold_flips_since": row.sold_flips_since,
        "retrain_ready": row.ready,
        "last_flip_id": row.last_flip_id,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


@router.post("/models/retrain")
async def retrain_now(_: None = Depends(require_operator)):
    return await run_retraining_if_ready(triggered_by="manual")


@router.get("/models/versions")
async def model_versions(limit: int = 20):
    return {"items": await list_model_versions(limit=limit)}


@router.get("/models/runs")
async def model_runs(limit: int = 30):
    return {"items": await list_training_runs(limit=limit)}


@router.post("/models/{version}/promote")
async def promote(version: str, _: None = Depends(require_operator)):
    return await promote_model_version(version)


@router.post("/models/rollback")
async def rollback(_: None = Depends(require_operator)):
    return await rollback_to_previous_active()
