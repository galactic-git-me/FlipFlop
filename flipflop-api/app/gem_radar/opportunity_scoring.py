"""Explainable, gated opportunity scoring for Gem Radar.

Market value, economics, liquidity and build preference are deliberately
separate.  A strong price signal can never compensate for an identity,
evidence or profitability veto.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from math import floor
from statistics import median
from typing import Any, Iterable


ACCESSORY_TERMS = {
    "backplate", "back plate", "bracket", "mount only", "fan only",
    "heatsink only", "cooler only", "empty box", "box only", "for parts",
    "spares or repair", "cable only", "adapter only", "waterblock",
}
BUNDLE_TERMS = {"job lot", "bundle of", "mystery box", "assorted parts"}
RETRO_PLATFORM_TERMS = {"am3", "am3+", "ddr3", "ddr2", "socket 775"}
COMPONENT_CATEGORIES = {"cpu", "gpu", "motherboard", "ram", "ssd", "psu", "case", "cooler", "fan"}


@dataclass(frozen=True)
class OpportunityPolicy:
    super_profit: float = 50.0
    super_roi_pct: float = 25.0
    super_confidence: float = 80.0
    super_liquidity: float = 60.0
    super_score: float = 85.0
    gem_profit: float = 30.0
    gem_roi_pct: float = 18.0
    gem_confidence: float = 70.0
    gem_liquidity: float = 45.0
    gem_score: float = 75.0
    delivery_fallback: float = 15.0
    ebay_fee_pct: float = 0.0
    packaging_cost: float = 6.0
    testing_refurbishment_cost: float = 10.0
    returns_warranty_pct: float = 5.0
    minimum_sold_comps: int = 5
    minimum_source_diversity: int = 2
    sold_lookback_days: int = 90


@dataclass(frozen=True)
class CategoryEconomics:
    super_profit: float
    super_roi_pct: float
    gem_profit: float
    gem_roi_pct: float
    super_score: float
    gem_score: float


def category_economics(category: str, policy: OpportunityPolicy) -> CategoryEconomics:
    """Cash-profit gates scaled to the capital normally tied up by a part.

    Confidence, liquidity and overall-score gates remain unchanged; these
    values only prevent a £6 CPU and a £600 GPU being judged by one cash
    hurdle. Complete systems continue to use the configured global policy.
    """
    if category in {"cpu", "ram", "ssd", "cooler", "fan"}:
        return CategoryEconomics(15.0, 50.0, 5.0, 18.0, 80.0, 60.0)
    if category in {"motherboard", "psu", "case"}:
        return CategoryEconomics(25.0, 40.0, 10.0, 20.0, 82.0, 65.0)
    if category == "gpu":
        return CategoryEconomics(40.0, 30.0, 20.0, 18.0, 83.0, 70.0)
    return CategoryEconomics(
        policy.super_profit, policy.super_roi_pct, policy.gem_profit,
        policy.gem_roi_pct, policy.super_score, policy.gem_score,
    )


async def load_opportunity_policy(db) -> OpportunityPolicy:
    from sqlalchemy import select
    from app.models.app_settings import AppSettings
    settings = (await db.execute(select(AppSettings).where(AppSettings.name == "default"))).scalar_one_or_none()
    if settings is None:
        return OpportunityPolicy()
    return OpportunityPolicy(
        super_profit=settings.opportunity_super_profit_gbp,
        super_roi_pct=settings.opportunity_super_roi_pct,
        super_confidence=settings.opportunity_super_confidence,
        super_liquidity=settings.opportunity_super_liquidity,
        super_score=settings.opportunity_super_score,
        gem_profit=settings.opportunity_gem_profit_gbp,
        gem_roi_pct=settings.opportunity_gem_roi_pct,
        gem_confidence=settings.opportunity_gem_confidence,
        gem_liquidity=settings.opportunity_gem_liquidity,
        gem_score=settings.opportunity_gem_score,
        delivery_fallback=settings.opportunity_delivery_fallback_gbp,
        ebay_fee_pct=settings.opportunity_ebay_fee_pct,
        packaging_cost=settings.opportunity_packaging_gbp,
        testing_refurbishment_cost=settings.opportunity_testing_refurbishment_gbp,
        returns_warranty_pct=settings.opportunity_returns_warranty_pct,
        minimum_sold_comps=settings.opportunity_minimum_sold_comps,
        minimum_source_diversity=settings.opportunity_minimum_source_diversity,
    )


@dataclass(frozen=True)
class SoldComparable:
    price: float
    postage: float = 0.0
    source_url: str | None = None
    observed_days_ago: float = 0.0

    @property
    def delivered_price(self) -> float:
        return self.price + self.postage


@dataclass(frozen=True)
class RobustMarket:
    lower: float
    median: float
    upper: float
    conservative_resale: float
    sample_size: int
    raw_sample_size: int
    source_diversity: int
    spread_pct: float
    confidence: float
    comparable_urls: tuple[str, ...]


@dataclass
class OpportunityResult:
    classification: str
    decision: str
    score: float
    expected_profit: float | None
    roi_pct: float | None
    walk_away_price: float | None
    liquidity_score: float
    desirability_score: float
    risk_score: float
    market: RobustMarket | None
    eligible: bool
    reasons: list[str] = field(default_factory=list)
    risk_flags: list[str] = field(default_factory=list)
    cost_breakdown: dict[str, float] = field(default_factory=dict)

    def explanation(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["market"] = asdict(self.market) if self.market else None
        return payload


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("percentile requires values")
    position = (len(ordered) - 1) * percentile
    lower = floor(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _source_key(url: str | None) -> str:
    if not url:
        return "unknown"
    lowered = url.lower().split("?", 1)[0].rstrip("/")
    return lowered


def robust_sold_market(
    comparables: Iterable[SoldComparable],
    *,
    subject_listing_id: str,
    policy: OpportunityPolicy,
) -> RobustMarket | None:
    """Build a unique, leave-one-out, MAD/IQR-controlled sold cohort."""
    unique: dict[str, SoldComparable] = {}
    for comp in comparables:
        if comp.delivered_price <= 0:
            continue
        key = _source_key(comp.source_url)
        if subject_listing_id and subject_listing_id.lower() in key:
            continue
        unique.setdefault(key if key != "unknown" else f"unknown:{comp.delivered_price:.2f}", comp)
    raw = list(unique.values())
    if len(raw) < policy.minimum_sold_comps:
        return None

    values = [c.delivered_price for c in raw]
    centre = median(values)
    deviations = [abs(value - centre) for value in values]
    mad = median(deviations)
    if mad > 0:
        # 3.5 modified-z is conservative for small marketplace cohorts.
        filtered = [c for c in raw if 0.6745 * abs(c.delivered_price - centre) / mad <= 3.5]
    else:
        q1, q3 = _percentile(values, 0.25), _percentile(values, 0.75)
        iqr = q3 - q1
        filtered = [c for c in raw if q1 - 1.5 * iqr <= c.delivered_price <= q3 + 1.5 * iqr]

    if len(filtered) < policy.minimum_sold_comps:
        return None
    filtered_values = [c.delivered_price for c in filtered]
    lower = _percentile(filtered_values, 0.25)
    mid = median(filtered_values)
    upper = _percentile(filtered_values, 0.75)
    # Sold rows currently originate mainly from eBay; until seller identity is
    # persisted, diversity means independently identified sold listings rather
    # than marketplace domains (which would make every eBay-only cohort fail).
    diversity = len({_source_key(c.source_url) for c in filtered})
    spread = ((upper - lower) / mid * 100.0) if mid else 100.0
    sample_component = min(55.0, len(filtered) * 8.0)
    diversity_component = min(20.0, diversity * 10.0)
    spread_component = max(0.0, 25.0 - min(25.0, spread / 2.0))
    confidence = min(100.0, sample_component + diversity_component + spread_component)
    return RobustMarket(
        lower=round(lower, 2), median=round(mid, 2), upper=round(upper, 2),
        conservative_resale=round(lower, 2), sample_size=len(filtered),
        raw_sample_size=len(raw), source_diversity=diversity,
        spread_pct=round(spread, 2), confidence=round(confidence, 1),
        comparable_urls=tuple(c.source_url for c in filtered if c.source_url),
    )


def identity_gates(title: str, cpk_data: dict[str, Any] | None, strategy: str = "standard") -> list[str]:
    lowered = title.lower()
    flags: list[str] = []
    category = (cpk_data or {}).get("category")
    brand = (cpk_data or {}).get("brand")
    model = (cpk_data or {}).get("model")
    if not category or not brand or not model:
        flags.append("identity_incomplete")
    if any(term in lowered for term in ACCESSORY_TERMS):
        flags.append("accessory_or_parts_listing")
    if any(term in lowered for term in BUNDLE_TERMS):
        flags.append("bundle_listing")
    if strategy != "retro_budget" and any(term in lowered for term in RETRO_PLATFORM_TERMS):
        flags.append("retro_platform_excluded")
    return flags


def desirability_score(title: str, cpk_data: dict[str, Any] | None, preferred: bool = False, inventory_fit: bool = False) -> float:
    lowered = title.lower()
    specs = (cpk_data or {}).get("specs") or {}
    score = 50.0
    socket = str(specs.get("socket", "")).lower()
    memory = str(specs.get("memory_type") or specs.get("type") or "").lower()
    interface = str(specs.get("interface", "")).lower()
    if socket == "am5": score += 15
    elif socket == "am4": score += 7
    if "ddr5" in memory or "ddr5" in lowered: score += 10
    elif "ddr4" in memory or "ddr4" in lowered: score += 4
    if "nvme" in interface or "nvme" in lowered: score += 10
    elif "sata" in interface or "sata ssd" in lowered: score += 4
    if "case" == (cpk_data or {}).get("category") and any(term in lowered for term in ("fans included", "with fans", "argb fans")): score += 8
    if (cpk_data or {}).get("category") == "cooler" and any(term in lowered for term in ("aio", "liquid cpu", "240mm", "280mm", "360mm")): score += 8
    if preferred: score += 10
    if inventory_fit: score += 8
    return max(0.0, min(100.0, score))


def score_opportunity(
    *, listing_price: float, title: str, cpk_data: dict[str, Any] | None,
    market: RobustMarket | None, sold_count_90d: int, active_count: int,
    watch_velocity: float | None, bid_velocity: float | None,
    policy: OpportunityPolicy, delivery_cost: float | None = None,
    preferred: bool = False, inventory_fit: bool = False,
    strategy: str = "standard", extra_risk_flags: Iterable[str] = (),
    listing_condition: str | None = None,
) -> OpportunityResult:
    risk_flags = identity_gates(title, cpk_data, strategy) + list(extra_risk_flags)
    if market is None:
        risk_flags.append("insufficient_same_condition_sold_comparables")
    elif market.source_diversity < policy.minimum_source_diversity:
        risk_flags.append("insufficient_comparable_source_diversity")

    liquidity = min(70.0, sold_count_90d * 7.0)
    if active_count > 0:
        liquidity += max(-20.0, min(15.0, (sold_count_90d / active_count - 0.5) * 20.0))
    if watch_velocity is not None: liquidity += min(8.0, watch_velocity * 4.0)
    if bid_velocity is not None: liquidity += min(12.0, bid_velocity * 12.0)
    liquidity = max(0.0, min(100.0, liquidity))
    desirability = desirability_score(title, cpk_data, preferred, inventory_fit)
    risk = max(0.0, 100.0 - len(risk_flags) * 30.0)

    if market is None:
        identity_vetoes = [flag for flag in risk_flags if flag != "insufficient_same_condition_sold_comparables"]
        if identity_vetoes:
            return OpportunityResult(
                "INELIGIBLE", "IGNORE", 0.0, None, None, None,
                liquidity, desirability, risk, None, False,
                ["A hard identity veto prevents deal classification."], risk_flags,
            )
        return OpportunityResult(
            "INSUFFICIENT_DATA", "INVESTIGATE", 0.0, None, None, None,
            liquidity, desirability, risk, None, False,
            ["A same-condition completed-sale cohort is required before a buy classification."], risk_flags,
        )

    category = str((cpk_data or {}).get("category") or "").lower()
    is_component = category in COMPONENT_CATEGORIES
    economics = category_economics(category, policy)
    is_new = (listing_condition or "").lower() == "new"
    # Gem Radar sources parts for incorporation into a build. Its listing
    # price is already the landed acquisition price, while outbound delivery,
    # packaging, eBay fees and whole-build QA are charged once by the build
    # economics layer. Applying them to every part double-counts those costs.
    shipping = 0.0 if is_component else (policy.delivery_fallback if delivery_cost is None else delivery_cost)
    ebay_fee = 0.0 if is_component else market.conservative_resale * policy.ebay_fee_pct / 100.0
    packaging = 0.0 if is_component else policy.packaging_cost
    testing = (0.0 if is_new else 3.0) if is_component else policy.testing_refurbishment_cost
    warranty_pct = (0.5 if is_new else 2.0) if is_component else policy.returns_warranty_pct
    warranty = market.conservative_resale * warranty_pct / 100.0
    costs = {
        "purchase": listing_price, "delivery": shipping, "ebay_fee": ebay_fee,
        "packaging": packaging, "testing_refurbishment": testing,
        "returns_warranty_reserve": warranty,
    }
    total_cost = sum(costs.values())
    profit = market.conservative_resale - total_cost
    roi = profit / total_cost * 100.0 if total_cost > 0 else 0.0
    non_purchase_cost = total_cost - listing_price
    walk_away = max(0.0, market.conservative_resale / 1.25 - non_purchase_cost)
    economic_score = max(0.0, min(100.0, (roi / economics.super_roi_pct) * 55.0 + (profit / economics.super_profit) * 45.0))
    total_score = economic_score * .45 + liquidity * .20 + desirability * .15 + market.confidence * .15 + risk * .05
    provisional_evidence = "preliminary_sold_cohort" in risk_flags
    blocking_flags = [flag for flag in risk_flags if flag != "preliminary_sold_cohort"]
    eligible = not risk_flags
    reasons = [
        f"Conservative resale uses the lower quartile of {market.sample_size} robust same-condition sold comparables.",
        f"Expected net profit £{profit:.2f}; ROI {roi:.1f}%; liquidity {liquidity:.0f}/100.",
    ]
    if is_component:
        reasons.append("Component economics exclude build-level fulfilment costs, which are charged once to the completed build.")
        reasons.append(
            f"{category.upper()} gates: GEM £{economics.gem_profit:.0f}/{economics.gem_roi_pct:.0f}% ROI; "
            f"SUPER_GEM £{economics.super_profit:.0f}/{economics.super_roi_pct:.0f}% ROI."
        )
    emerging_profit_floor = min(policy.gem_profit, 10.0) if is_component else policy.gem_profit
    if blocking_flags:
        classification, decision = "INELIGIBLE", "IGNORE"
        reasons.append("A hard identity or market-quality veto prevents deal classification.")
    elif provisional_evidence and profit >= emerging_profit_floor and roi >= 25 and market.confidence >= 40 and liquidity >= 20 and desirability >= 55:
        classification, decision = "EMERGING_OPPORTUNITY", "INVESTIGATE"
        reasons.append("Promising economics, but only 3–4 robust sold comparables: verify manually before buying.")
    elif provisional_evidence:
        classification, decision = "INSUFFICIENT_DATA", "INVESTIGATE"
        reasons.append("Only 3–4 sold comparables are available and the provisional opportunity gates were not all met.")
    elif eligible and profit >= economics.super_profit and roi >= economics.super_roi_pct and market.confidence >= policy.super_confidence and liquidity >= policy.super_liquidity and total_score >= economics.super_score:
        classification, decision = "SUPER_GEM", "BUY_NOW"
    elif eligible and profit >= economics.gem_profit and roi >= economics.gem_roi_pct and market.confidence >= policy.gem_confidence and liquidity >= policy.gem_liquidity and total_score >= economics.gem_score:
        classification, decision = "GEM", "BUY_NOW"
    elif profit > 0 and eligible:
        classification, decision = "OK_DEAL", "MAKE_OFFER"
    elif profit > 0:
        classification, decision = "AVERAGE_DEAL", "INVESTIGATE"
    else:
        classification, decision = "POOR_DEAL", "IGNORE"
    return OpportunityResult(classification, decision, round(total_score, 1), round(profit, 2), round(roi, 2), round(walk_away, 2), round(liquidity, 1), round(desirability, 1), round(risk, 1), market, eligible, reasons, risk_flags, {k: round(v, 2) for k, v in costs.items()})
