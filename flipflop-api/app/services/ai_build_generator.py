"""AI-generated PC builds — maintains an ongoing top-6 list of build
combinations sourced from GEM and SUPER_GEM CPU/Motherboard/GPU/RAM
listings, validated against live eBay market data for the *finished build*
(not just the sum of its parts).

GEM-tier listings are allowed as a fallback when SUPER_GEM inventory is thin,
but ranking always favours the build with the most SUPER_GEM components
first — profit is only the tiebreaker among builds tied on that count. A
build made of 4 SUPER_GEM parts beats one with 3 SUPER_GEM + 1 GEM part even
if the latter is nominally more profitable.

Runs on a schedule (see app.workers.scheduler) and persists results to
data/ai_generated_builds.json so the PC Builder "AI-Generated" tab loads
instantly instead of hitting eBay on every page view — mirrors the pattern
already used by app.services.price_refresh for data/price_benchmarks.json.

Compatibility is inferred from listing titles only (no structured
socket/chipset column exists on GemRadarScoredListing) — CPU and Motherboard
must agree on socket (AM4/AM5/LGA1700/...) when both are detectable, and
Motherboard/RAM must agree on DDR generation when both are detectable.
Undetectable sockets don't exclude a pairing (SUPER_GEM/GEM inventory is
scarce enough already) but are flagged with compatibility_confidence="unknown"
so the frontend/operator can see which pairings are unverified.
"""
from __future__ import annotations

import json
import re
import statistics
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import structlog
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.gem_radar.adapters.sold_comps import PlaywrightSoldCompsAdapter
from app.gem_radar.identity import resolve_identity
from app.gem_radar.marketplace import fallback_listing_url
from app.models.gem_radar_scored_listing import GemRadarScoredListing
from app.services.ebay_browse import search_active_listings

log = structlog.get_logger(__name__)

_OUTPUT_FILE = Path(__file__).resolve().parents[2] / "data" / "ai_generated_builds.json"

_LOOKBACK_DAYS = 7
_TOP_BUILDS = 6
_MAX_TRIPLE_CANDIDATES_PER_TYPE = 15  # bound the CPU x MB x RAM search space before eBay validation
_GPU_CANDIDATES = 8  # GPU has no compatibility constraint, so only a handful of top candidates are needed
_MAX_VALIDATED_CANDIDATES = 10  # how many super-gem-count-then-profit-ranked combos get real eBay lookups

_REQUIRED_CATEGORIES = ("cpu", "motherboard", "ram", "gpu")
_GEM_TIERS = ("SUPER_GEM", "GEM")  # SUPER_GEM preferred, GEM allowed as fallback when SUPER_GEM inventory is thin
_OPTIONAL_CATEGORIES = ("psu", "ssd", "cooler", "case")

_SOCKET_PATTERN = re.compile(r"\b(am4|am5|lga\s?1700|lga\s?1200|lga\s?1151|lga\s?1150|lga\s?2066)\b", re.IGNORECASE)
_DDR_PATTERN = re.compile(r"\bddr([345])\b", re.IGNORECASE)


def _capacity_gb(title: str) -> int:
    tb = [int(v) * 1000 for v in re.findall(r"\b(\d{1,2})\s*tb\b", title, re.IGNORECASE)]
    gb = [int(v) for v in re.findall(r"\b(\d{2,4})\s*gb\b", title, re.IGNORECASE)]
    return max([0, *tb, *gb])


def _psu_watts(title: str) -> int:
    values = [int(v) for v in re.findall(r"\b(\d{3,4})\s*w(?:att)?s?\b", title, re.IGNORECASE)]
    return max([0, *values])


def _valid_optional_component(listing: GemRadarScoredListing) -> bool:
    """Reject accessories that were loosely classified into required build slots."""
    title = (listing.title or "").lower()
    category = listing.category
    if category == "psu":
        return _psu_watts(title) >= 400 and any(k in title for k in ["psu", "power supply"])
    if category == "ssd":
        return _capacity_gb(title) >= 256 and any(k in title for k in ["ssd", "nvme", "solid state drive"]) and not any(k in title for k in ["case", "enclosure", "caddy", "adapter"])
    if category == "case":
        return any(k in title for k in ["pc case", "computer case", "atx case", "matx case", "mid tower", "full tower", "chassis"]) and not any(k in title for k in ["cover", "panel", "dust", "screw", "bag"])
    if category == "cooler":
        return any(k in title for k in ["cpu cooler", "aio cooler", "liquid cooler", "tower cooler", "240mm aio", "280mm aio", "360mm aio"]) and not any(k in title for k in ["mini heatsink", "tape", "cover", "bracket only"])
    return False


def _normalize_socket(raw: str) -> str:
    return raw.upper().replace(" ", "")


def _extract_socket(title: str) -> str | None:
    m = _SOCKET_PATTERN.search(title)
    return _normalize_socket(m.group(1)) if m else None


def _extract_ddr_gen(title: str) -> str | None:
    m = _DDR_PATTERN.search(title)
    return f"DDR{m.group(1)}" if m else None


def _listing_profit(listing: GemRadarScoredListing) -> float:
    resale = ((listing.market_new_price or 0) + (listing.market_used_price or 0)) / 2
    return resale - listing.delivered_price


def _listing_dict(listing: GemRadarScoredListing) -> dict:
    return {
        "id": listing.id,
        "listing_id": listing.listing_id,
        "category": listing.category,
        "title": listing.title,
        "seller": listing.seller_name,
        "image_url": listing.image_url,
        "delivered_price": listing.delivered_price,
        "market_new_price": listing.market_new_price,
        "market_used_price": listing.market_used_price,
        "classification": listing.classification,
        "estimated_profit": round(_listing_profit(listing), 2),
        "url": listing.url or fallback_listing_url(listing.listing_id, listing.source),
    }


def _is_super_gem(listing: GemRadarScoredListing) -> bool:
    return listing.classification == "SUPER_GEM"


@dataclass
class Triple:
    cpu: GemRadarScoredListing
    motherboard: GemRadarScoredListing
    ram: GemRadarScoredListing
    compatibility_confidence: str  # "matched" | "unknown"
    raw_profit: float


@dataclass
class Combo:
    cpu: GemRadarScoredListing
    motherboard: GemRadarScoredListing
    ram: GemRadarScoredListing
    gpu: GemRadarScoredListing
    compatibility_confidence: str  # "matched" | "unknown"
    raw_profit: float
    super_gem_count: int  # how many of the 4 required components are SUPER_GEM (vs GEM fallback)


def _compatible_triples(
    cpus: list[GemRadarScoredListing],
    motherboards: list[GemRadarScoredListing],
    rams: list[GemRadarScoredListing],
) -> list[Triple]:
    triples: list[Triple] = []
    for cpu in cpus[:_MAX_TRIPLE_CANDIDATES_PER_TYPE]:
        cpu_socket = _extract_socket(cpu.title)
        for mobo in motherboards[:_MAX_TRIPLE_CANDIDATES_PER_TYPE]:
            mobo_socket = _extract_socket(mobo.title)
            if cpu_socket and mobo_socket and cpu_socket != mobo_socket:
                continue
            socket_known = bool(cpu_socket and mobo_socket)
            mobo_ddr = _extract_ddr_gen(mobo.title)
            for ram in rams[:_MAX_TRIPLE_CANDIDATES_PER_TYPE]:
                ram_ddr = _extract_ddr_gen(ram.title)
                if mobo_ddr and ram_ddr and mobo_ddr != ram_ddr:
                    continue
                ram_known = bool(mobo_ddr and ram_ddr)
                confidence = "matched" if (socket_known and ram_known) else "unknown"
                raw_profit = _listing_profit(cpu) + _listing_profit(mobo) + _listing_profit(ram)
                triples.append(Triple(cpu, mobo, ram, confidence, raw_profit))
    triples.sort(key=lambda t: t.raw_profit, reverse=True)
    return triples


def _rank_combos(triples: list[Triple], gpu_candidates: list[GemRadarScoredListing]) -> list[Combo]:
    """Cross triples with GPU candidates and rank by SUPER_GEM count first,
    raw profit second — a build with more SUPER_GEM parts always outranks one
    with fewer, regardless of profit, per the priority the operator wants."""
    combos: list[Combo] = []
    for triple in triples:
        for gpu in gpu_candidates:
            super_gem_count = sum(
                1 for c in (triple.cpu, triple.motherboard, triple.ram, gpu) if _is_super_gem(c)
            )
            combos.append(
                Combo(
                    cpu=triple.cpu,
                    motherboard=triple.motherboard,
                    ram=triple.ram,
                    gpu=gpu,
                    compatibility_confidence=triple.compatibility_confidence,
                    raw_profit=triple.raw_profit + _listing_profit(gpu),
                    super_gem_count=super_gem_count,
                )
            )
    combos.sort(key=lambda c: (c.super_gem_count, c.raw_profit), reverse=True)
    return combos


def _build_query(cpu: GemRadarScoredListing, gpu: GemRadarScoredListing, ram: GemRadarScoredListing) -> str:
    cpu_model = resolve_identity(cpu.title).model or cpu.title[:30]
    gpu_model = resolve_identity(gpu.title).model or gpu.title[:30]
    ram_match = _DDR_PATTERN.search(ram.title)
    ram_capacity = re.search(r"\b(\d{1,3})\s?gb\b", ram.title, re.IGNORECASE)
    ram_part = f"{ram_capacity.group(1)}gb" if ram_capacity else ""
    return f"gaming pc {cpu_model} {gpu_model} {ram_part}".strip()


async def _validate_against_ebay(query: str) -> dict:
    """Fetch real market comparables for a finished-build query: average sold
    price (from completed listings) and the active BIN price range/average."""
    sold_result = await PlaywrightSoldCompsAdapter().fetch(query, condition="used")
    sold_prices = [c.price for c in sold_result.comps] if sold_result.available else []

    bin_items = await search_active_listings(query, condition_filter="USED|EXCELLENT|VERY_GOOD|GOOD|ACCEPTABLE", limit=50)
    bin_prices = [i["price"] for i in bin_items]

    return {
        "query": query,
        "sold": {
            "available": bool(sold_prices),
            "count": len(sold_prices),
            "average_price": round(statistics.mean(sold_prices), 2) if sold_prices else None,
            "unavailable_reason": None if sold_result.available else sold_result.unavailable_reason,
        },
        "bin": {
            "available": bool(bin_prices),
            "count": len(bin_prices),
            "min_price": round(min(bin_prices), 2) if bin_prices else None,
            "max_price": round(max(bin_prices), 2) if bin_prices else None,
            "average_price": round(statistics.mean(bin_prices), 2) if bin_prices else None,
        },
    }


def _resale_estimate(market: dict, fallback: float) -> tuple[float, str]:
    """Prefer real sold-price average (actual completed transactions) over
    active BIN average (asking prices, typically inflated) over the
    component-sum fallback (no live comparable data at all)."""
    if market["sold"]["available"]:
        return market["sold"]["average_price"], "sold_average"
    if market["bin"]["available"]:
        return market["bin"]["average_price"], "bin_average"
    return fallback, "component_estimate"


async def generate_ai_builds() -> dict:
    """Rebuild the top-6 AI-generated build list from current GEM/SUPER_GEM
    inventory, validated against live eBay data, and persist to disk.
    Builds are ranked by SUPER_GEM component count first, profit second."""
    log.info("ai_build_generator.start")
    since = datetime.now(timezone.utc) - timedelta(days=_LOOKBACK_DAYS)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(GemRadarScoredListing).where(
                GemRadarScoredListing.scored_at >= since.replace(tzinfo=None),
                GemRadarScoredListing.category.in_(_REQUIRED_CATEGORIES),
                GemRadarScoredListing.classification.in_(_GEM_TIERS),
            )
        )
        gem_tier_listings = result.scalars().all()

        optional_result = await db.execute(
            select(GemRadarScoredListing).where(
                GemRadarScoredListing.scored_at >= since.replace(tzinfo=None),
                GemRadarScoredListing.category.in_(_OPTIONAL_CATEGORIES),
            )
        )
        optional_listings = optional_result.scalars().all()

    by_category: dict[str, list[GemRadarScoredListing]] = {}
    for listing in gem_tier_listings:
        by_category.setdefault(listing.category, []).append(listing)
    for listings in by_category.values():
        # SUPER_GEM listings sort ahead of GEM listings within each category
        # (regardless of profit) so the candidate pools favour SUPER_GEM
        # before the ranking step even runs.
        listings.sort(key=lambda l: (_is_super_gem(l), _listing_profit(l)), reverse=True)

    cpus = by_category.get("cpu", [])
    motherboards = by_category.get("motherboard", [])
    rams = by_category.get("ram", [])
    gpus = by_category.get("gpu", [])

    if not (cpus and motherboards and rams and gpus):
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "builds": [],
            "unavailable_reason": "Not enough Gem/Super Gem listings across CPU/Motherboard/RAM/GPU yet.",
        }
        _write(payload)
        return payload

    best_optional: dict[str, GemRadarScoredListing] = {}
    for category in _OPTIONAL_CATEGORIES:
        candidates = [l for l in optional_listings if l.category == category and _valid_optional_component(l)]
        if candidates:
            best_optional[category] = max(candidates, key=_listing_profit)

    triples = _compatible_triples(cpus, motherboards, rams)
    if not triples:
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "builds": [],
            "unavailable_reason": "No socket/RAM-compatible Gem/Super Gem CPU+Motherboard+RAM combination found.",
        }
        _write(payload)
        return payload

    gpu_candidates = gpus[:_GPU_CANDIDATES]
    combos = _rank_combos(triples, gpu_candidates)

    candidates = combos[:_MAX_VALIDATED_CANDIDATES]
    validated_builds: list[dict] = []

    for combo in candidates:
        components = [combo.cpu, combo.motherboard, combo.gpu, combo.ram, *best_optional.values()]
        build_cost = sum(c.delivered_price for c in components)
        component_profit_sum = sum(_listing_profit(c) for c in components)
        component_resale_fallback = build_cost + component_profit_sum

        query = _build_query(combo.cpu, combo.gpu, combo.ram)
        try:
            market = await _validate_against_ebay(query)
        except Exception as exc:
            log.warning("ai_build_generator.validation_failed", query=query, error=str(exc))
            market = {
                "query": query,
                "sold": {"available": False, "count": 0, "average_price": None, "unavailable_reason": str(exc)},
                "bin": {"available": False, "count": 0, "min_price": None, "max_price": None, "average_price": None},
            }

        resale_estimate, resale_source = _resale_estimate(market, component_resale_fallback)
        validated_profit = round(resale_estimate - build_cost, 2)

        validated_builds.append(
            {
                "components": [_listing_dict(c) for c in components],
                "compatibility_confidence": combo.compatibility_confidence,
                "super_gem_count": combo.super_gem_count,
                "build_cost": round(build_cost, 2),
                "market": market,
                "resale_estimate": round(resale_estimate, 2),
                "resale_source": resale_source,
                "estimated_profit": validated_profit,
            }
        )

    # SUPER_GEM count is the primary sort key — a build with more SUPER_GEM
    # parts always outranks one with fewer, profit only breaks ties within
    # the same count.
    validated_builds.sort(key=lambda b: (b["super_gem_count"], b["estimated_profit"]), reverse=True)
    top_builds = validated_builds[:_TOP_BUILDS]
    for rank, build in enumerate(top_builds):
        build["rank"] = rank + 1

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "builds": top_builds,
        "candidates_evaluated": len(candidates),
        "total_compatible_combinations": len(triples),
    }
    _write(payload)
    log.info("ai_build_generator.done", builds=len(top_builds), candidates=len(candidates))
    return payload


def _write(payload: dict) -> None:
    _OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    _OUTPUT_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")


def load_ai_builds() -> dict:
    """Read the last-generated build list. Returns an empty/not-yet-generated
    payload if the job hasn't run yet."""
    if not _OUTPUT_FILE.exists():
        return {"generated_at": None, "builds": [], "unavailable_reason": "AI build generation has not run yet."}
    try:
        return json.loads(_OUTPUT_FILE.read_text(encoding="utf-8"))
    except Exception as exc:
        log.warning("ai_build_generator.load_failed", error=str(exc))
        return {"generated_at": None, "builds": [], "unavailable_reason": f"Failed to read cached builds: {exc}"}
