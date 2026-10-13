"""Admin API for the curated-build playbook and catalogue subset."""
import json
import re
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models.catalogue import CatalogueVariant, PlaybookSlot
from app.models.curated_build_segment import CuratedBuildSegment
from app.models.listing import Listing, ListingStatus
from app.models.amazon_bestseller_observation import AmazonBestsellerObservation
from app.models.gem_radar_listing_cpk import GemRadarListingCpk
from app.models.flip import Flip, FlipStage
from app.models.benchmark import HardwareBenchmark
from app.models.part import Part
from app.models.playbook import Playbook
from app.services.benchmark_normaliser import normalise_cpu, normalise_gpu
from app.routes.admin_auth import get_current_admin

router = APIRouter(prefix="/curated-builds", tags=["curated-builds"], dependencies=[Depends(get_current_admin)])


@router.get("/draft-playbook")
async def draft_playbook():
    """Return the local planning draft without implying supplier approval."""
    path = Path(__file__).resolve().parents[3] / "tmp" / "curated-playbooks-v1-stub.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Draft playbook file is unavailable")
    return json.loads(path.read_text(encoding="utf-8"))


@router.get("/definitions")
async def curated_cell_definitions(db: AsyncSession = Depends(get_db)):
    """Return the curated customer-type × budget cells for Ready-to-Ship assignment."""
    from app.services.curated_build_policy import definitions

    cells = definitions().get("builds", [])
    names = {str(cell.get("segment") or "") for cell in cells}
    playbooks = (await db.execute(select(Playbook).where(Playbook.name.in_(names)))).scalars().all()
    playbooks_by_name = {playbook.name.casefold(): playbook for playbook in playbooks}
    return {
        "items": [
            {**cell, "playbook_id": (playbooks_by_name.get(str(cell.get("segment") or "").casefold()).id
                                      if playbooks_by_name.get(str(cell.get("segment") or "").casefold()) else None)}
            for cell in cells
        ]
    }


@router.get("/bestseller-catalogue")
async def bestseller_catalogue(db: AsyncSession = Depends(get_db)):
    """Every captured Amazon bestseller, with its own ASIN as a minimum match.

    The Amazon snapshot supplies product identity and rank. Marketplace prices
    remain separate from the Amazon observation and are never treated as an
    approved component or procurement quote.
    """
    rows = (await db.execute(text("""
        WITH latest AS (
            SELECT DISTINCT ON (category, asin)
                category, asin, title, url, image_url, rank, cpk, price,
                rating, review_count, captured_at
            FROM amazon_bestseller_observations
            ORDER BY category, asin, captured_at DESC
        )
        SELECT a.category, a.asin, a.title, a.url, a.image_url, a.rank,
            COALESCE(a.cpk, 'asin:' || a.asin) AS cpk, a.price,
            a.rating, a.review_count, a.captured_at,
            COALESCE(r.status, 'pending') AS review_status,
            COALESCE(m.listing_id, 'amazon-bestseller:' || a.asin) AS marketplace_listing_id,
            COALESCE(m.source, 'amazon') AS marketplace_source,
            COALESCE(m.title, a.title) AS marketplace_title,
            COALESCE(m.url, a.url) AS marketplace_url,
            COALESCE(m.image_url, a.image_url) AS marketplace_image_url,
            (m.listing_id IS NOT NULL AND m.image_url IS NULL) AS marketplace_image_is_reference,
            (m.listing_id IS NULL) AS marketplace_is_self_capture,
            COALESCE(m.delivered_price, a.price) AS marketplace_price,
            m.condition AS marketplace_condition,
            COALESCE(m.scored_at, a.captured_at) AS marketplace_seen_at
        FROM latest a
        LEFT JOIN LATERAL (
            SELECT s.listing_id, s.source, s.title,
                s.url, COALESCE(
                    CASE WHEN s.image_url ~* '^https?://' AND s.image_url NOT LIKE '%._RC' THEN s.image_url END,
                    o.image_url
                ) AS image_url,
                s.delivered_price, s.condition, s.scored_at
            FROM gem_radar_scored_listings s
            LEFT JOIN LATERAL (
                SELECT image_url FROM gem_radar_listing_observations
                WHERE listing_id = s.listing_id
                  AND image_url ~* '^https?://'
                  AND image_url NOT LIKE '%._RC'
                ORDER BY observed_at DESC, id DESC LIMIT 1
            ) o ON true
            WHERE s.delivered_price > 0
              AND (s.listing_id = a.asin OR (
                a.cpk IS NOT NULL AND s.cpk = a.cpk AND s.category IN (
                  CASE a.category WHEN 'storage' THEN 'ssd'
                      WHEN 'cooler' THEN 'cooling' ELSE a.category END,
                  a.category
                )
              ))
            ORDER BY (s.listing_id = a.asin) DESC,
                (COALESCE(
                CASE WHEN s.image_url ~* '^https?://' AND s.image_url NOT LIKE '%._RC' THEN s.image_url END,
                o.image_url
            ) IS NOT NULL) DESC,
                s.scored_at DESC
            LIMIT 1
        ) m ON true
        LEFT JOIN curated_bestseller_reviews r
            ON r.category = a.category AND r.cpk = COALESCE(a.cpk, 'asin:' || a.asin)
        WHERE a.category <> 'cooler' OR (
            a.title ~* '\\m(cpu[[:space:]]+(air[[:space:]]+|liquid[[:space:]]+)?cooler|air[[:space:]]+cooler|liquid[[:space:]]+cooler|aio|all[-[:space:]]in[-[:space:]]one[[:space:]]+(cpu[[:space:]]+)?cooler|cpu[[:space:]]+heatsink)\\M'
            AND a.title !~* '\\m(thermal[[:space:]]+paste|paste|thermal[[:space:]]+compound|thermal[[:space:]]+grease|thermal[[:space:]]+pad|cooling[[:space:]]+pad|case[[:space:]]+fan|fan[[:space:]]+hub)\\M'
        )
        ORDER BY a.category, a.rank
    """))).mappings().all()
    return {"items": [dict(row) for row in rows]}


class BestsellerReviewInput(BaseModel):
    category: str = Field(min_length=1, max_length=40)
    cpk: str = Field(min_length=1, max_length=255)
    status: str


@router.put("/bestseller-catalogue/review")
async def review_bestseller(body: BestsellerReviewInput, db: AsyncSession = Depends(get_db)):
    if body.status not in {"approved", "rejected", "pending"}:
        raise HTTPException(status_code=422, detail="Invalid review status")
    exists = (await db.execute(text("""
        SELECT EXISTS (
            SELECT 1 FROM amazon_bestseller_observations a
            WHERE a.category = :category
              AND COALESCE(a.cpk, 'asin:' || a.asin) = :cpk
        )
    """), {"category": body.category, "cpk": body.cpk})).scalar()
    if not exists:
        raise HTTPException(status_code=404, detail="Matched bestseller product not found")
    invalidated_cells = 0
    if body.status != "approved":
        segments = (await db.execute(select(CuratedBuildSegment))).scalars().all()
        for segment in segments:
            pair = segment.approved_upgrades or []
            if any(
                item.get("popularity_evidence", {}).get("category") == body.category
                and item.get("popularity_evidence", {}).get("cpk") == body.cpk
                for item in pair if isinstance(item, dict)
            ):
                segment.approved_upgrades = []
                segment.is_live = False
                invalidated_cells += 1
    if body.status == "approved":
        has_image = (await db.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM amazon_bestseller_observations a
                WHERE a.category = :category
                  AND COALESCE(a.cpk, 'asin:' || a.asin) = :cpk
                  AND a.image_url ~* '^https?://'
                  AND a.image_url NOT LIKE '%._RC'
            ) OR EXISTS (
                SELECT 1 FROM gem_radar_scored_listings s
                WHERE s.cpk = :cpk AND s.delivered_price > 0
                  AND s.category IN (
                      CASE :category WHEN 'storage' THEN 'ssd'
                          WHEN 'cooler' THEN 'cooling' ELSE :category END,
                      :category
                  )
                  AND ((s.image_url ~* '^https?://' AND s.image_url NOT LIKE '%._RC') OR EXISTS (
                      SELECT 1 FROM gem_radar_listing_observations o
                      WHERE o.listing_id = s.listing_id
                        AND ((o.image_url ~* '^https?://' AND o.image_url NOT LIKE '%._RC')
                          OR jsonb_array_length(COALESCE(o.image_urls::jsonb, '[]'::jsonb)) > 0)
                  ))
            )
        """), {"category": body.category, "cpk": body.cpk})).scalar()
        if not has_image:
            raise HTTPException(status_code=409, detail="Capture a product picture before approving this match")
    if body.status == "pending":
        await db.execute(text("""
            DELETE FROM curated_bestseller_reviews
            WHERE category = :category AND cpk = :cpk
        """), {"category": body.category, "cpk": body.cpk})
    else:
        await db.execute(text("""
            INSERT INTO curated_bestseller_reviews (category, cpk, status, reviewed_at)
            VALUES (:category, :cpk, :status, now())
            ON CONFLICT (category, cpk) DO UPDATE
            SET status = EXCLUDED.status, reviewed_at = EXCLUDED.reviewed_at
        """), {"category": body.category, "cpk": body.cpk, "status": body.status})
    return {"category": body.category, "cpk": body.cpk, "review_status": body.status, "invalidated_cells": invalidated_cells}


class SegmentInput(BaseModel):
    customer_type: str = Field(min_length=1, max_length=120)
    budget_level: str = Field(min_length=1, max_length=80)
    budget_min: float | None = None
    budget_max: float | None = None
    components: dict[str, int] | None = None
    software_profile: dict | None = None
    approved_upgrades: list[dict] | None = None
    allow_flip_component_sources: bool | None = None
    selling_price: float | None = None
    is_live: bool | None = None


@router.get("/match-budget")
async def match_budget(customer_type: str, budget_gbp: float, db: AsyncSession = Depends(get_db)):
    if budget_gbp < 0:
        raise HTTPException(status_code=422, detail="Budget must be zero or greater")
    segments = (await db.execute(select(CuratedBuildSegment).where(
        CuratedBuildSegment.customer_type == customer_type,
        CuratedBuildSegment.budget_min.is_not(None),
    ))).scalars().all()
    matches = [s for s in segments if s.budget_min <= budget_gbp and (s.budget_max is None or budget_gbp < s.budget_max)]
    if len(matches) != 1:
        raise HTTPException(status_code=404, detail="No unique budget segment found for this customer type and amount")
    return _segment_json(matches[0])


@router.get("/segments/{segment_id}/flip-matches")
async def match_potential_flips_to_segment(
    segment_id: int,
    delivery_mode: str = "flexible",
    db: AsyncSession = Depends(get_db),
):
    """Find potential whole-PC flips that can meet a playbook cell's baseline.

    This is a sourcing suggestion only: it does not allocate inventory,
    publish a product, or mark a flip as ready for sale.
    """
    if delivery_mode not in {"flexible", "ready_to_ship"}:
        raise HTTPException(status_code=422, detail="Flip sources are only allowed for Flexible or Ready-to-Ship builds")
    segment = await db.get(CuratedBuildSegment, segment_id)
    if not segment:
        raise HTTPException(status_code=404, detail="Playbook segment not found")
    if not segment.allow_flip_component_sources:
        return {"segment_id": segment.id, "delivery_mode": delivery_mode, "matches": [], "reason": "Flip component sourcing is disabled for this playbook cell"}

    selected = {key: int(value) for key, value in (segment.components or {}).items() if str(value).isdigit()}
    target_rows = (await db.execute(
        select(PlaybookSlot.slot_type, Listing)
        .join(CatalogueVariant, CatalogueVariant.slot_id == PlaybookSlot.id)
        .join(Listing, Listing.id == CatalogueVariant.listing_id)
        .where(CatalogueVariant.id.in_(set(selected.values())))
    )).all()
    targets = {slot_type: listing for slot_type, listing in target_rows}
    benchmark_rows = (await db.execute(select(HardwareBenchmark).where(
        HardwareBenchmark.component_type.in_(["cpu", "gpu"]),
        HardwareBenchmark.overall_score.is_not(None),
    ))).scalars().all()
    benchmark_index: dict[tuple[str, str], HardwareBenchmark] = {}
    for row in benchmark_rows:
        key = (row.component_type.casefold(), row.normalized_model)
        current = benchmark_index.get(key)
        if current is None or (row.confidence_score or 0) > (current.confidence_score or 0):
            benchmark_index[key] = row

    use_case = (segment.customer_type or "").casefold()
    metric = "gaming_score" if "gaming" in use_case else "workstation_score" if any(word in use_case for word in ("workstation", "creator", "ai")) else "overall_score"

    def benchmark(kind: str, model: str | None):
        if not model:
            return None
        normalised = normalise_cpu(model) if kind == "cpu" else normalise_gpu(model)
        return benchmark_index.get((kind, normalised)) if normalised else None

    flips = (await db.execute(
        select(Flip, Listing).join(Listing, Listing.id == Flip.listing_id)
        .where(Flip.stage.in_([FlipStage.selected, FlipStage.building, FlipStage.ready_for_sale]))
        .order_by(Flip.created_at.desc()).limit(200)
    )).all()
    matches = []
    for flip, candidate in flips:
        checks = []
        upgrade_models: dict[str, str] = {}
        upgrade_component_names: list[str] = []
        for category, part_id in (flip.selected_upgrade_ids or {}).items():
            try:
                part = await db.get(Part, int(part_id))
            except (TypeError, ValueError):
                part = None
            if not part:
                continue
            category_key = str(category).casefold().replace(" ", "_")
            if category_key in {"cpu", "gpu", "graphics", "graphics_card"}:
                upgrade_models["gpu" if category_key in {"graphics", "graphics_card"} else category_key] = part.model or part.name
            upgrade_component_names.append(part.name)
        candidate_cost = (flip.listing_price or flip.current_estimated_resale or candidate.estimated_resale)
        if candidate_cost is None or segment.budget_min is None:
            checks.append({"slot": "budget", "status": "insufficient_evidence", "reason": "A resale estimate and segment budget range are required"})
        elif candidate_cost < segment.budget_min or (segment.budget_max is not None and candidate_cost >= segment.budget_max):
            checks.append({"slot": "budget", "status": "below_or_above_range", "candidate_gbp": round(candidate_cost, 2)})
        else:
            checks.append({"slot": "budget", "status": "matched", "candidate_gbp": round(candidate_cost, 2)})

        for slot, kind in (("cpu", "cpu"), ("gpu", "gpu")):
            if slot not in selected:
                if slot == "cpu":
                    checks.append({"slot": slot, "status": "insufficient_evidence", "reason": "The playbook cell has no selected CPU baseline"})
                continue
            target = targets.get(slot)
            target_model = ((target.cpu if kind == "cpu" else target.gpu) or target.title) if target else None
            candidate_model = upgrade_models.get(kind) or getattr(candidate, kind)
            target_benchmark = benchmark(kind, target_model)
            candidate_benchmark = benchmark(kind, candidate_model)
            if not target_benchmark or not candidate_benchmark:
                checks.append({"slot": slot, "status": "insufficient_evidence", "target_model": target_model, "candidate_model": candidate_model})
                continue
            target_score = getattr(target_benchmark, metric, None) or target_benchmark.overall_score
            candidate_score = getattr(candidate_benchmark, metric, None) or candidate_benchmark.overall_score
            if target_score is None or candidate_score is None:
                checks.append({"slot": slot, "status": "insufficient_evidence", "target_model": target_benchmark.model, "candidate_model": candidate_benchmark.model, "metric": metric})
                continue
            checks.append({
                "slot": slot,
                "status": "matched" if candidate_score >= target_score else "below_target",
                "target_model": target_benchmark.model,
                "candidate_model": candidate_benchmark.model,
                "metric": metric,
                "target_score": target_score,
                "candidate_score": candidate_score,
            })

        # The flip PC will receive a replacement case as part of refurbishment;
        # other component slots not represented by measurable specs remain an
        # explicit follow-up check instead of being assumed compatible.
        for slot in selected.keys() - {"cpu", "gpu", "case"}:
            checks.append({"slot": slot, "status": "manual_compatibility_check", "reason": "This component's fit/specs are not fully represented on the potential-flip listing"})
        measurable = [check for check in checks if check["slot"] in {"budget", "cpu", "gpu"}]
        eligible = bool(measurable) and all(check["status"] == "matched" for check in measurable)
        if eligible or any(check["status"] != "matched" for check in checks):
            matches.append({
                "flip_id": flip.id,
                "listing_id": candidate.id,
                "title": candidate.title,
                "url": candidate.url,
                "stage": flip.stage.value if hasattr(flip.stage, "value") else str(flip.stage),
                "estimated_customer_price_gbp": round(candidate_cost, 2) if candidate_cost is not None else None,
                "meets_measured_requirements": eligible,
                "checks": checks,
                "recovered_component_slots": [slot for slot, value in (("cpu", upgrade_models.get("cpu") or candidate.cpu), ("gpu", upgrade_models.get("gpu") or candidate.gpu), ("ram", candidate.ram_gb), ("storage", candidate.storage_gb), ("psu", candidate.psu_wattage)) if value],
                "selected_upgrade_components": upgrade_component_names,
                "case_replacement_required": True,
            })
    return {"segment_id": segment.id, "delivery_mode": delivery_mode, "performance_metric": metric, "matches": matches}


SLOT_BESTSELLER_CATEGORY = {
    "cpu": "cpu", "gpu": "gpu", "motherboard": "motherboard",
    "ram": "ram", "storage": "storage", "psu": "psu",
    "cooling": "cooler", "case": "case",
}


def _segment_json(segment: CuratedBuildSegment) -> dict:
    return {
        "id": segment.id,
        "customer_type": segment.customer_type,
        "budget_level": segment.budget_level,
        "budget_min": segment.budget_min,
        "budget_max": segment.budget_max,
        "components": segment.components or {},
        "software_profile": segment.software_profile,
        "approved_upgrades": segment.approved_upgrades or [],
        "bestseller_components": segment.bestseller_components or {},
        "allow_flip_component_sources": segment.allow_flip_component_sources,
        "selling_price": segment.selling_price,
        "proposed_selling_price": segment.proposed_selling_price,
        "availability_status": segment.availability_status,
        "is_live": segment.is_live,
        "regeneration_status": segment.regeneration_status,
        "regeneration_request_id": segment.regeneration_request_id,
        "regeneration_error": segment.regeneration_error,
        "updated_at": segment.updated_at.isoformat() if segment.updated_at else None,
    }


async def _validate_approved_upgrades(
    db: AsyncSession, customer_type: str, budget_level: str, upgrades: list[dict]
) -> list[dict]:
    """Bind reviewed component offers to draft candidates and market evidence."""
    if not upgrades:
        return []
    draft_path = Path(__file__).resolve().parents[3] / "tmp" / "curated-playbooks-v1-stub.json"
    if not draft_path.is_file():
        raise ValueError("The source Playbook draft is unavailable")
    draft = json.loads(draft_path.read_text(encoding="utf-8"))
    cell = next((item for item in draft.get("playbooks", [])
                 if str(item.get("customer_type", "")).casefold() == customer_type.casefold()
                 and str(item.get("budget_tier", "")).casefold() == budget_level.casefold()), None)
    if cell is None:
        raise ValueError("No matching source Playbook cell exists")
    candidates = cell.get("upsells", [])
    selected: list[dict] = []
    candidate_indexes: set[int] = set()
    target_ids: set[int] = set()
    playbook_id = (await db.execute(
        select(Playbook.id).where(Playbook.name.ilike(customer_type))
    )).scalar_one_or_none()
    if playbook_id is None:
        raise ValueError("The customer type does not have a Playbook catalogue")
    for item in upgrades:
        try:
            index = int(item["candidate_index"])
            saved_evidence = item.get("popularity_evidence") or {}
            cpk = str(item.get("popularity_cpk") or saved_evidence.get("cpk") or "").strip()
            evidence_category = str(item.get("evidence_category") or saved_evidence.get("category") or "").strip()
            target_variant_id = int(item.get("target_variant_id") or (item.get("target_variant") or {}).get("id"))
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("Each upgrade needs a candidate, approved bestseller match and curated catalogue component") from exc
        if index < 0 or index >= len(candidates) or index in candidate_indexes:
            raise ValueError("Selected upgrade does not identify a unique source candidate")
        if not cpk:
            raise ValueError("The popularity match must be identified")
        candidate = candidates[index]
        if item.get("to_sku") and (
            item.get("to_sku") != candidate.get("to_sku")
            or item.get("from_sku") != candidate.get("from_sku")
            or item.get("category") != candidate.get("category")
        ):
            raise ValueError("The source Playbook candidate changed; review the selected pair again")
        expected_category = {
            "cpu / apu": "cpu", "motherboard": "motherboard", "memory": "ram",
            "graphics": "gpu", "primary storage": "storage", "power supply": "psu",
            "cpu cooling": "cooler",
        }.get(str(candidate.get("category", "")).casefold())
        if expected_category is None:
            raise ValueError("Case upgrades are not supported by the component catalogue")
        if evidence_category != expected_category:
            raise ValueError("Bestseller evidence must be from the selected component category")
        expected_slot = {"cpu": "cpu", "gpu": "gpu", "motherboard": "motherboard", "ram": "ram",
                         "storage": "storage", "psu": "psu", "cooler": "cooling", "case": "case"}[expected_category]
        target = (await db.execute(
            select(CatalogueVariant, Listing, PlaybookSlot)
            .join(Listing, Listing.id == CatalogueVariant.listing_id)
            .join(PlaybookSlot, PlaybookSlot.id == CatalogueVariant.slot_id)
            .where(
                CatalogueVariant.id == target_variant_id,
                CatalogueVariant.curated_for_builds.is_(True),
                CatalogueVariant.status == "active",
                Listing.status == "active",
                PlaybookSlot.playbook_id == playbook_id,
                PlaybookSlot.slot_type == expected_slot,
            )
        )).first()
        if not target:
            raise ValueError("Upgrade target must be active in this Playbook cell's curated catalogue")
        target_variant, target_listing, target_slot = target
        if target_variant.id in target_ids:
            raise ValueError("A curated component can only be approved once for this Playbook cell")
        target_ids.add(target_variant.id)
        evidence = (await db.execute(text("""
            SELECT a.rank, a.price, a.title, a.url, a.captured_at
            FROM amazon_bestseller_observations a
            JOIN curated_bestseller_reviews r ON r.category = a.category
                AND r.cpk = COALESCE(a.cpk, 'asin:' || a.asin)
                AND r.status = 'approved'
            WHERE a.category = :category
              AND COALESCE(a.cpk, 'asin:' || a.asin) = :cpk
            ORDER BY a.captured_at DESC LIMIT 1
        """), {"category": evidence_category, "cpk": cpk})).mappings().first()
        if not evidence or not evidence["rank"] or not evidence["price"] or evidence["price"] <= 0:
            raise ValueError("Popularity evidence must be an approved bestseller with a rank and price")
        normalize = lambda value: "".join(char.casefold() for char in str(value) if char.isalnum())
        if normalize(candidate.get("to_sku", "")) not in normalize(evidence["title"]):
            raise ValueError("Approved bestseller evidence does not identify the selected upgrade model")
        if normalize(candidate.get("to_sku", "")) not in normalize(target_listing.title):
            raise ValueError("Curated catalogue target does not identify the selected upgrade model")
        performance_evidence = None
        if expected_category in {"cpu", "gpu"}:
            normalize_model = normalise_cpu if expected_category == "cpu" else normalise_gpu
            benchmark_models = {
                value for value in (
                    normalize_model(str(candidate.get("from_sku") or "")),
                    normalize_model(str(candidate.get("to_sku") or "")),
                ) if value
            }
            benchmark_rows = (await db.execute(
                select(HardwareBenchmark).where(
                    HardwareBenchmark.component_type == expected_category,
                    HardwareBenchmark.normalized_model.in_(benchmark_models),
                )
            )).scalars().all() if benchmark_models else []
            performance_evidence = _upgrade_performance_evidence(
                component_type=expected_category,
                baseline_model=str(candidate.get("from_sku") or ""),
                candidate_model=str(candidate.get("to_sku") or ""),
                customer_type=customer_type,
                benchmark_rows=benchmark_rows,
            )
        candidate_indexes.add(index)
        selected.append({
            "candidate_index": index,
            "category": candidate["category"],
            "from_sku": candidate["from_sku"],
            "to_sku": candidate["to_sku"],
            "delta_cost_gbp": float(candidate["delta_cost_gbp"]),
            "slot_id": target_slot.id,
            "target_variant_id": target_variant.id,
            "target_title": target_listing.title,
            "target_display_price": float(target_variant.display_price),
            "performance_evidence": performance_evidence,
            "popularity_evidence": {
                "source": "approved_amazon_bestseller",
                "category": evidence_category,
                "cpk": cpk,
                "rank": int(evidence["rank"]),
                "observed_price_gbp": float(evidence["price"]),
                "title": evidence["title"],
                "url": evidence["url"],
                "captured_at": evidence["captured_at"].isoformat() if evidence["captured_at"] else None,
            },
        })
    return selected


def _upgrade_performance_evidence(
    *,
    component_type: str,
    baseline_model: str,
    candidate_model: str,
    customer_type: str,
    benchmark_rows: list[HardwareBenchmark],
) -> dict:
    """Require benchmark-backed, equal-or-better CPU/GPU upgrades per cell."""
    metric = (
        "gaming_score" if "gaming" in customer_type.casefold()
        else "workstation_score"
        if any(word in customer_type.casefold() for word in ("workstation", "creator", "ai"))
        else "overall_score"
    )
    normalize = normalise_cpu if component_type == "cpu" else normalise_gpu
    baseline_key = normalize(baseline_model)
    candidate_key = normalize(candidate_model)

    def best_match(model_key: str) -> HardwareBenchmark | None:
        matches = [
            row for row in benchmark_rows
            if row.component_type.casefold() == component_type
            and row.normalized_model == model_key
        ]
        return max(matches, key=lambda row: row.confidence_score or 0, default=None)

    baseline = best_match(baseline_key) if baseline_key else None
    candidate = best_match(candidate_key) if candidate_key else None
    if baseline is None or candidate is None:
        raise ValueError(
            f"Cannot approve this {component_type.upper()} upgrade: current benchmark evidence is missing for the baseline or proposed model"
        )
    baseline_score = getattr(baseline, metric, None) or baseline.overall_score
    candidate_score = getattr(candidate, metric, None) or candidate.overall_score
    if baseline_score is None or candidate_score is None:
        raise ValueError(
            f"Cannot approve this {component_type.upper()} upgrade: benchmark scores are missing for the baseline or proposed model"
        )
    if candidate_score < baseline_score:
        raise ValueError(
            f"The proposed {component_type.upper()} upgrade scores below this Playbook cell's baseline ({candidate_score:g} < {baseline_score:g})"
        )
    return {
        "metric": metric,
        "baseline_model": baseline.model,
        "baseline_score": float(baseline_score),
        "candidate_model": candidate.model,
        "candidate_score": float(candidate_score),
        "benchmark_source": candidate.benchmark_source,
        "baseline_benchmark_source": baseline.benchmark_source,
    }


async def _component_context(db: AsyncSession, ids: set[int]) -> dict[int, dict]:
    if not ids:
        return {}
    rows = (await db.execute(
        select(CatalogueVariant, Listing, PlaybookSlot)
        .join(Listing, Listing.id == CatalogueVariant.listing_id)
        .join(PlaybookSlot, PlaybookSlot.id == CatalogueVariant.slot_id)
        .where(CatalogueVariant.id.in_(ids))
    )).all()
    return {
        variant.id: {
            "id": variant.id,
            "slot_type": slot.slot_type,
            "title": listing.title,
            "price": listing.price,
            "status": listing.status.value if hasattr(listing.status, "value") else listing.status,
            "last_seen_at": listing.last_seen_at.isoformat() if listing.last_seen_at else None,
            "image_url": listing.image_urls[0] if listing.image_urls else None,
            "url": listing.url,
            "curated_for_builds": variant.curated_for_builds,
        }
        for variant, listing, slot in rows
    }


def _listing_asin(listing: Listing) -> str | None:
    """Read an ASIN only from an exact Amazon identifier or product URL."""
    for key, value in (listing.raw_specs or {}).items():
        if str(key).casefold() not in {"asin", "amazon_asin"}:
            continue
        candidate = str(value or "").strip().upper()
        if len(candidate) == 10 and candidate.isalnum():
            return candidate
    external_id = str(listing.external_id or "").strip().upper()
    if len(external_id) == 10 and external_id.isalnum():
        return external_id
    match = re.search(r"/(?:dp|gp/product)/([A-Z0-9]{10})(?:[/?]|$)", listing.url or "", re.I)
    return match.group(1).upper() if match else None


@router.post("/auto-link-bestseller-components")
async def auto_link_bestseller_components(db: AsyncSession = Depends(get_db)):
    """Link Playbook CPK/ASIN identities to matching active curated listings."""
    segments = (await db.execute(select(CuratedBuildSegment))).scalars().all()
    identities = {
        (slot, str(choice.get("category") or SLOT_BESTSELLER_CATEGORY.get(slot) or ""), str(choice.get("cpk") or ""))
        for segment in segments
        for slot, choice in (segment.bestseller_components or {}).items()
        if isinstance(choice, dict) and choice.get("cpk")
    }
    cpks = {cpk for _, _, cpk in identities}
    if not cpks:
        return {"linked": 0, "unmatched": 0, "segments_updated": 0, "message": "No saved Amazon CPK identities were found."}

    categories = {category for _, category, _ in identities if category}
    asin_rows = (await db.execute(
        select(AmazonBestsellerObservation.category, AmazonBestsellerObservation.cpk, AmazonBestsellerObservation.asin)
        .where(
            AmazonBestsellerObservation.cpk.in_(cpks),
            AmazonBestsellerObservation.category.in_(categories),
        )
        .order_by(AmazonBestsellerObservation.captured_at.desc())
    )).all()
    asins_by_identity: dict[tuple[str, str], set[str]] = {}
    for category, cpk, asin in asin_rows:
        if cpk and asin:
            asins_by_identity.setdefault((str(category), str(cpk)), set()).add(str(asin).upper())

    variants = (await db.execute(
        select(CatalogueVariant, Listing, PlaybookSlot)
        .join(Listing, Listing.id == CatalogueVariant.listing_id)
        .join(PlaybookSlot, PlaybookSlot.id == CatalogueVariant.slot_id)
        .where(Listing.status == ListingStatus.active)
    )).all()
    listing_cpks = (await db.execute(
        select(GemRadarListingCpk.listing_id, GemRadarListingCpk.cpk)
        .where(GemRadarListingCpk.cpk.in_(cpks))
    )).all()
    cpk_by_listing = {str(listing_id): str(cpk) for listing_id, cpk in listing_cpks}
    candidates_by_slot: dict[str, list[tuple[int, int, str, str | None, float, bool]]] = {}
    for variant, listing, slot in variants:
        candidate_cpk = cpk_by_listing.get(str(listing.external_id))
        candidate_asin = _listing_asin(listing)
        candidates_by_slot.setdefault(slot.slot_type, []).append((
            slot.playbook_id, variant.id, candidate_cpk or "", candidate_asin,
            float(listing.price or variant.display_price or 0), variant.curated_for_builds,
        ))

    linked = unmatched = segments_updated = 0
    linked_needs_curation = 0
    playbooks = (await db.execute(
        select(Playbook.id, Playbook.name).where(
            func.lower(Playbook.name).in_({segment.customer_type.casefold() for segment in segments})
        )
    )).all()
    playbook_ids = {name.casefold(): playbook_id for playbook_id, name in playbooks}
    for segment in segments:
        components = dict(segment.components or {})
        segment_changed = False
        for slot, choice in (segment.bestseller_components or {}).items():
            if not isinstance(choice, dict) or not choice.get("cpk"):
                continue
            cpk = str(choice["cpk"])
            expected_category = SLOT_BESTSELLER_CATEGORY.get(slot)
            if not expected_category or choice.get("category") != expected_category:
                unmatched += 1
                continue
            asin_set = asins_by_identity.get((expected_category, cpk), set())
            matches = [
                candidate for candidate in candidates_by_slot.get(slot, [])
                if candidate[0] == playbook_ids.get(segment.customer_type.casefold())
                and (candidate[2] == cpk or (candidate[3] and candidate[3] in asin_set))
            ]
            if not matches:
                unmatched += 1
                continue
            # Keep already-curated offers first; then prefer an exact ASIN and
            # the lowest active price among equivalent supplier offers.
            matches.sort(key=lambda candidate: (not candidate[5], candidate[3] not in asin_set, candidate[4], candidate[1]))
            components[slot] = matches[0][1]
            if not matches[0][5]:
                linked_needs_curation += 1
            linked += 1
            segment_changed = True
        if segment_changed:
            segment.components = components
            segments_updated += 1

    await db.commit()
    return {
        "linked": linked,
        "unmatched": unmatched,
        "linked_needs_curation": linked_needs_curation,
        "segments_updated": segments_updated,
    }


@router.get("")
async def get_curated_builds(db: AsyncSession = Depends(get_db)):
    segments = (await db.execute(select(CuratedBuildSegment).order_by(
        CuratedBuildSegment.customer_type, CuratedBuildSegment.budget_min,
        CuratedBuildSegment.budget_level,
    ))).scalars().all()
    customer_types = {segment.customer_type for segment in segments}
    playbooks = (await db.execute(select(Playbook).where(Playbook.name.in_(customer_types)))).scalars().all() if customer_types else []
    playbooks_by_name = {playbook.name.casefold(): playbook for playbook in playbooks}
    ids = {int(value) for segment in segments for value in (segment.components or {}).values() if str(value).isdigit()}
    context = await _component_context(db, ids)
    payload = []
    for segment in segments:
        row = _segment_json(segment)
        if segment.software_profile is None:
            from app.services.software_catalogue import effective_software_profile_for_playbook
            playbook = playbooks_by_name.get(segment.customer_type.casefold())
            row["effective_software_profile"] = effective_software_profile_for_playbook(
                segment.customer_type,
                playbook.software_profile if playbook else None,
            )
        else:
            row["effective_software_profile"] = segment.software_profile
        component_rows = {key: context.get(int(value)) for key, value in (segment.components or {}).items()}
        row["component_details"] = component_rows
        selected = [item for item in component_rows.values() if item]
        total = sum(item["price"] or 0 for item in selected)
        row["component_cost"] = round(total, 2)
        if segment.component_cost_snapshot is not None and segment.selling_price is not None:
            delta = total - segment.component_cost_snapshot
            if abs(delta) >= 0.01 and segment.proposed_selling_price is None:
                row["proposed_selling_price"] = round(max(0, segment.selling_price + delta), 2)
        assigned_count = len(segment.components or {})
        if assigned_count == 0:
            row["availability_status"] = "not_configured"
        else:
            row["availability_status"] = "out_of_stock" if len(selected) != assigned_count or any(item["status"] != "active" for item in selected) else "in_stock"
        if row["availability_status"] != "in_stock" and segment.is_live:
            segment.is_live = False
        payload.append(row)
    return {"segments": payload, "components": list((await _component_context(db, {
        row[0].id for row in (await db.execute(
            select(CatalogueVariant, Listing, PlaybookSlot)
            .join(Listing, Listing.id == CatalogueVariant.listing_id)
            .join(PlaybookSlot, PlaybookSlot.id == CatalogueVariant.slot_id)
            .where(CatalogueVariant.curated_for_builds.is_(True))
        )).all()
    })).values())}


@router.post("/segments")
async def upsert_segment(body: SegmentInput, db: AsyncSession = Depends(get_db)):
    if body.budget_min is not None and body.budget_min < 0:
        raise HTTPException(status_code=422, detail="Minimum budget must be zero or greater")
    if body.budget_max is not None and (body.budget_min is None or body.budget_max <= body.budget_min):
        raise HTTPException(status_code=422, detail="Maximum budget must be greater than minimum budget")
    # Curated-cell software profiles are consumed by Getting Ready package
    # generation. Lock the owning Playbook before reading/upserting the cell
    # so generation can serialize against both edits and first-time inserts.
    (await db.execute(
        select(Playbook.id)
        .where(func.lower(func.trim(Playbook.name)) == body.customer_type.strip().casefold())
        .with_for_update()
    )).scalar_one_or_none()
    segment = (await db.execute(select(CuratedBuildSegment).where(
        CuratedBuildSegment.customer_type == body.customer_type,
        CuratedBuildSegment.budget_level == body.budget_level,
    ))).scalar_one_or_none()
    if body.budget_min is not None:
        peers = (await db.execute(select(CuratedBuildSegment).where(
            CuratedBuildSegment.customer_type == body.customer_type,
            CuratedBuildSegment.budget_min.is_not(None),
        ))).scalars().all()
        for peer in peers:
            if segment is not None and peer.id == segment.id:
                continue
            if (body.budget_max is None or peer.budget_min < body.budget_max) and (peer.budget_max is None or body.budget_min < peer.budget_max):
                raise HTTPException(status_code=409, detail=f"Budget range overlaps {peer.budget_level}")
    if segment is None:
        segment = CuratedBuildSegment(customer_type=body.customer_type, budget_level=body.budget_level)
        db.add(segment)
    segment.budget_min = body.budget_min
    segment.budget_max = body.budget_max
    if body.components is not None:
        segment.components = body.components
    if "software_profile" in body.model_fields_set:
        if body.software_profile is None:
            segment.software_profile = None
        else:
            from app.services.software_catalogue import normalize_software_profile
            try:
                segment.software_profile = normalize_software_profile(body.software_profile)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
    if "approved_upgrades" in body.model_fields_set:
        if segment.is_live and not body.approved_upgrades:
            raise HTTPException(status_code=409, detail="Unpublish this Playbook cell before removing its reviewed component offers")
        try:
            segment.approved_upgrades = await _validate_approved_upgrades(
                db, segment.customer_type, segment.budget_level, body.approved_upgrades or []
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    if body.allow_flip_component_sources is not None:
        segment.allow_flip_component_sources = body.allow_flip_component_sources
    if body.selling_price is not None:
        segment.selling_price = body.selling_price
        ids = {int(value) for value in (body.components or segment.components or {}).values() if str(value).isdigit()}
        context = await _component_context(db, ids)
        segment.component_cost_snapshot = sum(item["price"] or 0 for item in context.values())
    if body.is_live is not None:
        segment.is_live = body.is_live
    await db.flush()
    return _segment_json(segment)


class BestsellerComponentInput(BaseModel):
    slot: str
    cpk: str | None = None


@router.put("/segments/{segment_id}/bestseller-component")
async def set_segment_bestseller_component(
    segment_id: int, body: BestsellerComponentInput, db: AsyncSession = Depends(get_db)
):
    segment = await db.get(CuratedBuildSegment, segment_id)
    if not segment:
        raise HTTPException(status_code=404, detail="Playbook segment not found")
    category = SLOT_BESTSELLER_CATEGORY.get(body.slot)
    if not category:
        raise HTTPException(status_code=422, detail="Unknown build component slot")
    choices = dict(segment.bestseller_components or {})
    if body.cpk:
        eligible = (await db.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM amazon_bestseller_observations a
                JOIN gem_radar_scored_listings s ON s.cpk = a.cpk
                LEFT JOIN curated_bestseller_reviews r
                    ON r.category = a.category AND r.cpk = a.cpk
                WHERE a.category = :category AND a.cpk = :cpk
                  AND (a.category <> 'cooler' OR (
                      a.title ~* '\\m(cpu[[:space:]]+(air[[:space:]]+|liquid[[:space:]]+)?cooler|air[[:space:]]+cooler|liquid[[:space:]]+cooler|aio|all[-[:space:]]in[-[:space:]]one[[:space:]]+(cpu[[:space:]]+)?cooler|cpu[[:space:]]+heatsink)\\M'
                      AND a.title !~* '\\m(thermal[[:space:]]+paste|paste|thermal[[:space:]]+compound|thermal[[:space:]]+grease|thermal[[:space:]]+pad|cooling[[:space:]]+pad|case[[:space:]]+fan|fan[[:space:]]+hub)\\M'
                  ))
                  AND COALESCE(r.status, 'pending') <> 'rejected'
                  AND s.delivered_price > 0
                  AND s.category IN (
                      CASE a.category WHEN 'storage' THEN 'ssd'
                          WHEN 'cooler' THEN 'cooling' ELSE a.category END,
                      a.category
                  )
                  AND (a.image_url ~* '^https?://' OR
                       (s.image_url ~* '^https?://' AND s.image_url NOT LIKE '%._RC') OR EXISTS (
                      SELECT 1 FROM gem_radar_listing_observations o
                      WHERE o.listing_id = s.listing_id
                        AND o.image_url ~* '^https?://'
                        AND o.image_url NOT LIKE '%._RC'
                  ))
            )
        """), {"category": category, "cpk": body.cpk})).scalar()
        if not eligible:
            raise HTTPException(status_code=409, detail="This bestseller has no eligible marketplace match")
        choices[body.slot] = {"category": category, "cpk": body.cpk}
    else:
        choices.pop(body.slot, None)
    segment.bestseller_components = choices
    segment.is_live = False
    return _segment_json(segment)


@router.patch("/variants/{variant_id}/curated")
async def set_curated_variant(variant_id: int, body: dict, db: AsyncSession = Depends(get_db)):
    variant = await db.get(CatalogueVariant, variant_id)
    if not variant:
        raise HTTPException(status_code=404, detail="Catalogue item not found")
    variant.curated_for_builds = bool(body.get("curated_for_builds"))
    variant.updated_at = datetime.utcnow().isoformat()
    return {"id": variant.id, "curated_for_builds": variant.curated_for_builds}


@router.post("/segments/{segment_id}/generate")
async def generate_segment(segment_id: int, db: AsyncSession = Depends(get_db)):
    segment = await db.get(CuratedBuildSegment, segment_id)
    if not segment:
        raise HTTPException(status_code=404, detail="Playbook segment not found")
    webhook_url = get_settings().hermes_curated_build_webhook_url
    if not webhook_url:
        raise HTTPException(status_code=503, detail="Hermes build webhook is not configured (HERMES_CURATED_BUILD_WEBHOOK_URL)")
    request_id = str(uuid4())
    payload = {
        "event": "curated_build.generate",
        "request_id": request_id,
        "segment": _segment_json(segment),
        "callback_url": get_settings().hermes_curated_build_callback_url or None,
    }
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(webhook_url, json=payload)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Hermes webhook request failed: {exc}") from exc
    segment.regeneration_status = "queued"
    segment.regeneration_request_id = request_id
    segment.regeneration_error = None
    return {"request_id": request_id, "status": "queued", "hermes_response": response.text[:1000]}


@router.post("/segments/{segment_id}/apply-price")
async def apply_proposed_price(segment_id: int, db: AsyncSession = Depends(get_db)):
    segment = await db.get(CuratedBuildSegment, segment_id)
    if not segment or segment.proposed_selling_price is None:
        raise HTTPException(status_code=409, detail="No proposed price is available")
    segment.selling_price = segment.proposed_selling_price
    segment.proposed_selling_price = None
    ids = {int(value) for value in (segment.components or {}).values() if str(value).isdigit()}
    context = await _component_context(db, ids)
    segment.component_cost_snapshot = sum(item["price"] or 0 for item in context.values())
    return _segment_json(segment)


@router.post("/segments/{segment_id}/publish")
async def publish_segment(segment_id: int, body: dict, db: AsyncSession = Depends(get_db)):
    segment = await db.get(CuratedBuildSegment, segment_id)
    if not segment:
        raise HTTPException(status_code=404, detail="Playbook segment not found")
    if not body.get("is_live", True):
        segment.is_live = False
        return _segment_json(segment)
    required = {"cpu", "gpu", "motherboard", "ram", "storage", "psu", "case"}
    selected = segment.components or {}
    if not required.issubset(selected):
        raise HTTPException(status_code=409, detail="Assign CPU, GPU, motherboard, RAM, storage, PSU and case before publishing")
    if segment.selling_price is None or segment.selling_price <= 0:
        raise HTTPException(status_code=409, detail="Set a valid selling price before publishing")
    draft_path = Path(__file__).resolve().parents[3] / "tmp" / "curated-playbooks-v1-stub.json"
    if not draft_path.is_file():
        raise HTTPException(status_code=409, detail="The source Playbook draft is unavailable; component offers cannot be verified")
    draft = json.loads(draft_path.read_text(encoding="utf-8"))
    draft_cell = next((item for item in draft.get("playbooks", [])
                       if str(item.get("customer_type", "")).casefold() == segment.customer_type.casefold()
                       and str(item.get("budget_tier", "")).casefold() == segment.budget_level.casefold()), None)
    if draft_cell is None:
        raise HTTPException(status_code=409, detail="No source Playbook cell is available to verify component offers")
    slot_categories = {"cpu / apu", "motherboard", "memory", "graphics", "primary storage", "power supply", "cpu cooling"}
    draft_upsells = draft_cell.get("upsells", [])
    required_offer_categories = {
        str(item.get("category", "")).casefold()
        for item in draft_upsells
        if isinstance(item, dict) and str(item.get("category", "")).casefold() in slot_categories
    }
    approved_indexes = {
        int(item["candidate_index"])
        for item in (segment.approved_upgrades or [])
        if isinstance(item, dict) and item.get("candidate_index") is not None
    }
    approved_offer_categories = {
        str(draft_upsells[index].get("category", "")).casefold()
        for index in approved_indexes
        if 0 <= index < len(draft_upsells) and isinstance(draft_upsells[index], dict)
    }
    missing_offer_count = len(required_offer_categories - approved_offer_categories)
    if missing_offer_count:
        raise HTTPException(
            status_code=409,
            detail=f"Review and save an offer for every component category with a drafted upgrade ({missing_offer_count} still missing)",
        )
    approved_target_ids = {
        int(item["target_variant_id"])
        for item in (segment.approved_upgrades or [])
        if isinstance(item, dict) and item.get("target_variant_id") is not None
    }
    active_approved_targets = set()
    if approved_target_ids:
        active_approved_targets = set((await db.execute(
            select(CatalogueVariant.id)
            .join(Listing, Listing.id == CatalogueVariant.listing_id)
            .where(
                CatalogueVariant.id.in_(approved_target_ids),
                CatalogueVariant.curated_for_builds.is_(True),
                CatalogueVariant.status == "active",
                Listing.status == "active",
            )
        )).scalars().all())
    if active_approved_targets != approved_target_ids:
        raise HTTPException(status_code=409, detail="One or more reviewed upgrade targets are no longer active in the curated catalogue")
    ids = {int(value) for value in selected.values() if str(value).isdigit()}
    context = await _component_context(db, ids)
    if len(context) != len(ids) or any(not item["curated_for_builds"] or item["status"] != "active" for item in context.values()):
        raise HTTPException(status_code=409, detail="Every selected component must remain curated and currently available")
    segment.is_live = True
    segment.availability_status = "in_stock"
    return _segment_json(segment)
