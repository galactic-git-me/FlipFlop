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

    sourcing = await run_flip_opportunities_swarm()
    demand = await ingest_external_demand_signals()
    evolution = await run_playbook_evolution()
    outcomes = await capture_outcomes_and_check_retrain()

    finished = datetime.utcnow()
    duration_ms = int((finished - started).total_seconds() * 1000)

    result = {
        "ok": True,
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "duration_ms": duration_ms,
        "steps": {
            "sourcing": sourcing,
            "external_demand": demand,
            "playbook_evolution": evolution,
            "outcome_capture": outcomes,
        },
    }
    log.info("autonomous_cycle.done", duration_ms=duration_ms)
    return result
