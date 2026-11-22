"""Durable, provider-free processor for completed GEM Radar sweep QA events."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import and_, or_, select

from app.database import AsyncSessionLocal
from app.models.gem_radar_build_qa_event import GemRadarBuildQAEvent
from app.services.gem_build_qa import build_sweep_qa_snapshot

log = structlog.get_logger(__name__)
_STALE_PROCESSING_AFTER = timedelta(minutes=10)
_MAX_ATTEMPTS = 5


def _sheet_sync_status(states: list[str]) -> str:
    if "write_failed" in states:
        return "write_failed"
    if any(state in {"written", "already_written"} for state in states):
        return "written"
    if "needs_credentials" in states:
        return "needs_credentials"
    if "blocked_unverified_or_incompatible" in states:
        return "blocked_unverified_or_incompatible"
    return "disabled"


def _sheet_retry_status(final_sync: str, attempts: int) -> str:
    if final_sync != "write_failed":
        return "completed"
    return "queued" if attempts < _MAX_ATTEMPTS else "failed"


async def enqueue_completed_sweep_qa(db, *, environment: str, requested_at) -> str | None:
    """Persist one idempotent QA event in the completed-sweep transaction."""
    if requested_at is None:
        return None
    completed_at = requested_at
    if completed_at.tzinfo is None:
        completed_at = completed_at.replace(tzinfo=timezone.utc)
    run_id = completed_at.astimezone(timezone.utc).isoformat()
    existing = (await db.execute(select(GemRadarBuildQAEvent).where(
        GemRadarBuildQAEvent.environment == environment,
        GemRadarBuildQAEvent.sweep_run_id == run_id,
    ))).scalar_one_or_none()
    if existing is None:
        db.add(GemRadarBuildQAEvent(environment=environment, sweep_run_id=run_id,
            completed_at=completed_at, status="queued", attempts=0,
            sheet_sync_status="disabled"))
        await db.flush()
    return run_id


async def process_pending_gem_build_qa_events(limit: int = 1) -> dict:
    """Build deterministic snapshots and optionally publish them from DEV only."""
    from app.services.gem_build_qa_sheets import publish_snapshot
    claimed: list[tuple[int, str, str, object, dict | None]] = []
    now = datetime.now(timezone.utc)
    stale_before = now - _STALE_PROCESSING_AFTER
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(GemRadarBuildQAEvent).where(
            or_(
                GemRadarBuildQAEvent.status == "queued",
                and_(GemRadarBuildQAEvent.status == "processing",
                     or_(GemRadarBuildQAEvent.processing_started_at.is_(None),
                         GemRadarBuildQAEvent.processing_started_at < stale_before)),
            )
        ).order_by(GemRadarBuildQAEvent.created_at, GemRadarBuildQAEvent.id)
         .with_for_update(skip_locked=True).limit(limit))).scalars().all()
        for row in rows:
            if row.status == "processing" and row.attempts >= _MAX_ATTEMPTS:
                row.status = "failed"
                row.processing_started_at = None
                row.sheet_sync_status = "calculation_failed"
                continue
            row.status = "processing"
            row.attempts += 1
            row.processing_started_at = now
            retry_payload = row.payload if row.sheet_sync_status == "write_failed" else None
            claimed.append((row.id, row.environment, row.sweep_run_id, row.completed_at, retry_payload))
        await db.commit()

    processed = 0
    for event_id, environment, run_id, completed_at, retry_payload in claimed:
        try:
            if retry_payload is not None:
                snapshot = retry_payload
            else:
                async with AsyncSessionLocal() as db:
                    snapshot = await build_sweep_qa_snapshot(db, environment=environment,
                        sweep_run_id=run_id, completed_at=completed_at)
                # Persist calculation before any optional network write.
                async with AsyncSessionLocal() as db:
                    event = await db.get(GemRadarBuildQAEvent, event_id, with_for_update=True)
                    if event is None or event.status != "processing":
                        continue
                    event.payload = snapshot
                    await db.commit()

            sync_states = []
            for platform_snapshot in snapshot.values():
                try:
                    state = await asyncio.to_thread(publish_snapshot, platform_snapshot)
                    sync_states.append(state.get("status", "unknown"))
                except Exception as error:
                    log.warning("gem_build_qa.sheets_sync_failed", event_id=event_id,
                                error_type=type(error).__name__)
                    sync_states.append("write_failed")
            final_sync = _sheet_sync_status(sync_states)
            async with AsyncSessionLocal() as db:
                event = await db.get(GemRadarBuildQAEvent, event_id, with_for_update=True)
                if event is not None:
                    # Retry partial Sheets failures with the persisted snapshot.
                    # Successful tabs deduplicate by sweep run ID on retry.
                    event.status = _sheet_retry_status(final_sync, event.attempts)
                    event.processing_started_at = None
                    event.sheet_sync_status = final_sync
                    await db.commit()
            if final_sync != "write_failed":
                processed += 1
            log.info("gem_build_qa.completed", event_id=event_id, environment=environment,
                     sweep_run_id=run_id, sheet_sync_status=final_sync,
                     am4_status=snapshot.get("AM4", {}).get("status"),
                     am5_status=snapshot.get("AM5", {}).get("status"))
        except Exception as error:
            async with AsyncSessionLocal() as db:
                event = await db.get(GemRadarBuildQAEvent, event_id, with_for_update=True)
                if event is not None:
                    event.status = "queued" if event.attempts < _MAX_ATTEMPTS else "failed"
                    event.processing_started_at = None
                    event.sheet_sync_status = "calculation_failed"
                    event.sheet_sync_error = type(error).__name__[:200]
                    await db.commit()
            log.warning("gem_build_qa.calculation_failed", event_id=event_id,
                        error_type=type(error).__name__)
    return {"processed": processed, "claimed": len(claimed)}
