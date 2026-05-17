"""
APScheduler wrapper — manages all swarm cron jobs.
"""
from collections import deque
from datetime import datetime, timezone, timedelta
from time import perf_counter
from typing import Awaitable, Callable
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from app.config import get_settings
from app.swarms.flip_opportunities import run_flip_opportunities_swarm
from app.swarms.upgrade_parts import run_upgrade_parts_swarm
from app.swarms.cases import run_cases_swarm
from app.swarms.accessories import run_accessories_swarm
from app.services.external_demand import ingest_external_demand_signals
from app.services.playbook_evolution import run_playbook_evolution
from app.services.autonomous_loop import run_autonomous_cycle
from app.services.outcome_capture import capture_outcomes_and_check_retrain
from app.services.retraining_pipeline import run_retraining_if_ready
from app.services.alerts import emit_alert, check_stale_retrain_checkpoint
import structlog

log = structlog.get_logger(__name__)
settings = get_settings()

_scheduler: AsyncIOScheduler | None = None
_job_history: dict[str, deque[dict]] = {
    "flip_opportunities": deque(maxlen=50),
    "upgrade_parts": deque(maxlen=50),
    "cases": deque(maxlen=50),
    "accessories": deque(maxlen=50),
    "external_demand": deque(maxlen=50),
    "playbook_evolution": deque(maxlen=50),
    "autonomous_cycle": deque(maxlen=50),
    "outcome_capture": deque(maxlen=50),
    "model_retraining": deque(maxlen=50),
}
_running_jobs: set[str] = set()


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
    if job_id in _running_jobs:
        now = datetime.now(timezone.utc)
        _push_history(job_id, "skipped", now, now, "Skipped: previous run still in progress")
        log.warning("job.skipped.already_running", job_id=job_id)
        return {"ok": False, "skipped": True, "reason": "already_running"}

    _running_jobs.add(job_id)
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
        try:
            await emit_alert(
                code="job_failed",
                source=job_id,
                severity="critical",
                message=f"Scheduled job '{job_id}' failed: {exc}",
            )
        except Exception:
            pass
        raise
    finally:
        _running_jobs.discard(job_id)


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
    return _scheduler


def start_scheduler():
    scheduler = get_scheduler()

    now = datetime.now(timezone.utc)
    flip_now = now
    upgrade_start = now + timedelta(minutes=5)
    cases_start = now + timedelta(minutes=10)
    accessories_start = now + timedelta(minutes=15)
    external_demand_start = now + timedelta(minutes=20)
    playbook_evolution_start = now + timedelta(minutes=25)
    autonomous_cycle_start = now + timedelta(minutes=30)
    outcome_capture_start = now + timedelta(minutes=35)
    model_retraining_start = now + timedelta(minutes=40)

    scheduler.add_job(
        _run_job_with_history,
        trigger=IntervalTrigger(minutes=settings.flip_scan_interval_minutes),
        id="flip_opportunities",
        name="Flip Opportunities Swarm",
        kwargs={"job_id": "flip_opportunities", "fn": run_flip_opportunities_swarm},
        replace_existing=True,
        max_instances=1,
        next_run_time=flip_now,   # primary sourcing starts immediately
    )

    scheduler.add_job(
        _run_job_with_history,
        trigger=IntervalTrigger(hours=settings.parts_update_interval_hours),
        id="upgrade_parts",
        name="Upgrade Parts Swarm",
        kwargs={"job_id": "upgrade_parts", "fn": run_upgrade_parts_swarm},
        replace_existing=True,
        max_instances=1,
        next_run_time=upgrade_start,   # stagger writes to avoid SQLite contention
    )

    scheduler.add_job(
        _run_job_with_history,
        trigger=IntervalTrigger(hours=24),
        id="cases",
        name="Cases Catalogue Swarm",
        kwargs={"job_id": "cases", "fn": run_cases_swarm},
        replace_existing=True,
        max_instances=1,
        next_run_time=cases_start,   # stagger writes to avoid SQLite contention
    )

    scheduler.add_job(
        _run_job_with_history,
        trigger=IntervalTrigger(hours=24),
        id="accessories",
        name="Accessories Swarm",
        kwargs={"job_id": "accessories", "fn": run_accessories_swarm},
        replace_existing=True,
        max_instances=1,
        next_run_time=accessories_start,   # stagger writes to avoid SQLite contention
    )

    scheduler.add_job(
        _run_job_with_history,
        trigger=IntervalTrigger(hours=2),
        id="external_demand",
        name="External Demand Signals",
        kwargs={"job_id": "external_demand", "fn": ingest_external_demand_signals},
        replace_existing=True,
        max_instances=1,
        next_run_time=external_demand_start,
    )

    scheduler.add_job(
        _run_job_with_history,
        trigger=IntervalTrigger(hours=24),
        id="playbook_evolution",
        name="Playbook Evolution",
        kwargs={"job_id": "playbook_evolution", "fn": run_playbook_evolution},
        replace_existing=True,
        max_instances=1,
        next_run_time=playbook_evolution_start,
    )

    scheduler.add_job(
        _run_job_with_history,
        trigger=IntervalTrigger(hours=6),
        id="autonomous_cycle",
        name="Autonomous Cycle",
        kwargs={"job_id": "autonomous_cycle", "fn": run_autonomous_cycle},
        replace_existing=True,
        max_instances=1,
        next_run_time=autonomous_cycle_start,
    )

    scheduler.add_job(
        _run_job_with_history,
        trigger=IntervalTrigger(hours=6),
        id="outcome_capture",
        name="Outcome Capture",
        kwargs={"job_id": "outcome_capture", "fn": capture_outcomes_and_check_retrain},
        replace_existing=True,
        max_instances=1,
        next_run_time=outcome_capture_start,
    )

    scheduler.add_job(
        _run_job_with_history,
        trigger=IntervalTrigger(hours=6),
        id="model_retraining",
        name="Model Retraining",
        kwargs={"job_id": "model_retraining", "fn": run_retraining_if_ready},
        replace_existing=True,
        max_instances=1,
        next_run_time=model_retraining_start,
    )

    scheduler.add_job(
        check_stale_retrain_checkpoint,
        trigger=IntervalTrigger(hours=6),
        id="retrain_checkpoint_watchdog",
        name="Retrain Checkpoint Watchdog",
        replace_existing=True,
        max_instances=1,
        next_run_time=model_retraining_start,
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
    if swarm_id == "external_demand":
        return await _run_job_with_history("external_demand", ingest_external_demand_signals)
    if swarm_id == "playbook_evolution":
        return await _run_job_with_history("playbook_evolution", run_playbook_evolution)
    if swarm_id == "autonomous_cycle":
        return await _run_job_with_history("autonomous_cycle", run_autonomous_cycle)
    if swarm_id == "outcome_capture":
        return await _run_job_with_history("outcome_capture", capture_outcomes_and_check_retrain)
    if swarm_id == "model_retraining":
        return await _run_job_with_history("model_retraining", run_retraining_if_ready)
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
