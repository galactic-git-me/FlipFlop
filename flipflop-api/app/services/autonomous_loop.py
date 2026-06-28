from __future__ import annotations

from datetime import datetime

import structlog

from app.services.external_demand import ingest_external_demand_signals
from app.services.outcome_capture import capture_outcomes_and_check_retrain
from app.services.playbook_evolution import run_playbook_evolution
from app.swarms.flip_opportunities import run_flip_opportunities_swarm

log = structlog.get_logger(__name__)


async def run_autonomous_cycle() -> dict:
    started = datetime.utcnow()
    failed_steps: list[str] = []

    async def _safe_step(name: str, fn):
        try:
            return await fn()
        except Exception as exc:
            failed_steps.append(name)
            log.error("autonomous_cycle.step_failed", step=name, error=str(exc))
            return {"ok": False, "error": str(exc), "step": name}

    sourcing = await _safe_step("sourcing", run_flip_opportunities_swarm)
    demand = await _safe_step("external_demand", ingest_external_demand_signals)
    evolution = await _safe_step("playbook_evolution", run_playbook_evolution)
    outcomes = await _safe_step("outcome_capture", capture_outcomes_and_check_retrain)

    finished = datetime.utcnow()
    duration_ms = int((finished - started).total_seconds() * 1000)

    result = {
        "ok": len(failed_steps) == 0,
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "duration_ms": duration_ms,
        "failed_steps": failed_steps,
        "steps": {
            "sourcing": sourcing,
            "external_demand": demand,
            "playbook_evolution": evolution,
            "outcome_capture": outcomes,
        },
    }
    log.info("autonomous_cycle.done", duration_ms=duration_ms)
    return result
