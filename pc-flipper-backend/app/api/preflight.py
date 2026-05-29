from fastapi import APIRouter

from app.services.antibot_preflight import preflight_status, trigger_antibot_preflight

router = APIRouter(prefix="/preflight", tags=["Preflight"])


@router.get("/antibot")
async def get_antibot_preflight_status():
    return preflight_status()


@router.post("/antibot/trigger")
async def trigger_antibot_preflight_now():
    return trigger_antibot_preflight()

