"""
Public catalogue endpoints — no auth required.
Consumed by the customer website (Subsystem 3).
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.catalogue import CaseCatalogue, CatalogueVariant, PlaybookSlot
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

    output = []
    for pb in playbooks:
        slots_result = await db.execute(
            select(PlaybookSlot).where(PlaybookSlot.playbook_id == pb.id)
        )
        slots = slots_result.scalars().all()
        output.append({
            "id": pb.id,
            "name": pb.name,
            "slots": [
                {
                    "id": s.id,
                    "slot_type": s.slot_type,
                    "is_customer_visible": s.is_customer_visible,
                    "tier_names": s.tier_names,
                }
                for s in slots
            ],
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

    output = []
    for slot in slots:
        variants_result = await db.execute(
            select(CatalogueVariant, Listing)
            .join(Listing, CatalogueVariant.listing_id == Listing.id)
            .where(
                CatalogueVariant.slot_id == slot.id,
                CatalogueVariant.status == "active",
            )
            .order_by(CatalogueVariant.display_price)
        )
        rows = variants_result.all()

        by_tier: dict[str, list] = {"budget": [], "mid": [], "high": []}
        for v, l in rows:
            by_tier[v.tier].append({
                "id": v.id,
                "title": l.title,
                "display_price": v.display_price,
                "gem_score": l.gem_score,
            })

        output.append({
            "slot_id": slot.id,
            "slot_type": slot.slot_type,
            "tier_names": slot.tier_names,
            "variants_by_tier": by_tier,
        })

    return output


@router.get("/cases")
async def public_list_cases(db: AsyncSession = Depends(get_db)):
    """Active cases only — images, form_factor, transparent panel flag."""
    result = await db.execute(
        select(CaseCatalogue)
        .where(CaseCatalogue.status == "active")
        .order_by(CaseCatalogue.brand, CaseCatalogue.name)
    )
    cases = result.scalars().all()
    return [
        {
            "id": c.id,
            "name": c.name,
            "brand": c.brand,
            "form_factor": c.form_factor,
            "images": c.images,
            "rrp_gbp": c.rrp_gbp,
            "is_transparent_panel": c.is_transparent_panel,
        }
        for c in cases
    ]
