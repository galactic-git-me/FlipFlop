from fastapi import APIRouter
import asyncio
import httpx
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from app.config import get_settings
from app.services.alerts import list_alerts
from app.services.ram_watcher import run_ram_watcher, _send_ntfy, _FEEDS

router = APIRouter(prefix="/ram-watch", tags=["ram-watch"])

# ── Feed cache — only hit Reddit once per 15 min regardless of UI refreshes ──
_feed_cache: list[dict] = []
_feed_cache_ts: float = 0.0
_feed_cache_ttl: float = 15 * 60   # seconds
_feed_lock = asyncio.Lock()

_UA  = "FlipFlop/1.0 RAM price watcher (contact: flipflop-app)"
_NS  = {"atom": "http://www.w3.org/2005/Atom"}


async def _fetch_feed() -> list[dict]:
    global _feed_cache, _feed_cache_ts
    async with _feed_lock:
        if _feed_cache and time.monotonic() - _feed_cache_ts < _feed_cache_ttl:
            return _feed_cache
        posts: list[dict] = []
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            for feed in _FEEDS:
                rss_url = f"https://www.reddit.com/r/{feed['subreddit']}/new.rss?limit=100"
                try:
                    resp = await client.get(rss_url, headers={"User-Agent": _UA})
                    if resp.status_code != 200:
                        continue
                    root = ET.fromstring(resp.content)
                    for entry in root.findall("atom:entry", _NS):
                        title = (entry.findtext("atom:title", "", _NS) or "").strip()
                        link_el = entry.find("atom:link", _NS)
                        url = link_el.get("href", "") if link_el is not None else ""
                        published = entry.findtext("atom:published", "", _NS) or ""
                        content = (entry.findtext("atom:content", "", _NS) or "")[:400]
                        try:
                            ts = int(datetime.fromisoformat(published).timestamp()) if published else 0
                        except Exception:
                            ts = 0
                        post_id = url.rstrip("/").split("/")[-1] if url else ""
                        flair = ""
                        if title.startswith("["):
                            end = title.find("]")
                            if end > 0:
                                flair = title[1:end]
                                title = title[end + 1:].strip()
                        posts.append({
                            "subreddit":   feed["subreddit"],
                            "id":          post_id,
                            "title":       title,
                            "url":         url,
                            "flair":       flair,
                            "created_utc": ts,
                            "selftext":    content,
                        })
                except Exception:
                    continue
        posts.sort(key=lambda p: p["created_utc"], reverse=True)
        if posts:
            _feed_cache = posts
            _feed_cache_ts = time.monotonic()
        return _feed_cache


# ── Routes ────────────────────────────────────────────────────────────────────

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
async def get_reddit_feed():
    """Return recent posts from both subreddits. Cached for 15 min."""
    return await _fetch_feed()


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
