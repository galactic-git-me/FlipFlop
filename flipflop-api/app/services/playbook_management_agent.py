"""Event adapter for autonomous, policy-bounded Playbook maintenance.

The caller must invoke this only after the source transaction (in particular an
Extension capture batch) has committed. Selection, compatibility, economics,
price movement limits and publication remain owned by ``playbook_service`` and
its existing deterministic policy gates.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Any
from uuid import NAMESPACE_URL, uuid5
from sqlalchemy import text


PLAYBOOK_MANAGER_STALE_AFTER = timedelta(minutes=5)
PLAYBOOK_MANAGER_HEARTBEAT_SECONDS = 15


class PlaybookRefreshInProgress(RuntimeError):
    """A duplicate handoff must remain unsettled while its refresh is active."""


def _manager_run_is_fresh(run: Any, now: datetime) -> bool:
    if run.status not in {"queued", "running"}:
        return False
    last_progress = run.heartbeat_at or run.started_at
    return bool(last_progress and now - last_progress <= PLAYBOOK_MANAGER_STALE_AFTER)


def _event_dump(event: Any) -> dict[str, Any]:
    if hasattr(event, "model_dump"):
        value = event.model_dump(mode="json")
    elif isinstance(event, dict):
        value = dict(event)
    else:
        raise TypeError("Playbook agent requires a validated AgentEvent")
    if not isinstance(value, dict) or not value.get("event_id") or not value.get("idempotency_key"):
        raise ValueError("AgentEvent must include event_id and idempotency_key")
    return value


def _demand_fingerprint(event: dict[str, Any]) -> str:
    payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
    refs = payload.get("demand_event_ids") or []
    if event.get("event_type") == "demand_signal_batch_ready":
        refs = [*refs, str(event.get("event_id", "")), str(payload.get("batch_id", ""))]
    if not isinstance(refs, list) or any(not isinstance(item, str) for item in refs):
        raise ValueError("demand_event_ids must be a list of strings")
    return sha256("\n".join(sorted(refs)).encode("utf-8")).hexdigest()


async def run_playbook_manager_cycle(event: Any):
    """Refresh proposals and eligible live cells for one committed source event.

    A deterministic UUID derived from the shared event idempotency key is used
    in the existing durable ``PlaybookRefreshRun`` table. No new schema or
    parallel publication path is introduced.
    """
    from app.schemas.autonomous_agents import AgentEvent
    from app.services.agent_skill_loader import load_agent_skill
    from app.database import AsyncSessionLocal
    from app.models.playbook_refresh_run import PlaybookRefreshRun
    from app.services.playbook_service import refresh_playbooks, _utcnow
    incoming = _event_dump(event)
    normalized = AgentEvent.model_validate(incoming)
    event_type = normalized.event_type
    accepted = {
        "demand_signal_batch_ready",
        "component_market_price_changed",
        "playbook_refresh_requested",
    }
    if event_type not in accepted:
        raise ValueError(f"Unsupported Playbook manager trigger: {event_type}")

    skill = load_agent_skill("playbook")
    if hasattr(skill, "__await__"):
        skill = await skill
    skill_text = skill if isinstance(skill, str) else getattr(skill, "content", None)
    if not isinstance(skill_text, str) or not skill_text.strip():
        raise RuntimeError("The Playbook agent skill is missing or empty; refusing live maintenance")

    demand_fingerprint = _demand_fingerprint(incoming)
    job_id = str(uuid5(NAMESPACE_URL, f"flipflop:playbook-manager:{normalized.idempotency_key}"))
    now = _utcnow()
    async with AsyncSessionLocal() as db:
        await db.execute(text("SELECT pg_advisory_xact_lock(61311, 9)"))
        existing = await db.get(PlaybookRefreshRun, job_id)
        if existing and existing.status == "succeeded":
            prior = existing.result if isinstance(existing.result, dict) else {}
            return AgentEvent(
                event_type="playbook_refresh_completed",
                event_id=str(uuid5(NAMESPACE_URL, f"flipflop:playbook-completed:{normalized.idempotency_key}")),
                producer="playbook",
                occurred_at=datetime.now(timezone.utc),
                idempotency_key=f"playbook-complete:{normalized.idempotency_key}",
                correlation_id=normalized.correlation_id or normalized.event_id,
                evidence_refs=[*normalized.evidence_refs, job_id],
                payload={"job_id": job_id, "status": existing.status, "duplicate": True,
                         "result": prior, "blockers": prior.get("blockers", [])},
            )
        if existing and _manager_run_is_fresh(existing, now):
            raise PlaybookRefreshInProgress(
                "A matching Playbook refresh is still active; the source event remains unsettled."
            )
        if existing is None:
            existing = PlaybookRefreshRun(
                job_id=job_id, actor_id=0, mode="agent", status="running",
                phase="Refreshing committed source evidence through existing Playbook policy",
                started_at=now, heartbeat_at=now,
            )
            db.add(existing)
        else:
            existing.status = "running"
            existing.phase = "Retrying failed Playbook manager run"
            existing.started_at = now
            existing.heartbeat_at = now
            existing.completed_at = None
            existing.error = None
        await db.commit()

    async def heartbeat():
        from app.database import AsyncSessionLocal
        while True:
            await asyncio.sleep(PLAYBOOK_MANAGER_HEARTBEAT_SECONDS)
            async with AsyncSessionLocal() as heartbeat_db:
                run = await heartbeat_db.get(PlaybookRefreshRun, job_id)
                if run is None or run.status != "running":
                    return
                run.heartbeat_at = _utcnow()
                await heartbeat_db.commit()

    heartbeat_task = asyncio.create_task(heartbeat())
    try:
        async with AsyncSessionLocal() as db:
            result = await refresh_playbooks(db, actor_id=0, maintain_live_offers=True)
            blockers = [
                {"cell_id": offer.get("cell_id"), "reasons": offer.get("blockers", [])}
                for offer in result.get("offers", []) if offer.get("blockers")
            ]
            maintenance = result.get("maintenance") or {}
            cell_results = [{
                "cell_id": offer.get("cell_id"),
                "revision_sha256": offer.get("revision_sha256"),
                "components": offer.get("components", []),
                "delivery_products": offer.get("delivery_products", {}),
                "compatibility_review": offer.get("compatibility_review"),
                "availability_replacements": offer.get("availability_replacements", []),
                "blockers": offer.get("blockers", []),
            } for offer in result.get("offers", [])]
            payload = incoming.get("payload") if isinstance(incoming.get("payload"), dict) else {}
            run_result = {
                "trigger_event_id": normalized.event_id,
                "trigger_event_type": event_type,
                "extension_batch_id": payload.get("extension_batch_id"),
                "demand_event_ids": payload.get("demand_event_ids",
                    [normalized.event_id] if event_type == "demand_signal_batch_ready" else []),
                "price_event_ids": payload.get("price_event_ids",
                    [normalized.event_id] if event_type == "component_market_price_changed" else []),
                "demand_fingerprint": demand_fingerprint,
                "skill_sha256": sha256(skill_text.encode("utf-8")).hexdigest(),
                "cells": result.get("cells", 0),
                "complete_hardware": result.get("complete_hardware", 0),
                "ready_for_approval": result.get("ready_for_approval", 0),
                "published": maintenance.get("published", []),
                "paused": maintenance.get("paused", []),
                "exceptions": maintenance.get("exceptions", []),
                "blockers": blockers,
                "cells_result": cell_results,
                "limitations": [
                    "Normalized cross-source demand evidence is linked and audited, but the current deterministic candidate selector consumes paid-component sales only. This run does not claim external demand changed a selected BOM."
                ],
            }
            run = await db.get(PlaybookRefreshRun, job_id)
            run.status = "succeeded"
            run.phase = "Playbook policy refresh completed"
            run.heartbeat_at = _utcnow()
            run.completed_at = _utcnow()
            run.result = run_result
            await db.commit()
        return AgentEvent(
            event_type="playbook_refresh_completed",
            event_id=str(uuid5(NAMESPACE_URL, f"flipflop:playbook-completed:{normalized.idempotency_key}")),
            producer="playbook",
            occurred_at=datetime.now(timezone.utc),
            idempotency_key=f"playbook-complete:{normalized.idempotency_key}",
            correlation_id=normalized.correlation_id or normalized.event_id,
            evidence_refs=[*normalized.evidence_refs, job_id],
            payload={"job_id": job_id, "status": "succeeded", "result": run_result,
                     "blockers": blockers},
        )
    except Exception as error:
        async with AsyncSessionLocal() as db:
            run = await db.get(PlaybookRefreshRun, job_id)
            if run is not None:
                run.status = "failed"
                run.phase = "Playbook policy refresh failed"
                run.heartbeat_at = _utcnow()
                run.completed_at = _utcnow()
                run.error = f"{type(error).__name__}: {error}"
                await db.commit()
        raise
    finally:
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass
