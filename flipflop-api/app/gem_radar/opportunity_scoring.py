"""Explainable, gated opportunity scoring for Gem Radar.

Market value, economics, liquidity and build preference are deliberately
separate.  A strong price signal can never compensate for an identity,
evidence or profitability veto.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from math import floor
import re
from statistics import median
from typing import Any, Iterable


ACCESSORY_TERMS = {
    "backplate", "back plate", "bracket", "mount only", "fan only",
    "heatsink only", "cooler only", "empty box", "box only", "for parts",
    "spares or repair", "cable only", "adapter only", "waterblock",
    "riser cable", "extension cable", "gpu riser", "*box*",
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
    minimum_sold_comps: int = 3
    minimum_source_diversity: int = 2
    sold_lookback_days: int = 90
    super_discount_pct: float = -30.0
    gem_discount_pct: float = -20.0


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
        return CategoryEconomics(8.0, 25.0, 3.0, 15.0, 80.0, 60.0)
    if category in {"motherboard", "psu", "case"}:
        return CategoryEconomics(15.0, 22.0, 6.0, 16.0, 82.0, 65.0)
    if category == "gpu":
        return CategoryEconomics(25.0, 20.0, 12.0, 15.0, 83.0, 70.0)
    return CategoryEconomics(
        policy.super_profit, policy.super_roi_pct, policy.gem_profit,
        policy.gem_roi_pct, policy.super_score, policy.gem_score,
    )


_CLASSIFICATION_SCORE_BANDS: dict[str, tuple[float, float]] = {
    "SUPER_GEM": (85.0, 100.0),
    "GEM": (75.0, 84.9),
    "EVIDENCE_LIMITED_DEAL": (70.0, 74.9),
    "OK_DEAL": (65.0, 69.9),
    "AVERAGE_DEAL": (50.0, 64.9),
    "POOR_DEAL": (0.0, 49.9),
}


def score_within_classification(raw_score: float, classification: str) -> float:
    """Preserve ranking within a tier without contradicting the tier label."""
    band = _CLASSIFICATION_SCORE_BANDS.get(classification)
    if band is None:
        return max(0.0, min(100.0, raw_score))
    lower, upper = band
    return lower + (upper - lower) * max(0.0, min(100.0, raw_score)) / 100.0


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
        super_discount_pct=settings.deal_super_gem_threshold_pct,
        gem_discount_pct=settings.deal_gem_threshold_pct,
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
    basis: str = "SOLD_REFINED"
    realisation_factor: float = 1.0


@dataclass
class OpportunityResult:
    classification: str
    decision: str
    score: float
    expected_profit: float | None
    roi_pct: float | None
    walk_away_price: float | None
    liquidity_score: float | None
    desirability_score: float | None
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
    # Compatibility/model text frequently names the component an accessory
    # fits (for example an i3-12100 stock cooler or an RTX-ready PSU).  Those
    # names can fool CPK extraction, so veto strong product-type conflicts
    # independently of the extracted model.
    if category == "cpu" and re.search(
        r"\b(?:cpu|processor)\s+(?:cooler|fan|heatsink)\b|"
        r"\b(?:stock|replacement)\s+(?:cpu\s+)?(?:cooler|fan|heatsink)\b",
        lowered,
    ):
        flags.append("accessory_or_parts_listing")
    if category == "gpu" and re.search(
        r"\b(?:power supply|psu|atx\s*3(?:\.\d)?|80\s*\+?\s*(?:gold|platinum|bronze)|"
        r"\d{3,4}\s*w(?:att)?s?\b)",
        lowered,
    ):
        flags.append("category_identity_conflict")
    if category == "case" and re.search(
        r"\b(?:retaining clips?|panel clips?|replacement panel|dust filters?|case feet|thumbscrews?|"
        r"fan\s*(?:&|and)?\s*rgb controller|fan controller)\b",
        lowered,
    ):
        flags.append("accessory_or_parts_listing")
    if any(term in lowered for term in BUNDLE_TERMS):
        flags.append("bundle_listing")
    if category in COMPONENT_CATEGORIES and any(term in lowered for term in ("mini pc", "laptop", "notebook", "desktop computer")):
        flags.append("whole_system_misclassified_as_component")
    if category in COMPONENT_CATEGORIES and re.search(
        r"\b(gaming desktop|optiplex|thinkcentre|elitedesk|prodesk)\b|"
        r"\blegion\b.*\b(?:ram|ssd)\b|"
        r"\b(?:rtx|gtx)\s*\d{3,4}\b.*\b\d+gb\s+ram\b|"
        r"\b\d+gb\s+ram\b.*\b(?:rtx|gtx)\s*\d{3,4}\b",
        lowered,
    ):
        flags.append("whole_system_misclassified_as_component")
    if category in COMPONENT_CATEGORIES and re.search(
        r"\b(?:ram|memory)\b.*\b(?:and|\+)\b.*\b(?:cpu|processor|ryzen|core\s+i[3579])\b|"
        r"\b(?:cpu|processor|ryzen|core\s+i[3579])\b.*\b(?:and|\+)\b.*\b(?:ram|memory)\b",
        lowered,
    ):
        flags.append("bundle_listing")
    if re.search(r"\b\d+\s*/\s*\d+(?:\s*/\s*\d+)?\s*gb\b", lowered):
        flags.append("multi_variant_listing")
    capacities = set(re.findall(r"\b\d+(?:\.\d+)?\s*(?:tb|gb)\b", lowered))
    if category in {"ssd", "ram"} and len(capacities) > 1:
        flags.append("multi_variant_listing")
    if category == "gpu" and any(term in lowered for term in ("mining gpu", "mining card", "cmp 170")):
        flags.append("specialised_mining_hardware")
    if strategy != "retro_budget" and any(term in lowered for term in RETRO_PLATFORM_TERMS):
        flags.append("retro_platform_excluded")
    return flags


def desirability_score(title: str, cpk_data: dict[str, Any] | None, preferred: bool = False, inventory_fit: bool = False) -> float:
    """Rank build-market appeal independently from listing economics."""
    lowered = title.lower()
    data = cpk_data or {}
    if not data.get("category") or not data.get("brand") or not data.get("model"):
        return 0.0
    specs = data.get("specs") or {}
    category = str(data.get("category") or "").lower()
    brand = str(data.get("brand") or "").lower()
    score = {"gpu": 57.0, "cpu": 55.0, "motherboard": 50.0, "ram": 48.0,
             "ssd": 50.0, "psu": 45.0, "case": 44.0, "cooler": 43.0,
             "fan": 38.0}.get(category, 42.0)
    if brand in {"amd", "intel", "nvidia", "asus", "msi", "gigabyte", "corsair", "samsung", "crucial", "kingston", "noctua"}:
        score += 4
    socket = str(specs.get("socket", "")).lower()
    memory = str(specs.get("memory_type") or specs.get("type") or "").lower()
    interface = str(specs.get("interface", "")).lower()
    if socket == "am5": score += 14
    elif socket == "am4": score += 6
    elif socket in {"lga1700", "lga1851"}: score += 10
    if "ddr5" in memory or "ddr5" in lowered: score += 9
    elif "ddr4" in memory or "ddr4" in lowered: score += 3
    if "nvme" in interface or "nvme" in lowered or "pcie 4" in lowered: score += 9
    elif "sata" in interface or "sata ssd" in lowered: score += 2
    if category == "gpu" and re.search(r"\b(?:rtx\s*[345]\d{3}|rx\s*(?:6[7-9]|7)\d{2})\b", lowered): score += 8
    if category in {"ram", "ssd"} and re.search(r"\b(?:32|64)\s*gb\b|\b[12]\s*tb\b", lowered): score += 5
    if category == "psu" and re.search(r"\b(?:80\s*\+?\s*)?(?:gold|platinum|titanium)\b", lowered): score += 7
    if category == "case" and any(term in lowered for term in ("fans included", "with fans", "argb fans")): score += 8
    if category == "cooler" and any(term in lowered for term in ("aio", "liquid cpu", "240mm", "280mm", "360mm")): score += 8
    if any(term in lowered for term in RETRO_PLATFORM_TERMS): score -= 18
    if any(term in lowered for term in ("untested", "unknown condition", "damaged", "spares or repair")): score -= 12
    if preferred: score += 10
    if inventory_fit: score += 8
    return max(0.0, min(100.0, score))


RISK_PENALTIES = {
    "identity_incomplete": 35.0, "accessory_or_parts_listing": 55.0,
    "category_identity_conflict": 55.0, "whole_system_misclassified_as_component": 55.0,
    "bundle_listing": 35.0, "multi_variant_listing": 30.0,
    "specialised_mining_hardware": 35.0, "retro_platform_excluded": 25.0,
    "insufficient_same_condition_sold_comparables": 18.0,
    "insufficient_comparable_source_diversity": 15.0, "preliminary_sold_cohort": 10.0,
}


def risk_safety_score(flags: Iterable[str]) -> float:
    """Return 0-100 safety using flag severity rather than raw flag count."""
    penalty = sum(RISK_PENALTIES.get(flag, 20.0) for flag in set(flags))
    return max(0.0, min(100.0, 100.0 - penalty))


def sell_through_rate_pct(sold_count: int, active_count: int) -> float | None:
    """Return matched-cohort sell-through, or None when there is no cohort.

    The denominator intentionally includes both sold and live listings.  This
    is the conventional rate; ``active / sold`` is retained only as an
    optional supply-to-sales diagnostic, not called sell-through.
    """
    total = max(0, sold_count) + max(0, active_count)
    return None if total == 0 else max(0, sold_count) / total * 100.0


def liquidity_score(sold_count_90d: int, active_count: int,
                    watch_velocity: float | None, bid_velocity: float | None) -> float | None:
    """Return demand strength using sales volume and matched sell-through."""
    sell_through = sell_through_rate_pct(sold_count_90d, active_count)
    if sell_through is None and watch_velocity is None and bid_velocity is None:
        return None
    # Volume prevents a single sale from being over-valued; rate prevents a
    # large live supply from being mistaken for strong demand.  Together they
    # retain the existing 0-100 liquidity contribution (20% of deal score).
    score = min(55.0, max(0, sold_count_90d) * 9.0)
    if sell_through is not None:
        score += sell_through * 0.35
    if watch_velocity is not None: score += min(8.0, max(0.0, watch_velocity) * 4.0)
    if bid_velocity is not None: score += min(12.0, max(0.0, bid_velocity) * 12.0)
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
    elif market.source_diversity < policy.minimum_source_diversity and market.basis != "FIXED_RETAIL_CONTEXT":
        risk_flags.append("insufficient_comparable_source_diversity")

    liquidity = liquidity_score(sold_count_90d, active_count, watch_velocity, bid_velocity)
    desirability = desirability_score(title, cpk_data, preferred, inventory_fit)
    risk = risk_safety_score(risk_flags)

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
    # Median is the operational resale basis. The lower and upper quartiles
    # remain available on RobustMarket for downside/upside display, but deal
    # tier, profit, ROI and walk-away price must all use one coherent basis.
    resale_value = market.median
    ebay_fee = 0.0 if is_component else resale_value * policy.ebay_fee_pct / 100.0
    packaging = 0.0 if is_component else policy.packaging_cost
    testing = (0.0 if is_new else 3.0) if is_component else policy.testing_refurbishment_cost
    warranty_pct = (0.5 if is_new else 2.0) if is_component else policy.returns_warranty_pct
    warranty = resale_value * warranty_pct / 100.0
    costs = {
        "purchase": listing_price, "delivery": shipping, "ebay_fee": ebay_fee,
        "packaging": packaging, "testing_refurbishment": testing,
        "returns_warranty_reserve": warranty,
    }
    total_cost = sum(costs.values())
    profit = resale_value - total_cost
    roi = profit / total_cost * 100.0 if total_cost > 0 else 0.0
    non_purchase_cost = total_cost - listing_price
    walk_away = max(0.0, resale_value / 1.25 - non_purchase_cost)
    economic_score = max(0.0, min(100.0, (roi / economics.super_roi_pct) * 55.0 + (profit / economics.super_profit) * 45.0))
    score_parts = [(economic_score, .45), (desirability, .15), (market.confidence, .15), (risk, .05)]
    if liquidity is not None:
        score_parts.append((liquidity, .20))
    total_score = sum(value * weight for value, weight in score_parts) / sum(weight for _, weight in score_parts)
    provisional_evidence = "preliminary_sold_cohort" in risk_flags
    evidence_limited = provisional_evidence or market.sample_size < policy.minimum_sold_comps
    hard_identity_vetoes = {
        "identity_incomplete", "accessory_or_parts_listing", "category_identity_conflict",
        "whole_system_misclassified_as_component", "bundle_listing", "specialised_mining_hardware"
    }
    blocking_flags = [flag for flag in risk_flags if flag in hard_identity_vetoes]
    eligible = not blocking_flags
    evidence_label = "completed sales" if market.basis == "SOLD_REFINED" else "active market prices"
    reasons = [
        f"Resale basis uses the median of {market.sample_size} robust same-condition {evidence_label}; lower quartile remains the downside case.",
        f"Expected net profit £{profit:.2f}; ROI {roi:.1f}%; "
        + (f"liquidity {liquidity:.0f}/100." if liquidity is not None else "liquidity unknown (no demand evidence)."),
    ]
    sell_through = sell_through_rate_pct(sold_count_90d, active_count)
    if sell_through is not None:
        reasons.append(
            f"Sampled 90-day sell-through is {sell_through:.1f}% "
            f"({sold_count_90d} sold / {active_count} active matched listings)."
        )
    if market.basis == "BIN_ESTIMATED":
        reasons.append(
            f"BIN estimate applies a {100 * (1 - market.realisation_factor):.0f}% realisation haircut and lower confidence until sold evidence refines it."
        )
    elif market.basis in {"FIXED_RETAIL_ESTIMATED", "FIXED_RETAIL_CONTEXT"}:
        reasons.append("Fixed-price retailer evidence receives no offer/negotiation haircut; sold evidence can still refine confidence.")
    elif market.basis == "MIXED_ACTIVE_ESTIMATE":
        reasons.append("Mixed active evidence keeps fixed retailer prices intact and haircuts negotiable marketplace BIN prices.")
    if is_component:
        reasons.append("Component economics exclude build-level fulfilment costs, which are charged once to the completed build.")
        reasons.append(
            f"{category.upper()} gates: GEM £{economics.gem_profit:.0f}/{economics.gem_roi_pct:.0f}% ROI; "
            f"SUPER_GEM £{economics.super_profit:.0f}/{economics.super_roi_pct:.0f}% ROI."
        )
    emerging_profit_floor = min(policy.gem_profit, 10.0) if is_component else policy.gem_profit
    # Deal tier answers "how exceptional is the buy?"  Evidence and identity
    # remain hard gates, but liquidity/desirability rank urgency rather than
    # vetoing a genuine bargain.  The former all-gates-at-once rule made a
    # slow-moving item mathematically incapable of being a SUPER_GEM even at
    # a 60% discount with a strong comparable cohort.
    super_confidence_floor = max(55.0, policy.super_confidence - 25.0)
    gem_confidence_floor = max(50.0, policy.gem_confidence - 20.0)
    if blocking_flags:
        classification, decision = "INELIGIBLE", "IGNORE"
        reasons.append("A hard identity or market-quality veto prevents deal classification.")
    elif evidence_limited and profit >= emerging_profit_floor and roi >= 25 and market.confidence >= 40:
        classification, decision = "EVIDENCE_LIMITED_DEAL", "INVESTIGATE"
        reasons.append(
            f"Promising economics, but only {market.sample_size} robust comparable"
            f"{'s' if market.sample_size != 1 else ''}: verify identity and price manually before buying."
        )
    elif evidence_limited:
        classification, decision = "INSUFFICIENT_DATA", "INVESTIGATE"
        reasons.append("The comparable cohort is below the minimum evidence requirement and the provisional opportunity gates were not all met.")
    elif eligible and profit >= economics.super_profit and roi >= economics.super_roi_pct and market.confidence >= super_confidence_floor and liquidity is not None and liquidity >= policy.super_liquidity:
        classification, decision = "SUPER_GEM", "BUY_NOW"
    elif eligible and profit >= economics.gem_profit and roi >= economics.gem_roi_pct and market.confidence >= gem_confidence_floor and liquidity is not None and liquidity >= policy.gem_liquidity:
        classification, decision = "GEM", "BUY_NOW"
    elif eligible and profit >= economics.gem_profit and roi >= economics.gem_roi_pct:
        classification, decision = "EVIDENCE_LIMITED_DEAL", "INVESTIGATE"
        liquidity_text = "unknown" if liquidity is None else f"{liquidity:.0f}/100"
        reasons.append(
            f"Economics pass the {category.upper() or 'configured'} GEM gates, but "
            f"market confidence is {market.confidence:.0f}/100 (needs {gem_confidence_floor:.0f}) "
            f"and liquidity is {liquidity_text} (needs {policy.gem_liquidity:.0f}/100)."
        )
    elif profit > 0 and eligible:
        classification, decision = "OK_DEAL", "MAKE_OFFER"
    elif profit > 0:
        classification, decision = "AVERAGE_DEAL", "INVESTIGATE"
    else:
        classification, decision = "POOR_DEAL", "IGNORE"
    tier_aligned_score = score_within_classification(total_score, classification)
    return OpportunityResult(classification, decision, round(tier_aligned_score, 1), round(profit, 2), round(roi, 2), round(walk_away, 2), None if liquidity is None else round(liquidity, 1), round(desirability, 1), round(risk, 1), market, eligible, reasons, risk_flags, {k: round(v, 2) for k, v in costs.items()})
