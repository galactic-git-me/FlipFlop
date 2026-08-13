"""Phase 2 of the CPK-driven market-price system: classify a listing purely
from its % price offset against a settled CPK market price (see
app/gem_radar/cpk_market.py) — no LLM, no external benchmarks. Thresholds and
which market price (lower/median/upper) to offset against are user-
configurable (app.models.app_settings.AppSettings), matching the FlipFlop
extension's settings popup.

Deliberately reuses the existing Classification taxonomy (SUPER_GEM, GEM,
OK_DEAL, AVERAGE_DEAL, POOR_DEAL) rather than inventing new labels, so
existing dashboard/extension code that already understands these five tiers
keeps working. The plain-English "fair deal / poor deal / terrible deal"
framing from the product spec maps onto OK_DEAL / AVERAGE_DEAL / POOR_DEAL
respectively.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.gem_radar.cpk_market import CPKMarketPrice
from app.gem_radar.schemas import Classification
from app.models.app_settings import AppSettings

MarketPriceSource = Literal["lower", "median", "upper"]

# Recommendation shown to the user for this pathway — deliberately a
# separate field from the existing `decision` column (BUY_NOW/MAKE_OFFER/
# WATCH/INVESTIGATE/IGNORE), which is driven by the LLM-assisted pipeline's
# risk flags and confidence band, neither of which this pathway computes.
Recommendation = Literal["BUY_NOW_NO_QUESTION", "BUY_NOW", "OFFER_DEAL", "DO_NOT_BUY"]

_RECOMMENDATION_BY_CLASSIFICATION: dict[Classification, Recommendation] = {
    "SUPER_GEM": "BUY_NOW_NO_QUESTION",
    "GEM": "BUY_NOW",
    "OK_DEAL": "OFFER_DEAL",
    "AVERAGE_DEAL": "OFFER_DEAL",
    "POOR_DEAL": "DO_NOT_BUY",
}

# deal_score anchor at each classification boundary — mirrors the 0-10 scale
# scoring.CLASSIFICATION_BOUNDARIES already uses elsewhere in the app
# (SUPER_GEM >= 8.5, GEM >= 7.5, OK_DEAL >= 6.5, AVERAGE_DEAL >= 5.0), so a
# listing scored by this pathway sits on the same scale as one scored by the
# LLM-assisted pipeline.
_SCORE_AT_SUPER_GEM_BOUNDARY = 8.5
_SCORE_AT_GEM_BOUNDARY = 7.5
_SCORE_AT_OK_DEAL_BOUNDARY = 6.5
_SCORE_AT_AVERAGE_DEAL_BOUNDARY = 5.0


@dataclass(frozen=True)
class DealThresholds:
    """All % values are offset-from-market-price thresholds (negative =
    listing priced below market = a better deal). Loaded from AppSettings so
    they stay in sync with whatever the FlipFlopXtension settings popup last
    saved (see PUT /api/settings/)."""
    market_price_source: MarketPriceSource
    super_gem_pct: float
    gem_pct: float
    ok_deal_pct: float
    average_deal_pct: float


async def load_deal_thresholds(db) -> DealThresholds:
    from sqlalchemy import select

    result = await db.execute(select(AppSettings).where(AppSettings.name == "default"))
    settings = result.scalar_one_or_none()
    if settings is None:
        return DealThresholds(
            market_price_source="median",
            super_gem_pct=-30.0,  # Tightened from -20% to reduce false positives
            gem_pct=-20.0,  # Adjusted to maintain spacing
            ok_deal_pct=-10.0,  # Adjusted accordingly
            average_deal_pct=5.0,  # Adjusted accordingly
        )

    source = settings.deal_market_price_source
    if source not in ("lower", "median", "upper"):
        source = "median"

    return DealThresholds(
        market_price_source=source,  # type: ignore[arg-type]
        super_gem_pct=settings.deal_super_gem_threshold_pct,
        gem_pct=settings.deal_gem_threshold_pct,
        ok_deal_pct=settings.deal_ok_deal_threshold_pct,
        average_deal_pct=settings.deal_average_deal_threshold_pct,
    )


def market_price_for_source(market: CPKMarketPrice, source: MarketPriceSource) -> float:
    if source == "lower":
        return market.min_price
    if source == "upper":
        return market.max_price
    return market.median_price


def pct_offset(listing_price: float, market_price: float) -> float:
    """% offset of listing_price from market_price. Negative = listing is
    cheaper than market (a better deal)."""
    if market_price <= 0:
        return 0.0
    return round((listing_price - market_price) / market_price * 100, 2)


def classify_by_offset(offset_pct: float, thresholds: DealThresholds) -> Classification:
    if offset_pct <= thresholds.super_gem_pct:
        return "SUPER_GEM"
    if offset_pct <= thresholds.gem_pct:
        return "GEM"
    if offset_pct <= thresholds.ok_deal_pct:
        return "OK_DEAL"
    if offset_pct <= thresholds.average_deal_pct:
        return "AVERAGE_DEAL"
    return "POOR_DEAL"


def recommendation_for_classification(classification: Classification) -> Recommendation:
    return _RECOMMENDATION_BY_CLASSIFICATION[classification]


def _interpolate(x: float, x1: float, y1: float, x2: float, y2: float) -> float:
    if x2 == x1:
        return y1
    slope = (y2 - y1) / (x2 - x1)
    return y1 + slope * (x - x1)


def deal_score_from_offset(offset_pct: float, thresholds: DealThresholds) -> float:
    """0-10 granular deal score (1 d.p.) purely derived from % offset,
    piecewise-linear through the same anchor points classify_by_offset uses
    as tier boundaries — so a listing just inside SUPER_GEM always scores
    >= 8.5, matching the app's existing 0-10 scale semantics, while still
    giving a continuous ranking *within* a tier (e.g. to pick "top 10 super
    gems" or "bottom 3 gems").
    """
    anchors = [
        (thresholds.average_deal_pct, _SCORE_AT_AVERAGE_DEAL_BOUNDARY),
        (thresholds.ok_deal_pct, _SCORE_AT_OK_DEAL_BOUNDARY),
        (thresholds.gem_pct, _SCORE_AT_GEM_BOUNDARY),
        (thresholds.super_gem_pct, _SCORE_AT_SUPER_GEM_BOUNDARY),
    ]
    # Sorted ascending by offset (most negative/best deal first) — a
    # misconfigured settings popup (thresholds not monotonically increasing)
    # would otherwise silently produce a non-monotonic score.
    anchors.sort(key=lambda a: a[0])

    if offset_pct <= anchors[0][0]:
        # Better than the best-tier boundary — extrapolate using the next
        # segment's slope, capped at 10.
        x1, y1 = anchors[0]
        x2, y2 = anchors[1]
        score = _interpolate(offset_pct, x1, y1, x2, y2)
        return round(max(0.0, min(10.0, score)), 1)

    if offset_pct >= anchors[-1][0]:
        # Worse than the worst-tier boundary — extrapolate using the
        # previous segment's slope, floored at 0.
        x1, y1 = anchors[-2]
        x2, y2 = anchors[-1]
        score = _interpolate(offset_pct, x1, y1, x2, y2)
        return round(max(0.0, min(10.0, score)), 1)

    for (x1, y1), (x2, y2) in zip(anchors, anchors[1:]):
        if x1 <= offset_pct <= x2:
            score = _interpolate(offset_pct, x1, y1, x2, y2)
            return round(max(0.0, min(10.0, score)), 1)

    return 5.0  # unreachable given the bounds checks above; neutral fallback
