"""
Store-wide revenue/margin/sell-through + seller-performance dashboard —
Algorithm Playbook rows 16, 37. Cross-build utilities, so they live in the
admin tool rather than on any single build's page (per the implementation
plan's explicit placement call for these two rows).
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

import httpx
import structlog
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.ebay_compliance import _get_app_token, _ebay_api_root

log = structlog.get_logger(__name__)


async def get_revenue_margin_summary(db: AsyncSession, days: int = 90) -> dict:
    """Row 37: real revenue/margin/sell-through numbers, not vanity view/watcher counts (row 28)."""
    from app.models.flip_intelligence import FlipIntelligence
    from app.models.flip import Flip, FlipStage

    since = datetime.utcnow() - timedelta(days=days)

    result = await db.execute(
        select(
            func.count(FlipIntelligence.id),
            func.coalesce(func.sum(FlipIntelligence.sell_price), 0.0),
            func.coalesce(func.sum(FlipIntelligence.profit), 0.0),
            func.coalesce(func.avg(FlipIntelligence.roi_pct), 0.0),
            func.coalesce(func.avg(FlipIntelligence.days_to_sell), 0.0),
        ).where(FlipIntelligence.created_at >= since)
    )
    sold_count, total_revenue, total_profit, avg_roi_pct, avg_days_to_sell = result.one()

    active_result = await db.execute(
        select(func.count(Flip.id)).where(Flip.stage == FlipStage.ready_for_sale)
    )
    active_count = active_result.scalar_one()

    # Row 33 guardrail: keep sell-through simple — sold vs. (sold + still-active) — no
    # compound formula on top of it.
    denom = sold_count + active_count
    sell_through_rate = (sold_count / denom) if denom else None

    return {
        "window_days": days,
        "sold_count": sold_count,
        "active_count": active_count,
        "total_revenue": round(total_revenue, 2),
        "total_profit": round(total_profit, 2),
        "avg_margin_pct": round(avg_roi_pct, 1),
        "avg_days_to_sell": round(avg_days_to_sell, 1),
        "sell_through_rate": round(sell_through_rate, 3) if sell_through_rate is not None else None,
    }


async def get_seller_performance_metrics() -> dict:
    """
    Row 16: eBay's 5 documented seller-performance metrics (defect rate,
    late-shipment rate, tracking uploaded/scanned on time, cases closed
    without seller resolution, return rate) — pulled from the Account API's
    seller standards endpoint. Degrades gracefully without a stored seller
    OAuth token, same pattern as demand_check.py, rather than failing the
    whole dashboard.
    """
    from app.config import get_settings

    settings = get_settings()
    token = (settings.ebay_seller_access_token or "").strip()
    if not token:
        return {
            "available": False,
            "note": "Seller-performance metrics require a stored eBay seller OAuth token "
                    "(Settings.ebay_seller_access_token is blank) — no consent flow exists "
                    "yet to populate it.",
            "metrics": None,
        }

    root = _ebay_api_root()
    url = f"{root}/sell/analytics/v1/seller_standards_profile/CURRENT"
    headers = {"Authorization": f"Bearer {token}", "X-EBAY-C-MARKETPLACE-ID": "EBAY_GB"}
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(url, headers=headers)
    except Exception as exc:
        log.warning("performance_dashboard.seller_standards_failed", error=str(exc))
        return {"available": False, "note": f"Request failed: {exc}", "metrics": None}

    if resp.status_code != 200:
        return {
            "available": False,
            "note": f"eBay Analytics API returned {resp.status_code}.",
            "metrics": None,
        }

    body = resp.json()
    return {"available": True, "note": None, "metrics": body}


async def search_title_keywords(query: str) -> dict:
    """
    Row 38: source title keywords from eBay's own autocomplete + sold-listing
    titles, rather than generic keyword tools. eBay has no official public
    autosuggest API in the documented Sell/Buy surface (flagged in the
    implementation plan as the one row where App Automation classification
    needs verification) — this falls back to active-listing titles from the
    Browse API as a directional signal until that's resolved.
    """
    from app.services.ebay_browse import get_component_prices

    prices = await get_component_prices(query, force_refresh=False, min_price=20.0)
    titles = []
    if prices.get("used_cheapest"):
        titles.append(prices["used_cheapest"]["title"])
    if prices.get("new_cheapest"):
        titles.append(prices["new_cheapest"]["title"])

    tokens: dict[str, int] = {}
    for title in titles:
        for word in title.split():
            w = word.strip(",.()").upper()
            if len(w) >= 3:
                tokens[w] = tokens.get(w, 0) + 1

    return {
        "query": query,
        "sample_titles": titles,
        "frequent_tokens": sorted(tokens.items(), key=lambda kv: -kv[1])[:20],
        "note": "eBay autosuggest has no documented public API — this uses active Browse "
                "listing titles as a directional signal. Verify feasibility of the real "
                "autosuggest endpoint before relying on this for production title copy.",
    }
