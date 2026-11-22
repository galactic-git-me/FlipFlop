"""Post-scrape AM4/AM5 QA snapshots from current SUPER_GEM listings.

This service performs database reads and deterministic checks only. It does
not call an LLM, retailer, marketplace, or Google API.
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.gem_radar_observation import GemRadarListingObservation
from app.models.gem_radar_scored_listing import GemRadarScoredListing
from app.models.listing import Listing
from app.services.build_compatibility_gate import evaluate_build_compatibility


SLOT_CATEGORY = {
    "motherboard": "motherboard", "cpu": "cpu", "cooler": "cooling",
    "ram": "ram", "gpu": "gpu", "ssd": "storage", "psu": "psu", "case": "case",
}
PLATFORMS = {"AM4": "am4", "AM5": "am5"}


def _source_properties(raw_specs: Any, exact_url: str) -> list[dict]:
    if not isinstance(raw_specs, dict):
        return []
    maps = []
    for key in ("playbook_product_capture", "playbook_product_engineering_capture", "playbook_amazon_catalog_capture"):
        capture = raw_specs.get(key)
        if not isinstance(capture, dict) or capture.get("url") != exact_url:
            continue
        props = capture.get("product_properties")
        if isinstance(props, dict):
            maps.append(props)
    return maps


def _engineering(role: str, listing: Listing | None, title: str) -> dict[str, Any]:
    """Use exact-URL captures or an explicitly reviewed configurator record."""
    if listing is None:
        return {"reviewed": False}
    raw = listing.raw_specs if isinstance(listing.raw_specs, dict) else {}
    configured = raw.get("configurator") if isinstance(raw.get("configurator"), dict) else {}
    exact_config_source = bool(listing.url and configured.get("source_url") == listing.url)
    facts = {key: value for key, value in configured.items() if key != "source_url"}
    capture_maps = _source_properties(raw, str(listing.url or ""))
    facts["reviewed"] = configured.get("reviewed") is True and exact_config_source
    if capture_maps:
        # Reuse the approved exact-source core-fact policy. It handles
        # conflicts with manual specs and never uses the LLM or title-only
        # guesses to establish compatibility.
        from app.services.playbook_service import _apply_exact_source_core_engineering
        facts = _apply_exact_source_core_engineering(role, listing,
            {"url": listing.url, "product_properties": capture_maps}, facts,
            allow_title_facts=False)
    return facts


def _check_summary(checks: list[dict], role: str) -> str:
    relevant = [item for item in checks if role in (item.get("affected") or [])]
    if not relevant:
        relevant = checks
    return "; ".join(
        f"{item.get('code')}: {item.get('message')}" for item in relevant
    )[:1200]


async def build_platform_snapshot(
    db: AsyncSession, *, platform: str, environment: str, sweep_run_id: str,
    completed_at: datetime,
) -> dict[str, Any]:
    """Select the highest-scored current SUPER_GEM per slot and check the BOM.

    The combination is only labelled compatible if every blocking fact has
    exact reviewed support. An unverified candidate remains visible with its
    blockers and is never promoted to a compatible pick.
    """
    socket = PLATFORMS[platform]
    categories = tuple(SLOT_CATEGORY)
    from app.api.gem_radar import get_active_buy_it_now_listing_ids, usable_listing_url
    actionable_ids = await get_active_buy_it_now_listing_ids(db)
    rows = (await db.execute(
        select(GemRadarScoredListing)
        .where(GemRadarScoredListing.listing_id.in_(actionable_ids or {"__none__"}),
               GemRadarScoredListing.classification == "SUPER_GEM",
               GemRadarScoredListing.category.in_(categories))
        .order_by(GemRadarScoredListing.deal_score.desc(),
                  GemRadarScoredListing.delivered_price.asc(),
                  GemRadarScoredListing.listing_id.asc())
    )).scalars().all()
    # Bound the candidate fan-out deterministically and retain enough
    # alternatives to find the top platform-matching CPU/board.
    candidate_rows: dict[str, list[GemRadarScoredListing]] = {category: [] for category in categories}
    seen: set[str] = set()
    for row in rows:
        if row.listing_id in seen or row.category not in candidate_rows:
            continue
        seen.add(row.listing_id)
        if len(candidate_rows[row.category]) < 80:
            candidate_rows[row.category].append(row)
    listing_ids = {row.listing_id for pool in candidate_rows.values() for row in pool}
    observations = (await db.execute(
        select(GemRadarListingObservation)
        .where(GemRadarListingObservation.listing_id.in_(listing_ids or {"__none__"}))
        .order_by(GemRadarListingObservation.observed_at.desc(), GemRadarListingObservation.id.desc())
    )).scalars().all()
    evidence_by_id: dict[str, dict] = {}
    for observation in observations:
        evidence_by_id.setdefault(str(observation.listing_id), observation.commercial_source_evidence or {})
    urls = {str(value.get("url")) for value in evidence_by_id.values()
            if isinstance(value, dict) and value.get("url")}
    listings = (await db.execute(select(Listing).where(Listing.url.in_(urls or {"__none__"}))
                .order_by(Listing.id.desc()))).scalars().all()
    listing_by_url: dict[str, Listing] = {}
    for item in listings:
        listing_by_url.setdefault(str(item.url), item)

    selected: dict[str, dict] = {}
    parts: dict[str, dict] = {}
    for category, role in SLOT_CATEGORY.items():
        chosen = None
        chosen_listing = None
        for scored in candidate_rows.get(category, []):
            evidence = evidence_by_id.get(str(scored.listing_id), {})
            url = str(evidence.get("url") or "") if isinstance(evidence, dict) else ""
            catalogue = listing_by_url.get(url)
            engineering = _engineering(role, catalogue, scored.title)
            if role in {"cpu", "motherboard"}:
                candidate_socket = str(engineering.get("socket") or "").casefold()
                if engineering.get("reviewed") is not True or candidate_socket != socket:
                    continue
            chosen, chosen_listing = scored, catalogue
            parts[role] = engineering
            break
        if chosen is None:
            fallback = candidate_rows.get(category, [])
            if fallback:
                scored = fallback[0]
                evidence = evidence_by_id.get(str(scored.listing_id), {})
                selected[role] = {
                    "status": "unverified", "title": scored.title,
                    "price": float(scored.delivered_price) if scored.delivered_price is not None else None,
                    "url": usable_listing_url(scored.url or (evidence.get("url") if isinstance(evidence, dict) else None),
                        scored.listing_id, scored.source, scored.title),
                    "source": scored.source, "seller": scored.seller_name,
                    "condition": scored.condition,
                    "reason": f"No exact reviewed {socket.upper()} socket evidence found.",
                }
            else:
                selected[role] = {"status": "unavailable", "title": None, "price": None,
                                  "url": None, "source": None, "condition": None,
                                  "reason": "No eligible SUPER_GEM candidate in this category."}
            continue
        selected[role] = {
            "status": "candidate", "title": chosen.title,
            "price": float(chosen.delivered_price) if chosen.delivered_price is not None else None,
            "url": usable_listing_url(chosen.url or (evidence_by_id.get(str(chosen.listing_id), {}) or {}).get("url"),
                chosen.listing_id, chosen.source, chosen.title),
            "source": chosen.source, "seller": chosen.seller_name,
            "condition": chosen.condition, "classification": chosen.classification,
            "deal_score": float(chosen.deal_score or 0),
        }

    case_facts = parts.pop("case", {})
    case = {
        "form_factor": case_facts.get("form_factor"),
        "supported_form_factors": case_facts.get("supported_form_factors"),
        "max_gpu_length_mm": case_facts.get("max_gpu_length_mm"),
        "max_cooler_height_mm": case_facts.get("max_cooler_height_mm"),
        "radiator_support": case_facts.get("radiator_support", {}),
        "engineering": case_facts,
    }
    result = evaluate_build_compatibility(parts, case, gpu_required=True, required_socket=socket)
    verdict = result["status"]
    rows_out = []
    completed_local = completed_at.astimezone(ZoneInfo("Europe/London")).isoformat()
    for role, record in selected.items():
        rows_out.append({
            "scrape_completed_at": completed_local,
            "environment": environment,
            "scan_run_id": sweep_run_id,
            "platform": platform,
            "component_slot": role,
            "candidate_item": record.get("title"),
            "price_gbp": record.get("price"),
            "condition": record.get("condition"),
            "seller_source": record.get("seller") or record.get("source"),
            "listing_url": record.get("url"),
            "compatibility_status": verdict if record.get("status") == "candidate" else "unverified",
            "evidence_or_blockers": (record.get("reason") or _check_summary(result["checks"], role)),
        })
    return {
        "environment": environment, "sweep_run_id": sweep_run_id,
        "completed_at": completed_local, "platform": platform,
        "status": verdict, "can_proceed": result["can_proceed"],
        "ruleset": result["ruleset"], "rows": rows_out,
        "checks": result["checks"],
    }


async def build_sweep_qa_snapshot(
    db: AsyncSession, *, environment: str, sweep_run_id: str, completed_at: datetime,
) -> dict[str, Any]:
    return {
        platform: await build_platform_snapshot(db, platform=platform,
            environment=environment, sweep_run_id=sweep_run_id,
            completed_at=completed_at)
        for platform in PLATFORMS
    }
