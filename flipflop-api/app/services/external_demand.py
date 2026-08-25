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
    # Demand-intent lanes: what buyers are actively searching for.
    "pc_intent": ["gaming pc", "ai pc", "workstation pc", "budget gaming pc", "custom pc"],
    "market_tier": ["cheap gaming pc", "mid range gaming pc", "high end gaming pc"],
    "platform_builds": ["am4 gaming pc", "am5 gaming pc", "intel gaming pc", "ryzen gaming pc"],
    "ai_builds": ["local ai pc", "stable diffusion pc", "llm pc", "ai workstation", "ollama pc"],
}


async def ingest_external_demand_signals() -> dict:
    from app.services.rich_demand_collector import (
        collect_google_trends_rich,
        collect_reddit_rich,
        collect_steam_rich,
    )
    now = datetime.utcnow()
    signals: list[DemandSignal] = []

    for topic, queries in TOPIC_QUERIES.items():
        signals.extend(await _fetch_reddit_signals(topic, queries, now))
        signals.extend(await _fetch_google_trends_signals(topic, queries, now))
        signals.extend(await _fetch_steam_signals(topic, queries, now))

    inserted = await _persist_signals(signals)
    await _prune_old(days=30)

    # Collect rich detail data (time-series, geo, posts, hardware stats)
    gt_result = await collect_google_trends_rich(now)
    reddit_result = await collect_reddit_rich(now)
    steam_result = await collect_steam_rich(now)

    return {
        "ok": True,
        "inserted": inserted,
        "topics": len(TOPIC_QUERIES),
        "signals": len(signals),
        "rich": {
            "google_trends": gt_result,
            "reddit": reddit_result,
            "steam": steam_result,
        },
    }


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
    Real adapter (no API key), UK-focused:
      - Uses Google Trends explore API to get:
        1) interest over time (last 7 days)
        2) geographic interest by region (UK)
      - Produces one signal per query with score + geo insight notes.
    """
    out: list[DemandSignal] = []
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        for q in queries:
            q_clean = q.strip()
            if not q_clean:
                continue
            try:
                trend = await _google_trends_interest_for_query(client, q_clean)
                out.append(
                    DemandSignal(
                        source="google_trends",
                        topic=topic,
                        query=q_clean,
                        score=trend["score"],
                        confidence=trend["confidence"],
                        sample_size=trend["sample_size"],
                        signal_time=now,
                        notes=trend["notes"],
                    )
                )
            except Exception:
                out.append(
                    DemandSignal(
                        source="google_trends",
                        topic=topic,
                        query=q_clean,
                        score=0.0,
                        confidence=0.1,
                        sample_size=0,
                        signal_time=now,
                        notes="Google Trends fetch failed for query",
                    )
                )
    return out


def _parse_trends_json(payload: str) -> dict:
    cleaned = re.sub(r"^\)\]\}',?\n?", "", payload or "")
    return json.loads(cleaned) if cleaned else {}


async def _google_trends_interest_for_query(client: httpx.AsyncClient, query: str) -> dict:
    headers = {"User-Agent": "FlipFlopDemandBot/1.0"}
    req = {
        "comparisonItem": [{"keyword": query, "geo": "GB", "time": "now 7-d"}],
        "category": 0,
        "property": "",
    }

    explore_resp = await client.get(
        "https://trends.google.com/trends/api/explore",
        params={"hl": "en-GB", "tz": "0", "req": json.dumps(req, separators=(",", ":"))},
        headers=headers,
    )
    if explore_resp.status_code != 200:
        raise RuntimeError(f"explore status {explore_resp.status_code}")
    explore = _parse_trends_json(explore_resp.text)
    widgets = explore.get("widgets", []) or []
    if not widgets:
        raise RuntimeError("no widgets")

    timeseries_widget = next((w for w in widgets if str(w.get("id", "")).startswith("TIMESERIES")), None)
    geo_widget = next((w for w in widgets if str(w.get("id", "")).startswith("GEO_MAP")), None)
    if not timeseries_widget:
        raise RuntimeError("no timeseries widget")

    ts_req = timeseries_widget.get("request", {})
    ts_token = timeseries_widget.get("token")
    ts_resp = await client.get(
        "https://trends.google.com/trends/api/widgetdata/multiline",
        params={"hl": "en-GB", "tz": "0", "req": json.dumps(ts_req, separators=(",", ":")), "token": ts_token},
        headers=headers,
    )
    if ts_resp.status_code != 200:
        raise RuntimeError(f"multiline status {ts_resp.status_code}")
    ts_data = _parse_trends_json(ts_resp.text)
    timeline = ts_data.get("default", {}).get("timelineData", []) or []
    values = []
    for row in timeline:
        v = (row.get("value") or [0])[0]
        try:
            values.append(float(v))
        except Exception:
            continue
    avg_interest = sum(values) / len(values) if values else 0.0
    recent_interest = values[-1] if values else 0.0
    score = round(min(100.0, (avg_interest * 0.65) + (recent_interest * 0.35)), 2)

    top_regions = []
    if geo_widget and geo_widget.get("request") and geo_widget.get("token"):
        geo_resp = await client.get(
            "https://trends.google.com/trends/api/widgetdata/comparedgeo",
            params={
                "hl": "en-GB",
                "tz": "0",
                "req": json.dumps(geo_widget.get("request"), separators=(",", ":")),
                "token": geo_widget.get("token"),
            },
            headers=headers,
        )
        if geo_resp.status_code == 200:
            geo_data = _parse_trends_json(geo_resp.text)
            regions = geo_data.get("default", {}).get("geoMapData", []) or []
            ranked = []
            for r in regions:
                region_name = r.get("geoName")
                raw_val = (r.get("value") or [0])[0]
                try:
                    val = float(raw_val)
                except Exception:
                    val = 0.0
                if region_name and val > 0:
                    ranked.append((str(region_name), val))
            ranked.sort(key=lambda t: t[1], reverse=True)
            top_regions = [name for name, _ in ranked[:3]]

    notes = (
        f"Google Trends UK 7d interest avg={avg_interest:.1f}, latest={recent_interest:.1f}"
        + (f", top regions: {', '.join(top_regions)}" if top_regions else "")
    )
    confidence = 0.7 if values else 0.2
    return {
        "score": score,
        "confidence": confidence,
        "sample_size": len(values),
        "notes": notes,
    }


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
