"""
APScheduler wrapper — manages all swarm cron jobs.
"""
from datetime import datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from app.config import get_settings
from app.swarms.flip_opportunities import run_flip_opportunities_swarm
from app.swarms.upgrade_parts import run_upgrade_parts_swarm
from app.swarms.cases import run_cases_swarm
import structlog

log = structlog.get_logger(__name__)
settings = get_settings()

_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
    return _scheduler


def start_scheduler():
    scheduler = get_scheduler()

    now = datetime.now(timezone.utc)

    scheduler.add_job(
        run_flip_opportunities_swarm,
        trigger=IntervalTrigger(minutes=settings.flip_scan_interval_minutes),
        id="flip_opportunities",
        name="Flip Opportunities Swarm",
        replace_existing=True,
        max_instances=1,
        next_run_time=now,   # fire immediately on startup
    )

    scheduler.add_job(
        run_upgrade_parts_swarm,
        trigger=IntervalTrigger(hours=settings.parts_update_interval_hours),
        id="upgrade_parts",
        name="Upgrade Parts Swarm",
        replace_existing=True,
        max_instances=1,
        next_run_time=now,   # fire immediately on startup
    )

    scheduler.add_job(
        run_cases_swarm,
        trigger=IntervalTrigger(hours=24),
        id="cases",
        name="Cases Catalogue Swarm",
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
        return await run_flip_opportunities_swarm()
    if swarm_id == "upgrade_parts":
        return await run_upgrade_parts_swarm()
    if swarm_id == "cases":
        return await run_cases_swarm()
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
