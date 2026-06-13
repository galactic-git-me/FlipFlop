"""
PC component deal watcher — polls r/buildapcsales and r/buildapcuk every 15 min.
Fires an alert + ntfy.sh push when a tagged post falls below its GBP threshold.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

import httpx
import structlog

from app.config import get_settings
from app.services.alerts import emit_alert

log = structlog.get_logger(__name__)

_SEEN_FILE = Path(__file__).resolve().parents[2] / "data" / "ram_watch_seen.json"
_USD_TO_GBP = 0.79

_FEEDS = [
    {"subreddit": "buildapcsales", "url": "https://www.reddit.com/r/buildapcsales/new.json?limit=50"},
    {"subreddit": "buildapcuk",    "url": "https://www.reddit.com/r/buildapcuk/new.json?limit=50"},
]

_PRICE_GBP_RE = re.compile(r"£\s*(\d+(?:\.\d+)?)")
_PRICE_USD_RE = re.compile(r"\$\s*(\d+(?:\.\d+)?)")


@dataclass
class WatchRule:
    label: str            # human-readable, e.g. "DDR5 RAM"
    flairs: list[str]     # title tags to match, e.g. ["RAM"]
    keywords: list[str]   # any of these must appear in the title (case-insensitive)
    threshold_gbp: float
    ntfy_tags: str = "deal,alert"

    def _flair_re(self) -> re.Pattern:
        alts = "|".join(re.escape(f) for f in self.flairs)
        return re.compile(rf"\[({alts})\]", re.IGNORECASE)

    def matches(self, title: str) -> bool:
        if not self._flair_re().search(title):
            return False
        tl = title.lower()
        return any(kw.lower() in tl for kw in self.keywords)


def _build_rules(settings) -> list[WatchRule]:
    return [
        WatchRule(
            label="DDR5 RAM",
            flairs=["RAM"],
            keywords=["DDR5"],
            threshold_gbp=settings.ram_watch_threshold_gbp,
            ntfy_tags="ram,ddr5,deal",
        ),
        WatchRule(
            label="DDR4 RAM",
            flairs=["RAM"],
            keywords=["DDR4"],
            threshold_gbp=settings.ram_watch_ddr4_threshold_gbp,
            ntfy_tags="ram,ddr4,deal",
        ),
        WatchRule(
            label="AM4 CPU",
            flairs=["CPU"],
            keywords=[
                "AM4", "Ryzen",
                "3300X", "3600", "3600X", "3700X", "3800X", "3800XT",
                "3900X", "3900XT", "3950X",
                "5500", "5600", "5600X", "5600G",
                "5700X", "5700G", "5800X", "5800X3D",
                "5900X", "5950X",
            ],
            threshold_gbp=settings.ram_watch_cpu_threshold_gbp,
            ntfy_tags="cpu,am4,deal",
        ),
        WatchRule(
            label="AM4 Motherboard",
            flairs=["MOBO"],
            keywords=["AM4", "X570", "B550", "B450", "X470", "A520", "B350", "X370", "A320"],
            threshold_gbp=settings.ram_watch_mobo_threshold_gbp,
            ntfy_tags="mobo,am4,deal",
        ),
        WatchRule(
            label="GPU",
            flairs=["GPU"],
            keywords=[
                # AMD RDNA 2/3
                "RX 6600", "RX 6650", "RX 6700", "RX 6750", "RX 6800", "RX 6900",
                "RX 7600", "RX 7700", "RX 7800", "RX 7900",
                "6600", "6700", "6800", "6900", "7600", "7700", "7800", "7900",
                # Nvidia RTX 30/40
                "RTX 3060", "RTX 3070", "RTX 3080", "RTX 3090",
                "RTX 4060", "RTX 4070", "RTX 4080",
                "3060", "3070", "3080", "3090", "4060", "4070", "4080",
                # Intel Arc
                "Arc A", "Arc B",
            ],
            threshold_gbp=settings.ram_watch_gpu_threshold_gbp,
            ntfy_tags="gpu,deal",
        ),
    ]


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
        recent = list(seen)[-2000:]
        _SEEN_FILE.write_text(json.dumps(recent, ensure_ascii=True), encoding="utf-8")
    except Exception as exc:
        log.warning("ram_watcher.seen_save_failed", error=str(exc))


def _price_gbp(title: str) -> float | None:
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
            headers={"User-Agent": "FlipFlop/1.0 component watcher (contact: flipflop-app)"},
            timeout=15,
        )
        r.raise_for_status()
        return r.json().get("data", {}).get("children", [])
    except Exception as exc:
        log.warning("ram_watcher.fetch_failed", subreddit=feed["subreddit"], error=str(exc))
        return []


async def _send_ntfy(topic: str, title: str, body: str, click_url: str, tags: str = "deal,alert") -> None:
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
                    "Tags": tags,
                    "Click": click_url,
                },
                timeout=10,
            )
    except Exception as exc:
        log.warning("ram_watcher.ntfy_failed", error=str(exc))


async def run_ram_watcher() -> dict:
    settings = get_settings()
    ntfy_topic: str = settings.ntfy_topic
    rules = _build_rules(settings)

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

                # Find the first rule this post satisfies.
                matched_rule: WatchRule | None = None
                for rule in rules:
                    if rule.matches(title):
                        matched_rule = rule
                        break

                if matched_rule is None:
                    continue

                checked += 1
                price = _price_gbp(title)
                seen.add(post_id)

                if price is None or price > matched_rule.threshold_gbp:
                    continue

                alert_msg = (
                    f"[{matched_rule.label}] {title} — £{price:.2f} "
                    f"(threshold £{matched_rule.threshold_gbp:.0f}) | {post_url}"
                )
                await emit_alert(
                    code="pc_deal",
                    source=f"r/{feed['subreddit']}",
                    severity="info",
                    message=alert_msg,
                )

                ntfy_title = f"{matched_rule.label} Deal — £{price:.2f}"
                await _send_ntfy(
                    ntfy_topic,
                    ntfy_title,
                    f"{title}\n\n{post_url}",
                    post_url,
                    tags=matched_rule.ntfy_tags,
                )

                triggered.append({
                    "subreddit": feed["subreddit"],
                    "rule": matched_rule.label,
                    "title": title,
                    "price_gbp": price,
                    "url": post_url,
                })
                log.info(
                    "ram_watcher.deal_found",
                    rule=matched_rule.label,
                    title=title,
                    price_gbp=price,
                )

    _save_seen(seen)
    log.info("ram_watcher.done", checked=checked, deals=len(triggered))
    return {"ok": True, "checked": checked, "deals_found": len(triggered), "deals": triggered}
