"""
RAM price watcher — polls r/buildapcsales and r/buildapcuk RSS feeds every 15 min.
Fires an alert + ntfy.sh push when a [RAM] DDR5 post falls below the GBP threshold.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import httpx
import structlog

from app.config import get_settings
from app.services.alerts import emit_alert

log = structlog.get_logger(__name__)

_SEEN_FILE = Path(__file__).resolve().parents[2] / "data" / "ram_watch_seen.json"

# Approximate rate — good enough for alerting; we're not doing forex here.
_USD_TO_GBP = 0.79

_FEEDS = [
    {
        "subreddit": "buildapcsales",
        "url": "https://www.reddit.com/r/buildapcsales/new.json?limit=50",
    },
    {
        "subreddit": "buildapcuk",
        "url": "https://www.reddit.com/r/buildapcuk/new.json?limit=50",
    },
]

_DDR5_RE = re.compile(r"\bDDR5\b", re.IGNORECASE)
_RAM_TAG_RE = re.compile(r"\[RAM\]", re.IGNORECASE)
_PRICE_GBP_RE = re.compile(r"£\s*(\d+(?:\.\d+)?)")
_PRICE_USD_RE = re.compile(r"\$\s*(\d+(?:\.\d+)?)")


def _load_seen() -> set[str]:
    try:
        if _SEEN_FILE.exists():
            data = json.loads(_SEEN_FILE.read_text(encoding="utf-8"))
            return set(data) if isinstance(data, list) else set()
    except Exception:
        pass
    return set()


def _save_seen(seen: set[str]) -> None:
    try:
        _SEEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        # Cap at 2000 entries so the file doesn't grow forever.
        recent = list(seen)[-2000:]
        _SEEN_FILE.write_text(json.dumps(recent, ensure_ascii=True), encoding="utf-8")
    except Exception as exc:
        log.warning("ram_watcher.seen_save_failed", error=str(exc))


def _price_gbp(title: str) -> float | None:
    """Extract the first GBP price from a title, converting USD if needed."""
    m = _PRICE_GBP_RE.search(title)
    if m:
        return float(m.group(1))
    m = _PRICE_USD_RE.search(title)
    if m:
        return round(float(m.group(1)) * _USD_TO_GBP, 2)
    return None


async def _fetch_posts(client: httpx.AsyncClient, feed: dict) -> list[dict]:
    try:
        r = await client.get(
            feed["url"],
            headers={"User-Agent": "FlipFlop/1.0 RAM price watcher (contact: flipflop-app)"},
            timeout=15,
        )
        r.raise_for_status()
        return r.json().get("data", {}).get("children", [])
    except Exception as exc:
        log.warning("ram_watcher.fetch_failed", subreddit=feed["subreddit"], error=str(exc))
        return []


async def _send_ntfy(topic: str, title: str, body: str, click_url: str) -> None:
    if not topic:
        return
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"https://ntfy.sh/{topic}",
                content=body.encode(),
                headers={
                    "Title": title,
                    "Priority": "high",
                    "Tags": "ram,deal,alert",
                    "Click": click_url,
                },
                timeout=10,
            )
    except Exception as exc:
        log.warning("ram_watcher.ntfy_failed", error=str(exc))


async def run_ram_watcher() -> dict:
    settings = get_settings()
    threshold_gbp: float = settings.ram_watch_threshold_gbp
    ntfy_topic: str = settings.ntfy_topic

    seen = _load_seen()
    triggered: list[dict] = []
    checked = 0

    async with httpx.AsyncClient() as client:
        for feed in _FEEDS:
            posts = await _fetch_posts(client, feed)
            for post in posts:
                d = post.get("data", {})
                title: str = d.get("title", "")
                post_id: str = d.get("id", "")
                permalink: str = d.get("permalink", "")
                post_url = f"https://reddit.com{permalink}"

                if not post_id or post_id in seen:
                    continue
                if not _RAM_TAG_RE.search(title):
                    continue
                if not _DDR5_RE.search(title):
                    continue

                checked += 1
                price = _price_gbp(title)

                # Always mark seen so we don't re-evaluate next run.
                seen.add(post_id)

                if price is None or price > threshold_gbp:
                    continue

                alert_msg = (
                    f"{title} — £{price:.2f} "
                    f"(threshold £{threshold_gbp:.0f}) | {post_url}"
                )
                await emit_alert(
                    code="ram_deal",
                    source=f"r/{feed['subreddit']}",
                    severity="info",
                    message=alert_msg,
                )

                ntfy_title = f"DDR5 Deal — £{price:.2f}"
                await _send_ntfy(
                    ntfy_topic,
                    ntfy_title,
                    f"{title}\n\n{post_url}",
                    post_url,
                )

                triggered.append({
                    "subreddit": feed["subreddit"],
                    "title": title,
                    "price_gbp": price,
                    "url": post_url,
                })
                log.info("ram_watcher.deal_found", title=title, price_gbp=price, url=post_url)

    _save_seen(seen)
    log.info("ram_watcher.done", checked=checked, deals=len(triggered))
    return {"ok": True, "checked": checked, "deals_found": len(triggered), "deals": triggered}
