"""Deterministic pricing evidence service for the runtime Pricing agent.

This module deliberately does not own scheduler startup or persistence schema.
It builds provenance-preserving cohorts from the existing Gem Radar observation
ledger and returns price movement signals for the shared agent handoff.

Never combine active asks with completed sales, or new with used/refurbished.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from statistics import median
from typing import Iterable, Mapping, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.gem_radar_observation import GemRadarListingObservation
from app.models.gem_radar_scored_listing import GemRadarScoredListing
from app.models.gem_radar_sold_observation import GemRadarSoldObservation

MIN_COMPARABLES = 3
OUTLIER_MODIFIED_Z_LIMIT = 3.5


@dataclass(frozen=True)
class PriceObservation:
    identity: str
    source: str
    observed_at: datetime
    condition: str
    market_kind: str
    item_gbp: Decimal
    delivery_gbp: Decimal | None
    geography: str
    reference: str | None
    listing_id: str | None = None
    confidence: float | None = None

    @property
    def delivered_gbp(self) -> Decimal | None:
        if self.delivery_gbp is None or self.item_gbp <= 0 or self.delivery_gbp < 0:
            return None
        return self.item_gbp + self.delivery_gbp


@dataclass(frozen=True)
class PriceRangeEvidence:
    identity: str
    condition: str
    market_kind: str
    geography: str
    currency: str
    lower_gbp: Decimal | None
    median_gbp: Decimal | None
    upper_gbp: Decimal | None
    observed_from: datetime | None
    observed_to: datetime | None
    raw_sample_count: int
    accepted_sample_count: int
    excluded_outlier_count: int
    sources: tuple[str, ...]
    references: tuple[str, ...]
    confidence: str
    status: str


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _robust_values(values: Sequence[Decimal]) -> tuple[list[Decimal], int]:
    """MAD modified-z filtering (3.5) with small-sample and collapse guards."""
    ordered = sorted(values)
    if len(ordered) < MIN_COMPARABLES:
        return ordered, 0
    centre = Decimal(str(median(ordered)))
    deviations = [abs(value - centre) for value in ordered]
    mad = Decimal(str(median(deviations)))
    if mad == 0:
        return ordered, 0
    kept = [value for value, deviation in zip(ordered, deviations)
            if Decimal("0.6745") * deviation / mad <= Decimal(str(OUTLIER_MODIFIED_Z_LIMIT))]
    if len(kept) < MIN_COMPARABLES:
        return ordered, 0
    return kept, len(ordered) - len(kept)


def summarize_cohort(observations: Iterable[PriceObservation]) -> PriceRangeEvidence:
    rows = list(observations)
    identities = {(r.identity, r.condition, r.market_kind, r.geography) for r in rows}
    if len(identities) > 1:
        raise ValueError("A price cohort must have one exact identity, condition, market type and geography")
    exemplar = rows[0] if rows else None
    eligible = [r for r in rows if r.delivered_gbp is not None]
    values, outliers = _robust_values([r.delivered_gbp for r in eligible if r.delivered_gbp is not None])
    enough = len(values) >= MIN_COMPARABLES
    return PriceRangeEvidence(
        identity=exemplar.identity if exemplar else "",
        condition=exemplar.condition if exemplar else "",
        market_kind=exemplar.market_kind if exemplar else "",
        geography=exemplar.geography if exemplar else "GB",
        currency="GBP",
        lower_gbp=values[0].quantize(Decimal(".01")) if enough else None,
        median_gbp=Decimal(str(median(values))).quantize(Decimal(".01")) if enough else None,
        upper_gbp=values[-1].quantize(Decimal(".01")) if enough else None,
        observed_from=min((_as_utc(r.observed_at) for r in eligible), default=None),
        observed_to=max((_as_utc(r.observed_at) for r in eligible), default=None),
        raw_sample_count=len(rows),
        accepted_sample_count=len(values),
        excluded_outlier_count=outliers,
        sources=tuple(sorted({r.source for r in eligible})),
        references=tuple(sorted({r.reference for r in eligible if r.reference})),
        confidence="high" if enough and len({r.source for r in eligible}) >= 3 else
                   "medium" if enough and len({r.source for r in eligible}) >= 2 else
                   "low" if enough else "insufficient",
        status="usable" if enough else "insufficient_sample",
    )


def percentage_change(previous: Decimal, current: Decimal) -> Decimal | None:
    if previous <= 0 or current <= 0:
        return None
    return ((current - previous) / previous * Decimal(100)).quantize(Decimal(".01"))


def price_change_signal(*, identity: str, condition: str, geography: str,
                        previous: PriceRangeEvidence, current: PriceRangeEvidence,
                        threshold_percent: Decimal = Decimal("5")) -> dict | None:
    """Propose a comparable-median event; caller persists via shared handoff."""
    if (previous.status != "usable" or current.status != "usable"
            or (previous.identity, previous.condition, previous.geography, previous.market_kind)
            != (current.identity, current.condition, current.geography, current.market_kind)
            or previous.median_gbp is None or current.median_gbp is None):
        return None
    delta = percentage_change(previous.median_gbp, current.median_gbp)
    if delta is None or abs(delta) <= threshold_percent:
        return None
    return {
        "event_type": "component_market_price_changed",
        "idempotency_key": f"pricing:{identity}:{condition}:{geography}:{current.market_kind}:{current.observed_to.isoformat() if current.observed_to else 'unknown'}",
        "identity": identity, "condition": condition, "geography": geography,
        "market_kind": current.market_kind, "previous_median_gbp": str(previous.median_gbp),
        "current_median_gbp": str(current.median_gbp), "change_percent": str(delta),
        "evidence": asdict(current),
    }


def evaluate_autonomous_reprice(*, proposed_price_gbp: Decimal, current_price_gbp: Decimal,
                                contribution_gbp: Decimal, contribution_floor_gbp: Decimal,
                                configured_movement_cap_percent: Decimal = Decimal("10")) -> dict:
    """Fail closed against canonical policy: default 10%, maximum 25%, >=15% floor is upstream."""
    cap = min(Decimal("25"), max(Decimal("0"), configured_movement_cap_percent))
    change = percentage_change(current_price_gbp, proposed_price_gbp)
    blockers = []
    if change is None:
        blockers.append("missing_or_invalid_price")
    elif abs(change) > cap:
        blockers.append("movement_cap_exceeded")
    if contribution_gbp < contribution_floor_gbp:
        blockers.append("minimum_contribution_floor_failed")
    return {"allowed": not blockers, "change_percent": str(change) if change is not None else None,
            "movement_cap_percent": str(cap), "blockers": blockers,
            "policy": "autonomous_within_configured_cap_and_contribution_floor"}


async def load_component_price_cohorts(db: AsyncSession, *, lookback_days: int = 30,
                                       now: datetime | None = None) -> dict[tuple[str, str, str, str], PriceRangeEvidence]:
    """Load current 30-day component observation cohorts from existing ledgers.

    Active observations and sold observations are intentionally separate keys.
    Exact CPK identity is required; records without a CPK are not promoted into
    a shared product cohort. Current statuses are observations only and do not
    certify stock or checkout availability.
    """
    now = _as_utc(now or datetime.now(timezone.utc))
    cutoff = now - timedelta(days=lookback_days)
    result: dict[tuple[str, str, str, str], list[PriceObservation]] = {}

    active_rows = (await db.execute(select(GemRadarListingObservation, GemRadarScoredListing.cpk).join(
        GemRadarScoredListing, GemRadarScoredListing.listing_id == GemRadarListingObservation.listing_id
    ).where(
        GemRadarListingObservation.observed_at >= cutoff.replace(tzinfo=None),
        GemRadarListingObservation.source.is_not(None),
    ))).all()
    latest_active: dict[str, tuple[GemRadarListingObservation, str | None]] = {}
    for row, cpk in active_rows:
        previous = latest_active.get(row.listing_id)
        if previous is None or _as_utc(row.observed_at) > _as_utc(previous[0].observed_at):
            latest_active[row.listing_id] = (row, cpk)
    for row, cpk in latest_active.values():
        identity = str(cpk or "").strip()
        if not identity:
            continue
        condition = str(row.condition_normalised or "").lower()
        if condition not in {"new", "used", "refurbished"}:
            continue
        observation = PriceObservation(identity, str(row.source), row.observed_at, condition, "active",
            Decimal(str(row.item_price)), Decimal(str(row.postage_price)) if row.postage_price is not None else None,
            "GB", row.commercial_source_evidence.get("url") if isinstance(row.commercial_source_evidence, dict) else None,
            str(row.listing_id))
        result.setdefault((identity, condition, "active", "GB"), []).append(observation)

    sold_rows = (await db.execute(select(GemRadarSoldObservation).where(
        GemRadarSoldObservation.observed_at >= cutoff.replace(tzinfo=None),
        GemRadarSoldObservation.cpk.is_not(None),
    ))).scalars().all()
    latest_sold: dict[str, GemRadarSoldObservation] = {}
    for row in sold_rows:
        unique_key = row.source_url or f"{row.match_key}:{row.condition}:{row.price}:{row.postage}"
        previous = latest_sold.get(unique_key)
        if previous is None or _as_utc(row.observed_at) > _as_utc(previous.observed_at):
            latest_sold[unique_key] = row
    for row in latest_sold.values():
        identity = str(row.cpk or "").strip()
        condition = str(row.condition or "").lower()
        if not identity or condition not in {"new", "used"}:
            continue
        observation = PriceObservation(identity, "ebay_sold", row.observed_at, condition, "sold",
            Decimal(str(row.price)), Decimal(str(row.postage)) if row.postage is not None else None,
            "GB", row.source_url, confidence=row.identity_confidence)
        result.setdefault((identity, condition, "sold", "GB"), []).append(observation)

    return {key: summarize_cohort(rows) for key, rows in result.items()}


def estimate_build_value(component_ranges: Mapping[tuple[str, str, str, str], PriceRangeEvidence],
                         component_identities: Mapping[str, str], *, condition: str = "new") -> dict:
    """Sum comparable component market medians; never substitutes for quote economics."""
    lookup = lambda identity: component_ranges.get((identity, condition, "active", "GB"))
    missing = [role for role, identity in component_identities.items()
               if (evidence := lookup(identity)) is None
               or evidence.status != "usable" or evidence.median_gbp is None
               or evidence.condition != condition or evidence.market_kind != "active"]
    if missing:
        return {"status": "insufficient_component_evidence", "missing_roles": missing,
                "market_value_median_gbp": None, "components": {}}
    rows = {role: {"identity": identity, "median_gbp": str(lookup(identity).median_gbp),
                   "sources": list(lookup(identity).sources),
                   "sample_count": lookup(identity).accepted_sample_count}
            for role, identity in component_identities.items()}
    total = sum((Decimal(value["median_gbp"]) for value in rows.values()), Decimal("0"))
    return {"status": "component_sum_estimate_only", "market_value_median_gbp": str(total.quantize(Decimal(".01"))),
            "components": rows, "condition": condition, "geography": "GB",
            "limitation": "Component medians are not evidence of complete-PC market value or profitable selling price."}


def load_pricing_skill() -> str | None:
    """Return pricing agent skill text when root has installed the canonical file."""
    from pathlib import Path
    path = Path(__file__).resolve().parents[1] / "agent_skills" / "pricing" / "SKILL.md"
    return path.read_text(encoding="utf-8") if path.exists() else None
