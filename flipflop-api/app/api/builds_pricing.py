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
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, or_, and_, func
import structlog

from app.database import AsyncSessionLocal
from app.models.manual_build import ManualBuild
from app.models.build_sold_observation import BuildSoldObservation
from app.models.listing import Listing, ListingStatus
from app.gem_radar.schemas import CamelModel, ExtractedListing
from app.config import get_settings
from app.gem_radar.identity import resolve_identity
from app.gem_radar.adapters.sold_comps import SoldCompsResult
from app.services.ebay_browse import search_active_listings
from app.services.sold_comps_cache import get_sold_comps_cache
from app.services.figural_insurance import FiguralError, get_insurance_quote

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/builds", tags=["builds"])

_RAM_GB_PATTERN = re.compile(r"(\d+)\s*(?:gb|gig|gigabyte)\b", re.IGNORECASE)
_STORAGE_CAPACITY_PATTERN = re.compile(r"(\d+)\s*(tb|gb)\b", re.IGNORECASE)
_RAM_TOLERANCE_GB = 8  # comps within +/- this many GB of the build's actual RAM are treated as comparable


def _extract_ram_gb(title: str | None) -> int | None:
    if not title:
        return None
    for pattern in (r"(\d+)\s*gb\s*(?:ddr\d?|ram|memory)", r"(?:ram|memory)\s*(\d+)\s*gb"):
        match = re.search(pattern, title, re.IGNORECASE)
        if match:
            return int(match.group(1))
    # Component names generally contain only the RAM kit itself; retain the
    # generic fallback there while avoiding GPU VRAM in full build titles.
    if not any(token in title.lower() for token in ("rtx", "gtx", "radeon", "gaming pc", "desktop")):
        match = _RAM_GB_PATTERN.search(title)
        return int(match.group(1)) if match else None
    return None


def _extract_storage_gb(title: str | None) -> int | None:
    if not title:
        return None
    for pattern in (
        r"(\d+(?:\.\d+)?)\s*(tb|gb)\s*(?:nvme|ssd|hdd|storage)",
        r"(?:nvme|ssd|hdd|storage)\s*(\d+(?:\.\d+)?)\s*(tb|gb)",
    ):
        match = re.search(pattern, title, re.IGNORECASE)
        if match:
            value = float(match.group(1))
            return round(value * 1024) if match.group(2).lower() == "tb" else round(value)
    return None


def _condition_cohort(value: str | None) -> str:
    condition = (value or "unknown").lower().replace(" ", "_")
    if condition in {"new", "new_other", "open_box"}:
        return "new" if condition == "new" else "new_other"
    if condition in {"refurbished", "seller_refurbished", "certified_refurbished"}:
        return "refurbished"
    if condition in {"used", "pre_owned"}:
        return "used"
    return "unknown"


def _build_condition(ebay_condition: str | None, components: list[dict] | None = None) -> str:
    value = (ebay_condition or "").upper()
    if value == "NEW":
        return "new"
    if value in {"NEW_OTHER", "NEW_WITH_DEFECTS"}:
        return "new_other"
    if "REFURBISHED" in value:
        return "refurbished"
    if value.startswith("USED"):
        return "used"
    component_conditions = [_condition_cohort(item.get("condition")) for item in (components or [])]
    known = [value for value in component_conditions if value != "unknown"]
    if known and len(known) == len(component_conditions):
        if all(value == "new" for value in known):
            return "new"
        if any(value == "used" for value in known):
            return "used"
        if any(value == "refurbished" for value in known):
            return "refurbished"
        return "new_other"
    return "unknown"


def _title_has_model(title: str | None, model: str | None) -> bool:
    if not title or not model:
        return False
    title_key = re.sub(r"[^a-z0-9]", "", title.lower())
    model_key = re.sub(r"[^a-z0-9]", "", model.lower())
    if model_key and model_key in title_key:
        return True
    cpu = re.search(r"\b\d{4,5}(?:X3D|X|G|F|K|KF)?\b", model, re.IGNORECASE)
    gpu = re.search(r"\b(?:RTX|GTX|RX)\s*\d{3,4}(?:\s*(?:Ti|Super|XT|XTX))?\b", model, re.IGNORECASE)
    distinctive = cpu.group(0) if cpu else gpu.group(0) if gpu else None
    distinctive_key = re.sub(r"[^a-z0-9]", "", distinctive.lower()) if distinctive else ""
    return bool(distinctive_key and distinctive_key in title_key)


def _motherboard_chipset(title: str | None) -> str | None:
    if not title:
        return None
    match = re.search(r"\b(?:A|B|X|H|Z|Q|W)\d{3}[A-Z]?\b", title, re.IGNORECASE)
    return match.group(0).upper() if match else None


async def _standalone_capacity_value(kind: str, capacity_gb: int, condition: str) -> float | None:
    """Current UK standalone-component median used for spec deltas.

    Full PCs are excluded so a 64GB-vs-32GB adjustment reflects RAM kits,
    rather than accidentally comparing complete computers.
    """
    field = Listing.ram_gb if kind == "ram" else Listing.storage_gb
    condition_terms = ("new",) if condition == "new" else ("used", "refurbished")
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(Listing.price).where(
            Listing.status == ListingStatus.active,
            field == capacity_gb,
            Listing.price > 2,
            Listing.price < (400 if kind == "ram" else 600),
            ~or_(Listing.title.ilike("%gaming pc%"), Listing.title.ilike("%desktop%"), Listing.title.ilike("%computer%")),
            or_(*(Listing.condition.ilike(f"%{term}%") for term in condition_terms)),
        ).limit(100))).scalars().all()
    return statistics.median(rows) if len(rows) >= 2 else None


async def _standalone_chipset_value(chipset: str, condition: str) -> float | None:
    condition_terms = ("new",) if condition == "new" else ("used", "refurbished")
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(Listing.price).where(
            Listing.status == ListingStatus.active,
            Listing.title.ilike(f"%{chipset}%"),
            Listing.price.between(20, 800),
            or_(Listing.title.ilike("%motherboard%"), Listing.title.ilike("%mainboard%"), Listing.title.ilike("% mobo%")),
            or_(*(Listing.condition.ilike(f"%{term}%") for term in condition_terms)),
        ).limit(100))).scalars().all()
    return statistics.median(rows) if len(rows) >= 2 else None


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
    storage_gb: int | None = None
    original_price: float | None = None
    specification_adjustment: float = 0.0
    condition_adjustment: float = 0.0
    motherboard_match: str = "unknown"
    match_quality: str = "unverified"


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
    # "sold" is reserved for a genuine marketplace completion date. Existing
    # build sold-comp ingestion currently supplies only its retrieval time.
    date_kind: str = "observed"
    condition: str = "unknown"
    original_price: float | None = None
    specification_adjustment: float = 0.0
    condition_adjustment: float = 0.0
    match_quality: str = "unverified"


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


class PriceBridge(BaseModel):
    expected_sold_price: float
    build_cost: float
    delivery_cost: float
    insurance_cost: float
    packaging_cost: float
    warranty_reserve_pct: float
    warranty_reserve: float
    marketplace_fee_allowance: float
    negotiation_headroom_pct: float
    negotiation_headroom: float
    recommended_listing_price: float


class PricingCalibration(BaseModel):
    completed_sales: int
    offer_headroom_pct: float
    warranty_reserve_pct: float
    effective_fee_rate_pct: float
    basis: str


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
    price_bridge: PriceBridge
    build_condition: str
    condition_cohorts: dict[str, dict]
    excluded_comparable_count: int = 0
    component_condition_profile: dict
    calibration: PricingCalibration


class BuildSoldCompTarget(CamelModel):
    build_id: int
    name: str
    queries: list[str]


class BuildSoldCompSubmit(CamelModel):
    build_id: int
    query: str
    comps: list[ExtractedListing]


class BuildSoldCompSubmitResponse(CamelModel):
    inserted: int
    skipped: int


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = (len(ordered) - 1) * fraction
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    weight = index - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _weighted_median(comps: list[SoldCompDetail]) -> float:
    weighted = sorted(
        ((comp.price, 3 if comp.match_quality == "exact major specification" else 1) for comp in comps),
        key=lambda pair: pair[0],
    )
    threshold = sum(weight for _, weight in weighted) / 2
    cumulative = 0
    for price, weight in weighted:
        cumulative += weight
        if cumulative >= threshold:
            return price
    return weighted[-1][0] if weighted else 0.0


def _round_price(value: float, step: int = 10) -> float:
    return float(round(value / step) * step)


async def _component_valuations(components: list[dict]) -> list[ComponentValuation]:
    valuations: list[ComponentValuation] = []
    async with AsyncSessionLocal() as db:
        for component in components:
            name = str(component.get("name") or "")
            slot = str(component.get("slot") or "other").lower()
            paid = float(component.get("price_paid") or 0)
            recorded_market = float(
                component.get("market_price")
                or component.get("market_price_avg")
                or 0
            )
            identity = resolve_identity(name)
            model = identity.model or ""
            observed: list[float] = []
            listing_match = None
            if len(model) >= 4:
                listing_match = Listing.title.ilike(f"%{model}%")
            elif identity.category == "ssd" and identity.brand:
                # Generic but still useful descriptions such as "Samsung 1TB
                # M.2 NVMe SSD" do not resolve to a model. Match the recorded
                # brand, capacity and drive type instead of treating them as £0.
                capacity_match = _STORAGE_CAPACITY_PATTERN.search(name)
                if capacity_match:
                    capacity = "".join(capacity_match.groups()).upper()
                    listing_match = and_(
                        Listing.title.ilike(f"%{identity.brand}%"),
                        Listing.title.ilike(f"%{capacity}%"),
                        or_(Listing.title.ilike("%NVMe%"), Listing.title.ilike("%M.2%")),
                    )
            if listing_match is not None:
                rows = (await db.execute(
                    select(Listing.price).where(
                        Listing.status == ListingStatus.active,
                        listing_match,
                        Listing.price > 0,
                    ).order_by(Listing.last_seen_at.desc()).limit(12)
                )).scalars().all()
                observed = [float(price) for price in rows if paid <= 0 or paid * 0.2 <= float(price) <= paid * 3.0]

            if recorded_market > 0:
                estimate = recorded_market
                basis = "Recorded current market value"
                confidence = "medium"
            elif observed:
                estimate = statistics.median(observed)
                basis = f"Median of {len(observed)} current standalone listings"
                confidence = "medium" if len(observed) >= 3 else "low"
            else:
                # Do not manufacture a lower value by depreciating the purchase
                # price. If no market value is recorded and there is no exact
                # live evidence, retain the paid value as a transparent fallback.
                estimate = paid
                basis = "Purchase price fallback; no current market value available"
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
        date_kind="observed",
    ) for row in rows]


async def _live_close_build_comparables(
    cpu_model: str | None, gpu_model: str | None, target_ram_gb: int | None,
) -> list[MarketComparable]:
    """Find source-backed close matches even when no exact CPU+GPU result exists.

    eBay Browse treats multi-term queries loosely, so query each major anchor
    separately and then verify that anchor is actually present in the title.
    """
    queries: list[tuple[str, str]] = []
    if cpu_model:
        queries.append((f'gaming PC "{cpu_model}"', "same CPU"))
    if gpu_model:
        ram_term = f" {target_ram_gb}GB" if target_ram_gb else ""
        queries.append((f'gaming PC "{gpu_model}"{ram_term}', "same GPU"))

    found: dict[str, tuple[int, MarketComparable]] = {}
    for query, anchor_label in queries:
        items = await search_active_listings(
            query,
            condition_filter="USED|EXCELLENT|VERY_GOOD|GOOD|ACCEPTABLE",
            limit=50,
        )
        anchor = cpu_model if anchor_label == "same CPU" else gpu_model
        anchor_key = re.sub(r"[^a-z0-9]", "", (anchor or "").lower())
        for item in items:
            title = str(item.get("title") or "")
            title_key = re.sub(r"[^a-z0-9]", "", title.lower())
            if not anchor_key or anchor_key not in title_key:
                continue
            if not any(term in title.lower() for term in ("pc", "desktop", "gaming")):
                continue
            price = float(item.get("price") or 0)
            if price < 400:
                continue
            has_cpu = bool(cpu_model and re.sub(r"[^a-z0-9]", "", cpu_model.lower()) in title_key)
            has_gpu = bool(gpu_model and re.sub(r"[^a-z0-9]", "", gpu_model.lower()) in title_key)
            ram_gb = _extract_ram_gb(title)
            ram_close = bool(target_ram_gb and ram_gb and abs(ram_gb - target_ram_gb) <= _RAM_TOLERANCE_GB)
            score = (4 if has_cpu else 0) + (4 if has_gpu else 0) + (1 if ram_close else 0)
            matched = "same CPU and GPU" if has_cpu and has_gpu else anchor_label
            if ram_close:
                matched += f", RAM within {_RAM_TOLERANCE_GB}GB"
            url = str(item.get("url") or "")
            key = url or f"{title}|{price}"
            candidate = MarketComparable(
                source="eBay active", title=title, price=round(price, 2), status="active",
                observed_or_sold_at=datetime.now(timezone.utc).isoformat(),
                url=url or None, match_basis=f"Close match: {matched}",
                date_kind="observed",
            )
            if key not in found or score > found[key][0]:
                found[key] = (score, candidate)
    return [item for _, item in sorted(found.values(), key=lambda pair: pair[0], reverse=True)[:12]]


def _build_sold_queries(components: list[dict]) -> list[str]:
    cpu = _find_component(components, ("cpu", "processor"))
    gpu = _find_component(components, ("gpu", "graphics"))
    cpu_model = resolve_identity(cpu.get("name")).model if cpu else None
    gpu_model = resolve_identity(gpu.get("name")).model if gpu else None
    queries: list[str] = []
    cpu_search = None
    gpu_search = None
    if gpu_model:
        match = re.search(r"\b(?:RTX|GTX|RX)\s*\d{3,4}(?:\s*(?:Ti|Super|XT|XTX))?\b", gpu_model, re.IGNORECASE)
        gpu_search = match.group(0) if match else gpu_model
    if cpu_model:
        match = re.search(r"\b\d{4,5}(?:X3D|X|G|F|K|KF)?\b", cpu_model, re.IGNORECASE)
        cpu_search = match.group(0) if match else cpu_model
    # The combined query is the primary collection path. Separate searches
    # remain only to recover poorly titled listings; ingestion still requires
    # both exact identities before accepting a result.
    if cpu_search and gpu_search:
        queries.append(f'gaming PC "{cpu_search}" "{gpu_search}"')
    if gpu_search:
        queries.append(f'"{gpu_search}" PC')
    if cpu_search:
        queries.append(f'"{cpu_search}" PC')
    return list(dict.fromkeys(queries))


@router.get("/sold-comp-targets", response_model=list[BuildSoldCompTarget])
async def build_sold_comp_targets(limit: int = Query(2, ge=1, le=5)) -> list[BuildSoldCompTarget]:
    """Builds for FlipFlopXtension to enrich through the signed-in eBay tab."""
    cutoff = datetime.utcnow() - timedelta(days=90)
    async with AsyncSessionLocal() as db:
        builds = (await db.execute(
            select(ManualBuild)
            .where(ManualBuild.status.in_(("built", "listed")))
            .order_by(ManualBuild.updated_at.desc())
            .limit(30)
        )).scalars().all()
        observations = (await db.execute(select(BuildSoldObservation).where(
            BuildSoldObservation.build_id.in_([build.id for build in builds] or [-1]),
            BuildSoldObservation.observed_at >= cutoff,
        ))).scalars().all()
    counts: dict[tuple[int, str], int] = {}
    for observation in observations:
        key = (observation.build_id, _condition_cohort(observation.condition))
        counts[key] = counts.get(key, 0) + 1
    targets: list[BuildSoldCompTarget] = []
    for build in builds:
        target_condition = _build_condition(build.ebay_condition, build.components or [])
        queries = _build_sold_queries(build.components or [])
        if queries and counts.get((build.id, target_condition), 0) < 5:
            targets.append(BuildSoldCompTarget(build_id=build.id, name=build.name, queries=queries))
        if len(targets) >= limit:
            break
    return targets


@router.post("/sold-comps", response_model=BuildSoldCompSubmitResponse)
async def submit_build_sold_comps(payload: BuildSoldCompSubmit) -> BuildSoldCompSubmitResponse:
    """Persist extension-extracted complete-PC sold results for one build."""
    async with AsyncSessionLocal() as db:
        build = (await db.execute(select(ManualBuild).where(ManualBuild.id == payload.build_id))).scalar_one_or_none()
        if not build:
            raise HTTPException(status_code=404, detail="Build not found")
        cpu = _find_component(build.components or [], ("cpu", "processor"))
        gpu = _find_component(build.components or [], ("gpu", "graphics"))
        cpu_model = resolve_identity(cpu.get("name")).model if cpu else None
        gpu_model = resolve_identity(gpu.get("name")).model if gpu else None
        cpu_short = re.search(r"\b\d{4,5}(?:X3D|X|G|F|K|KF)?\b", cpu_model or "", re.IGNORECASE)
        cpu_key = re.sub(r"[^a-z0-9]", "", (cpu_short.group(0) if cpu_short else cpu_model or "").lower())
        gpu_short = re.search(r"\b(?:RTX|GTX|RX)\s*\d{3,4}(?:\s*(?:Ti|Super|XT|XTX))?\b", gpu_model or "", re.IGNORECASE)
        gpu_key = re.sub(r"[^a-z0-9]", "", (gpu_short.group(0) if gpu_short else gpu_model or "").lower())
        existing_urls = set((await db.execute(
            select(BuildSoldObservation.source_url).where(BuildSoldObservation.build_id == build.id)
        )).scalars().all())
        inserted = skipped = 0
        for comp in payload.comps:
            title_key = re.sub(r"[^a-z0-9]", "", comp.title.lower())
            has_cpu = bool(cpu_key and cpu_key in title_key)
            has_gpu = bool(gpu_key and gpu_key in title_key)
            is_pc = any(term in comp.title.lower() for term in (" pc", "desktop", "gaming computer"))
            if comp.listing_type == "auction" or not is_pc or not (has_cpu and has_gpu) or comp.current_delivered_price < 400:
                skipped += 1
                continue
            if comp.url in existing_urls:
                skipped += 1
                continue
            basis = "same CPU and GPU"
            db.add(BuildSoldObservation(
                build_id=build.id, title=comp.title, price=comp.item_price,
                postage=comp.postage_price, condition=comp.condition_normalised, sold_at=comp.extracted_at.isoformat(),
                source_url=comp.url, match_basis=f"Extension sold search: {basis}",
            ))
            existing_urls.add(comp.url)
            inserted += 1
        await db.commit()
    return BuildSoldCompSubmitResponse(inserted=inserted, skipped=skipped)


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
    storage = _find_component(components, ("storage", "ssd", "nvme", "hdd"))

    cpu_title = cpu.get("name") if cpu else None
    mobo_title = mobo.get("name") if mobo else None
    gpu_title = gpu.get("name") if gpu else None
    ram_title = ram.get("name") if ram else None
    storage_title = storage.get("name") if storage else None
    target_ram_gb = _extract_ram_gb(ram_title)
    target_storage_gb = _extract_storage_gb(storage_title)
    cpu_model = resolve_identity(cpu_title).model if cpu_title else None
    gpu_model = resolve_identity(gpu_title).model if gpu_title else None
    mobo_model = resolve_identity(mobo_title).model if mobo_title else None
    target_condition = _build_condition(build.ebay_condition, components)
    component_condition_profile = {
        "components": len(components),
        "known_condition": sum(_condition_cohort(item.get("condition")) != "unknown" for item in components),
        "with_warranty": sum(bool(item.get("warranty_expires_at")) for item in components),
        "with_proof_of_purchase": sum(bool(item.get("proof_of_purchase")) for item in components),
        "with_original_packaging": sum(bool(item.get("original_packaging")) for item in components),
    }

    cache_key = _build_cache_key(cpu_title, mobo_title, gpu_title)
    query = _build_search_query(cpu_title, gpu_title)

    cache = await get_sold_comps_cache()
    cache_info = CacheInfo(is_cached=False)
    market_data: dict = {}
    live_close_comparables: list[MarketComparable] = []

    if fetch_sold:
        log.info("builds_pricing.fetch_sold", build_id=build_id, query=query, cache_key=cache_key)
        try:
            cpu_model_for_search = resolve_identity(cpu_title).model if cpu_title else None
            gpu_model_for_search = resolve_identity(gpu_title).model if gpu_title else None
            live_close_comparables = await _live_close_build_comparables(
                cpu_model_for_search, gpu_model_for_search, target_ram_gb,
            )
            # Cache the source details as well as sold comps so a page reload
            # does not erase the evidence just fetched by the operator.
            sold_for_cache = await cache.get(cache_key)
            if sold_for_cache is None:
                sold_for_cache = SoldCompsResult(
                    available=False, comps=[], unavailable_reason="No completed-sale evidence",
                )
            await cache.set(
                cache_key,
                sold_for_cache,
                listings_data={"active_close_matches": [item.model_dump() for item in live_close_comparables]},
            )
        except Exception as exc:
            log.warning("builds_pricing.close_match_fetch_failed", build_id=build_id, error=str(exc))

    cached_result = await cache.get(cache_key)
    if not live_close_comparables:
        cached_listings = await cache.get_listings(cache_key)
        if cached_listings:
            live_close_comparables = [
                MarketComparable.model_validate(item)
                for item in cached_listings.get("active_close_matches", [])
            ]
    sold_comps_list: list[SoldCompDetail] = []
    async with AsyncSessionLocal() as db:
        stored_build_comps = (await db.execute(
            select(BuildSoldObservation)
            .where(BuildSoldObservation.build_id == build_id)
            .where(BuildSoldObservation.observed_at >= datetime.utcnow() - timedelta(days=90))
            .order_by(BuildSoldObservation.observed_at.desc())
            .limit(50)
        )).scalars().all()
    raw_sold: list[SoldCompDetail] = [SoldCompDetail(
        title=comp.title, price=round(comp.price + comp.postage, 2),
        condition=_condition_cohort(comp.condition), sold_at=comp.sold_at or comp.observed_at.isoformat(),
        url=comp.source_url, ram_gb=_extract_ram_gb(comp.title), storage_gb=_extract_storage_gb(comp.title),
    ) for comp in stored_build_comps]
    if cached_result and cached_result.available:
        cache_age_info = await cache.get_cache_age_and_expiry(cache_key)
        if cache_age_info:
            seconds_ago, seconds_until_expiry = cache_age_info
            cache_info = CacheInfo(seconds_ago=seconds_ago, seconds_until_expiry=seconds_until_expiry, is_cached=True)
        for comp in cached_result.comps:
            if comp.url and any(existing.url == comp.url for existing in raw_sold):
                continue
            raw_sold.append(
                SoldCompDetail(
                    title=comp.title,
                    price=comp.price,
                    condition=_condition_cohort(comp.condition),
                    sold_at=comp.sold_at,
                    url=comp.url,
                    ram_gb=_extract_ram_gb(comp.title),
                    storage_gb=_extract_storage_gb(comp.title),
                )
            )

    # CPU and GPU are mandatory identity anchors. RAM and storage differences
    # are normalised using the target component's recorded market/paid value.
    exact_identity = [comp for comp in raw_sold if _title_has_model(comp.title, cpu_model) and _title_has_model(comp.title, gpu_model)]
    excluded_comparable_count = len(raw_sold) - len(exact_identity)
    ram_value = float((ram or {}).get("market_price") or (ram or {}).get("market_price_avg") or (ram or {}).get("price_paid") or 0)
    storage_value = float((storage or {}).get("market_price") or (storage or {}).get("market_price_avg") or (storage or {}).get("price_paid") or 0)
    pricing_condition = "new" if target_condition in {"new", "new_other"} else "used"
    target_ram_market = await _standalone_capacity_value("ram", target_ram_gb, pricing_condition) if target_ram_gb else None
    target_storage_market = await _standalone_capacity_value("storage", target_storage_gb, pricing_condition) if target_storage_gb else None
    target_chipset = _motherboard_chipset(mobo_title)
    target_mobo_market = await _standalone_chipset_value(target_chipset, pricing_condition) if target_chipset else None
    ram_markets: dict[int, float | None] = {}
    storage_markets: dict[int, float | None] = {}
    chipset_markets: dict[str, float | None] = {}
    for comp in exact_identity:
        adjustment = 0.0
        if target_ram_gb and comp.ram_gb:
            if comp.ram_gb not in ram_markets:
                ram_markets[comp.ram_gb] = await _standalone_capacity_value("ram", comp.ram_gb, pricing_condition)
            comp_ram_market = ram_markets[comp.ram_gb]
            adjustment += (target_ram_market - comp_ram_market) if target_ram_market is not None and comp_ram_market is not None else (target_ram_gb - comp.ram_gb) * (ram_value / target_ram_gb)
        if target_storage_gb and comp.storage_gb:
            if comp.storage_gb not in storage_markets:
                storage_markets[comp.storage_gb] = await _standalone_capacity_value("storage", comp.storage_gb, pricing_condition)
            comp_storage_market = storage_markets[comp.storage_gb]
            adjustment += (target_storage_market - comp_storage_market) if target_storage_market is not None and comp_storage_market is not None else (target_storage_gb - comp.storage_gb) * (storage_value / target_storage_gb)
        comp_chipset = _motherboard_chipset(comp.title)
        if target_chipset and comp_chipset and comp_chipset != target_chipset:
            if comp_chipset not in chipset_markets:
                chipset_markets[comp_chipset] = await _standalone_chipset_value(comp_chipset, pricing_condition)
            comp_mobo_market = chipset_markets[comp_chipset]
            if target_mobo_market is not None and comp_mobo_market is not None:
                adjustment += target_mobo_market - comp_mobo_market
        comp.original_price = comp.price
        comp.specification_adjustment = round(adjustment, 2)
        comp.price = round(comp.price + adjustment, 2)
        comp.motherboard_match = "exact" if _title_has_model(comp.title, mobo_model) else "normalised" if target_chipset and comp_chipset else "unknown"
        comp.match_quality = "exact major specification" if comp.motherboard_match == "exact" and (not target_ram_gb or comp.ram_gb == target_ram_gb) and (not target_storage_gb or comp.storage_gb == target_storage_gb) else "normalised"

    cohorts: dict[str, list[SoldCompDetail]] = {name: [] for name in ("new", "new_other", "refurbished", "used", "unknown")}
    for comp in exact_identity:
        cohorts[_condition_cohort(comp.condition)].append(comp)
    sold_comps_list = cohorts.get(target_condition, []) if target_condition != "unknown" else cohorts["unknown"]
    # Cross-condition evidence is allowed only when both cohorts have enough
    # exact CPU+GPU observations to learn the condition spread from the market.
    # This avoids fixed "new is worth X%" assumptions.
    if target_condition != "unknown" and len(sold_comps_list) >= 3:
        target_median = statistics.median(item.price for item in sold_comps_list)
        for source_condition in ("new", "new_other", "refurbished", "used"):
            source_items = cohorts[source_condition]
            if source_condition == target_condition or len(source_items) < 3:
                continue
            condition_delta = target_median - statistics.median(item.price for item in source_items)
            for source in source_items:
                adjusted = source.model_copy(deep=True)
                adjusted.original_price = adjusted.original_price if adjusted.original_price is not None else adjusted.price
                adjusted.condition_adjustment = round(condition_delta, 2)
                adjusted.price = round(adjusted.price + condition_delta, 2)
                adjusted.match_quality = f"{adjusted.match_quality}; condition-normalised from {source_condition}"
                sold_comps_list.append(adjusted)

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
    condition_cohorts = {
        name: {
            "count": len(items),
            "median": round(statistics.median(item.price for item in items), 2) if items else None,
            "exact_spec_count": sum(item.match_quality == "exact major specification" for item in items),
            "used_for_valuation": name == target_condition,
        }
        for name, items in cohorts.items()
    }

    component_cost = build.total_cost or sum(c.get("price_paid", 0) for c in components)
    async with AsyncSessionLocal() as db:
        outcome_rows = (await db.execute(select(ManualBuild).where(
            ManualBuild.status == "sold",
            ManualBuild.sale_price_actual.is_not(None),
            ManualBuild.sale_price_actual > 0,
        ).order_by(ManualBuild.updated_at.desc()).limit(100))).scalars().all()
    realised_discounts = [
        max(0.0, (row.ebay_price / row.sale_price_actual - 1) * 100)
        for row in outcome_rows if row.ebay_price and row.sale_price_actual and row.ebay_price >= row.sale_price_actual
    ]
    observed_fee_rates = [
        ((row.marketplace_fees_actual or 0) + (row.promotion_cost_actual or 0)) / row.sale_price_actual
        for row in outcome_rows if row.sale_price_actual and row.marketplace_fees_actual is not None
    ]
    warranty_rates = [
        ((row.warranty_claim_cost or 0) / row.total_cost) * 100
        for row in outcome_rows if row.total_cost and row.warranty_claim_cost is not None
    ]
    calibrated_headroom = min(15.0, max(4.0, statistics.median(realised_discounts))) if len(realised_discounts) >= 3 else (10.0 if build.allow_offers else 4.0)
    configured_warranty_pct = build.warranty_reserve_pct if build.warranty_reserve_pct is not None else 3.0
    warranty_reserve_pct = min(10.0, max(1.0, statistics.mean(warranty_rates))) if len(warranty_rates) >= 5 else configured_warranty_pct
    configured_fee_rate = float(get_settings().ebay_final_value_fee_pct)
    fee_rate = statistics.median(observed_fee_rates) if len(observed_fee_rates) >= 3 else configured_fee_rate
    if build.promoted_enabled and build.promoted_ad_rate_pct:
        fee_rate += build.promoted_ad_rate_pct / 100.0
    fee_rate = min(0.45, max(0.0, fee_rate))
    calibration = PricingCalibration(
        completed_sales=len(outcome_rows),
        offer_headroom_pct=round(calibrated_headroom, 2),
        warranty_reserve_pct=round(warranty_reserve_pct, 2),
        effective_fee_rate_pct=round(fee_rate * 100, 2),
        basis="Observed outcomes" if len(outcome_rows) >= 3 else "Configured defaults until three completed sales are recorded",
    )
    delivery_cost = build.shipping_cost or 0.0
    insurance_cost = build.shipping_insurance_cost or 0.0
    packaging_cost = build.packaging_cost or 0.0
    warranty_reserve = component_cost * (warranty_reserve_pct / 100.0)

    if market_data["sold"]["available"]:
        estimated_price = market_data["sold"]["average_price"]
        resale_source = "sold_average"
    elif market_data["bin"]["available"]:
        estimated_price = market_data["bin"]["average_price"]
        resale_source = "bin_average"
    else:
        estimated_price = component_cost
        resale_source = "component_estimate"

    total_cost = component_cost + delivery_cost + insurance_cost + packaging_cost + warranty_reserve
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
        # The extension and current cache record when the comp was retrieved,
        # not the eBay completion date. Do not present that as a sold date.
        date_kind="observed",
        condition=comp.condition,
        original_price=comp.original_price,
        specification_adjustment=comp.specification_adjustment,
        condition_adjustment=comp.condition_adjustment,
        match_quality=comp.match_quality,
    ) for comp in sold_comps_list]
    market_comparables = sold_market_comparables + live_close_comparables + active_comparables

    sold_prices = [comp.price for comp in sold_comps_list]
    active_prices = [comp.price for comp in live_close_comparables + active_comparables]
    evidence_prices = sold_prices or active_prices
    if evidence_prices:
        market_low = _percentile(evidence_prices, 0.25)
        market_mid = _weighted_median(sold_comps_list) if sold_comps_list else statistics.median(evidence_prices)
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

    # Floor is the sale price required to net a 10% return after configured
    # marketplace fees and delivery, not merely the cash component total.
    floor_price = (total_cost * 1.10) / max(0.01, 1 - fee_rate)
    # Leave deliberate negotiating room above the protected floor when offers
    # are enabled; otherwise every non-full-price offer would be rejected.
    negotiation_headroom_pct = calibrated_headroom if build.allow_offers else 4.0
    market_launch_price = market_mid * (1 + negotiation_headroom_pct / 100.0)
    recommended_price = max(market_launch_price, floor_price)
    # Requote cover against the recommendation instead of retaining a quote
    # based on a stale provisional asking price. Persist it so Shipping & Risk
    # and later pricing loads share the same premium.
    try:
        quote = await get_insurance_quote(recommended_price)
        if abs(quote.price_gbp - insurance_cost) >= 0.01:
            total_cost += quote.price_gbp - insurance_cost
            insurance_cost = quote.price_gbp
            floor_price = (total_cost * 1.10) / max(0.01, 1 - fee_rate)
            recommended_price = max(market_launch_price, floor_price)
            async with AsyncSessionLocal() as db:
                persisted = await db.get(ManualBuild, build_id)
                if persisted:
                    persisted.shipping_insurance_cost = insurance_cost
                    await db.commit()
    except FiguralError as exc:
        log.info("builds_pricing.insurance_quote_unavailable", build_id=build_id, reason=str(exc))
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
    price_bridge = PriceBridge(
        expected_sold_price=round(market_mid, 2),
        build_cost=round(component_cost, 2),
        delivery_cost=round(delivery_cost, 2),
        insurance_cost=round(insurance_cost, 2),
        packaging_cost=round(packaging_cost, 2),
        warranty_reserve_pct=round(warranty_reserve_pct, 2),
        warranty_reserve=round(warranty_reserve, 2),
        marketplace_fee_allowance=round(recommended_price * fee_rate, 2),
        negotiation_headroom_pct=negotiation_headroom_pct,
        negotiation_headroom=round(market_mid * negotiation_headroom_pct / 100.0, 2),
        recommended_listing_price=recommended_price,
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
        price_bridge=price_bridge,
        build_condition=target_condition,
        condition_cohorts=condition_cohorts,
        excluded_comparable_count=excluded_comparable_count,
        component_condition_profile=component_condition_profile,
        calibration=calibration,
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
