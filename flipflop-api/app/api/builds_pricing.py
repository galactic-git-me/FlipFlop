"""Build pricing breakdown with on-demand sold comps fetching.

Endpoint to fetch a build's estimated listing price with detailed pricing
reasoning (sold comps, BIN prices, demand signals), computed against the
actual ManualBuild record (not the separate AI-generated-builds list).

Supports on-demand fetching of sold comparables with Redis 7-day caching.
The cache key is CPU+Motherboard+GPU model only (not RAM) so that a single
cached pull covers every RAM variant of the same build — RAM-driven price
variance is then handled client-side by filtering the returned comps to
those within a tolerance of the build's actual RAM capacity.
"""
from __future__ import annotations

import re
import statistics
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, or_, and_
import structlog

from app.database import AsyncSessionLocal
from app.models.manual_build import ManualBuild
from app.models.listing import Listing, ListingStatus
from app.config import get_settings
from app.gem_radar.identity import resolve_identity
from app.gem_radar.adapters.sold_comps import SoldComp, SoldCompsResult
from app.services.ai_build_generator import _validate_against_ebay
from app.services.sold_comps_cache import get_sold_comps_cache

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/builds", tags=["builds"])

_RAM_GB_PATTERN = re.compile(r"(\d+)\s*(?:gb|gig|gigabyte)\b", re.IGNORECASE)
_RAM_TOLERANCE_GB = 8  # comps within +/- this many GB of the build's actual RAM are treated as comparable


def _extract_ram_gb(title: str | None) -> int | None:
    if not title:
        return None
    match = _RAM_GB_PATTERN.search(title)
    return int(match.group(1)) if match else None


def _find_component(components: list[dict], slot_keywords: tuple[str, ...]) -> dict | None:
    for component in components:
        slot = (component.get("slot") or "").lower()
        if any(keyword in slot for keyword in slot_keywords):
            return component
    return None


def _build_cache_key(cpu_title: str | None, mobo_title: str | None, gpu_title: str | None) -> str:
    """CPU+Motherboard+GPU model only — deliberately excludes RAM/storage so
    one cache entry serves every RAM/storage variant of the same build."""
    cpu_model = resolve_identity(cpu_title).model if cpu_title else None
    mobo_model = resolve_identity(mobo_title).model if mobo_title else None
    gpu_model = resolve_identity(gpu_title).model if gpu_title else None
    parts = [p or "unknown" for p in (cpu_model, mobo_model, gpu_model)]
    return "sold_comps:" + "|".join(parts).lower().replace(" ", "-")


def _build_search_query(cpu_title: str | None, gpu_title: str | None) -> str:
    cpu_model = (resolve_identity(cpu_title).model if cpu_title else None) or (cpu_title or "")[:30]
    gpu_model = (resolve_identity(gpu_title).model if gpu_title else None) or (gpu_title or "")[:30]
    return f"gaming pc {cpu_model} {gpu_model}".strip()


def _filter_by_ram_proximity(comps: list["SoldCompDetail"], target_ram: int | None) -> list["SoldCompDetail"]:
    """Drop comps whose RAM is far from the build's actual RAM (e.g. exclude
    a 64GB sold comp when pricing a 16GB build) — without this, averaging
    across RAM configs can skew the estimate by hundreds of pounds."""
    if target_ram is None:
        return comps
    matching = [
        c for c in comps
        if c.ram_gb is None or abs(c.ram_gb - target_ram) <= _RAM_TOLERANCE_GB
    ]
    return matching if matching else comps  # fall back to all rather than showing nothing


class PricingDetail(BaseModel):
    type: str  # "sold_average", "bin_average", "component_estimate"
    value: float
    description: str


class CacheInfo(BaseModel):
    seconds_ago: int | None = None
    seconds_until_expiry: int | None = None
    is_cached: bool = False


class SoldCompDetail(BaseModel):
    title: str | None = None
    price: float
    condition: str
    sold_at: str
    url: str | None = None
    ram_gb: int | None = None


class ComponentValuation(BaseModel):
    slot: str
    name: str
    price_paid: float
    estimated_resale: float
    estimate_basis: str
    confidence: str
    evidence_count: int = 0


class MarketComparable(BaseModel):
    source: str
    title: str
    price: float
    status: str
    observed_or_sold_at: str | None = None
    url: str | None = None
    match_basis: str


class PriceAutomationStep(BaseModel):
    day: int
    action: str
    price: float
    rationale: str


class PriceRecommendation(BaseModel):
    market_low: float
    market_mid: float
    market_high: float
    recommended_price: float
    floor_price: float
    auto_accept_at: float
    counter_offer_from: float
    auto_reject_below: float
    fee_rate_pct: float
    confidence: str
    rationale: str
    automation: list[PriceAutomationStep]


class PricingBreakdown(BaseModel):
    estimated_price: float
    primary_reasoning: PricingDetail
    sold_comps: list[SoldCompDetail] = []
    bin_prices: list[float] = []
    demand_signals: dict | None = None
    cache_info: CacheInfo
    cost_price: float
    delivery_cost: float
    estimated_profit: float
    is_loss: bool
    fetched_at: str
    component_valuations: list[ComponentValuation] = []
    component_resale_total: float = 0.0
    market_comparables: list[MarketComparable] = []
    recommendation: PriceRecommendation


_COMPONENT_RETENTION = {
    "gpu": 0.95, "cpu": 0.90, "ram": 0.85, "motherboard": 0.82,
    "ssd": 0.70, "psu": 0.72, "case": 0.65, "cpu_cooler": 0.65,
    "case_fans": 0.50, "gpu_support": 0.50, "operating_system": 0.0,
}


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = (len(ordered) - 1) * fraction
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    weight = index - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _round_price(value: float, step: int = 10) -> float:
    return float(round(value / step) * step)


async def _component_valuations(components: list[dict]) -> list[ComponentValuation]:
    valuations: list[ComponentValuation] = []
    async with AsyncSessionLocal() as db:
        for component in components:
            name = str(component.get("name") or "")
            slot = str(component.get("slot") or "other").lower()
            paid = float(component.get("price_paid") or 0)
            identity = resolve_identity(name)
            model = identity.model or ""
            observed: list[float] = []
            if len(model) >= 4:
                rows = (await db.execute(
                    select(Listing.price).where(
                        Listing.status == ListingStatus.active,
                        Listing.title.ilike(f"%{model}%"),
                        Listing.price > 0,
                    ).order_by(Listing.last_seen_at.desc()).limit(12)
                )).scalars().all()
                observed = [float(price) for price in rows if paid <= 0 or paid * 0.2 <= float(price) <= paid * 3.0]

            if observed:
                estimate = statistics.median(observed)
                basis = f"Median of {len(observed)} current standalone listings"
                confidence = "medium" if len(observed) >= 3 else "low"
            else:
                estimate = paid * _COMPONENT_RETENTION.get(slot, 0.65)
                basis = "Conservative category retention model; no exact live match"
                confidence = "low"
            valuations.append(ComponentValuation(
                slot=slot, name=name, price_paid=round(paid, 2),
                estimated_resale=round(estimate, 2), estimate_basis=basis,
                confidence=confidence, evidence_count=len(observed),
            ))
    return valuations


async def _active_build_comparables(cpu_model: str | None, gpu_model: str | None) -> list[MarketComparable]:
    matchers = []
    if cpu_model:
        matchers.append(Listing.cpu.ilike(f"%{cpu_model}%"))
        matchers.append(Listing.title.ilike(f"%{cpu_model}%"))
    if gpu_model:
        matchers.append(Listing.gpu.ilike(f"%{gpu_model}%"))
        matchers.append(Listing.title.ilike(f"%{gpu_model}%"))
    if not matchers:
        return []
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(Listing).where(
                Listing.status == ListingStatus.active,
                Listing.price >= 400,
                or_(*matchers),
                or_(Listing.title.ilike("%pc%"), Listing.title.ilike("%desktop%"), Listing.title.ilike("%gaming%")),
            ).order_by(Listing.last_seen_at.desc()).limit(12)
        )).scalars().all()
    return [MarketComparable(
        source=row.source_name, title=row.title, price=round(row.price, 2), status="active",
        observed_or_sold_at=row.last_seen_at.isoformat() if row.last_seen_at else None,
        url=row.url, match_basis="Same CPU or GPU; verify full specification",
    ) for row in rows]


@router.get("/{build_id}/pricing")
async def get_build_pricing(
    build_id: int,
    fetch_sold: bool = Query(False, description="If True, fetch fresh sold comps via ScrapingBee; otherwise use cache only"),
) -> PricingBreakdown:
    """
    Fetch a ManualBuild's pricing breakdown, optionally triggering a fresh
    on-demand sold-comps pull (cached for 7 days per CPU+MB+GPU combo).
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(ManualBuild).where(ManualBuild.id == build_id))
        build = result.scalar_one_or_none()

    if not build:
        raise HTTPException(status_code=404, detail=f"Build {build_id} not found")

    components: list[dict] = build.components or []
    cpu = _find_component(components, ("cpu", "processor"))
    mobo = _find_component(components, ("motherboard", "mobo", "mainboard"))
    gpu = _find_component(components, ("gpu", "graphics"))
    ram = _find_component(components, ("ram", "memory"))

    cpu_title = cpu.get("name") if cpu else None
    mobo_title = mobo.get("name") if mobo else None
    gpu_title = gpu.get("name") if gpu else None
    ram_title = ram.get("name") if ram else None
    target_ram_gb = _extract_ram_gb(ram_title)

    cache_key = _build_cache_key(cpu_title, mobo_title, gpu_title)
    query = _build_search_query(cpu_title, gpu_title)

    cache = await get_sold_comps_cache()
    cache_info = CacheInfo(is_cached=False)
    market_data: dict = {}

    if fetch_sold:
        log.info("builds_pricing.fetch_sold", build_id=build_id, query=query, cache_key=cache_key)
        try:
            market_data = await _validate_against_ebay(query)
            if market_data.get("sold", {}).get("available"):
                # _validate_against_ebay only surfaces the average, not the
                # raw comps — pull them again for the detailed breakdown.
                from app.gem_radar.adapters.sold_comps import LiveSoldCompsAdapter
                sold_result = await LiveSoldCompsAdapter().fetch(query, condition="used")
                if sold_result.available:
                    await cache.set(cache_key, sold_result)
        except Exception as exc:
            log.warning("builds_pricing.fetch_failed", build_id=build_id, query=query, error=str(exc))

    cached_result = await cache.get(cache_key)
    sold_comps_list: list[SoldCompDetail] = []
    if cached_result and cached_result.available:
        cache_age_info = await cache.get_cache_age_and_expiry(cache_key)
        if cache_age_info:
            seconds_ago, seconds_until_expiry = cache_age_info
            cache_info = CacheInfo(seconds_ago=seconds_ago, seconds_until_expiry=seconds_until_expiry, is_cached=True)
        for comp in cached_result.comps:
            sold_comps_list.append(
                SoldCompDetail(
                    title=comp.title,
                    price=comp.price,
                    condition=comp.condition,
                    sold_at=comp.sold_at,
                    url=comp.url,
                    ram_gb=_extract_ram_gb(comp.title),
                )
            )
        sold_comps_list = _filter_by_ram_proximity(sold_comps_list, target_ram_gb)

    # If this request didn't trigger a fresh fetch, market_data is still empty
    # — reconstruct just enough of it from the filtered cached comps so the
    # reasoning/estimate below reflects the RAM-filtered set, not the raw cache.
    if not market_data.get("sold", {}).get("available") and sold_comps_list:
        prices = [c.price for c in sold_comps_list]
        market_data.setdefault("sold", {})
        market_data["sold"] = {
            "available": True,
            "count": len(prices),
            "average_price": round(statistics.mean(prices), 2),
        }
    elif not market_data.get("sold", {}).get("available"):
        market_data.setdefault("sold", {"available": False, "count": 0, "average_price": None})
    market_data.setdefault("bin", {"available": False, "count": 0, "min_price": None, "max_price": None, "average_price": None})

    component_cost = build.total_cost or sum(c.get("price_paid", 0) for c in components)
    delivery_cost = build.shipping_cost or 0.0

    if market_data["sold"]["available"]:
        estimated_price = market_data["sold"]["average_price"]
        resale_source = "sold_average"
    elif market_data["bin"]["available"]:
        estimated_price = market_data["bin"]["average_price"]
        resale_source = "bin_average"
    else:
        estimated_price = component_cost
        resale_source = "component_estimate"

    total_cost = component_cost + delivery_cost
    estimated_profit = round(estimated_price - total_cost, 2)

    primary_reasoning = PricingDetail(
        type=resale_source,
        value=estimated_price,
        description=_reasoning_description(resale_source, market_data),
    )

    bin_prices = market_data.get("bin", {}).get("prices", [])
    if not bin_prices and market_data.get("bin", {}).get("average_price"):
        bin_prices = [market_data["bin"]["average_price"]]

    component_valuations = await _component_valuations(components)
    component_resale_total = round(sum(item.estimated_resale for item in component_valuations), 2)
    cpu_model = resolve_identity(cpu_title).model if cpu_title else None
    gpu_model = resolve_identity(gpu_title).model if gpu_title else None
    active_comparables = await _active_build_comparables(cpu_model, gpu_model)
    sold_market_comparables = [MarketComparable(
        source="eBay sold", title=comp.title or "Comparable gaming PC", price=comp.price,
        status="sold", observed_or_sold_at=comp.sold_at, url=comp.url,
        match_basis="Completed sale matched by CPU, GPU and RAM tolerance",
    ) for comp in sold_comps_list]
    market_comparables = sold_market_comparables + active_comparables

    sold_prices = [comp.price for comp in sold_comps_list]
    active_prices = [comp.price for comp in active_comparables]
    evidence_prices = sold_prices or active_prices
    if evidence_prices:
        market_low = _percentile(evidence_prices, 0.25)
        market_mid = statistics.median(evidence_prices)
        market_high = _percentile(evidence_prices, 0.75)
        confidence = "high" if len(sold_prices) >= 5 else "medium" if len(evidence_prices) >= 3 else "low"
        rationale = (
            f"Anchored to {len(sold_prices)} completed sales" if sold_prices
            else f"Provisional range from {len(active_prices)} active asking prices; no completed-sale cohort is cached"
        )
    else:
        # A sum-of-parts value is context, not proof of what a complete PC will
        # sell for. Apply a modest assembly/warranty premium and label it low confidence.
        market_mid = max(component_resale_total * 1.10, total_cost * 1.10)
        market_low, market_high = market_mid * 0.92, market_mid * 1.10
        confidence = "low"
        rationale = "No comparable-build evidence is available; provisional range uses component values plus a modest complete-build premium"

    fee_rate = float(get_settings().ebay_final_value_fee_pct)
    # Floor is the sale price required to net a 10% return after configured
    # marketplace fees and delivery, not merely the cash component total.
    floor_price = (total_cost * 1.10) / max(0.01, 1 - fee_rate)
    # Leave deliberate negotiating room above the protected floor when offers
    # are enabled; otherwise every non-full-price offer would be rejected.
    recommended_price = max(market_mid, floor_price * (1.08 if build.allow_offers else 1.0))
    if build.allow_offers:
        recommended_price = max(recommended_price, market_high)
    recommended_price = _round_price(recommended_price)
    floor_price = _round_price(floor_price)
    auto_accept_at = _round_price(max(floor_price, recommended_price * 0.96))
    counter_offer_from = _round_price(max(floor_price, recommended_price * 0.88))
    auto_reject_below = _round_price(max(total_cost / max(0.01, 1 - fee_rate), counter_offer_from * 0.90))
    automation: list[PriceAutomationStep] = []
    for day, reduction, action in (
        (0, 0.00, "Launch at the recommended price"),
        (3, 0.00, "Review views and watchers; send a 3% watcher offer if eligible"),
        (7, 0.03, "Reduce by 3% if there is no serious buyer engagement"),
        (14, 0.06, "Re-anchor to fresh sold evidence; target roughly 6% below launch"),
        (21, 0.09, "Final automated step; stop at the protected floor and require review"),
    ):
        automation.append(PriceAutomationStep(
            day=day, action=action,
            price=_round_price(max(floor_price, recommended_price * (1 - reduction))),
            rationale="Never crosses the fee-aware 10% margin floor",
        ))
    recommendation = PriceRecommendation(
        market_low=round(market_low, 2), market_mid=round(market_mid, 2), market_high=round(market_high, 2),
        recommended_price=recommended_price, floor_price=floor_price,
        auto_accept_at=auto_accept_at, counter_offer_from=counter_offer_from,
        auto_reject_below=auto_reject_below, fee_rate_pct=round(fee_rate * 100, 2),
        confidence=confidence, rationale=rationale, automation=automation,
    )

    return PricingBreakdown(
        estimated_price=estimated_price,
        primary_reasoning=primary_reasoning,
        sold_comps=sold_comps_list,
        bin_prices=bin_prices,
        demand_signals=None,
        cache_info=cache_info,
        cost_price=round(component_cost, 2),
        delivery_cost=round(delivery_cost, 2),
        estimated_profit=estimated_profit,
        is_loss=estimated_profit < 0,
        fetched_at=datetime.now(timezone.utc).isoformat(),
        component_valuations=component_valuations,
        component_resale_total=component_resale_total,
        market_comparables=market_comparables,
        recommendation=recommendation,
    )


def _reasoning_description(source: str, market_data: dict) -> str:
    if source == "sold_average":
        count = market_data.get("sold", {}).get("count", 0)
        avg = market_data["sold"]["average_price"]
        return f"Based on {count} recently sold builds (RAM-matched) averaging £{avg:.2f}"
    elif source == "bin_average":
        count = market_data.get("bin", {}).get("count", 0)
        avg = market_data["bin"]["average_price"]
        return f"Based on {count} active listings averaging £{avg:.2f}"
    return "Based on component cost estimate (no market data available)"
