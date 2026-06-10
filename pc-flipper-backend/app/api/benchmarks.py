"""
Benchmark admin/debug API endpoints.
"""
from __future__ import annotations
import asyncio
from fastapi import APIRouter, Depends
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.benchmark import HardwareBenchmark, BenchmarkRefreshRun
from app.services.benchmark_refresh_job import run_benchmark_refresh

router = APIRouter(prefix="/benchmarks", tags=["benchmarks"])


@router.get("/status")
async def get_benchmark_status(db: AsyncSession = Depends(get_db)):
    cpu_count = await db.scalar(
        select(func.count()).select_from(HardwareBenchmark).where(HardwareBenchmark.component_type == "cpu")
    )
    gpu_count = await db.scalar(
        select(func.count()).select_from(HardwareBenchmark).where(HardwareBenchmark.component_type == "gpu")
    )
    storage_count = await db.scalar(
        select(func.count()).select_from(HardwareBenchmark).where(HardwareBenchmark.component_type == "storage")
    )
    total = await db.scalar(select(func.count()).select_from(HardwareBenchmark))

    last_run_result = await db.execute(
        select(BenchmarkRefreshRun).order_by(desc(BenchmarkRefreshRun.id)).limit(1)
    )
    last_run_row = last_run_result.scalar_one_or_none()

    return {
        "total_benchmarks": total or 0,
        "cpu_count": cpu_count or 0,
        "gpu_count": gpu_count or 0,
        "storage_count": storage_count or 0,
        "last_run": {
            "run_type": last_run_row.run_type if last_run_row else None,
            "status": last_run_row.status if last_run_row else None,
            "started_at": last_run_row.started_at if last_run_row else None,
            "completed_at": last_run_row.completed_at if last_run_row else None,
            "components_checked": last_run_row.components_checked if last_run_row else 0,
            "components_updated": last_run_row.components_updated if last_run_row else 0,
            "components_failed": last_run_row.components_failed if last_run_row else 0,
        } if last_run_row else None,
    }


@router.get("/top")
async def get_top_benchmarks(
    component_type: str = "cpu",
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(HardwareBenchmark)
        .where(HardwareBenchmark.component_type == component_type)
        .order_by(desc(HardwareBenchmark.overall_score))
        .limit(limit)
    )
    rows = result.scalars().all()
    return [
        {
            "model": r.model,
            "normalized_model": r.normalized_model,
            "overall_score": r.overall_score,
            "gaming_score": r.gaming_score,
            "workstation_score": r.workstation_score,
            "last_refreshed_at": r.last_refreshed_at,
            "confidence_score": r.confidence_score,
        }
        for r in rows
    ]


@router.get("/lookup")
async def lookup_benchmark(
    model: str,
    component_type: str = "cpu",
    db: AsyncSession = Depends(get_db),
):
    from app.services.benchmark_normaliser import normalise_cpu, normalise_gpu
    if component_type == "cpu":
        norm = normalise_cpu(model)
    elif component_type == "gpu":
        norm = normalise_gpu(model)
    else:
        norm = model.lower().replace(" ", "_")

    result = await db.execute(
        select(HardwareBenchmark).where(HardwareBenchmark.normalized_model == norm)
    )
    row = result.scalar_one_or_none()
    if not row:
        return {"found": False, "normalized_model": norm}
    return {
        "found": True,
        "model": row.model,
        "normalized_model": row.normalized_model,
        "overall_score": row.overall_score,
        "gaming_score": row.gaming_score,
        "workstation_score": row.workstation_score,
        "last_refreshed_at": row.last_refreshed_at,
        "confidence_score": row.confidence_score,
    }


@router.get("/refresh-runs")
async def list_refresh_runs(limit: int = 10, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(BenchmarkRefreshRun).order_by(desc(BenchmarkRefreshRun.id)).limit(limit)
    )
    rows = result.scalars().all()
    return [
        {
            "id": r.id,
            "run_type": r.run_type,
            "status": r.status,
            "started_at": r.started_at,
            "completed_at": r.completed_at,
            "components_checked": r.components_checked,
            "components_updated": r.components_updated,
            "components_failed": r.components_failed,
            "error_log": r.error_log,
        }
        for r in rows
    ]


@router.post("/refresh")
async def trigger_refresh(run_type: str = "manual"):
    asyncio.create_task(run_benchmark_refresh(run_type))
    return {"ok": True, "message": f"Benchmark refresh ({run_type}) started in background"}
