"""Server-side pricing for a playbook build configuration.

Mirrors the storefront's own `computeTotals` (lib/build-store.ts — "mirrors
quote_service") so the amount a customer sees matches what they're actually
charged, but recomputed here from the real catalogue rather than trusted
from the client: payment amounts must never be taken from client input.
"""

from dataclasses import dataclass, field

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalogue import CaseCatalogue, CatalogueVariant, PlaybookSlot
from app.models.listing import Listing
from app.models.playbook import Playbook
from app.models.curated_build_segment import CuratedBuildSegment

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
    applied_upgrades: list[dict] = field(default_factory=list)


class InvalidBuildError(ValueError):
    """Raised when a slot/case selection doesn't resolve to a real, active catalogue row."""


async def price_playbook_build(
    db: AsyncSession,
    playbook_id: int,
    slot_selections: dict[int, int],
    case_id: int | None,
    *,
    build_mode: str = "custom",
    curated_build_id: str | None = None,
    upgrade_candidate_indexes: list[int] | None = None,
    require_complete: bool = True,
) -> PricedBuild:
    """Validate and price a playbook build from real catalogue data.

    `slot_selections` maps playbook_slot.id -> catalogue_variants.id. Every
    variant must belong to an active slot for this playbook and be
    status="active"; anything else raises InvalidBuildError rather than
    silently pricing at 0 or trusting a client-supplied amount. Normal
    checkout requires every published component slot; saved drafts opt into
    partial repricing while retaining the same catalogue membership checks.
    """
    mode = "curated" if curated_build_id else build_mode
    if mode not in {"curated", "custom"}:
        raise InvalidBuildError("Build mode must be curated or custom")
    if mode == "curated" and not curated_build_id:
        raise InvalidBuildError("A curated Playbook cell is required for a curated build")
    if mode == "custom" and curated_build_id:
        raise InvalidBuildError("A curated Playbook cell cannot be applied to a custom build")

    if upgrade_candidate_indexes:
        slot_selections, applied_upgrades = await apply_curated_cell_upgrades(
            db, playbook_id, curated_build_id, slot_selections, upgrade_candidate_indexes
        )
    else:
        slot_selections, applied_upgrades = await apply_curated_cell_upgrades(
            db, playbook_id, curated_build_id, slot_selections, []
        )

    # Reuse the same public catalogue filters used by the configurator so a
    # modified payment request cannot select a hidden or non-curated part.
    # The local import avoids a module cycle: public_catalogue also imports
    # the labour/overhead constants defined in this service.
    from app.api.public_catalogue import public_curated_slots, public_custom_slots

    try:
        selectable = (
            await public_curated_slots(playbook_id, db, curated_build_id)
            if mode == "curated"
            else await public_custom_slots(playbook_id, db)
        )
    except HTTPException as exc:
        # Preserve unexpected service responses; translate only expected
        # cell/catalogue validation failures into a pricing rejection.
        if exc.status_code in {404, 409}:
            raise InvalidBuildError(str(exc.detail)) from exc
        raise

    if not selectable:
        raise InvalidBuildError("This Playbook has no currently selectable components")
    options_by_slot = {
        int(slot["slot_id"]): {
            int(variant["id"])
            for variants in (slot.get("variants_by_tier") or {}).values()
            for variant in variants
        }
        for slot in selectable
        if slot.get("slot_type") != "case"
    }
    optional_slot_ids = {
        int(slot["slot_id"])
        for slot in selectable
        if mode == "custom"
        and slot.get("slot_type") == "gpu"
        and slot.get("is_required") is False
    }
    required_slot_ids = set(options_by_slot) - optional_slot_ids
    if require_complete and not required_slot_ids.issubset(slot_selections):
        raise InvalidBuildError("Select every component slot shown in the configurator")
    if not set(slot_selections).issubset(options_by_slot):
        raise InvalidBuildError("A selected slot is not part of this configurator catalogue")
    for slot_id, variant_id in slot_selections.items():
        if variant_id not in options_by_slot.get(slot_id, set()):
            catalogue_name = "curated" if mode == "curated" else "custom"
            raise InvalidBuildError(f"Variant {variant_id} is not available in the {catalogue_name} catalogue for slot {slot_id}")

    build = PricedBuild(playbook_id=playbook_id, applied_upgrades=applied_upgrades)

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


async def apply_curated_cell_upgrades(
    db: AsyncSession,
    playbook_id: int,
    curated_build_id: str | None,
    slot_selections: dict[int, int],
    candidate_indexes: list[int],
) -> tuple[dict[int, int], list[dict]]:
    """Apply only the saved, cell-approved component substitutions."""
    if not candidate_indexes and not curated_build_id:
        return slot_selections, []
    if not curated_build_id:
        raise InvalidBuildError("Playbook upgrades are available only for a curated cell")
    if len(candidate_indexes) > 2 or len(set(candidate_indexes)) != len(candidate_indexes):
        raise InvalidBuildError("Choose at most two distinct Playbook upgrades")
    from app.services.curated_build_policy import definitions
    cell = next((item for item in definitions().get("builds", []) if item.get("id") == curated_build_id), None)
    if not cell:
        raise InvalidBuildError("Unknown curated Playbook cell")
    playbook_name = (await db.execute(select(Playbook.name).where(Playbook.id == playbook_id))).scalar_one_or_none()
    if not playbook_name or str(cell.get("segment", "")).casefold() != playbook_name.casefold():
        raise InvalidBuildError("The upgrade cell does not match the selected Playbook")
    segment = (await db.execute(select(CuratedBuildSegment).where(
        CuratedBuildSegment.customer_type == cell["segment"],
        CuratedBuildSegment.budget_level == cell["tier"],
    ))).scalar_one_or_none()
    approved = (segment.approved_upgrades or []) if segment and segment.is_live else []
    if len(approved) != 2:
        if candidate_indexes:
            raise InvalidBuildError("This curated cell has no complete approved upgrade pair")
        return slot_selections, []
    approved_by_index = {int(item["candidate_index"]): item for item in approved if isinstance(item, dict) and item.get("candidate_index") is not None}
    if any(index not in approved_by_index for index in candidate_indexes):
        raise InvalidBuildError("A selected upgrade is no longer approved for this Playbook cell")
    chosen = [approved_by_index[index] for index in candidate_indexes]
    target_ids = {int(item["target_variant_id"]) for item in approved if item.get("target_variant_id")}
    submitted_targets = {value for value in slot_selections.values() if value in target_ids}
    chosen_targets = {int(item["target_variant_id"]) for item in chosen}
    if submitted_targets - chosen_targets:
        raise InvalidBuildError("A Playbook upgrade component was supplied without selecting its approved upgrade")
    resolved = dict(slot_selections)
    occupied_slots: set[int] = set()
    for item in chosen:
        slot_id = int(item["slot_id"])
        if slot_id in occupied_slots:
            raise InvalidBuildError("Selected Playbook upgrades conflict in the same component slot")
        occupied_slots.add(slot_id)
        resolved[slot_id] = int(item["target_variant_id"])
    return resolved, chosen
