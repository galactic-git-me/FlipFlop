from fastapi import APIRouter
import httpx
from app.config import get_settings
from app.services.alerts import list_alerts
from app.services.ram_watcher import run_ram_watcher, _send_ntfy, _FEEDS

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


@router.get("/feed")
async def get_reddit_feed(limit: int = 50):
    """Return recent posts from both subreddits, newest first."""
    headers = {"User-Agent": "FlipFlop/1.0"}
    posts = []
    async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
        for feed in _FEEDS:
            try:
                resp = await client.get(feed["url"].replace("limit=50", f"limit={limit}"))
                if resp.status_code != 200:
                    continue
                children = resp.json().get("data", {}).get("children", [])
                for child in children:
                    d = child.get("data", {})
                    posts.append({
                        "subreddit": feed["subreddit"],
                        "id":        d.get("id"),
                        "title":     d.get("title", ""),
                        "url":       f"https://reddit.com{d.get('permalink', '')}",
                        "link_url":  d.get("url", ""),
                        "flair":     d.get("link_flair_text") or "",
                        "score":     d.get("score", 0),
                        "comments":  d.get("num_comments", 0),
                        "created_utc": d.get("created_utc", 0),
                        "selftext":  (d.get("selftext") or "")[:300],
                    })
            except Exception:
                continue
    posts.sort(key=lambda p: p["created_utc"], reverse=True)
    return posts


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
