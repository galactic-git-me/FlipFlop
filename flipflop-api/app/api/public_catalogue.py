"""
Public catalogue endpoints — no auth required.
Consumed by the customer website (Subsystem 3).
"""
from collections import defaultdict
from datetime import datetime, timedelta
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.catalogue import CaseCatalogue, CatalogueVariant, PlaybookSlot
from app.models.configurator import ConfiguratorCatalogueVisibility
from app.models.listing import Listing
from app.models.playbook import Playbook
from app.models.case import Case
from app.models.gem_radar_intelligence import PreferredComponent
from app.services.playbook_pricing import LABOUR_COST, OVERHEAD_RATE
from app.services.studio_fit import engineering_specs

router = APIRouter(prefix="/public", tags=["public"])

_TIER_ORDER = ("budget", "mid", "high")
_TIER_LABELS = {"budget": "Value", "mid": "Balanced", "high": "Performance"}


class BudgetRecommendationRequest(BaseModel):
    purpose: str = Field(min_length=2, max_length=100)
    budget_gbp: float = Field(gt=0, le=100000)


@router.post("/recommendation")
async def recommend_by_budget(body: BudgetRecommendationRequest, db: AsyncSession = Depends(get_db)):
    """Return the strongest complete curated tier within an all-in ceiling."""
    purpose = body.purpose.strip()
    playbook = (
        await db.execute(
            select(Playbook).where(
                Playbook.status == "active",
                Playbook.name.ilike(purpose),
            )
        )
    ).scalar_one_or_none()
    if not playbook:
        raise HTTPException(status_code=404, detail="Curated build purpose not found")

    slots = (
        await db.execute(
            select(PlaybookSlot).where(
                PlaybookSlot.playbook_id == playbook.id,
                PlaybookSlot.is_customer_visible == True,  # noqa: E712
            )
        )
    ).scalars().all()
    if not slots:
        raise HTTPException(status_code=409, detail="Curated build has no customer-visible slots")

    slot_ids = [slot.id for slot in slots]
    visibility_rows = (
        await db.execute(
            select(ConfiguratorCatalogueVisibility).where(
                ConfiguratorCatalogueVisibility.playbook_slot_id.in_(slot_ids),
                ConfiguratorCatalogueVisibility.is_publicly_visible == True,  # noqa: E712
            )
        )
    ).scalars().all()
    visible_ids = {row.catalogue_variant_id for row in visibility_rows}
    curated_slot_ids = {row.playbook_slot_id for row in visibility_rows}

    variant_status_filter = CatalogueVariant.status == "active"
    if visible_ids:
        variant_status_filter = or_(
            variant_status_filter,
            CatalogueVariant.id.in_(visible_ids),
        )
    variant_rows = (
        await db.execute(
            select(CatalogueVariant, Listing)
            .join(Listing, CatalogueVariant.listing_id == Listing.id)
            .where(
                CatalogueVariant.slot_id.in_(slot_ids),
                variant_status_filter,
            )
            .order_by(CatalogueVariant.display_price, CatalogueVariant.id)
        )
    ).all()
    if curated_slot_ids:
        variant_rows = [
            (variant, listing)
            for variant, listing in variant_rows
            if variant.slot_id not in curated_slot_ids or variant.id in visible_ids
        ]

    cheapest_case = (
        await db.execute(
            select(CaseCatalogue)
            .where(CaseCatalogue.status == "active")
            .order_by(CaseCatalogue.rrp_gbp, CaseCatalogue.id)
            .limit(1)
        )
    ).scalar_one_or_none()
    if not cheapest_case:
        raise HTTPException(status_code=409, detail="No active case is available")

    tiers = []
    for tier in _TIER_ORDER:
        selections = []
        missing_slots = []
        for slot in slots:
            match = next(
                (
                    (variant, listing)
                    for variant, listing in variant_rows
                    if variant.slot_id == slot.id and variant.tier == tier
                ),
                None,
            )
            if not match:
                missing_slots.append(slot.slot_type)
                continue
            variant, listing = match
            selections.append({
                "slot_id": slot.id,
                "slot_type": slot.slot_type,
                "variant_id": variant.id,
                "title": listing.title,
                "price_gbp": round(float(variant.display_price), 2),
            })

        parts_total = sum(item["price_gbp"] for item in selections) + float(cheapest_case.rrp_gbp)
        overhead = (parts_total + LABOUR_COST) * OVERHEAD_RATE
        total = round(parts_total + LABOUR_COST + overhead, 2)
        tiers.append({
            "tier": tier,
            "label": _TIER_LABELS[tier],
            "available": not missing_slots,
            "missing_slots": missing_slots,
            "total_gbp": total if not missing_slots else None,
            "within_budget": not missing_slots and total <= body.budget_gbp,
            "case": {
                "id": cheapest_case.id,
                "name": cheapest_case.name,
                "price_gbp": round(float(cheapest_case.rrp_gbp), 2),
            },
            "components": selections,
            "pricing": {
                "parts_and_case_gbp": round(parts_total, 2),
                "labour_gbp": LABOUR_COST,
                "overhead_gbp": round(overhead, 2),
                "all_in_total_gbp": total if not missing_slots else None,
            },
        })

    affordable = [tier for tier in tiers if tier["within_budget"]]
    recommended = affordable[-1] if affordable else None
    available = [tier for tier in tiers if tier["available"]]
    recommended_index = tiers.index(recommended) if recommended else -1
    return {
        "purpose": {"id": playbook.id, "name": playbook.name},
        "budget_gbp": round(body.budget_gbp, 2),
        "recommended": recommended,
        "lower_cost": tiers[recommended_index - 1] if recommended_index > 0 else None,
        "step_up": tiers[recommended_index + 1] if 0 <= recommended_index < len(tiers) - 1 and tiers[recommended_index + 1]["available"] else None,
        "nearest_option": min(available, key=lambda tier: tier["total_gbp"]) if not recommended and available else None,
        "tiers": tiers,
    }


@router.get("/playbooks")
async def public_list_playbooks(db: AsyncSession = Depends(get_db)):
    """Active playbooks with slot definitions and tier_names."""
    result = await db.execute(
        select(Playbook).where(Playbook.status == "active")
    )
    playbooks = result.scalars().all()

    playbook_ids = [pb.id for pb in playbooks]
    if playbook_ids:
        all_slots_result = await db.execute(
            select(PlaybookSlot).where(PlaybookSlot.playbook_id.in_(playbook_ids))
        )
        all_slots = all_slots_result.scalars().all()
    else:
        all_slots = []

    # Group slots by playbook_id in Python
    slots_by_playbook: dict[int, list] = defaultdict(list)
    for s in all_slots:
        slots_by_playbook[s.playbook_id].append({
            "id": s.id,
            "slot_type": s.slot_type,
            "is_customer_visible": s.is_customer_visible,
            "tier_names": s.tier_names,
        })

    output = []
    for pb in playbooks:
        output.append({
            "id": pb.id,
            "name": pb.name,
            "slots": slots_by_playbook[pb.id],
        })
    return output


@router.get("/playbooks/{playbook_id}/slots")
async def public_playbook_slots(playbook_id: int, db: AsyncSession = Depends(get_db)):
    """
    Customer-visible slots for a playbook, with active variants grouped by tier.
    Exposes display pricing, product media and whitelisted engineering data.
    """
    pb_result = await db.execute(
        select(Playbook).where(Playbook.id == playbook_id, Playbook.status == "active")
    )
    playbook = pb_result.scalar_one_or_none()
    if not playbook:
        raise HTTPException(status_code=404, detail="Playbook not found")

    slots_result = await db.execute(
        select(PlaybookSlot).where(
            PlaybookSlot.playbook_id == playbook_id,
            PlaybookSlot.is_customer_visible == True,  # noqa: E712
        )
    )
    slots = slots_result.scalars().all()
    slot_ids = [s.id for s in slots]

    # Load curation before the catalogue query. An explicitly public variant is
    # a fixed configurator choice and must survive the automated marketplace
    # freshness job changing its catalogue status to ``hidden``. Previously the
    # status filter ran first, so every curated build could become empty after
    # a refresh even though its visibility rows still said it was public.
    visible_variant_ids: set[int] = set()
    curated_slot_ids: set[int] = set()
    if slot_ids:
        vis_result = await db.execute(
            select(ConfiguratorCatalogueVisibility).where(
                ConfiguratorCatalogueVisibility.playbook_slot_id.in_(slot_ids)
            )
        )
        vis_rows = vis_result.scalars().all()
        curated_slot_ids = {r.playbook_slot_id for r in vis_rows}
        visible_variant_ids = {
            r.catalogue_variant_id for r in vis_rows if r.is_publicly_visible
        }

    # Active catalogue candidates plus explicitly curated fixed choices.
    if slot_ids:
        status_filter = CatalogueVariant.status == "active"
        if visible_variant_ids:
            status_filter = or_(
                status_filter,
                CatalogueVariant.id.in_(visible_variant_ids),
            )
        variants_result = await db.execute(
            select(CatalogueVariant, Listing)
            .join(Listing, CatalogueVariant.listing_id == Listing.id)
            .where(
                CatalogueVariant.slot_id.in_(slot_ids),
                status_filter,
            )
            .order_by(CatalogueVariant.slot_id, CatalogueVariant.display_price)
        )
        all_rows = variants_result.all()
    else:
        all_rows = []

    # Visibility gate (Commerce PRD Ch.6.5): once curation rows exist for a
    # GIVEN SLOT, only that slot's variants explicitly marked publicly visible
    # are shown. Scoped per-slot, not per-playbook — a playbook can have some
    # slot types curated and others still in pre-curation fallback (show all
    # active variants) simultaneously. This must stay per-slot: an earlier
    # version gated on "any vis_rows exist across slot_ids" playbook-wide,
    # which meant curating ONE slot type (e.g. adding motherboard visibility
    # rows) silently hid every OTHER slot type in the same playbook that had
    # no visibility rows of its own yet — a real regression caught 2026-08-12
    # (see PC_BUILDER_DISCOVERY_AND_IMPLEMENTATION_PLAN.md).
    if curated_slot_ids:
        all_rows = [
            (v, l) for v, l in all_rows
            if v.slot_id not in curated_slot_ids or v.id in visible_variant_ids
        ]

    # Group by slot_id in Python, guarding against unexpected tier values
    variants_by_slot: dict[int, dict[str, list]] = defaultdict(
        lambda: {"budget": [], "mid": [], "high": []}
    )
    for v, l in all_rows:
        tier = v.tier if v.tier in ("budget", "mid", "high") else "budget"
        variants_by_slot[v.slot_id][tier].append({
            "id": v.id,
            "title": l.title,
            "display_price": v.display_price,
            "gem_score": l.gem_score,
            "images": l.image_urls or [],
            "customer_option": {
                "capacity_gb": l.ram_gb if v.slot_id in {s.id for s in slots if s.slot_type == 'ram'} else l.storage_gb,
                "memory_type": l.ram_type,
                "interface": ('NVMe' if 'nvme' in (l.storage_type or '').lower() else 'SATA' if 'sata' in (l.storage_type or '').lower() and 'hdd' not in (l.storage_type or '').lower() else None),
            },
            "description": l.description,
            "specifications": engineering_specs(l.raw_specs),
            "price_updated_at": v.updated_at,
            "last_seen_at": v.last_seen_at,
            "availability": v.status,
        })

    output = []
    for slot in slots:
        output.append({
            "slot_id": slot.id,
            "slot_type": slot.slot_type,
            "tier_names": slot.tier_names,
            "variants_by_tier": variants_by_slot[slot.id],
        })

    return output


@router.get("/cases")
async def public_list_cases(db: AsyncSession = Depends(get_db)):
    """Active manual and live supplier cases from one unified catalogue."""
    result = await db.execute(
        select(CaseCatalogue)
        .where(CaseCatalogue.status == "active")
        .order_by(CaseCatalogue.brand, CaseCatalogue.name)
    )
    cases = result.scalars().all()
    live_cases = (await db.execute(select(Case).where(Case.status.in_(("active", "approved", "completed", "sourcing"))))).scalars().all()
    preferred_names = set((await db.execute(select(PreferredComponent.component_key).where(
        PreferredComponent.component_slot == "case", PreferredComponent.status == "preferred"
    ))).scalars().all())

    # Admin preferences are production data too. Promote a preferred case from
    # the operational `cases` table when the catalogue seed missed it, so it
    # is immediately available to the customer configurator.
    existing_names = {"".join(ch.lower() for ch in (c.name or "") if ch.isalnum()) for c in cases}
    for preferred_name in preferred_names:
        preferred = next((row for row in live_cases if "".join(ch.lower() for ch in (preferred_name or "") if ch.isalnum()) in "".join(ch.lower() for ch in (row.name or "") if ch.isalnum())), None)
        source_name = preferred.name if preferred else preferred_name
        key = "".join(ch.lower() for ch in source_name if ch.isalnum())
        if key in existing_names:
            continue
        promoted = CaseCatalogue(
            name=source_name[:200], brand=((preferred.brand if preferred else source_name.split()[0]) or "Unknown")[:100],
            form_factor=((preferred.form_factors if preferred else ["atx"])[0]).lower()[:10],
            images=[preferred.image_url] if preferred and preferred.image_url else [],
            rrp_gbp=float((preferred.price_new or preferred.price or preferred.rrp) if preferred else 0),
            status="active", notes="Promoted from admin preferred case",
        )
        db.add(promoted)
        await db.flush()
        cases.append(promoted)
        existing_names.add(key)

    def norm(value: str) -> str:
        return "".join(ch.lower() for ch in (value or "") if ch.isalnum())

    def words(value: str) -> list[str]:
        return [part.lower() for part in (value or "").replace("-", " ").replace("/", " ").split() if len(part) > 3]

    by_name = {norm(c.name): c for c in live_cases}
    # The operational cases table owns Amazon rank. Match exact names first,
    # then token containment for Amazon titles that include extra marketing copy.
    def live_for(catalogue_case):
        exact = by_name.get(norm(catalogue_case.name))
        if exact:
            return exact
        tokens = words(catalogue_case.name)
        return next((row for row in live_cases if all(t in " ".join(words(row.name)) for t in tokens[-3:])), None)

    output = []
    for c in cases:
        supplier_offer = None
        case_engineering = {}
        if c.notes:
            try:
                notes = json.loads(c.notes)
                supplier_offer = notes.get("supplier_offer")
                case_engineering = engineering_specs(notes)
            except (ValueError, TypeError, AttributeError):
                pass
        # Supplier availability is deliberately short-lived; never sell from
        # an old delivery promise just because its catalogue row still exists.
        if supplier_offer:
            try:
                observed = datetime.fromisoformat(supplier_offer["observed_at"])
                if datetime.utcnow() - observed > timedelta(hours=8):
                    continue
            except (KeyError, TypeError, ValueError):
                continue
        live = live_for(c)
        output.append({
            "id": c.id,
            "name": c.name,
            "brand": c.brand,
            "form_factor": c.form_factor,
            "images": c.images,
            "rrp_gbp": c.rrp_gbp,
            "bestseller_rank": live.bestseller_rank if live else None,
            "is_preferred": any(norm(name) in norm(c.name) or norm(c.name) in norm(name) for name in preferred_names) or bool(live and any(norm(name) in norm(live.name) for name in preferred_names)),
            "is_transparent_panel": c.is_transparent_panel,
            "supplier_offer": supplier_offer,
            "height_mm": c.height_mm,
            "width_mm": c.width_mm,
            "depth_mm": c.depth_mm,
            "max_gpu_length_mm": c.max_gpu_length_mm,
            "max_cooler_height_mm": c.max_cooler_height_mm,
            "radiator_support": c.radiator_support,
            "price_updated_at": c.updated_at,
            "engineering": case_engineering if case_engineering.get("reviewed") is True else {},
        })
    # Preferred cases must remain selectable even if they were never present in
    # the curated catalogue seed. Their existing case_catalogue ID is required
    # by pricing, so only emit records that already have a catalogue row.
    output.sort(key=lambda row: row["bestseller_rank"] if row["bestseller_rank"] is not None else float("-inf"), reverse=True)
    return output


@router.get('/playbooks/{playbook_id}/curated-slots')
async def public_curated_slots(playbook_id: int, db: AsyncSession = Depends(get_db), build_id: str | None = None):
    from app.services.curated_build_policy import curated_slots, definitions
    definition = None
    if build_id:
        definition = next((b for b in definitions()['builds'] if b['id'] == build_id), None)
        name = (await db.execute(select(Playbook.name).where(Playbook.id == playbook_id))).scalar_one_or_none()
        if not definition or definition['segment'] != name:
            raise HTTPException(404, 'Curated build not found for this user type')
    return curated_slots(await public_playbook_slots(playbook_id, db), definition)


@router.get('/curated-builds')
async def public_curated_builds(db: AsyncSession = Depends(get_db)):
    from app.services.curated_build_policy import definitions, curated_slots
    playbooks = await public_list_playbooks(db)
    cases = await public_list_cases(db)
    by_name = {p['name']: p for p in playbooks}
    catalogue = {p['id']: await public_playbook_slots(p['id'], db) for p in playbooks}
    result = []
    for definition in definitions()['builds']:
        pb = by_name.get(definition['segment'])
        slots = curated_slots(catalogue.get(pb['id'], []) if pb else [], definition)
        chosen = [next((v for values in s['variants_by_tier'].values() for v in values if v['id'] == s['default_variant_id']), None) for s in slots]
        missing = [s['slot_type'] for s, v in zip(slots, chosen) if v is None]
        if not cases:
            missing.append('case')
        parts = sum(float(v['display_price']) for v in chosen if v) + (min(float(c['rrp_gbp']) for c in cases) if cases else 0)
        result.append({**definition, 'playbook_id': pb['id'] if pb else None, 'missing_components': missing,
                       'price_gbp': round((parts + LABOUR_COST) * (1 + OVERHEAD_RATE), 2) if not missing else None})
    return result


@router.get('/playbooks/{playbook_id}/custom-slots')
async def public_custom_slots(playbook_id: int, db: AsyncSession = Depends(get_db)):
    """Full selection from the same published component base as curated builds."""
    base = await public_playbook_slots(playbook_id, db)
    pool = {}
    for pb in await public_list_playbooks(db):
        for slot in await public_playbook_slots(pb['id'], db):
            bucket = pool.setdefault(slot['slot_type'], {})
            for values in slot['variants_by_tier'].values():
                for variant in values:
                    bucket[variant['id']] = variant
    return [{**slot, 'variants_by_tier': {'budget': [], 'mid': list(pool.get(slot['slot_type'], {}).values()), 'high': []}} for slot in base]
