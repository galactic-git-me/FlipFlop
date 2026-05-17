from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable

import httpx
import re
import json
from sqlalchemy import delete, select

from app.database import AsyncSessionLocal
from app.models.external_demand_signal import ExternalDemandSignal


@dataclass
class DemandSignal:
    source: str
    topic: str
    query: str | None
    score: float
    confidence: float
    sample_size: int | None
    signal_time: datetime
    notes: str | None = None


TOPIC_QUERIES: dict[str, list[str]] = {
    "am5_bundles": ["7700x b650", "am5 bundle", "ryzen bundle", "ddr5 bundle"],
    "midrange_gpu": ["rtx 3060", "rtx 3070", "rx 6700 xt", "rx 7600"],
    "workstation_cpu": ["ryzen 7900", "ryzen 9700x", "i7 12700", "i9 12900"],
}


async def ingest_external_demand_signals() -> dict:
    now = datetime.utcnow()
    signals: list[DemandSignal] = []

    for topic, queries in TOPIC_QUERIES.items():
        signals.extend(await _fetch_reddit_signals(topic, queries, now))
        signals.extend(await _fetch_google_trends_signals(topic, queries, now))
        signals.extend(await _fetch_steam_signals(topic, queries, now))

    inserted = await _persist_signals(signals)
    await _prune_old(days=30)
    return {"ok": True, "inserted": inserted, "topics": len(TOPIC_QUERIES), "signals": len(signals)}


async def _fetch_reddit_signals(topic: str, queries: Iterable[str], now: datetime) -> list[DemandSignal]:
    out: list[DemandSignal] = []
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        for q in queries:
            try:
                # Public endpoint: lightweight pulse (not authenticated)
                resp = await client.get(
                    "https://www.reddit.com/search.json",
                    params={"q": q, "sort": "new", "limit": 25, "t": "month"},
                    headers={"User-Agent": "FlipFlopDemandBot/1.0"},
                )
                if resp.status_code != 200:
                    continue
                data = resp.json()
                children = data.get("data", {}).get("children", [])
                count = len(children)
                score = min(100.0, float(count) * 4.0)
                out.append(
                    DemandSignal(
                        source="reddit",
                        topic=topic,
                        query=q,
                        score=score,
                        confidence=0.55,
                        sample_size=count,
                        signal_time=now,
                        notes="Reddit post count proxy (last month, newest)",
                    )
                )
            except Exception:
                continue
    return out


async def _fetch_google_trends_signals(topic: str, queries: Iterable[str], now: datetime) -> list[DemandSignal]:
    """
    Real adapter (no API key):
      - Reads Google Daily Trends feed for GB.
      - Scores query relevance by keyword mention hits in trending titles.
    """
    out: list[DemandSignal] = []
    trends_titles: list[str] = []
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        try:
            resp = await client.get(
                "https://trends.google.com/trends/api/dailytrends",
                params={"hl": "en-GB", "tz": "0", "geo": "GB"},
                headers={"User-Agent": "FlipFlopDemandBot/1.0"},
            )
            if resp.status_code == 200:
                payload = resp.text
                # Trends API prepends anti-XSSI chars like )]}'
                payload = re.sub(r"^\)\]\}',?\n?", "", payload)
                data = json.loads(payload)
                days = data.get("default", {}).get("trendingSearchesDays", [])
                for day in days:
                    for item in day.get("trendingSearches", []):
                        title = (item.get("title", {}) or {}).get("query")
                        if title:
                            trends_titles.append(str(title).lower())
        except Exception:
            trends_titles = []

    total_titles = max(1, len(trends_titles))
    corpus = " | ".join(trends_titles)
    for q in queries:
        ql = q.lower().strip()
        if not ql:
            continue
        hits = corpus.count(ql)
        # include partial-token hits for key words
        for token in [t for t in re.split(r"\s+", ql) if len(t) >= 3]:
            hits += corpus.count(token) * 0.15
        score = min(100.0, float(hits) * 18.0)
        out.append(
            DemandSignal(
                source="google_trends",
                topic=topic,
                query=q,
                score=round(score, 2),
                confidence=0.5 if trends_titles else 0.15,
                sample_size=total_titles,
                signal_time=now,
                notes="Google Daily Trends (GB) relevance proxy",
            )
        )
    return out


async def _fetch_steam_signals(topic: str, queries: Iterable[str], now: datetime) -> list[DemandSignal]:
    """
    Real adapter (no API key):
      - Scrapes public Steam Hardware Survey page text.
      - Uses keyword mention frequency as relative demand proxy.
    """
    out: list[DemandSignal] = []
    body = ""
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        try:
            resp = await client.get(
                "https://store.steampowered.com/hwsurvey/Steam-Hardware-Software-Survey-Welcome-to-Steam",
                headers={"User-Agent": "FlipFlopDemandBot/1.0"},
            )
            if resp.status_code == 200:
                body = resp.text.lower()
        except Exception:
            body = ""

    for q in queries:
        ql = q.lower().strip()
        if not ql:
            continue
        tokens = [t for t in re.split(r"\s+", ql) if len(t) >= 3]
        hits = sum(body.count(t) for t in tokens) if body else 0
        score = min(100.0, hits * 2.5)
        out.append(
            DemandSignal(
                source="steam_hardware",
                topic=topic,
                query=q,
                score=round(score, 2),
                confidence=0.45 if body else 0.15,
                sample_size=len(tokens) if tokens else None,
                signal_time=now,
                notes="Steam Hardware Survey keyword incidence proxy",
            )
        )
    return out


async def _persist_signals(signals: list[DemandSignal]) -> int:
    if not signals:
        return 0
    async with AsyncSessionLocal() as db:
        for s in signals:
            db.add(
                ExternalDemandSignal(
                    source=s.source,
                    topic=s.topic,
                    query=s.query,
                    score=s.score,
                    confidence=s.confidence,
                    sample_size=s.sample_size,
                    signal_time=s.signal_time,
                    notes=s.notes,
                )
            )
        await db.commit()
    return len(signals)


async def _prune_old(days: int = 30) -> None:
    cutoff = datetime.utcnow() - timedelta(days=days)
    async with AsyncSessionLocal() as db:
        await db.execute(delete(ExternalDemandSignal).where(ExternalDemandSignal.signal_time < cutoff))
        await db.commit()


async def latest_external_signal_snapshot(limit_per_source: int = 50) -> dict:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ExternalDemandSignal)
            .order_by(ExternalDemandSignal.signal_time.desc())
            .limit(max(10, min(1000, limit_per_source * 8)))
        )
        rows = list(result.scalars().all())

    by_source: dict[str, list[dict]] = {}
    for r in rows:
        by_source.setdefault(r.source, [])
        if len(by_source[r.source]) >= limit_per_source:
            continue
        by_source[r.source].append(
            {
                "id": r.id,
                "topic": r.topic,
                "query": r.query,
                "score": r.score,
                "confidence": r.confidence,
                "sample_size": r.sample_size,
                "signal_time": r.signal_time.isoformat() if r.signal_time else None,
                "notes": r.notes,
            }
        )

    summary = {
        source: {
            "count": len(items),
            "avg_score": round(sum(float(i["score"]) for i in items) / len(items), 2) if items else 0.0,
            "avg_confidence": round(sum(float(i["confidence"]) for i in items) / len(items), 2) if items else 0.0,
        }
        for source, items in by_source.items()
    }

    return {"summary": summary, "items": by_source}
