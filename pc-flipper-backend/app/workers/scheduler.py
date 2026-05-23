"""
APScheduler wrapper — manages all swarm cron jobs.
"""
from collections import deque
from datetime import datetime, timezone, timedelta
from time import perf_counter
from typing import Awaitable, Callable
import json
from pathlib import Path
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
from app.services.compliant_market_ingestion import run_compliant_market_ingestion
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
    "retrain_checkpoint_watchdog": deque(maxlen=50),
    "compliant_market_ingestion": deque(maxlen=50),
}
_running_jobs: set[str] = set()
_STATE_FILE = Path(__file__).resolve().parents[2] / "data" / "scheduler_state.json"


def _load_state() -> dict:
    try:
        if not _STATE_FILE.exists():
            return {}
        return json.loads(_STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(state: dict) -> None:
    try:
        _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _STATE_FILE.write_text(json.dumps(state, ensure_ascii=True, indent=2), encoding="utf-8")
    except Exception:
        # Best-effort persistence only; scheduler should still run if this fails.
        pass


def _mark_success(job_id: str, finished_at: datetime) -> None:
    state = _load_state()
    state[job_id] = {"last_success_at": finished_at.isoformat()}
    _save_state(state)


def _next_run_for(job_id: str, interval_minutes: int, now: datetime) -> datetime:
    """
    Return next run time for a periodic job.
    If the last successful run was recent (inside interval), delay startup run
    so we don't rescan immediately after backend restart.
    """
    state = _load_state()
    rec = state.get(job_id) if isinstance(state, dict) else None
    if not isinstance(rec, dict):
        return now
    ts = rec.get("last_success_at")
    if not isinstance(ts, str):
        return now
    try:
        last_success = datetime.fromisoformat(ts)
        if last_success.tzinfo is None:
            last_success = last_success.replace(tzinfo=timezone.utc)
        elapsed = now - last_success.astimezone(timezone.utc)
        interval = timedelta(minutes=max(1, interval_minutes))
        if elapsed < interval:
            return now + (interval - elapsed)
    except Exception:
        return now
    return now


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
        if isinstance(result, dict) and result.get("ok") is False:
            reason = str(result.get("reason") or "not_ready")
            summary = f"Skipped ({reason}, {took_ms}ms)"
            _push_history(job_id, "skipped", started, finished, summary)
        else:
            summary = f"Completed ({took_ms}ms)"
            _push_history(job_id, "success", started, finished, summary)
            _mark_success(job_id, finished)
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
    flip_next = _next_run_for("flip_opportunities", settings.flip_scan_interval_minutes, now)
    upgrade_start = _next_run_for("upgrade_parts", max(1, int(settings.parts_update_interval_hours * 60)), now)
    cases_start = _next_run_for("cases", 24 * 60, now)
    accessories_start = _next_run_for("accessories", 24 * 60, now)
    external_demand_start = _next_run_for("external_demand", 60, now)
    playbook_evolution_start = _next_run_for("playbook_evolution", 60, now)
    autonomous_cycle_start = _next_run_for("autonomous_cycle", 60, now)
    outcome_capture_start = _next_run_for("outcome_capture", 60, now)
    model_retraining_start = _next_run_for("model_retraining", 60, now)
    retrain_watchdog_start = _next_run_for("retrain_checkpoint_watchdog", 60, now)
    compliant_ingestion_start = _next_run_for("compliant_market_ingestion", 60, now)

    scheduler.add_job(
        _run_job_with_history,
        trigger=IntervalTrigger(minutes=settings.flip_scan_interval_minutes),
        id="flip_opportunities",
        name="Flip Opportunities Swarm",
        kwargs={"job_id": "flip_opportunities", "fn": run_flip_opportunities_swarm},
        replace_existing=True,
        max_instances=1,
        next_run_time=flip_next,
    )

    scheduler.add_job(
        _run_job_with_history,
        trigger=IntervalTrigger(hours=settings.parts_update_interval_hours),
        id="upgrade_parts",
        name="Upgrade Parts Swarm",
        kwargs={"job_id": "upgrade_parts", "fn": run_upgrade_parts_swarm},
        replace_existing=True,
        max_instances=1,
        next_run_time=upgrade_start,
    )

    scheduler.add_job(
        _run_job_with_history,
        trigger=IntervalTrigger(hours=24),
        id="cases",
        name="Cases Catalogue Swarm",
        kwargs={"job_id": "cases", "fn": run_cases_swarm},
        replace_existing=True,
        max_instances=1,
        next_run_time=cases_start,
    )

    scheduler.add_job(
        _run_job_with_history,
        trigger=IntervalTrigger(hours=24),
        id="accessories",
        name="Accessories Swarm",
        kwargs={"job_id": "accessories", "fn": run_accessories_swarm},
        replace_existing=True,
        max_instances=1,
        next_run_time=accessories_start,
    )

    scheduler.add_job(
        _run_job_with_history,
        trigger=IntervalTrigger(hours=1),
        id="external_demand",
        name="External Demand Signals",
        kwargs={"job_id": "external_demand", "fn": ingest_external_demand_signals},
        replace_existing=True,
        max_instances=1,
        next_run_time=external_demand_start,
    )

    scheduler.add_job(
        _run_job_with_history,
        trigger=IntervalTrigger(hours=1),
        id="playbook_evolution",
        name="Playbook Evolution",
        kwargs={"job_id": "playbook_evolution", "fn": run_playbook_evolution},
        replace_existing=True,
        max_instances=1,
        next_run_time=playbook_evolution_start,
    )

    scheduler.add_job(
        _run_job_with_history,
        trigger=IntervalTrigger(hours=1),
        id="autonomous_cycle",
        name="Autonomous Cycle",
        kwargs={"job_id": "autonomous_cycle", "fn": run_autonomous_cycle},
        replace_existing=True,
        max_instances=1,
        next_run_time=autonomous_cycle_start,
    )

    scheduler.add_job(
        _run_job_with_history,
        trigger=IntervalTrigger(hours=1),
        id="outcome_capture",
        name="Outcome Capture",
        kwargs={"job_id": "outcome_capture", "fn": capture_outcomes_and_check_retrain},
        replace_existing=True,
        max_instances=1,
        next_run_time=outcome_capture_start,
    )

    scheduler.add_job(
        _run_job_with_history,
        trigger=IntervalTrigger(hours=1),
        id="model_retraining",
        name="Model Retraining",
        kwargs={"job_id": "model_retraining", "fn": run_retraining_if_ready},
        replace_existing=True,
        max_instances=1,
        next_run_time=model_retraining_start,
    )

    scheduler.add_job(
        _run_job_with_history,
        trigger=IntervalTrigger(hours=1),
        id="retrain_checkpoint_watchdog",
        name="Retrain Checkpoint Watchdog",
        kwargs={"job_id": "retrain_checkpoint_watchdog", "fn": check_stale_retrain_checkpoint},
        replace_existing=True,
        max_instances=1,
        next_run_time=retrain_watchdog_start,
    )

    scheduler.add_job(
        _run_job_with_history,
        trigger=IntervalTrigger(hours=1),
        id="compliant_market_ingestion",
        name="Compliant Market Ingestion",
        kwargs={"job_id": "compliant_market_ingestion", "fn": run_compliant_market_ingestion},
        replace_existing=True,
        max_instances=1,
        next_run_time=compliant_ingestion_start,
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
    if swarm_id == "compliant_market_ingestion":
        return await _run_job_with_history("compliant_market_ingestion", run_compliant_market_ingestion)
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
