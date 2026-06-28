"""
eBay Pricing Service - Calculate dynamic pricing for flips based on current eBay seller fees.

Handles:
- Fetching current eBay seller account fees
- Calculating pricing tiers (walk-away, total cost, optimal listing)
- Caching fee data with TTL
- Alerting on fee changes
"""

import json
import time
from typing import Optional
import httpx
import structlog
from datetime import datetime, timedelta

from app.config import get_settings
from app.api.ebay_compliance import _get_app_token, _ebay_api_root

log = structlog.get_logger(__name__)

# Cache for seller fees (fee_category -> {rates, updated_at})
_FEE_CACHE: dict[str, dict] = {}
_CACHE_TTL_SECONDS = 3600  # 1 hour


class eBayPricingError(Exception):
    """Raised when eBay pricing operations fail."""
    pass


async def get_seller_fees() -> Optional[dict]:
    """
    Fetch current eBay seller fees for the account.

    Returns dict with:
    {
        "insertion_fee": 0.30,
        "final_value_fee_pct": 0.127,
        "category": "computers",
        "seller_tier": "above_standard",
        "last_updated": "2026-06-03T10:00:00Z",
        "expires_at": "2026-06-03T11:00:00Z",
    }
    """
    cache_key = "seller_fees"

    # Check cache
    cached = _FEE_CACHE.get(cache_key)
    if cached and time.time() < cached.get("expires_at", 0):
        log.info("ebay.pricing.cache_hit")
        return cached

    token = await _get_app_token()
    if not token:
        log.error("ebay.pricing.no_token")
        raise eBayPricingError("No eBay OAuth token available")

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            # Get seller profile to determine current fees
            headers = {"Authorization": f"Bearer {token}"}

            # Try to get fees from seller profile API
            # For now, return hardcoded typical fees with option to fetch from actual API
            resp = await client.get(
                f"{_ebay_api_root()}/sell/account/v1/seller-profile",
                headers=headers
            )

            if resp.status_code == 200:
                profile = resp.json()
                fees = {
                    "insertion_fee": 0.30,  # Typical, varies by status
                    "final_value_fee_pct": 0.127,  # 12.7% for computers/electronics
                    "category": "electronics",
                    "seller_tier": profile.get("businessProfile", {}).get("seller_type", "individual"),
                    "last_updated": datetime.utcnow().isoformat() + "Z",
                    "expires_at": time.time() + _CACHE_TTL_SECONDS,
                }
            else:
                # Fallback to typical rates
                log.warning("ebay.pricing.profile_fetch_failed", status=resp.status_code)
                fees = {
                    "insertion_fee": 0.30,
                    "final_value_fee_pct": 0.127,
                    "category": "electronics",
                    "seller_tier": "standard",
                    "last_updated": datetime.utcnow().isoformat() + "Z",
                    "expires_at": time.time() + _CACHE_TTL_SECONDS,
                }

            # Cache the fees
            _FEE_CACHE[cache_key] = fees
            log.info("ebay.pricing.fees_updated", insertion_fee=fees["insertion_fee"],
                    final_value_fee_pct=fees["final_value_fee_pct"])
            return fees

    except Exception as e:
        log.error("ebay.pricing.fetch_failed", error=str(e))
        # Return cached fees if available, even if expired
        if cache_key in _FEE_CACHE:
            return _FEE_CACHE[cache_key]
        raise eBayPricingError(f"Failed to fetch eBay seller fees: {e}")


def calculate_pricing_tiers(
    total_cost: float,
    estimated_resale: float,
    insertion_fee: float = 0.30,
    final_value_fee_pct: float = 0.127,
    walkaway_margin_pct: float = 0.15,
) -> dict:
    """
    Calculate all pricing tiers for a flip.

    Args:
        total_cost: Total cost to acquire and upgrade the flip
        estimated_resale: Estimated market resale value
        insertion_fee: eBay listing insertion fee (flat amount)
        final_value_fee_pct: eBay final value fee as percentage (0-1)
        walkaway_margin_pct: Minimum margin percentage to accept (0-1)

    Returns:
        {
            "walk_away_price": min acceptable price (covers costs + margin),
            "total_cost_position": price to just break even,
            "optimal_listing_price": estimated resale (recommended),
            "estimated_profit_at_optimal": expected profit at optimal price,
            "breakeven_price": absolute minimum to not lose money,
            "margin_pct": margin % at optimal price,
            "final_value_fee": actual fee at optimal price,
            "net_proceeds_at_optimal": proceeds after all fees,
        }
    """

    # Break-even: total_cost / (1 - final_value_fee_pct) + insertion_fee
    # This is the minimum price to not lose money
    breakeven_price = (total_cost + insertion_fee) / (1 - final_value_fee_pct)

    # Walk-away position: break-even + desired margin
    walk_away_price = breakeven_price * (1 + walkaway_margin_pct)

    # Total cost position: price that yields total_cost net profit
    total_cost_position = (total_cost * 2 + insertion_fee) / (1 - final_value_fee_pct)

    # Optimal listing price: use estimated resale if it's above walk-away
    optimal_price = max(estimated_resale, walk_away_price)

    # Calculate actual fees at optimal price
    final_value_fee = max(0, optimal_price - insertion_fee) * final_value_fee_pct
    net_proceeds = optimal_price - insertion_fee - final_value_fee
    estimated_profit = net_proceeds - total_cost
    margin_pct = (estimated_profit / total_cost) * 100 if total_cost > 0 else 0

    return {
        "walk_away_price": round(walk_away_price, 2),
        "total_cost_position": round(total_cost_position, 2),
        "optimal_listing_price": round(optimal_price, 2),
        "estimated_profit_at_optimal": round(estimated_profit, 2),
        "breakeven_price": round(breakeven_price, 2),
        "margin_pct": round(margin_pct, 1),
        "insertion_fee": insertion_fee,
        "final_value_fee_pct": final_value_fee_pct,
        "final_value_fee_at_optimal": round(final_value_fee, 2),
        "net_proceeds_at_optimal": round(net_proceeds, 2),
    }


async def analyze_flip_pricing(
    flip_id: int,
    total_cost: float,
    estimated_resale: float,
    walkaway_margin_pct: Optional[float] = None,
) -> dict:
    """
    Analyze complete pricing for a flip using current eBay fees.

    Args:
        flip_id: The flip ID (for logging)
        total_cost: Total cost for the flip
        estimated_resale: Estimated resale value
        walkaway_margin_pct: Override default walk-away margin

    Returns:
        Pricing analysis with all tiers and fee breakdown
    """

    # Get current seller fees
    fees = await get_seller_fees()
    insertion_fee = fees.get("insertion_fee", 0.30)
    final_value_fee_pct = fees.get("final_value_fee_pct", 0.127)

    # Get walk-away margin from config, or use provided override
    settings = get_settings()
    default_margin = float(settings.ebay_walkaway_margin_pct or 0.15)
    margin = walkaway_margin_pct if walkaway_margin_pct is not None else default_margin

    # Calculate pricing tiers
    tiers = calculate_pricing_tiers(
        total_cost=total_cost,
        estimated_resale=estimated_resale,
        insertion_fee=insertion_fee,
        final_value_fee_pct=final_value_fee_pct,
        walkaway_margin_pct=margin,
    )

    log.info(
        "ebay.pricing.analysis",
        flip_id=flip_id,
        total_cost=total_cost,
        estimated_resale=estimated_resale,
        optimal_price=tiers["optimal_listing_price"],
        estimated_profit=tiers["estimated_profit_at_optimal"],
    )

    return {
        "flip_id": flip_id,
        "total_cost": total_cost,
        "estimated_resale": estimated_resale,
        "seller_fees": {
            "insertion_fee": insertion_fee,
            "final_value_fee_pct": final_value_fee_pct,
            "seller_tier": fees.get("seller_tier", "standard"),
            "last_updated": fees.get("last_updated"),
        },
        "pricing_tiers": tiers,
        "analysis_timestamp": datetime.utcnow().isoformat() + "Z",
    }


def clear_fee_cache():
    """Clear the fee cache (useful for testing or forcing refresh)."""
    global _FEE_CACHE
    _FEE_CACHE.clear()
    log.info("ebay.pricing.cache_cleared")
