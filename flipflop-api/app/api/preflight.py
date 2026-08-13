from fastapi import APIRouter

from app.services.antibot_preflight import preflight_status, trigger_antibot_preflight
from app.database import get_db_pool_stats

router = APIRouter(prefix="/preflight", tags=["Preflight"])


@router.get("/antibot")
async def get_antibot_preflight_status():
    return preflight_status()


@router.post("/antibot/trigger")
async def trigger_antibot_preflight_now():
    return trigger_antibot_preflight()


@router.get("/health")
async def health_check():
    """Check API health including database connection pool."""
    pool_stats = get_db_pool_stats()
    return {
        "status": "healthy",
        "db_pool": pool_stats,
        "pool_utilization": f"{(pool_stats['checked_out'] / pool_stats['pool_size'] * 100):.1f}%"
    }

