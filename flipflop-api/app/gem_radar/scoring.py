"""Deterministic 0-10 deal scoring (PRD §15-18, §21-22).

Every input here is either a real number extracted from the listing/
benchmarks, or an explicit neutral default when data is genuinely absent
(e.g. seller feedback isn't shown on eBay search-result cards) — never a
value invented to make the score look more confident than the evidence
supports. Claude is not involved in this module at all; see
claude_screening.py for where Claude assists (identity/risk/bundles only).
"""
from __future__ import annotations

from app.gem_radar.schemas import (
    BenchmarkStat,
    Classification,
    Decision,
    ExtractedListing,
    Identity,
    OfferStrategy,
    PriceBundle,
    RiskFlag,
)

# PRD §15.2 weighted model, minus seller_trust and time_sensitivity (removed
# — both depended on fields the extension's extraction layer can never
# actually populate in practice: eBay's search-result-card markup exposes no
# seller element at all, and auction_end_at is hardcoded null in every
# extraction path. Locked at their neutral defaults, those two sub-scores
# were pure ceiling tax: every listing paid their combined weight against a
# permanently-midpoint input, capping the achievable deal_score below the
# SUPER_GEM threshold no matter what. Their weight is redistributed
# proportionally across the remaining 5 components so they still sum to 1.0,
# rather than left as a static discount every score takes for two inputs
# that never varied. _REMAINING_WEIGHT_SUM MUST equal the sum of the five
# numerators below (0.35+0.15+0.10+0.10+0.05=0.75) — it was previously
# hardcoded to 0.80, which silently compressed every deal_score to 93.75% of
# its intended 0-10 scale (a perfect listing scored 9.375, not 10.0), pushing
# listings near a classification boundary down a tier (e.g. GEM instead of
# SUPER_GEM) without ever throwing an error.
_REMAINING_WEIGHT_SUM = 0.35 + 0.15 + 0.10 + 0.10 + 0.05
WEIGHT_SOLD_ADVANTAGE = 0.35 / _REMAINING_WEIGHT_SUM
WEIGHT_BIN_ADVANTAGE = 0.15 / _REMAINING_WEIGHT_SUM
WEIGHT_COMPARABLE_QUALITY = 0.10 / _REMAINING_WEIGHT_SUM
WEIGHT_CONDITION_CONFIDENCE = 0.10 / _REMAINING_WEIGHT_SUM
WEIGHT_LISTING_COMPLETENESS = 0.05 / _REMAINING_WEIGHT_SUM

CLASSIFICATION_BOUNDARIES: list[tuple[float, Classification]] = [
    (8.5, "SUPER_GEM"),
    (7.5, "GEM"),
    (6.5, "OK_DEAL"),
    (5.0, "AVERAGE_DEAL"),
]

# Hard sanity ceiling per category (mirrors app.services.part_gem_scorer's
# CATEGORY_BOUNDS). A relative discount alone ("X% below our own benchmark")
# is not sufficient evidence for a high-ticket item to be a genuine flip
# opportunity — the benchmark itself can be wrong (see _remove_iqr_outliers'
# docstring in benchmarks.py) and a large absolute outlay for a marginal %
# saving is a different risk profile than a small one. Above this price, a
# listing is capped at OK_DEAL regardless of computed score; it still
# surfaces (nothing is hidden), it just never gets the BUY_NOW-on-sight
# treatment GEM/SUPER_GEM implies.
CATEGORY_PRICE_CEILINGS: dict[str, float] = {
    "gpu": 1500.0,
    "ram": 500.0,
    "ssd": 600.0,
    "cpu": 1000.0,
    "psu": 400.0,
    "motherboard": 600.0,
    "case": 400.0,
    "cooler": 200.0,
}

# Benchmark labels backed by a real transaction price (completed eBay sale)
# or a single live retail price (Amazon) count as verified outright.
def _is_verified_price_source(benchmark_label: str) -> bool:
    return "sold" in benchmark_label or "amazon" in benchmark_label


# A listing is a SUPER_GEM if it's priced in the lower tail of the market —
# an outlier lower in an otherwise normal distribution. This is the deal: not
# "tight consensus + 50% off" (impossible), but "real market variation + you
# found the cheapest instance."
_OUTLIER_PERCENTILE = 0.25  # Bottom 25th percentile = genuine bargain


def _is_outlier_lower(price: float, market_stat: BenchmarkStat | None) -> bool:
    """True if price is in the lower tail of observed market prices. With only
    min/median/max available, the lower tail is approximated as <= median.
    A listing priced at/below the observed median is a genuine bargain relative
    to the typical market price."""
    if market_stat is None or market_stat.median is None or market_stat.median <= 0:
        return False
    return price <= market_stat.median


def classify(
    score: float,
    benchmark_label: str | None = None,
    category: str | None = None,
    price: float | None = None,
    market_stat: BenchmarkStat | None = None,
) -> Classification:
    classification: Classification = "POOR_DEAL"
    for threshold, label in CLASSIFICATION_BOUNDARIES:
        if score >= threshold:
            classification = label
            break

    # SUPER_GEM requires either:
    # 1. A verified source (sold comps or Amazon), OR
    # 2. An outlier-lower price (at or below the median observed market price)
    if classification == "SUPER_GEM":
        is_verified = benchmark_label is not None and _is_verified_price_source(benchmark_label)
        if not is_verified and (price is None or market_stat is None):
            classification = "GEM"
        elif not is_verified and market_stat is not None:
            if not _is_outlier_lower(price or float('inf'), market_stat):
                classification = "GEM"

    if classification in ("SUPER_GEM", "GEM") and category is not None and price is not None:
        ceiling = CATEGORY_PRICE_CEILINGS.get(category)
        if ceiling is not None and price > ceiling:
            classification = "OK_DEAL"

    return classification


def _price_advantage_subscore(actual_delivered: float, benchmark: BenchmarkStat) -> float:
    """0-100: how far below the benchmark median the actual price sits.
    0% below market -> 50 (neutral), 50%+ below -> 100, above market -> <50.
    """
    if benchmark.status != "ok" or benchmark.median is None or benchmark.median <= 0:
        return 50.0  # neutral — no evidence either way, not a penalty
    variance_pct = (benchmark.median - actual_delivered) / benchmark.median * 100
    return max(0.0, min(100.0, 50.0 + variance_pct))


def pick_condition_benchmark(condition: str, prices: PriceBundle) -> tuple[BenchmarkStat, str]:
    """PRD §13 benchmark priority chain. Returns the benchmark actually used
    and a label describing which tier of the chain supplied it — this label
    feeds directly into confidenceScore and the audit trail, never hidden.
    """
    if condition in ("new", "new_other"):
        chain = [
            (prices.ebay_new_sold, "exact_sku_new_sold"),
            (prices.ebay_new_bin, "exact_sku_new_bin"),
            (prices.amazon_uk_new, "amazon_uk_new"),
        ]
    elif condition == "refurbished":
        chain = [
            (prices.ebay_used_sold, "refurbished_sold"),
            (prices.ebay_used_bin, "refurbished_bin"),
            (prices.ebay_new_bin, "new_context_only"),
        ]
    elif condition in ("parts_only", "untested"):
        # PRD §13.3 — never benchmark against working-condition value.
        # With sold comps unavailable, there is currently no compliant
        # benchmark for this tier; the caller must treat this as
        # low-confidence rather than silently falling back to used BIN.
        chain = [(prices.ebay_used_sold, "parts_or_untested_sold")]
    else:  # used / unknown
        chain = [
            (prices.ebay_used_sold, "exact_sku_used_sold"),
            (prices.ebay_used_bin, "exact_sku_used_bin"),
        ]

    for stat, label in chain:
        if stat.status == "ok":
            return stat, label
    # Nothing in the chain had a usable sample — return the first (for its
    # unavailable_reason) so callers can surface *why*, not just that it failed.
    return chain[0][0], f"{chain[0][1]}_unavailable"


def _condition_confidence(condition: str) -> float:
    # "used" is the primary case for a flipping business (not a lesser one
    # than "new"), so it is not structurally penalised relative to new —
    # only genuinely uncertain conditions (untested/parts_only/unknown) are.
    return {"new": 90, "new_other": 80, "refurbished": 80, "used": 85, "untested": 30, "parts_only": 20, "unknown": 40}.get(
        condition, 40
    )


def _listing_completeness(listing: ExtractedListing) -> float:
    fields = [listing.seller, listing.condition_raw, listing.image_url]
    present = sum(1 for f in fields if f)
    return (present / len(fields)) * 100


def compute_deal_score(
    listing: ExtractedListing,
    prices: PriceBundle,
    risk_penalty: float,
) -> tuple[float, str]:
    market_stat, benchmark_label = pick_condition_benchmark(listing.condition_normalised, prices)
    sold_advantage = _price_advantage_subscore(listing.current_delivered_price, market_stat)
    bin_advantage = _price_advantage_subscore(
        listing.current_delivered_price,
        prices.ebay_new_bin if listing.condition_normalised in ("new", "new_other") else prices.ebay_used_bin,
    )
    comparable_quality = 80.0 if market_stat.status == "ok" else 30.0
    condition_confidence = _condition_confidence(listing.condition_normalised)
    listing_completeness = _listing_completeness(listing)

    weighted_0_100 = (
        sold_advantage * WEIGHT_SOLD_ADVANTAGE
        + bin_advantage * WEIGHT_BIN_ADVANTAGE
        + comparable_quality * WEIGHT_COMPARABLE_QUALITY
        + condition_confidence * WEIGHT_CONDITION_CONFIDENCE
        + listing_completeness * WEIGHT_LISTING_COMPLETENESS
    )

    score_0_10 = (weighted_0_100 / 10) - risk_penalty
    return round(max(0.0, min(10.0, score_0_10)), 2), benchmark_label


def compute_confidence(
    identity: Identity,
    prices: PriceBundle,
    condition: str,
    listing: ExtractedListing,
    benchmark_label: str,
) -> tuple[float, str]:
    market_stat, _ = pick_condition_benchmark(condition, prices)
    sample_component = min(100.0, market_stat.valid_sample_size * 12) if market_stat.status == "ok" else 10.0
    sku_component = (identity.exact_sku_confidence or 0.0) * 100
    condition_component = _condition_confidence(condition)
    freshness_component = 100.0 if (market_stat.age_minutes is not None and market_stat.age_minutes < 360) else 40.0
    seller_component = 70.0 if listing.seller_feedback_percent is not None else 40.0
    completeness_component = _listing_completeness(listing)
    unavailable_penalty = 30.0 if benchmark_label.endswith("_unavailable") else 0.0

    raw = (
        sample_component * 0.30
        + sku_component * 0.20
        + condition_component * 0.15
        + freshness_component * 0.15
        + seller_component * 0.10
        + completeness_component * 0.10
    ) - unavailable_penalty

    confidence = round(max(0.0, min(100.0, raw)), 1)
    band = "high" if confidence >= 80 else "medium" if confidence >= 60 else "low"
    return confidence, band


def compute_decision(classification: Classification, confidence_band: str, risk_flags: list[RiskFlag]) -> Decision:
    has_high_risk = any(f.severity == "high" for f in risk_flags)
    if has_high_risk and classification in ("SUPER_GEM", "GEM"):
        return "INVESTIGATE"  # PRD §15.1 "subject only to explicit hard blockers"
    # A low-confidence SUPER_GEM has no branch below to catch it either —
    # GEM's low-confidence case explicitly falls to MAKE_OFFER, but SUPER_GEM's
    # only handled the confidence_band != "low" case, so a low-confidence
    # SUPER_GEM silently fell all the way through to the IGNORE default —
    # the same label used for a genuinely worthless POOR_DEAL. A huge score
    # paired with a shaky identity match is exactly what INVESTIGATE exists
    # for (same signal as the risk-flag branch above): verify it manually
    # before acting, don't hide it as if it were junk.
    if classification == "SUPER_GEM":
        return "BUY_NOW" if confidence_band != "low" else "INVESTIGATE"
    if classification == "GEM":
        return "BUY_NOW" if confidence_band == "high" else "MAKE_OFFER"
    if classification == "OK_DEAL":
        return "MAKE_OFFER" if confidence_band != "low" else "WATCH"
    if classification == "AVERAGE_DEAL":
        return "WATCH"
    return "IGNORE"


def compute_flip_score(deal_score: float, prices: PriceBundle, condition: str) -> float | None:
    """Standalone resale attractiveness (PRD §18.2) — reuses the same
    benchmark evidence but weights liquidity of the used-sold market higher
    than raw discount, since a flip's success depends on it reselling.
    """
    used_sold = prices.ebay_used_sold
    if used_sold.status != "ok":
        return round(deal_score * 0.8, 2)  # degrade gracefully, don't invent a liquidity signal
    liquidity_bonus = min(1.0, used_sold.valid_sample_size / 10)
    return round(min(10.0, deal_score * (0.7 + 0.3 * liquidity_bonus)), 2)


def compute_build_value_score(deal_score: float, identity: Identity) -> float | None:
    """Attractiveness as a component input to a finished PC build (PRD
    §18.3). Categories that are always build-relevant (cpu/gpu/ram/
    motherboard) score closer to the deal score; peripheral-adjacent
    categories are discounted.
    """
    core_categories = {"cpu", "gpu", "ram", "motherboard", "ssd", "psu"}
    if identity.category not in core_categories:
        return round(deal_score * 0.5, 2)
    return round(deal_score, 2)


def compute_offer_strategy(
    actual_delivered_price: float, prices: PriceBundle, condition: str, confidence_band: str
) -> OfferStrategy | None:
    market_stat, _ = pick_condition_benchmark(condition, prices)
    if market_stat.status != "ok" or market_stat.median is None:
        return None
    margin_target = 0.15 if confidence_band == "high" else 0.25  # wider margin cushion when less certain
    walk_away = round(market_stat.median * (1 - margin_target), 2)
    target = round((actual_delivered_price + walk_away) / 2, 2)
    opening = round(min(actual_delivered_price * 0.85, target * 0.9), 2)
    return OfferStrategy(opening_offer=opening, target_buy_price=target, walk_away_price=walk_away)
