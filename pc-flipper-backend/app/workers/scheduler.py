"""
APScheduler wrapper — manages all swarm cron jobs.
"""
from collections import deque
from datetime import datetime, timezone
from time import perf_counter
from typing import Awaitable, Callable
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from app.config import get_settings
from app.swarms.flip_opportunities import run_flip_opportunities_swarm
from app.swarms.upgrade_parts import run_upgrade_parts_swarm
from app.swarms.cases import run_cases_swarm
from app.swarms.accessories import run_accessories_swarm
import structlog

log = structlog.get_logger(__name__)
settings = get_settings()

_scheduler: AsyncIOScheduler | None = None
_job_history: dict[str, deque[dict]] = {
    "flip_opportunities": deque(maxlen=50),
    "upgrade_parts": deque(maxlen=50),
    "cases": deque(maxlen=50),
    "accessories": deque(maxlen=50),
}


def _push_history(job_id: str, status: str, started_at: datetime, finished_at: datetime | None, message: str):
    duration_ms = None
    if finished_at is not None:
        duration_ms = int((finished_at - started_at).total_seconds() * 1000)
    _job_history.setdefault(job_id, deque(maxlen=50)).appendleft(
        {
            "id": f"{job_id}-{int(started_at.timestamp() * 1000)}",
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat() if finished_at else None,
            "status": status,
            "message": message,
            "duration_ms": duration_ms,
        }
    )


async def _run_job_with_history(job_id: str, fn: Callable[[], Awaitable[dict]]) -> dict:
    started = datetime.now(timezone.utc)
    t0 = perf_counter()
    _push_history(job_id, "running", started, None, "Job started")
    try:
        result = await fn()
        finished = datetime.now(timezone.utc)
        took_ms = int((perf_counter() - t0) * 1000)
        summary = f"Completed ({took_ms}ms)"
        _push_history(job_id, "success", started, finished, summary)
        return result
    except Exception as exc:
        finished = datetime.now(timezone.utc)
        _push_history(job_id, "failed", started, finished, str(exc))
        raise


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
    return _scheduler


def start_scheduler():
    scheduler = get_scheduler()

    now = datetime.now(timezone.utc)

    scheduler.add_job(
        _run_job_with_history,
        trigger=IntervalTrigger(minutes=settings.flip_scan_interval_minutes),
        id="flip_opportunities",
        name="Flip Opportunities Swarm",
        kwargs={"job_id": "flip_opportunities", "fn": run_flip_opportunities_swarm},
        replace_existing=True,
        max_instances=1,
        next_run_time=now,   # fire immediately on startup
    )

    scheduler.add_job(
        _run_job_with_history,
        trigger=IntervalTrigger(hours=settings.parts_update_interval_hours),
        id="upgrade_parts",
        name="Upgrade Parts Swarm",
        kwargs={"job_id": "upgrade_parts", "fn": run_upgrade_parts_swarm},
        replace_existing=True,
        max_instances=1,
        next_run_time=now,   # fire immediately on startup
    )

    scheduler.add_job(
        _run_job_with_history,
        trigger=IntervalTrigger(hours=24),
        id="cases",
        name="Cases Catalogue Swarm",
        kwargs={"job_id": "cases", "fn": run_cases_swarm},
        replace_existing=True,
        max_instances=1,
        next_run_time=now,   # fire immediately on startup
    )

    scheduler.add_job(
        _run_job_with_history,
        trigger=IntervalTrigger(hours=24),
        id="accessories",
        name="Accessories Swarm",
        kwargs={"job_id": "accessories", "fn": run_accessories_swarm},
        replace_existing=True,
        max_instances=1,
        next_run_time=now,   # fire immediately on startup
    )

    scheduler.start()
    log.info("scheduler.started", jobs=len(scheduler.get_jobs()))


def stop_scheduler():
    scheduler = get_scheduler()
    if scheduler.running:
        scheduler.shutdown()
        log.info("scheduler.stopped")


async def trigger_swarm(swarm_id: str) -> dict:
    """Manually trigger a swarm by ID."""
    if swarm_id == "flip_opportunities":
        return await _run_job_with_history("flip_opportunities", run_flip_opportunities_swarm)
    if swarm_id == "upgrade_parts":
        return await _run_job_with_history("upgrade_parts", run_upgrade_parts_swarm)
    if swarm_id == "cases":
        return await _run_job_with_history("cases", run_cases_swarm)
    if swarm_id == "accessories":
        return await _run_job_with_history("accessories", run_accessories_swarm)
    raise ValueError(f"Unknown swarm: {swarm_id!r}")


def get_swarm_status() -> list[dict]:
    scheduler = get_scheduler()
    return [
        {
            "id": job.id,
            "name": job.name,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            "running": scheduler.running,
        }
        for job in scheduler.get_jobs()
    ]


def set_job_enabled(job_id: str, enabled: bool) -> bool:
    scheduler = get_scheduler()
    if enabled:
        scheduler.resume_job(job_id)
    else:
        scheduler.pause_job(job_id)
    return True


def list_job_runs(job_id: str) -> list[dict]:
    return list(_job_history.get(job_id, []))
