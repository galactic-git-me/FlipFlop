"""
Benchmark refresh orchestrator.
Daily: refresh active components only.
Weekly: refresh entire PassMark catalogue.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
import structlog
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.benchmark import HardwareBenchmark, BenchmarkRefreshRun
from app.services.benchmark_fetcher import (
    fetch_passmark_cpus, fetch_passmark_gpus, fetch_passmark_disks, BenchmarkRecord
)
from app.services.benchmark_normaliser import normalise_cpu, normalise_gpu, detect_component_type

log = structlog.get_logger(__name__)

STALENESS_DAYS = 30


@dataclass
class ActiveModel:
    raw: str
    normalized: str
    component_type: str


def is_benchmark_stale(last_refreshed_at: Optional[str], staleness_days: int = STALENESS_DAYS) -> bool:
    if not last_refreshed_at:
        return True
    try:
        last = datetime.fromisoformat(last_refreshed_at)
        return (datetime.utcnow() - last) > timedelta(days=staleness_days)
    except Exception:
        return True


def build_active_model_list(
    playbook_models: list[str],
    listing_models: list[str],
) -> list[ActiveModel]:
    seen: set[str] = set()
    result: list[ActiveModel] = []
    for raw in playbook_models + listing_models:
        if not raw or not raw.strip():
            continue
        ct = detect_component_type(raw)
        if ct == "cpu":
            norm = normalise_cpu(raw)
        elif ct == "gpu":
            norm = normalise_gpu(raw)
        else:
            norm = raw.lower().strip().replace(" ", "_")
        if norm in seen:
            continue
        seen.add(norm)
        result.append(ActiveModel(raw=raw, normalized=norm, component_type=ct))
    return result


async def _upsert_benchmark(db, record: BenchmarkRecord) -> bool:
    existing = await db.execute(
        select(HardwareBenchmark).where(
            HardwareBenchmark.normalized_model == record.normalized_model,
            HardwareBenchmark.benchmark_source == record.benchmark_source,
        )
    )
    row = existing.scalar_one_or_none()
    now = datetime.utcnow().isoformat()
    if row:
        row.overall_score = record.overall_score
        row.gaming_score = record.gaming_score
        row.workstation_score = record.workstation_score
        row.last_refreshed_at = now
        row.updated_at = now
        return False
    else:
        db.add(HardwareBenchmark(
            component_type=record.component_type,
            model=record.model,
            normalized_model=record.normalized_model,
            benchmark_source=record.benchmark_source,
            overall_score=record.overall_score,
            gaming_score=record.gaming_score,
            workstation_score=record.workstation_score,
            single_thread_score=record.single_thread_score,
            multi_thread_score=record.multi_thread_score,
            storage_score=record.storage_score,
            vram_gb=record.vram_gb,
            storage_interface=record.storage_interface,
            source_url=record.source_url,
            confidence_score=record.confidence_score,
            last_refreshed_at=now,
            updated_at=now,
        ))
        return True


async def _get_playbook_models(db) -> list[str]:
    from app.models.playbook import Playbook
    result = await db.execute(select(Playbook).where(Playbook.status == "active"))
    playbooks = result.scalars().all()
    models: list[str] = []
    for pb in playbooks:
        us = pb.upgrade_strategy or {}
        for item in (us.get("required") or []) + (us.get("optional") or []):
            target = str(item.get("target") or "").strip()
            if target:
                for part in target.split("/"):
                    if part.strip():
                        models.append(part.strip())
    return models


async def _get_active_listing_models(db) -> list[str]:
    from app.models.listing import Listing, ListingStatus
    result = await db.execute(
        select(Listing.cpu, Listing.gpu)
        .where(Listing.status == ListingStatus.active)
        .limit(500)
    )
    rows = result.all()
    models: list[str] = []
    for cpu, gpu in rows:
        if cpu:
            models.append(cpu)
        if gpu:
            models.append(gpu)
    return models


async def run_benchmark_refresh(run_type: str = "daily") -> dict:
    """Main entry point called by scheduler. run_type: 'daily' | 'weekly' | 'manual'"""
    started_at = datetime.utcnow().isoformat()
    run_row = BenchmarkRefreshRun(
        run_type=run_type, started_at=started_at, status="running", source="passmark",
    )
    async with AsyncSessionLocal() as db:
        db.add(run_row)
        await db.commit()
        await db.refresh(run_row)
        run_id = run_row.id

    checked = updated = failed = 0
    errors: list[str] = []

    try:
        log.info("benchmark_refresh.fetching", run_type=run_type)
        cpu_records = await fetch_passmark_cpus()
        gpu_records = await fetch_passmark_gpus()
        disk_records = await fetch_passmark_disks()
        all_records = cpu_records + gpu_records + disk_records

        if run_type == "daily":
            async with AsyncSessionLocal() as db:
                pb_models = await _get_playbook_models(db)
                listing_models = await _get_active_listing_models(db)
            active = build_active_model_list(pb_models, listing_models)
            active_norms = {m.normalized for m in active}
            all_records = [r for r in all_records if r.normalized_model in active_norms]

        log.info("benchmark_refresh.upserting", count=len(all_records))
        async with AsyncSessionLocal() as db:
            for record in all_records:
                checked += 1
                try:
                    await _upsert_benchmark(db, record)
                    updated += 1
                except Exception as exc:
                    failed += 1
                    errors.append(f"{record.model}: {exc}")
            await db.commit()

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(BenchmarkRefreshRun).where(BenchmarkRefreshRun.id == run_id))
            run_row = result.scalar_one_or_none()
            if run_row:
                run_row.completed_at = datetime.utcnow().isoformat()
                run_row.status = "completed"
                run_row.components_checked = checked
                run_row.components_updated = updated
                run_row.components_failed = failed
                run_row.error_log = "; ".join(errors[:20]) if errors else None
            await db.commit()

        log.info("benchmark_refresh.done", checked=checked, updated=updated, failed=failed)
        return {"ok": True, "checked": checked, "updated": updated, "failed": failed}

    except Exception as exc:
        log.error("benchmark_refresh.failed", error=str(exc))
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(BenchmarkRefreshRun).where(BenchmarkRefreshRun.id == run_id))
            run_row = result.scalar_one_or_none()
            if run_row:
                run_row.completed_at = datetime.utcnow().isoformat()
                run_row.status = "failed"
                run_row.error_log = str(exc)
            await db.commit()
        return {"ok": False, "error": str(exc)}
