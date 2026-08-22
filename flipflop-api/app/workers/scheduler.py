"""
APScheduler wrapper — manages all swarm cron jobs.
"""
import asyncio
from collections import deque
from datetime import datetime, timezone, timedelta
from time import perf_counter
from typing import Awaitable, Callable
import json
from pathlib import Path
from functools import partial
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from app.config import get_settings
# Cases swarm: feeds PC case data for 3D model sourcing workflow
# Other swarms (flip_opportunities, upgrade_parts, accessories) are handled by FlipFlopXtension
from app.swarms.cases import run_cases_swarm
from app.services.external_demand import ingest_external_demand_signals
from app.services.playbook_evolution import run_playbook_evolution
from app.services.autonomous_loop import run_autonomous_cycle
from app.services.outcome_capture import capture_outcomes_and_check_retrain
from app.services.retraining_pipeline import run_retraining_if_ready
from app.services.alerts import emit_alert, check_stale_retrain_checkpoint
from app.services.compliant_market_ingestion import run_compliant_market_ingestion
from app.services.benchmark_refresh_job import run_benchmark_refresh
from app.services.ram_watcher import run_ram_watcher
from app.services.price_refresh import run_price_refresh
from app.services.catalogue_service import run_catalogue_pipeline_job, run_catalogue_digest_job
from app.workers.recreate_cycle import run_deferred_publish_job, run_recreate_cycle_job
from app.workers.manual_build_scheduler import run_deferred_manual_build_publish_job
from app.workers.markdown_event import run_markdown_event_scan_job, run_manual_build_markdown_event_scan_job
from app.workers.offer_poll import run_offer_poll_job, run_send_to_watchers_job
from app.workers.manual_build_lifecycle import (
    run_manual_build_offer_poll_job,
    run_manual_build_send_to_watchers_job,
    run_manual_build_recreate_cycle_job,
)
from app.workers.message_poll import run_message_poll_job
from app.services.ai_build_generator import generate_ai_builds
from app.services.email_monitor import EmailMonitor
from app.services.ebay_sales_tracker import get_tracker as get_ebay_sales_tracker
from app.database import get_db
import structlog

log = structlog.get_logger(__name__)
settings = get_settings()

_scheduler: AsyncIOScheduler | None = None
_job_history: dict[str, deque[dict]] = {
    "cases": deque(maxlen=50),
    "external_demand": deque(maxlen=50),
    "playbook_evolution": deque(maxlen=50),
    "autonomous": deque(maxlen=50),
    "outcome_capture": deque(maxlen=50),
    "model_retraining": deque(maxlen=50),
    "retrain_checkpoint_watchdog": deque(maxlen=50),
    "compliant_market_ingestion": deque(maxlen=50),
    "benchmark_refresh_daily": deque(maxlen=50),
    "benchmark_refresh_weekly": deque(maxlen=50),
    "price_refresh": deque(maxlen=50),
    "ram_watcher": deque(maxlen=50),
    "catalogue_pipeline": deque(maxlen=50),
    "catalogue_digest": deque(maxlen=50),
    "deferred_publish": deque(maxlen=50),
    "manual_build_deferred_publish": deque(maxlen=50),
    "recreate_cycle": deque(maxlen=50),
    "manual_build_recreate_cycle": deque(maxlen=50),
    "markdown_event_scan": deque(maxlen=50),
    "manual_build_markdown_event_scan": deque(maxlen=50),
    "offer_poll": deque(maxlen=50),
    "manual_build_offer_poll": deque(maxlen=50),
    "send_to_watchers": deque(maxlen=50),
    "manual_build_send_to_watchers": deque(maxlen=50),
    "message_poll": deque(maxlen=50),
    "ai_build_generator": deque(maxlen=50),
    "email_monitor": deque(maxlen=50),
    "ebay_sales_tracker": deque(maxlen=50),
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
    except Exception as exc:
        # Best-effort persistence only; scheduler should still run if this fails.
        log.warning("scheduler.state_save_failed", error=str(exc))


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


def _last_success_at(job_id: str) -> datetime | None:
    state = _load_state()
    rec = state.get(job_id) if isinstance(state, dict) else None
    if not isinstance(rec, dict):
        return None
    ts = rec.get("last_success_at")
    if not isinstance(ts, str):
        return None
    try:
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _is_due(job_id: str, interval_minutes: int) -> bool:
    last = _last_success_at(job_id)
    if last is None:
        return True
    elapsed = datetime.now(timezone.utc) - last
    return elapsed >= timedelta(minutes=max(1, int(interval_minutes)))


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
        # Job is already running — don't push a new history entry; the existing
        # "running" entry already reflects the true state correctly.
        log.info("job.deduplicated.already_running", job_id=job_id)
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
        except Exception as alert_exc:
            log.warning("job.failed.alert_emit_error", job_id=job_id, error=str(alert_exc))
        raise
    finally:
        _running_jobs.discard(job_id)


async def run_email_monitor() -> dict:
    """Wrapper for email monitor job — handles database session creation."""
    if not settings.email_monitor_enabled:
        return {"ok": False, "reason": "email_monitor_disabled"}

    try:
        async for db in get_db():
            monitor = EmailMonitor()
            await monitor.run(db)
        return {"ok": True}
    except Exception as e:
        log.error("email_monitor.run_failed", error=str(e))
        raise


async def run_ebay_sales_tracker() -> dict:
    """Wrapper for the eBay sales poll job — checks every eBay-listed flip
    against eBay's order API and marks it sold when a paid order appears."""
    if not settings.ebay_reselling_enabled:
        return {"ok": False, "reason": "ebay_reselling_disabled"}

    tracker = get_ebay_sales_tracker()
    return await tracker.poll_sales()


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
    return _scheduler


def start_scheduler():
    scheduler = get_scheduler()

    now = datetime.now(timezone.utc)
    # DISABLED: Backend scraper swarms replaced by FlipFlopXtension
    # flip_next = _next_run_for("flip_opportunities", settings.flip_scan_interval_minutes, now)
    # upgrade_start = now
    # cases_start = now
    # accessories_start = now
    # Keep startup deterministic: external_demand + playbook_evolution are handled
    # by run_startup_bootstrap(). Delay their scheduled cron jobs (and other hourly
    # analysis jobs) to avoid duplicate/overlapping execution at app boot.
    external_demand_start = now + timedelta(hours=1)
    playbook_evolution_start = now + timedelta(hours=1)
    autonomous_start = now + timedelta(hours=1)
    outcome_capture_start = now + timedelta(hours=1)
    model_retraining_start = now + timedelta(hours=1)
    retrain_watchdog_start = now + timedelta(hours=1)
    compliant_ingestion_start = now + timedelta(hours=1)

    # DISABLED: Scraping is handled entirely by FlipFlopXtension (browser extension).
    # Backend swarms are legacy code — data sourcing was moved to the extension.
    # Keeping these disabled to avoid duplicate scraping.
    # Uncomment below if you want to re-enable backend-side scraping.

    # scheduler.add_job(
    #     _run_job_with_history,
    #     trigger=IntervalTrigger(minutes=settings.flip_scan_interval_minutes),
    #     id="flip_opportunities",
    #     name="Flip Opportunities Swarm",
    #     kwargs={"job_id": "flip_opportunities", "fn": partial(run_flip_opportunities_swarm, "main")},
    #     replace_existing=True,
    #     max_instances=1,
    #     next_run_time=flip_next,
    # )
    #
    # scheduler.add_job(
    #     _run_job_with_history,
    #     trigger=IntervalTrigger(minutes=settings.flip_scan_interval_minutes),
    #     id="upgrade_parts",
    #     name="Upgrade Parts Swarm",
    #     kwargs={"job_id": "upgrade_parts", "fn": partial(run_upgrade_parts_swarm, "main")},
    #     replace_existing=True,
    #     max_instances=1,
    #     next_run_time=upgrade_start,
    # )
    #
    scheduler.add_job(
        _run_job_with_history,
        trigger=IntervalTrigger(hours=24),
        id="cases",
        name="Cases Catalogue Swarm",
        kwargs={"job_id": "cases", "fn": partial(run_cases_swarm, "main")},
        replace_existing=True,
        max_instances=1,
        next_run_time=now + timedelta(hours=24),  # Run 24 hours from now, not immediately
    )
    #
    # scheduler.add_job(
    #     _run_job_with_history,
    #     trigger=IntervalTrigger(minutes=settings.flip_scan_interval_minutes),
    #     id="accessories",
    #     name="Accessories Swarm",
    #     kwargs={"job_id": "accessories", "fn": partial(run_accessories_swarm, "main")},
    #     replace_existing=True,
    #     max_instances=1,
    #     next_run_time=accessories_start,
    # )

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
        id="autonomous",
        name="Autonomous",
        kwargs={"job_id": "autonomous", "fn": run_autonomous_cycle},
        replace_existing=True,
        max_instances=1,
        next_run_time=autonomous_start,
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

    benchmark_daily_start = now + timedelta(hours=2)
    benchmark_weekly_start = now + timedelta(hours=3)
    price_refresh_start = now + timedelta(minutes=5)  # first run shortly after startup

    scheduler.add_job(
        _run_job_with_history,
        trigger=IntervalTrigger(hours=24),
        id="benchmark_refresh_daily",
        name="Benchmark Refresh (Daily)",
        kwargs={"job_id": "benchmark_refresh_daily", "fn": partial(run_benchmark_refresh, "daily")},
        replace_existing=True,
        max_instances=1,
        next_run_time=benchmark_daily_start,
    )

    scheduler.add_job(
        _run_job_with_history,
        trigger=IntervalTrigger(days=7),
        id="benchmark_refresh_weekly",
        name="Benchmark Refresh (Weekly)",
        kwargs={"job_id": "benchmark_refresh_weekly", "fn": partial(run_benchmark_refresh, "weekly")},
        replace_existing=True,
        max_instances=1,
        next_run_time=benchmark_weekly_start,
    )

    scheduler.add_job(
        _run_job_with_history,
        trigger=IntervalTrigger(hours=24),
        id="price_refresh",
        name="Component Price Refresh (eBay UK Sold)",
        kwargs={"job_id": "price_refresh", "fn": run_price_refresh},
        replace_existing=True,
        max_instances=1,
        next_run_time=price_refresh_start,
    )

    scheduler.add_job(
        _run_job_with_history,
        trigger=IntervalTrigger(minutes=15),
        id="ram_watcher",
        name="RAM Price Watcher",
        kwargs={"job_id": "ram_watcher", "fn": run_ram_watcher},
        replace_existing=True,
        max_instances=1,
        next_run_time=now,
    )

    scheduler.add_job(
        _run_job_with_history,
        trigger=IntervalTrigger(hours=1),
        id="catalogue_pipeline",
        name="Catalogue Pipeline (auto-publish, freshness, prices)",
        kwargs={"job_id": "catalogue_pipeline", "fn": run_catalogue_pipeline_job},
        replace_existing=True,
        max_instances=1,
        next_run_time=now + timedelta(hours=1),
    )
    scheduler.add_job(
        _run_job_with_history,
        trigger="cron",
        hour=8,
        minute=0,
        id="catalogue_digest",
        name="Catalogue Review Digest",
        kwargs={"job_id": "catalogue_digest", "fn": run_catalogue_digest_job},
        replace_existing=True,
        max_instances=1,
    )

    # Playbook rows 1, 2, 3, 5, 6, 9, 36, 46 — freshness/recreate cycle
    scheduler.add_job(
        _run_job_with_history,
        trigger=IntervalTrigger(minutes=15),
        id="deferred_publish",
        name="Deferred Listing Publish",
        kwargs={"job_id": "deferred_publish", "fn": run_deferred_publish_job},
        replace_existing=True,
        max_instances=1,
        next_run_time=now,
    )
    scheduler.add_job(
        _run_job_with_history,
        trigger=IntervalTrigger(minutes=15),
        id="manual_build_deferred_publish",
        name="Manual Build Deferred Listing Publish",
        kwargs={"job_id": "manual_build_deferred_publish", "fn": run_deferred_manual_build_publish_job},
        replace_existing=True,
        max_instances=1,
        next_run_time=now,
    )
    scheduler.add_job(
        _run_job_with_history,
        trigger=IntervalTrigger(hours=1),
        id="recreate_cycle",
        name="Relist/Recreate Cycle",
        kwargs={"job_id": "recreate_cycle", "fn": run_recreate_cycle_job},
        replace_existing=True,
        max_instances=1,
        next_run_time=now,
    )
    scheduler.add_job(
        _run_job_with_history,
        trigger=IntervalTrigger(hours=24),
        id="markdown_event_scan",
        name="Markdown Event Candidate Scan",
        kwargs={"job_id": "markdown_event_scan", "fn": run_markdown_event_scan_job},
        replace_existing=True,
        max_instances=1,
        next_run_time=now + timedelta(hours=4),
    )
    scheduler.add_job(
        _run_job_with_history,
        trigger=IntervalTrigger(hours=1),
        id="manual_build_recreate_cycle",
        name="Manual Build Relist/Recreate Cycle",
        kwargs={"job_id": "manual_build_recreate_cycle", "fn": run_manual_build_recreate_cycle_job},
        replace_existing=True,
        max_instances=1,
        next_run_time=now,
    )
    scheduler.add_job(
        _run_job_with_history,
        trigger=IntervalTrigger(hours=24),
        id="manual_build_markdown_event_scan",
        name="Manual Build Markdown Event Candidate Scan",
        kwargs={"job_id": "manual_build_markdown_event_scan", "fn": run_manual_build_markdown_event_scan_job},
        replace_existing=True,
        max_instances=1,
        next_run_time=now + timedelta(hours=4),
    )

    # Playbook rows 8, 21, 45, 47 — offer/message polling. Every job here
    # no-ops (logged, cheap) until an eBay refresh token is configured.
    scheduler.add_job(
        _run_job_with_history,
        trigger=IntervalTrigger(minutes=30),
        id="offer_poll",
        name="Best-Offer Poll",
        kwargs={"job_id": "offer_poll", "fn": run_offer_poll_job},
        replace_existing=True,
        max_instances=1,
        next_run_time=now,
    )
    scheduler.add_job(
        _run_job_with_history,
        trigger=IntervalTrigger(hours=12),
        id="send_to_watchers",
        name="Send Offers to Watchers",
        kwargs={"job_id": "send_to_watchers", "fn": run_send_to_watchers_job},
        replace_existing=True,
        max_instances=1,
        next_run_time=now,
    )
    scheduler.add_job(
        _run_job_with_history,
        trigger=IntervalTrigger(minutes=30),
        id="manual_build_offer_poll",
        name="Manual Build Best-Offer Poll",
        kwargs={"job_id": "manual_build_offer_poll", "fn": run_manual_build_offer_poll_job},
        replace_existing=True,
        max_instances=1,
        next_run_time=now,
    )
    scheduler.add_job(
        _run_job_with_history,
        trigger=IntervalTrigger(hours=12),
        id="manual_build_send_to_watchers",
        name="Manual Build Send Offers to Watchers",
        kwargs={"job_id": "manual_build_send_to_watchers", "fn": run_manual_build_send_to_watchers_job},
        replace_existing=True,
        max_instances=1,
        next_run_time=now,
    )
    scheduler.add_job(
        _run_job_with_history,
        trigger=IntervalTrigger(minutes=30),
        id="message_poll",
        name="Buyer Message Response-Time Alert",
        kwargs={"job_id": "message_poll", "fn": run_message_poll_job},
        replace_existing=True,
        max_instances=1,
        next_run_time=now,
    )
    scheduler.add_job(
        _run_job_with_history,
        # Tied to the same configured refresh period as the sourcing swarms
        # (settings.flip_scan_interval_minutes) rather than a fixed interval,
        # so tightening/loosening that one setting also speeds up/slows down
        # how often new AI builds get generated.
        trigger=IntervalTrigger(minutes=settings.flip_scan_interval_minutes),
        id="ai_build_generator",
        name="AI-Generated Builds (Gem/Super Gem combos, eBay-validated)",
        kwargs={"job_id": "ai_build_generator", "fn": generate_ai_builds},
        replace_existing=True,
        max_instances=1,
        next_run_time=now + timedelta(minutes=10),
    )

    if settings.email_monitor_enabled:
        scheduler.add_job(
            _run_job_with_history,
            trigger=IntervalTrigger(seconds=settings.email_monitor_interval_seconds),
            id="email_monitor",
            name="Email Monitor (receipts + sales)",
            kwargs={"job_id": "email_monitor", "fn": run_email_monitor},
            replace_existing=True,
            max_instances=1,
            next_run_time=now + timedelta(minutes=1),
        )

    if settings.ebay_reselling_enabled:
        scheduler.add_job(
            _run_job_with_history,
            trigger=IntervalTrigger(seconds=settings.ebay_sales_poll_interval_seconds),
            id="ebay_sales_tracker",
            name="eBay Sales Tracker (order API poll)",
            kwargs={"job_id": "ebay_sales_tracker", "fn": run_ebay_sales_tracker},
            replace_existing=True,
            max_instances=1,
            next_run_time=now + timedelta(minutes=2),
        )

    scheduler.start()
    log.info("scheduler.started", jobs=len(scheduler.get_jobs()))


async def run_startup_bootstrap() -> dict:
    """
    One-shot startup bootstrap (data sourcing disabled — handled by FlipFlopXtension):
      1) Skip flip opportunities scraper (backend swarms disabled, extension handles sourcing)
      2) Pull external demand (lightweight)
      3) Run playbook evolution
    Swarms run sequentially to avoid database locks.
    """
    log.info("startup_bootstrap.start")

    # DISABLED: Flip opportunities scraper replaced by FlipFlopXtension
    # flip_opp = None
    # try:
    #     flip_opp = await _run_job_with_history("flip_opportunities", partial(run_flip_opportunities_swarm, "startup"))
    #     log.info("startup_bootstrap.flip_opportunities_done", status=flip_opp.get("ok"), listings=flip_opp.get("listings_found", 0))
    # except Exception as e:
    #     log.error("startup_bootstrap.flip_opportunities_failed", error=str(e))
    #     flip_opp = {"ok": False, "error": str(e)}

    # Wait before next job to ensure database is unlocked
    # await asyncio.sleep(2)
    flip_opp = None

    demand = None
    try:
        demand = await _run_job_with_history("external_demand", ingest_external_demand_signals)
        log.info("startup_bootstrap.external_demand_done", status=demand.get("ok"))
    except Exception as e:
        log.error("startup_bootstrap.external_demand_failed", error=str(e))
        demand = {"ok": False, "error": str(e)}

    evolution = None
    try:
        evolution = await _run_job_with_history("playbook_evolution", run_playbook_evolution)
        log.info("startup_bootstrap.playbook_evolution_done", status=evolution.get("ok"))
    except Exception as e:
        log.error("startup_bootstrap.playbook_evolution_failed", error=str(e))
        evolution = {"ok": False, "error": str(e)}

    out = {
        "ok": True,
        "steps": {
            "flip_opportunities": flip_opp,
            "external_demand": demand,
            "playbook_evolution": evolution
        }
    }
    log.info("startup_bootstrap.done", summary=out)
    return out


def stop_scheduler():
    scheduler = get_scheduler()
    if scheduler.running:
        scheduler.shutdown()
        log.info("scheduler.stopped")


async def trigger_swarm(swarm_id: str) -> dict:
    """Manually trigger a swarm by ID."""
    # Cases swarm re-enabled (uses direct httpx method)
    # flip_opportunities, upgrade_parts, accessories still disabled
    if swarm_id in ("flip_opportunities", "upgrade_parts", "accessories"):
        return {"ok": False, "reason": "Backend scrapers disabled — data sourcing handled by FlipFlopXtension"}
    if swarm_id == "cases":
        return await _run_job_with_history("cases", partial(run_cases_swarm, "main"))
    if swarm_id == "external_demand":
        return await _run_job_with_history("external_demand", ingest_external_demand_signals)
    if swarm_id == "playbook_evolution":
        return await _run_job_with_history("playbook_evolution", run_playbook_evolution)
    if swarm_id == "autonomous":
        return await _run_job_with_history("autonomous", run_autonomous_cycle)
    if swarm_id == "outcome_capture":
        return await _run_job_with_history("outcome_capture", capture_outcomes_and_check_retrain)
    if swarm_id == "model_retraining":
        return await _run_job_with_history("model_retraining", run_retraining_if_ready)
    if swarm_id == "compliant_market_ingestion":
        return await _run_job_with_history("compliant_market_ingestion", run_compliant_market_ingestion)
    if swarm_id == "benchmark_refresh_daily":
        return await _run_job_with_history("benchmark_refresh_daily", partial(run_benchmark_refresh, "daily"))
    if swarm_id == "benchmark_refresh_weekly":
        return await _run_job_with_history("benchmark_refresh_weekly", partial(run_benchmark_refresh, "weekly"))
    if swarm_id == "price_refresh":
        return await _run_job_with_history("price_refresh", run_price_refresh)
    if swarm_id == "ram_watcher":
        return await _run_job_with_history("ram_watcher", run_ram_watcher)
    if swarm_id == "catalogue_pipeline":
        return await _run_job_with_history("catalogue_pipeline", run_catalogue_pipeline_job)
    if swarm_id == "catalogue_digest":
        return await _run_job_with_history("catalogue_digest", run_catalogue_digest_job)
    if swarm_id == "ai_build_generator":
        return await _run_job_with_history("ai_build_generator", generate_ai_builds)
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
