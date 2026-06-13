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

# ── Community feed cache (r/PCBuildsUK, r/HotUKDeals) ────────────────────────
_COMMUNITY_FEEDS = [
    {"subreddit": "PCBuildsUK",  "label": "PCBuildsUK"},
    {"subreddit": "HotUKDeals",  "label": "HotUKDeals"},
]
_community_cache: list[dict] = []
_community_cache_ts: float = 0.0
_community_lock = asyncio.Lock()

_UA  = "FlipFlop/1.0 RAM price watcher (contact: flipflop-app)"
_NS  = {"atom": "http://www.w3.org/2005/Atom"}


async def _fetch_feed() -> list[dict]:
    global _feed_cache, _feed_cache_ts
    async with _feed_lock:
        age = time.monotonic() - _feed_cache_ts
        if _feed_cache_ts > 0 and age < _feed_cache_ttl:
            return _feed_cache
        posts: list[dict] = []
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            for i, feed in enumerate(_FEEDS):
                if i > 0:
                    await asyncio.sleep(12)
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


async def _fetch_community_feed() -> list[dict]:
    global _community_cache, _community_cache_ts
    async with _community_lock:
        # Return cached result (even empty) if we tried recently (avoid 429 storms)
        age = time.monotonic() - _community_cache_ts
        if _community_cache_ts > 0 and age < _feed_cache_ttl:
            return _community_cache
        posts: list[dict] = []
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            for i, feed in enumerate(_COMMUNITY_FEEDS):
                if i > 0:
                    await asyncio.sleep(12)  # Reddit rate limit: ~1 req / 10s per IP
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
            _community_cache = posts
            _community_cache_ts = time.monotonic()
        return _community_cache


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/deals")
async def get_ram_deals(limit: int = 100):
    alerts = await list_alerts(limit=limit, include_acked=True)
    return [a for a in alerts if a["code"] in ("ram_deal", "pc_deal")]


@router.get("/config")
async def get_config():
    s = get_settings()
    return {
        "ntfy_topic": s.ntfy_topic,
        "enabled": s.ram_watch_enabled,
        "thresholds": {
            "ddr5_ram_gbp": s.ram_watch_threshold_gbp,
            "ddr4_ram_gbp": s.ram_watch_ddr4_threshold_gbp,
            "cpu_gbp": s.ram_watch_cpu_threshold_gbp,
            "mobo_gbp": s.ram_watch_mobo_threshold_gbp,
            "gpu_gbp": s.ram_watch_gpu_threshold_gbp,
        },
    }


@router.get("/feed")
async def get_reddit_feed():
    """Return recent posts from both subreddits. Cached for 15 min."""
    return await _fetch_feed()


@router.get("/community-feed")
async def get_community_feed():
    """Return recent posts from r/PCBuildsUK and r/HotUKDeals. Cached for 15 min."""
    return await _fetch_community_feed()


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
        "FlipFlop PC Watch — Test",
        "Component deal watcher is live. Watching: "
        f"DDR5 RAM <£{s.ram_watch_threshold_gbp:.0f}, "
        f"DDR4 RAM <£{s.ram_watch_ddr4_threshold_gbp:.0f}, "
        f"AM4 CPU <£{s.ram_watch_cpu_threshold_gbp:.0f}, "
        f"MOBO <£{s.ram_watch_mobo_threshold_gbp:.0f}, "
        f"GPU <£{s.ram_watch_gpu_threshold_gbp:.0f}",
        "https://reddit.com/r/buildapcsales",
        tags="test,deal",
    )
    return {"ok": True}
