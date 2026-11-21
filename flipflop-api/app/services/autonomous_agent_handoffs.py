"""Persistence and dispatch for versioned agent handoff events."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_handoff_event import AgentHandoffEvent
from app.schemas.autonomous_agents import AgentEvent


async def persist_agent_event(db: AsyncSession, event: AgentEvent | dict[str, Any]) -> bool:
    parsed = AgentEvent.model_validate(event)
    values = parsed.model_dump(mode="json")
    values["occurred_at"] = parsed.occurred_at.replace(tzinfo=None)
    statement = insert(AgentHandoffEvent).values(**values).on_conflict_do_nothing(
        index_elements=[AgentHandoffEvent.idempotency_key]
    )
    result = await db.execute(statement)
    return bool(result.rowcount)


async def pending_agent_events(db: AsyncSession, *, event_types: tuple[str, ...], limit: int = 100) -> list[AgentEvent]:
    rows = (await db.execute(select(AgentHandoffEvent).where(
        AgentHandoffEvent.processing_status.in_(("pending", "failed")),
        AgentHandoffEvent.event_type.in_(event_types),
    ).order_by(AgentHandoffEvent.occurred_at).limit(limit))).scalars().all()
    return [AgentEvent(
        event_id=row.event_id, event_type=row.event_type, producer=row.producer,
        occurred_at=row.occurred_at.replace(tzinfo=timezone.utc),
        idempotency_key=row.idempotency_key, correlation_id=row.correlation_id,
        evidence_refs=row.evidence_refs or [], payload=row.payload or {},
    ) for row in rows]


async def run_pending_agent_handoffs() -> dict:
    """Retry durable Playbook handoffs after backend or provider interruptions."""
    handled = 0
    failures = 0
    async with AsyncSessionLocal() as db:
        events = await pending_agent_events(db, event_types=(
            "demand_signal_batch_ready", "component_market_price_changed", "playbook_refresh_requested",
        ), limit=50)
    for event in events:
        try:
            await process_playbook_event(event)
            handled += 1
        except Exception as exc:
            async with AsyncSessionLocal() as db:
                await mark_agent_event(db, event.event_id, status="failed", error=f"{type(exc).__name__}: {exc}")
                await db.commit()
            failures += 1
    return {"ok": failures == 0, "handled": handled, "failed": failures}


async def process_playbook_event(event: AgentEvent) -> AgentEvent:
    """Run Playbook, durably record its completion event, and settle the trigger."""
    from app.services.playbook_management_agent import run_playbook_manager_cycle

    completion = await run_playbook_manager_cycle(event)
    async with AsyncSessionLocal() as db:
        await persist_agent_event(db, completion)
        await mark_agent_event(db, event.event_id, status="completed")
        await db.commit()
    return completion


async def mark_agent_event(db: AsyncSession, event_id: str, *, status: str, error: str | None = None) -> None:
    row = await db.get(AgentHandoffEvent, event_id)
    if row is None:
        return
    row.processing_status = status
    row.processed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    row.error = error
