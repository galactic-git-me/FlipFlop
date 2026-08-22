"""
Sold-comp pricing engine — Algorithm Playbook rows 19, 20, 21, 22, 23, 44, 49.

Pure, unit-testable pricing math plus the async orchestration that recalculates
a Flip's pricing fields from fresh eBay data. Kept deliberately re-anchoring
(never carrying a stale target forward) per the playbook's explicit fix for
the "does sold-comp pricing cause a downward spiral" risk: the flaw that would
cause a spiral is re-anchoring from a decayed number instead of fresh data, or
only ever stepping price down — both are avoided here (see `bias_from_fast_sale`
for the upward-bias half of that fix, row 49).

Defaults proposed in the implementation plan, confirm once:
  - price floor = cost basis + 10% minimum margin
  - auto-drop window = 7 days
  - price step-down per recreate cycle = 3%
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

import structlog

DEFAULT_MIN_MARGIN_PCT = 0.10
DEFAULT_DROP_WINDOW_DAYS = 7
DEFAULT_RECREATE_STEP_PCT = 0.03

log = structlog.get_logger(__name__)


def compute_price_floor(total_cost: float, min_margin_pct: float = DEFAULT_MIN_MARGIN_PCT) -> float:
    """Row 20 guardrail: never auto-drop below cost basis + minimum acceptable margin."""
    return round(total_cost * (1 + min_margin_pct), 2)


def compute_active_range_ceiling(active_prices: list[float]) -> Optional[float]:
    """
    Top of the active-listing range, excluding outliers, per row 19.
    Outliers are anything above the 90th percentile of the sorted active prices.
    """
    if not active_prices:
        return None
    prices = sorted(active_prices)
    if len(prices) == 1:
        return prices[0]
    cutoff_idx = max(0, min(len(prices) - 1, round(len(prices) * 0.9) - 1))
    return round(prices[cutoff_idx], 2)


def compute_bin_anchor(
    sold_comp_target: Optional[float],
    active_range_ceiling: Optional[float],
    offers_enabled: bool,
) -> Optional[float]:
    """
    Row 19: if offers are on, anchor near the top of the active range so
    negotiation lands back at the sold-comp target instead of undershooting it.
    Row 21 guardrail: never anchor exactly at the sold-comp target while offers
    are on — that stacks a second discount once an offer is accepted.
    """
    if offers_enabled and active_range_ceiling is not None:
        return active_range_ceiling
    if sold_comp_target is not None:
        return sold_comp_target
    return active_range_ceiling


def compute_next_drop_price(
    current_price: float,
    sold_comp_target: Optional[float],
    price_floor: float,
    step_pct: float = DEFAULT_RECREATE_STEP_PCT,
) -> tuple[float, bool]:
    """
    Row 20: step the price down toward the sold-comp target after the drop
    window elapses with no sale/accepted offer. Returns (new_price, floor_hit).

    Row 22/23 guardrails are enforced by construction: this only ever steps
    toward sold_comp_target (never below it opportunistically) and never below
    price_floor, so it can't undercut the market race-to-the-bottom pattern or
    price dramatically below market value.
    """
    target = sold_comp_target if sold_comp_target is not None else price_floor
    stepped = current_price * (1 - step_pct)
    new_price = max(stepped, target, price_floor)
    floor_hit = new_price <= price_floor + 0.01
    return round(new_price, 2), floor_hit


def is_drop_due(last_recalculated_at: Optional[datetime], window_days: int = DEFAULT_DROP_WINDOW_DAYS) -> bool:
    if last_recalculated_at is None:
        return True
    return datetime.utcnow() - last_recalculated_at >= timedelta(days=window_days)


@dataclass
class FastSaleSignal:
    """Row 49: a fast/near-asking sale is an underpriced signal for the *next* similar build."""
    was_fast_or_near_asking: bool
    suggested_anchor_bias_pct: float  # e.g. 0.05 = bias the next build's initial anchor 5% higher


def bias_from_fast_sale(days_to_sell: int, sale_price: float, listing_price: Optional[float]) -> FastSaleSignal:
    """
    Row 49 fix for the pricing-ratchets-down risk: fast sales or near-asking
    accepted offers should push the *next* similar build's initial anchor up,
    not just reset pricing to the same starting point every cycle.

    Default proposed, confirm once: "fast" = sold within 3 days of listing;
    "near-asking" = sale price within 5% of the listing price.
    """
    fast = days_to_sell <= 3
    near_asking = listing_price is not None and listing_price > 0 and (sale_price / listing_price) >= 0.95
    triggered = fast or near_asking
    return FastSaleSignal(
        was_fast_or_near_asking=triggered,
        suggested_anchor_bias_pct=0.05 if triggered else 0.0,
    )


DEFAULT_PC_WEIGHT_KG = 10.0
GPU_WEIGHT_KG = 2.0

# UK courier tiers for a large/heavy parcel (default proposed, confirm once).
_SHIPPING_TIERS = [(10.0, 15.0), (15.0, 20.0), (20.0, 28.0), (float("inf"), 35.0)]


def estimate_build_weight_kg(has_gpu: bool) -> float:
    """Row 35: rough build weight for the shipping-inclusive price calculator."""
    return DEFAULT_PC_WEIGHT_KG + (GPU_WEIGHT_KG if has_gpu else 0.0)


def estimate_shipping_cost(weight_kg: float) -> float:
    """Row 35: tiered UK courier estimate for a build's weight, to bake into a flat listed price."""
    for max_weight, cost in _SHIPPING_TIERS:
        if weight_kg <= max_weight:
            return cost
    return _SHIPPING_TIERS[-1][1]


def shipping_inclusive_price(base_price: float, has_gpu: bool) -> dict:
    """Row 35: flat listed price with shipping baked in, rather than exposed at checkout."""
    weight = estimate_build_weight_kg(has_gpu)
    shipping = estimate_shipping_cost(weight)
    return {
        "estimated_weight_kg": weight,
        "estimated_shipping_cost": shipping,
        "shipping_inclusive_price": round(base_price + shipping, 2),
    }


DEFAULT_AD_RATE_PCT = 0.05
MAX_AD_SPEND_SHARE_OF_PROFIT = 0.15
MIN_MARGIN_PCT_TO_PROMOTE = 0.10


def suggest_promoted_ad_rate(estimated_profit: float, total_cost: float) -> dict:
    """
    Row 40: suggest a Promoted Listings ad rate that keeps spend inside an
    acceptable margin band, rather than picking a rate by feel. Default
    proposed, confirm once: 5% starting rate (mid-point between eBay's
    typical 2-8% range and T4's empirically-tested 7%), capped so ad spend
    never exceeds 15% of estimated profit; flags builds too thin to promote.
    """
    margin_pct = (estimated_profit / total_cost) if total_cost else 0.0
    if margin_pct < MIN_MARGIN_PCT_TO_PROMOTE:
        return {
            "suggested_ad_rate_pct": 0.0,
            "too_thin_to_promote": True,
            "max_ad_spend": 0.0,
            "reason": f"Margin {margin_pct * 100:.1f}% is below the {MIN_MARGIN_PCT_TO_PROMOTE * 100:.0f}% threshold to promote profitably.",
        }

    max_ad_spend = round(estimated_profit * MAX_AD_SPEND_SHARE_OF_PROFIT, 2)
    return {
        "suggested_ad_rate_pct": DEFAULT_AD_RATE_PCT,
        "too_thin_to_promote": False,
        "max_ad_spend": max_ad_spend,
        "reason": f"Default {DEFAULT_AD_RATE_PCT * 100:.0f}% starting rate, capped at £{max_ad_spend:.2f} "
                  f"({MAX_AD_SPEND_SHARE_OF_PROFIT * 100:.0f}% of estimated profit).",
    }


def _component_spec(build, slot: str) -> Optional[str]:
    """ManualBuild has no single Listing to read cpu/gpu off — pull the
    name of the component in the given slot from its own `components` JSON
    instead (each item is {"slot": ..., "name": ...} or a BuildComponent)."""
    for c in build.components or []:
        c_slot = c["slot"] if isinstance(c, dict) else c.slot
        if c_slot and c_slot.lower() == slot.lower():
            return c["name"] if isinstance(c, dict) else c.name
    return None


async def recalculate_manual_build_pricing(build, db) -> dict:
    """
    ManualBuild equivalent of recalculate_pricing() below — same sold-comp
    re-anchoring math (never carries a stale target forward), adapted to
    read cpu/gpu from `components` instead of a Listing, and to write onto
    ManualBuild's fields (ebay_price is this system's listing-price anchor,
    auto_reject_below_price its min-offer floor).
    """
    from app.services.demand_check import build_query
    from app.services.ebay_browse import get_component_prices
    from app.services.cpu_tier import extract_cpu_tier
    from app.models.pricing_bias import PricingBias

    cpu = _component_spec(build, "CPU")
    gpu = _component_spec(build, "GPU")
    query = build_query(cpu, gpu)
    prices = await get_component_prices(query, force_refresh=True, min_price=50.0)

    active_prices = sorted(prices["used_prices"] + prices["new_prices"])
    ceiling = compute_active_range_ceiling(active_prices)
    sold_target = prices["used_median"]

    floor = compute_price_floor(build.total_cost or 0.0)
    anchor = compute_bin_anchor(sold_target, ceiling, build.allow_offers)

    cpu_tier = extract_cpu_tier(cpu)
    if anchor is not None and cpu_tier:
        bias_row = await db.get(PricingBias, cpu_tier)
        if bias_row and bias_row.anchor_bias_pct:
            anchor = round(anchor * (1 + bias_row.anchor_bias_pct), 2)

    build.active_range_ceiling = ceiling
    build.sold_comp_target = sold_target
    build.price_floor = floor
    if anchor is not None:
        build.ebay_price = anchor
    build.price_last_recalculated_at = datetime.utcnow()

    log.info(
        "pricing_engine.manual_build_recalculated",
        build_id=getattr(build, "id", None),
        anchor=anchor,
        sold_target=sold_target,
        ceiling=ceiling,
        floor=floor,
    )
    return {
        "listing_price": anchor,
        "sold_comp_target": sold_target,
        "active_range_ceiling": ceiling,
        "price_floor": floor,
    }


async def recalculate_pricing(flip, db) -> dict:
    """
    Orchestrates a fresh pricing recalculation for a Flip: pulls current active
    listing data, recomputes the sold-comp target/ceiling/floor/anchor, and
    writes them onto the flip. Never carries a prior cycle's numbers forward —
    every call re-derives from fresh data, per the playbook's explicit fix for
    the downward-spiral risk.
    """
    from app.services.demand_check import build_query
    from app.services.ebay_browse import get_component_prices
    from app.services.cpu_tier import extract_cpu_tier
    from app.models.listing import Listing
    from app.models.pricing_bias import PricingBias

    listing = await db.get(Listing, flip.listing_id)
    query = build_query(listing.cpu if listing else None, listing.gpu if listing else None)
    prices = await get_component_prices(query, force_refresh=True, min_price=50.0)

    active_prices = sorted(prices["used_prices"] + prices["new_prices"])
    ceiling = compute_active_range_ceiling(active_prices)
    # Fall back to used_median as the sold-comp proxy when Marketplace Insights
    # sold data isn't available (see demand_check.py) — flagged via note.
    sold_target = prices["used_median"]

    floor = compute_price_floor(flip.total_cost)
    anchor = compute_bin_anchor(sold_target, ceiling, flip.offers_enabled)

    # Row 49: apply any upward bias a fast/near-asking sale of a similar
    # (same cpu_tier) build left behind — the other half of the fix for the
    # "sold-comp pricing ratchets down" risk (see pricing_engine module docstring).
    cpu_tier = extract_cpu_tier(listing.cpu if listing else None)
    if anchor is not None and cpu_tier:
        bias_row = await db.get(PricingBias, cpu_tier)
        if bias_row and bias_row.anchor_bias_pct:
            anchor = round(anchor * (1 + bias_row.anchor_bias_pct), 2)

    flip.active_range_ceiling = ceiling
    flip.sold_comp_target = sold_target
    flip.price_floor = floor
    if anchor is not None:
        flip.listing_price = anchor
    flip.price_last_recalculated_at = datetime.utcnow()

    log.info(
        "pricing_engine.recalculated",
        flip_id=getattr(flip, "id", None),
        anchor=anchor,
        sold_target=sold_target,
        ceiling=ceiling,
        floor=floor,
    )
    return {
        "listing_price": anchor,
        "sold_comp_target": sold_target,
        "active_range_ceiling": ceiling,
        "price_floor": floor,
    }
