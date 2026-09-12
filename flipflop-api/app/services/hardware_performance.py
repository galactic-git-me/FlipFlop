"""Attach independent CPU/GPU performance context to sourcing rows.

Market price answers "is this cheap?".  This module answers "what am I
buying?" and deliberately keeps the two signals separate.  It is pure apart
from the small lookup helper, which makes the policy easy to test and tune.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from app.models.benchmark import HardwareBenchmark
from app.services.benchmark_normaliser import normalise_cpu, normalise_gpu


def _normalise_for_category(category: str | None, value: str | None) -> str | None:
    if not value or category not in {"cpu", "gpu"}:
        return None
    return normalise_cpu(value) if category == "cpu" else normalise_gpu(value)


def index_benchmarks(rows: Iterable[HardwareBenchmark]) -> dict[tuple[str, str], HardwareBenchmark]:
    """Index one best row per category/model, preferring confidence then score."""
    result: dict[tuple[str, str], HardwareBenchmark] = {}
    for row in rows:
        key = (row.component_type, row.normalized_model)
        current = result.get(key)
        if current is None or (row.confidence_score, row.overall_score or 0) > (
            current.confidence_score, current.overall_score or 0
        ):
            result[key] = row
    return result


def _percentile(score: float | None, peer_scores: list[float]) -> float | None:
    if score is None or not peer_scores:
        return None
    # Percentile is the share of peers at or below this score.  This is more
    # understandable in the table than a raw PassMark number alone.
    return round(sum(1 for peer in peer_scores if peer <= score) / len(peer_scores) * 100, 1)


def _fit_label(release_year: int | None, percentile: float | None) -> tuple[str, str]:
    """Return an explainable buyer-facing hardware tier and action."""
    if release_year is not None:
        age = datetime.now(timezone.utc).year - release_year
        if age >= 7:
            return "LEGACY_OR_ENTRY", "AVOID_FOR_MODERN_BUILDS"
        if age >= 4:
            return "CAPABLE_OLDER", "CHECK_USE_CASE"
    if percentile is not None and percentile >= 70:
        return "HIGH_PERFORMER", "GOOD_GENERAL_FIT"
    if percentile is not None and percentile < 30:
        return "LEGACY_OR_ENTRY", "AVOID_FOR_MODERN_BUILDS"
    return "MIDRANGE_OR_OLDER", "CHECK_USE_CASE"


def enrich_listing_performance(
    *,
    category: str | None,
    title: str,
    canonical_model_id: str | None,
    release_year: int | None,
    delivered_price: float | None,
    benchmark_index: dict[tuple[str, str], HardwareBenchmark],
    peer_scores: dict[str, list[float]],
) -> dict:
    """Match a scored listing and return serialisable performance fields."""
    if category not in {"cpu", "gpu"}:
        return {"performance_status": "NOT_APPLICABLE"}

    # Claude's canonical id is the strongest key; title is the fallback for
    # older rows which pre-date canonical identity enrichment.
    candidates = [canonical_model_id, title]
    match = None
    match_method = None
    for candidate in candidates:
        norm = _normalise_for_category(category, candidate)
        if norm and (match := benchmark_index.get((category, norm))):
            match_method = "canonical_model" if candidate == canonical_model_id else "title_model"
            break
    if not match:
        return {
            "performance_status": "UNMATCHED",
            "performance_fit": "UNKNOWN",
            "performance_decision": "VERIFY_MODEL",
        }

    score = match.overall_score
    peers = peer_scores.get(category, [])
    percentile = _percentile(score, peers)
    price = float(delivered_price or 0)
    per_pound = round(score / price, 2) if score is not None and price > 0 else None
    fit, decision = _fit_label(release_year, percentile)
    return {
        "performance_status": "MATCHED",
        "performance_match_method": match_method,
        "performance_model": match.model,
        "performance_score": score,
        "gaming_score": match.gaming_score,
        "workstation_score": match.workstation_score,
        "performance_rank": (sorted(peers, reverse=True).index(score) + 1) if score in peers else None,
        "performance_peer_count": len(peers),
        "performance_percentile": percentile,
        "performance_per_pound": per_pound,
        "performance_source": match.benchmark_source,
        "performance_source_url": match.source_url,
        "performance_refreshed_at": match.last_refreshed_at,
        "performance_confidence": match.confidence_score,
        "performance_fit": fit,
        "performance_decision": decision,
    }
