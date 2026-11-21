"""Demand worker wrapper that turns each completed evidence collection into a durable handoff."""
from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid5

from app.database import AsyncSessionLocal
from app.schemas.autonomous_agents import AgentEvent
from app.services.autonomous_agent_handoffs import mark_agent_event, process_playbook_event, persist_agent_event


async def run_demand_agent_cycle() -> dict:
    from app.services.agent_skill_loader import load_agent_skill
    from app.services.external_demand import ingest_external_demand_signals

    if not load_agent_skill("demand").strip():
        raise RuntimeError("Demand agent skill is missing")
    result = await ingest_external_demand_signals()
    if not result.get("ok"):
        return result
    completed = datetime.now(timezone.utc)
    batch_id = completed.strftime("demand-%Y%m%dT%H")
    event = AgentEvent(
        event_id=str(uuid5(NAMESPACE_URL, f"flipflop:demand:{batch_id}")),
        event_type="demand_signal_batch_ready", producer="demand", occurred_at=completed,
        idempotency_key=f"demand-batch:{batch_id}", correlation_id=batch_id,
        payload={"batch_id": batch_id, "sources": ["google_trends", "reddit", "steam_hwsurvey"],
                 "observation_count": int(result.get("signals", 0)), "completed_at": completed.isoformat(),
                 "not_yet_integrated": ["flipflop_sales", "ebay_sold"],
                 "collection": result},
    )
    async with AsyncSessionLocal() as db:
        await persist_agent_event(db, event)
        await db.commit()
    try:
        await process_playbook_event(event)
    except Exception:
        # Preserve the demand event. The event worker can retry it after a transient failure.
        async with AsyncSessionLocal() as db:
            await mark_agent_event(db, event.event_id, status="failed", error="Playbook handoff failed; queued for retry")
            await db.commit()
        raise
    return {**result, "handoff_event_id": event.event_id}
