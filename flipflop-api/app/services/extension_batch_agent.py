"""Debounce completed Extension scan-history rows into one Playbook handoff."""
from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.agent_handoff_event import AgentHandoffEvent
from app.models.gem_radar_scan_run import GemRadarScanRun
from app.schemas.autonomous_agents import AgentEvent
from app.services.autonomous_agent_handoffs import mark_agent_event, persist_agent_event, process_playbook_event


async def run_extension_batch_handoff() -> dict:
    async with AsyncSessionLocal() as db:
        latest = (await db.execute(select(GemRadarScanRun).order_by(GemRadarScanRun.id.desc()).limit(1))).scalars().first()
        if latest is None:
            return {"ok": True, "skipped": "no_extension_scan_history"}
        latest_time = latest.occurred_at.replace(tzinfo=timezone.utc) if latest.occurred_at.tzinfo is None else latest.occurred_at
        if (datetime.now(timezone.utc) - latest_time).total_seconds() < 300:
            return {"ok": True, "skipped": "extension_batch_still_active"}

        events = (await db.execute(select(AgentHandoffEvent).where(
            AgentHandoffEvent.event_type == "playbook_refresh_requested",
            AgentHandoffEvent.producer == "system",
        ).order_by(AgentHandoffEvent.occurred_at.desc()).limit(100))).scalars().all()
        existing = next((row for row in events if isinstance(row.payload, dict)
                         and row.payload.get("trigger") == "extension_batch"), None)
        if existing and existing.processing_status in {"pending", "failed"}:
            event = AgentEvent.model_validate({
                "event_id": existing.event_id, "event_type": existing.event_type, "producer": existing.producer,
                "occurred_at": existing.occurred_at.replace(tzinfo=timezone.utc),
                "idempotency_key": existing.idempotency_key, "correlation_id": existing.correlation_id,
                "evidence_refs": existing.evidence_refs or [], "payload": existing.payload or {},
            })
        else:
            last_id = int(existing.payload.get("last_scan_id", 0)) if existing and isinstance(existing.payload, dict) else 0
            if latest.id <= last_id:
                return {"ok": True, "skipped": "no_new_committed_extension_batch"}
            first_new = (await db.execute(select(GemRadarScanRun).where(
                GemRadarScanRun.id > last_id,
            ).order_by(GemRadarScanRun.id.asc()).limit(1))).scalars().first()
            first_id = first_new.id if first_new else latest.id
            batch_id = f"extension-scan-batch:{first_id}:{latest.id}"
            event = AgentEvent(
                event_id=str(uuid5(NAMESPACE_URL, f"flipflop:{batch_id}")),
                event_type="playbook_refresh_requested", producer="system", occurred_at=datetime.now(timezone.utc),
                idempotency_key=batch_id, correlation_id=batch_id,
                evidence_refs=[f"gem_radar_scan_runs:{first_id}-{latest.id}"],
                payload={"trigger": "extension_batch", "extension_batch_id": batch_id,
                         "first_scan_id": first_id, "last_scan_id": latest.id,
                         "search_terms": [row.search_term for row in (await db.execute(
                             select(GemRadarScanRun).where(GemRadarScanRun.id >= first_id,
                                                           GemRadarScanRun.id <= latest.id)
                         )).scalars().all()]},
            )
            await persist_agent_event(db, event)
            await db.commit()
        try:
            await process_playbook_event(event)
            await mark_agent_event(db, event.event_id, status="completed")
            await db.commit()
            return {"ok": True, "event_id": event.event_id}
        except Exception as exc:
            await mark_agent_event(db, event.event_id, status="failed", error=f"{type(exc).__name__}: {exc}")
            await db.commit()
            raise
