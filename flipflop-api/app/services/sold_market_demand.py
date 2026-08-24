"""Sold-market demand snapshot and grounded AI commentary.

The extension collects a bounded sample of eBay completed listings. These
figures are therefore evidence coverage and supply-pressure indicators, not
eBay's complete sales volume or a literal sell-through rate.
"""
from __future__ import annotations

import json
import math
import statistics
from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.gem_radar_scored_listing import GemRadarScoredListing
from app.models.gem_radar_sold_observation import GemRadarSoldObservation

_CATEGORY_LABELS = {
    "cpu": "CPUs", "gpu": "Graphics Cards", "motherboard": "Motherboards",
    "ram": "Memory", "ssd": "Storage", "psu": "Power Supplies",
    "cooler": "Cooling", "case": "PC Cases", "fan": "Case Fans",
}
_AI_CACHE: dict[str, object] = {"at": None, "data": None}
_AI_CACHE_TTL = timedelta(hours=6)


def _median(values: list[float]) -> float | None:
    return round(statistics.median(values), 2) if values else None


def _strength(score: float) -> str:
    return "High" if score >= 70 else "Medium" if score >= 40 else "Low"


async def build_sold_market_snapshot(db: AsyncSession, days: int = 90) -> dict:
    now = datetime.utcnow()
    cutoff = now - timedelta(days=days)
    sold = list((await db.execute(
        select(GemRadarSoldObservation).where(
            GemRadarSoldObservation.observed_at >= cutoff,
            GemRadarSoldObservation.cpk.is_not(None),
        )
    )).scalars().all())
    active = list((await db.execute(
        select(GemRadarScoredListing).where(
            GemRadarScoredListing.scored_at >= cutoff,
            GemRadarScoredListing.cpk.is_not(None),
            GemRadarScoredListing.category.is_not(None),
        )
    )).scalars().all())

    # Latest scored row provides the human-readable identity/category for a CPK.
    active_by_id: dict[str, GemRadarScoredListing] = {}
    cpk_identity: dict[str, GemRadarScoredListing] = {}
    for row in sorted(active, key=lambda item: item.scored_at or datetime.min):
        active_by_id[row.listing_id] = row
        if row.cpk:
            cpk_identity[row.cpk] = row

    category_active: dict[str, list[GemRadarScoredListing]] = defaultdict(list)
    for row in active_by_id.values():
        if row.category in _CATEGORY_LABELS:
            category_active[row.category].append(row)

    category_sold: dict[str, list[GemRadarSoldObservation]] = defaultdict(list)
    product_sold: dict[str, list[GemRadarSoldObservation]] = defaultdict(list)
    unmatched = 0
    for row in sold:
        identity = cpk_identity.get(row.cpk or "")
        if not identity or identity.category not in _CATEGORY_LABELS:
            unmatched += 1
            continue
        category_sold[identity.category].append(row)
        product_sold[row.cpk or ""].append(row)

    categories = []
    for category in _CATEGORY_LABELS:
        sold_rows = category_sold.get(category, [])
        active_rows = category_active.get(category, [])
        if not sold_rows and not active_rows:
            continue
        sold_count = len(sold_rows)
        active_count = len(active_rows)
        product_count = len({r.cpk for r in sold_rows})
        evidence_ratio = sold_count / max(sold_count + active_count, 1)
        coverage = min(100.0, sold_count / 25 * 100)
        balance = min(100.0, evidence_ratio * 180)
        demand_score = round(coverage * 0.55 + balance * 0.45, 1)
        recent = sum(1 for r in sold_rows if r.observed_at >= now - timedelta(days=30))
        prior = sum(1 for r in sold_rows if now - timedelta(days=60) <= r.observed_at < now - timedelta(days=30))
        trend_pct = None if prior == 0 else round((recent - prior) / prior * 100, 1)
        categories.append({
            "category": category,
            "label": _CATEGORY_LABELS[category],
            "sold_observations": sold_count,
            "active_listings": active_count,
            "products_with_sold_evidence": product_count,
            "median_sold_price": _median([r.price + (r.postage or 0) for r in sold_rows]),
            "median_active_price": _median([r.delivered_price for r in active_rows]),
            "evidence_ratio_pct": round(evidence_ratio * 100, 1),
            "sample_confidence_pct": round(coverage, 1),
            "demand_score": demand_score,
            "strength": _strength(demand_score),
            "recent_30d": recent,
            "previous_30d": prior,
            "trend_pct": trend_pct,
        })
    categories.sort(key=lambda row: (row["demand_score"], row["sold_observations"]), reverse=True)

    products = []
    active_by_cpk: dict[str, list[GemRadarScoredListing]] = defaultdict(list)
    for row in active_by_id.values():
        if row.cpk:
            active_by_cpk[row.cpk].append(row)
    for cpk, sold_rows in product_sold.items():
        identity = cpk_identity[cpk]
        active_rows = active_by_cpk.get(cpk, [])
        sold_count = len(sold_rows)
        active_count = len(active_rows)
        products.append({
            "cpk": cpk,
            "name": identity.canonical_model_id or identity.title,
            "category": identity.category,
            "sold_observations": sold_count,
            "active_listings": active_count,
            "median_sold_price": _median([r.price + (r.postage or 0) for r in sold_rows]),
            "median_active_price": _median([r.delivered_price for r in active_rows]),
            "evidence_ratio_pct": round(sold_count / max(sold_count + active_count, 1) * 100, 1),
        })
    products.sort(key=lambda row: (row["sold_observations"], row["evidence_ratio_pct"]), reverse=True)

    weekly = []
    for index in range(11, -1, -1):
        start = now - timedelta(days=(index + 1) * 7)
        end = now - timedelta(days=index * 7)
        weekly.append({
            "week": end.strftime("%d %b"),
            "sold_observations": sum(1 for row in sold if start <= row.observed_at < end),
        })

    return {
        "generated_at": now.isoformat() + "Z", "window_days": days,
        "methodology": "Bounded completed-listing samples compared with currently scored live supply; evidence ratio is not a marketplace-wide sell-through rate.",
        "totals": {
            "sold_observations": len(sold), "matched_sold_observations": len(sold) - unmatched,
            "unmatched_sold_observations": unmatched, "active_listings": len(active_by_id),
            "products_with_sold_evidence": len(product_sold),
        },
        "categories": categories, "top_products": products[:20], "weekly": weekly,
    }


def fallback_insights(snapshot: dict) -> dict:
    categories = snapshot["categories"]
    if not categories:
        text = "There is not enough matched completed-sale evidence yet to identify reliable demand patterns."
    else:
        leader = categories[0]
        constrained = max(categories, key=lambda row: row["evidence_ratio_pct"])
        text = (
            f"{leader['label']} currently has the strongest sampled demand signal "
            f"({leader['demand_score']:.0f}/100 from {leader['sold_observations']} completed-sale observations). "
            f"{constrained['label']} has the highest completed-evidence-to-live-supply balance "
            f"at {constrained['evidence_ratio_pct']:.1f}%. Prioritise products with adequate sample confidence; "
            "small samples should be treated as research leads, not purchasing instructions."
        )
    return {"insight": text, "model": "deterministic-fallback", "generated_at": datetime.utcnow().isoformat() + "Z"}


async def generate_ai_insights(snapshot: dict, refresh: bool = False) -> dict:
    cached_at = _AI_CACHE.get("at")
    if not refresh and isinstance(cached_at, datetime) and datetime.utcnow() - cached_at < _AI_CACHE_TTL:
        return _AI_CACHE["data"]  # type: ignore[return-value]
    compact = {"totals": snapshot["totals"], "categories": snapshot["categories"], "top_products": snapshot["top_products"][:8]}
    prompt = f"""Analyse this UK PC-component demand snapshot and write a concise decision brief (maximum 180 words).
Use only the supplied data. Separate strong evidence from weak samples. Explain what to source more of, what to watch, and one key risk. Never call evidence_ratio a true sell-through rate. Use short markdown headings or bullets.
DATA: {json.dumps(compact, separators=(',', ':'))}"""
    try:
        from app.services.ai_service import chat
        insight, model = await chat(prompt, history=[])
        if model == "none":
            result = fallback_insights(snapshot)
        else:
            result = {"insight": insight, "model": model, "generated_at": datetime.utcnow().isoformat() + "Z"}
    except Exception:
        result = fallback_insights(snapshot)
    _AI_CACHE.update({"at": datetime.utcnow(), "data": result})
    return result
