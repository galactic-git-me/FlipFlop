"""
Public catalogue endpoints — no auth required.
Consumed by the customer website (Subsystem 3).
"""
from collections import defaultdict
from datetime import datetime, timedelta
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.catalogue import CaseCatalogue, CatalogueVariant, PlaybookSlot
from app.models.configurator import ConfiguratorCatalogueVisibility
from app.models.listing import Listing
from app.models.playbook import Playbook

router = APIRouter(prefix="/public", tags=["public"])


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
    Each variant exposes only display_price, title, and gem_score.
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
    output = []
    for c in cases:
        supplier_offer = None
        if c.notes:
            try:
                supplier_offer = json.loads(c.notes).get("supplier_offer")
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
        output.append({
            "id": c.id,
            "name": c.name,
            "brand": c.brand,
            "form_factor": c.form_factor,
            "images": c.images,
            "rrp_gbp": c.rrp_gbp,
            "is_transparent_panel": c.is_transparent_panel,
            "supplier_offer": supplier_offer,
        })
    return output
