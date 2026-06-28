"""
/api/price-benchmarks — view and trigger the live component price refresh.

GET  /api/price-benchmarks        → current benchmark values + metadata
POST /api/price-benchmarks/refresh → trigger an immediate refresh (async; returns job id)
"""
from fastapi import APIRouter, BackgroundTasks
from app.services.price_refresh import load_benchmarks, run_price_refresh

router = APIRouter(prefix="/price-benchmarks", tags=["price-benchmarks"])


@router.get("")
async def get_price_benchmarks():
    """
    Return the most-recent eBay UK sold price benchmarks.

    Fields prefixed with:
      cost_  → what WE pay to buy a component (sourcing cost)
      gpu_   → standalone GPU sold price (what a GPU adds × 0.90 = in-system contribution)
      sys_   → complete bare PC (no GPU) sold price (maps to CPU_BASE_RESALE)

    refreshed_at_iso  → when the last successful refresh ran
    age_hours         → how old the data is; > 48 means the estimator is using fallback defaults
    """
    b = load_benchmarks()
    from app.services.price_refresh import _BENCHMARKS_FILE
    import time, json
    from pathlib import Path

    meta: dict = {}
    if _BENCHMARKS_FILE.exists():
        try:
            raw = json.loads(_BENCHMARKS_FILE.read_text(encoding="utf-8"))
            refreshed_at = raw.get("refreshed_at", 0)
            meta = {
                "refreshed_at_iso": raw.get("refreshed_at_iso"),
                "age_hours": round((time.time() - refreshed_at) / 3600, 1),
                "updated_count": raw.get("updated_count"),
                "failed_count": raw.get("failed_count"),
                "file": str(_BENCHMARKS_FILE),
                "live": len(b) > 0,
            }
        except Exception:
            pass
    else:
        meta = {"live": False, "reason": "file not yet written — price_refresh job has not run"}

    return {
        "meta": meta,
        "benchmarks": b,
    }


@router.post("/refresh")
async def trigger_price_refresh(background_tasks: BackgroundTasks):
    """
    Kick off a full price refresh immediately (runs in background, ~3-4 min).
    The scheduler runs this automatically every 24 h; use this to force an update.
    """
    background_tasks.add_task(run_price_refresh)
    return {"ok": True, "message": "Price refresh started in background. Check /api/price-benchmarks in ~4 min."}
