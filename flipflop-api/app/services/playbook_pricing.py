"""Server-side pricing for a playbook build configuration.

Mirrors the storefront's own `computeTotals` (lib/build-store.ts — "mirrors
quote_service") so the amount a customer sees matches what they're actually
charged, but recomputed here from the real catalogue rather than trusted
from the client: payment amounts must never be taken from client input.
"""

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalogue import CaseCatalogue, CatalogueVariant, PlaybookSlot
from app.models.listing import Listing
from app.models.playbook import Playbook

LABOUR_COST = 87.5  # 3.5h x GBP25 — mirrors quote_service
OVERHEAD_RATE = 0.1


@dataclass
class PricedSlot:
    slot_id: int
    slot_type: str
    variant_id: int
    title: str
    price: float


@dataclass
class PricedBuild:
    playbook_id: int
    playbook_name: str = ""
    slots: list[PricedSlot] = field(default_factory=list)
    case_id: int | None = None
    case_name: str | None = None
    case_price: float = 0.0
    parts_total: float = 0.0
    labour: float = LABOUR_COST
    overhead: float = 0.0
    total: float = 0.0


class InvalidBuildError(ValueError):
    """Raised when a slot/case selection doesn't resolve to a real, active catalogue row."""


async def price_playbook_build(
    db: AsyncSession,
    playbook_id: int,
    slot_selections: dict[int, int],
    case_id: int | None,
) -> PricedBuild:
    """Validate and price a playbook build from real catalogue data.

    `slot_selections` maps playbook_slot.id -> catalogue_variants.id. Every
    variant must belong to an active slot for this playbook and be
    status="active"; anything else raises InvalidBuildError rather than
    silently pricing at 0 or trusting a client-supplied amount.
    """
    build = PricedBuild(playbook_id=playbook_id)

    pb_result = await db.execute(select(Playbook.name).where(Playbook.id == playbook_id))
    build.playbook_name = pb_result.scalar_one_or_none() or ""

    if slot_selections:
        slot_ids = list(slot_selections.keys())
        slots_result = await db.execute(
            select(PlaybookSlot).where(
                PlaybookSlot.id.in_(slot_ids),
                PlaybookSlot.playbook_id == playbook_id,
            )
        )
        slots_by_id = {s.id: s for s in slots_result.scalars().all()}

        variant_ids = list(slot_selections.values())
        variants_result = await db.execute(
            select(CatalogueVariant, Listing)
            .join(Listing, CatalogueVariant.listing_id == Listing.id)
            .where(
                CatalogueVariant.id.in_(variant_ids),
                CatalogueVariant.status == "active",
            )
        )
        variants_by_id = {v.id: (v, listing) for v, listing in variants_result.all()}

        for slot_id, variant_id in slot_selections.items():
            slot = slots_by_id.get(slot_id)
            if slot is None:
                raise InvalidBuildError(
                    f"Slot {slot_id} does not belong to playbook {playbook_id}"
                )
            resolved = variants_by_id.get(variant_id)
            if resolved is None:
                raise InvalidBuildError(
                    f"Variant {variant_id} is not an active catalogue option for slot {slot_id}"
                )
            variant, listing = resolved
            if variant.slot_id != slot_id:
                raise InvalidBuildError(
                    f"Variant {variant_id} does not belong to slot {slot_id}"
                )
            build.slots.append(
                PricedSlot(
                    slot_id=slot_id,
                    slot_type=slot.slot_type,
                    variant_id=variant_id,
                    title=listing.title,
                    price=variant.display_price,
                )
            )
            build.parts_total += variant.display_price

    if case_id is not None:
        case_result = await db.execute(
            select(CaseCatalogue).where(
                CaseCatalogue.id == case_id, CaseCatalogue.status == "active"
            )
        )
        case = case_result.scalar_one_or_none()
        if case is None:
            raise InvalidBuildError(f"Case {case_id} is not an active catalogue option")
        build.case_id = case_id
        build.case_name = case.name
        build.case_price = case.rrp_gbp
        build.parts_total += case.rrp_gbp

    subtotal = build.parts_total + LABOUR_COST
    build.overhead = subtotal * OVERHEAD_RATE
    build.total = round(subtotal + build.overhead, 2)
    return build
