import asyncio
from fastapi import APIRouter, BackgroundTasks, HTTPException
from app.workers.scheduler import trigger_swarm, get_swarm_status
from app.services import scan_state

router = APIRouter(prefix="/swarms", tags=["swarms"])


@router.get("/")
@router.get("", include_in_schema=False)
async def list_swarms():
    return get_swarm_status()


@router.get("/scan/status")
async def scan_status():
    return scan_state.get_state()


@router.post("/{swarm_id}/trigger")
async def trigger(swarm_id: str, background_tasks: BackgroundTasks):
    """Trigger a swarm in the background and return immediately so the scan overlay can animate."""
    # Validate swarm ID first
    valid = {
        "flip_opportunities",
        "upgrade_parts",
        "cases",
        "case_content_sourcing",
        "amazon_case_bestsellers",
        "accessories",
        "external_demand",
        "playbook_evolution",
        "autonomous",
        "outcome_capture",
        "model_retraining",
        "compliant_market_ingestion",
    }
    if swarm_id not in valid:
        raise HTTPException(400, f"Unknown swarm: {swarm_id!r}")

    # If already running, don't double-start
    state = scan_state.get_state()
    if state["running"]:
        return {"ok": True, "queued": False, "message": "Scan already in progress"}

    background_tasks.add_task(_run_swarm_bg, swarm_id)
    return {"ok": True, "queued": True}


async def _run_swarm_bg(swarm_id: str):
    try:
        await trigger_swarm(swarm_id)
    except Exception as exc:
        import structlog
        structlog.get_logger(__name__).error("swarm.bg_error", swarm=swarm_id, error=str(exc))
