from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from apscheduler.triggers.interval import IntervalTrigger

from app.workers.scheduler import (
    get_scheduler,
    get_swarm_status,
    list_job_runs,
    set_job_enabled,
    trigger_swarm,
)
from app.api.deps import require_operator

router = APIRouter(prefix="/schedule", tags=["schedule"])


def _job_category(job_id: str) -> str:
    if job_id == "flip_opportunities":
        return "sourcing"
    if job_id in {"upgrade_parts", "cases", "amazon_case_bestsellers", "accessories", "external_demand"}:
        return "scraping"
    if job_id == "playbook_evolution":
        return "analysis"
    if job_id == "autonomous":
        return "maintenance"
    if job_id == "outcome_capture":
        return "analysis"
    if job_id == "model_retraining":
        return "analysis"
    if job_id == "retrain_checkpoint_watchdog":
        return "maintenance"
    return "maintenance"

_JOB_DESCRIPTIONS: dict[str, str] = {
    "flip_opportunities": "Scans enabled marketplaces and auctions for profitable PCs, scores gems, and updates listing lifecycle.",
    "upgrade_parts": "Refreshes component pricing from sold comps and retail references for build-cost accuracy.",
    "cases": "Updates themed case catalogue pricing and availability from supported sources.",
    "amazon_case_bestsellers": "Refreshes Amazon UK's live best-selling PC case ranks, prices, RRP, ratings, reviews, and sales velocity.",
    "accessories": "Updates accessory pricing and inventory candidates used for upsell opportunities.",
    "external_demand": "Collects external demand signals (Reddit + scaffolded Google Trends/Steam) for playbook intelligence.",
    "playbook_evolution": "Creates pending playbook update proposals from sold-flip outcomes for human approval.",
    "autonomous": "Runs end-to-end autonomous loop (sourcing, external demand ingestion, playbook evolution).",
    "outcome_capture": "Captures sold outcomes and raises retrain-ready checkpoints once enough new results accumulate.",
    "model_retraining": "Trains candidate model versions when checkpoint thresholds are met, with promote/rollback support.",
    "retrain_checkpoint_watchdog": "Raises alerts when retrain checkpoints stay ready too long without training/promotion.",
}


def _interval_label(trigger: IntervalTrigger | object) -> tuple[str, str]:
    if not isinstance(trigger, IntervalTrigger):
        return ("custom", "Custom")
    secs = int(trigger.interval.total_seconds())
    if secs % 86400 == 0:
        days = secs // 86400
        return (f"every {days} day(s)", f"Every {days} day(s)")
    if secs % 3600 == 0:
        hours = secs // 3600
        return (f"every {hours} hour(s)", f"Every {hours} hour(s)")
    mins = max(1, secs // 60)
    return (f"every {mins} minute(s)", f"Every {mins} min")


@router.get("")
async def list_schedule_jobs():
    scheduler = get_scheduler()
    jobs = scheduler.get_jobs()
    job_map = {j["id"]: j for j in get_swarm_status()}

    out = []
    for job in jobs:
        cron_raw, cron_label = _interval_label(job.trigger)
        status_info = job_map.get(job.id, {})
        last_runs = list_job_runs(job.id)
        last = last_runs[0] if last_runs else None

        out.append(
            {
                "id": job.id,
                "name": job.name,
                "description": _JOB_DESCRIPTIONS.get(job.id, f"Scheduled worker: {job.id.replace('_', ' ')}"),
                "cron": cron_raw,
                "cron_label": cron_label,
                "enabled": job.next_run_time is not None,
                "last_run_at": last["started_at"] if last else None,
                "last_status": last["status"] if last else None,
                "next_run_at": status_info.get("next_run"),
                "category": _job_category(job.id),
            }
        )

    return out


@router.post("/{job_id}/toggle")
async def toggle_schedule_job(job_id: str, _: None = Depends(require_operator)):
    scheduler = get_scheduler()
    job = scheduler.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    currently_enabled = job.next_run_time is not None
    set_job_enabled(job_id, not currently_enabled)
    return {"ok": True, "enabled": not currently_enabled}


@router.post("/{job_id}/run")
async def run_schedule_job(job_id: str, _: None = Depends(require_operator)):
    started = datetime.utcnow()
    await trigger_swarm(job_id)
    finished = datetime.utcnow()
    return {
        "ok": True,
        "status": "success",
        "duration_ms": int((finished - started).total_seconds() * 1000),
    }


@router.get("/{job_id}/runs")
async def get_schedule_runs(job_id: str):
    scheduler = get_scheduler()
    if not scheduler.get_job(job_id):
        raise HTTPException(404, "Job not found")
    return list_job_runs(job_id)
