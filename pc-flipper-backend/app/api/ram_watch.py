from fastapi import APIRouter
from app.config import get_settings
from app.services.alerts import list_alerts
from app.services.ram_watcher import run_ram_watcher, _send_ntfy

router = APIRouter(prefix="/ram-watch", tags=["ram-watch"])


@router.get("/deals")
async def get_ram_deals(limit: int = 100):
    alerts = await list_alerts(limit=limit, include_acked=True)
    return [a for a in alerts if a["code"] == "ram_deal"]


@router.get("/config")
async def get_config():
    s = get_settings()
    return {
        "threshold_gbp": s.ram_watch_threshold_gbp,
        "ntfy_topic": s.ntfy_topic,
        "enabled": s.ram_watch_enabled,
    }


@router.post("/trigger")
async def trigger_watcher():
    return await run_ram_watcher()


@router.post("/test-notify")
async def test_notification():
    s = get_settings()
    if not s.ntfy_topic:
        return {"ok": False, "reason": "ntfy_topic not configured in .env"}
    await _send_ntfy(
        s.ntfy_topic,
        "FlipFlop RAM Watch — Test",
        "Your DDR5 price watcher is working. Deals below £"
        + str(int(s.ram_watch_threshold_gbp))
        + " will ping here.",
        "https://reddit.com/r/buildapcsales",
    )
    return {"ok": True}
