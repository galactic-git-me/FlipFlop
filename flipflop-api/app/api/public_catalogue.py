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
from app.models.curated_build_segment import CuratedBuildSegment
from app.models.case import Case
from app.models.gem_radar_scored_listing import GemRadarScoredListing
from app.models.component_3d_asset import AssetSubjectType, Component3DAsset, Component3DAssetStatus
from app.models.gem_radar_intelligence import PreferredComponent
from app.schemas.payment import PlaybookBuildConfig
from app.services.playbook_pricing import LABOUR_COST, OVERHEAD_RATE
from app.services.studio_fit import engineering_specs

router = APIRouter(prefix="/public", tags=["public"])


@router.post("/playbooks/{playbook_id}/delivery-quotes")
async def playbook_delivery_quotes(playbook_id: int, build_config: PlaybookBuildConfig):
    """Keep the current storefront compatible while commercial quotes are unavailable.

    The storefront supports this legacy response and continues to use its
    existing server-validated build quote for checkout eligibility. Do not
    fabricate delivery prices or promises when no reviewed commercial quote
    is available on this API version.
    """
    if playbook_id != build_config.playbook_id:
        raise HTTPException(status_code=422, detail="The selected build belongs to a different Playbook")
    return {
        "pricing_mode": "legacy",
        "quote_snapshot_id": None,
        "review_required": False,
        "modes": {},
    }

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
    # Amazon refreshes can leave newly observed rows in ``pending`` while they
    # are being reviewed. Their rank is still production data and must be
    # available for catalogue ordering, so include ranked rows regardless of
    # review status alongside the normal sellable statuses.
    live_cases = (await db.execute(select(Case).where(
        (Case.status.in_(("active", "approved", "completed", "sourcing")))
        | (Case.bestseller_rank.is_not(None))
    ))).scalars().all()
    # A rights-cleared, scale-validated final case model is also a signal that
    # its sourced case can be offered in the configurator. Keep its catalogue
    # ID for price/evaluation, and expose the sourcing-case ID separately for
    # resolving the matching 3D asset.
    final_case_assets = (await db.execute(select(Component3DAsset).where(
        Component3DAsset.subject_type == AssetSubjectType.CASE,
        Component3DAsset.status == Component3DAssetStatus.FINAL,
        Component3DAsset.is_active.is_(True),
        Component3DAsset.subject_id.is_not(None),
    ))).scalars().all()
    asset_case_ids = {int(asset.subject_id) for asset in final_case_assets}
    final_asset_by_case_id = {int(asset.subject_id): asset for asset in final_case_assets if asset.subject_id is not None}
    final_cases = (await db.execute(select(Case).where(Case.id.in_(asset_case_ids)))).scalars().all() if asset_case_ids else []
    known_live_ids = {item.id for item in live_cases}
    live_cases.extend(item for item in final_cases if item.id not in known_live_ids)

    def norm(value: str) -> str:
        return "".join(ch.lower() for ch in (value or "") if ch.isalnum())

    existing_names = {norm(c.name) for c in cases}
    for sourced_case in final_cases:
        case_name = (sourced_case.name or "").strip()
        name_key = norm(case_name)
        if not name_key or name_key in existing_names:
            continue
        words_in_name = [part for part in case_name.replace("-", " ").split() if part]
        brand = (sourced_case.brand or (words_in_name[0].title() if words_in_name else "Unknown")).strip()
        model_tokens = [part.lower() for part in words_in_name if any(ch.isdigit() for ch in part)]
        matching_case = next((item for item in cases if norm(item.brand) == norm(brand) and any(token in norm(item.name) for token in model_tokens)), None)
        if matching_case:
            existing_names.add(name_key)
            continue
        price = sourced_case.price_new or sourced_case.price or sourced_case.rrp
        if not price or float(price) <= 0:
            continue
        asset = final_asset_by_case_id.get(sourced_case.id)
        images = [url for url in (asset.source_image_refs if asset else []) if isinstance(url, str) and url.startswith(("https://", "http://"))]
        if not images and sourced_case.image_url:
            images = [sourced_case.image_url]
        factors = sourced_case.form_factors or ["atx"]
        promoted = CaseCatalogue(
            name=case_name[:200], brand=brand[:100], form_factor=str(factors[0]).lower()[:10],
            images=images, rrp_gbp=float(price), status="active",
            notes=f"Automatically listed from final 3D case asset {asset.id if asset else ''}".strip(),
        )
        db.add(promoted)
        await db.flush()
        cases.append(promoted)
        existing_names.add(name_key)
    preferred_names = set((await db.execute(select(PreferredComponent.component_key).where(
        PreferredComponent.component_slot == "case", PreferredComponent.status == "preferred"
    ))).scalars().all())

    # Admin preferences are production data too. Promote a preferred case from
    # the operational `cases` table when the catalogue seed missed it, so it
    # is immediately available to the customer configurator.
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

    def asset_case_for(catalogue_case):
        live = live_for(catalogue_case)
        if live and live.id in asset_case_ids:
            return live
        catalogue_brand = norm(catalogue_case.brand)
        catalogue_name = norm(catalogue_case.name)
        for candidate in final_cases:
            source_words = [part for part in (candidate.name or "").replace("-", " ").split() if part]
            source_brand = norm(candidate.brand or (source_words[0] if source_words else ""))
            model_tokens = [norm(part) for part in source_words if any(ch.isdigit() for ch in part)]
            if catalogue_brand == source_brand and any(token and token in catalogue_name for token in model_tokens):
                return candidate
        return None

    output = []
    for c in cases:
        live = live_for(c)
        asset_case = asset_case_for(c)
        supplier_offer = None
        case_engineering = {}
        fallback_price = None
        if c.notes:
            try:
                notes = json.loads(c.notes)
                supplier_offer = notes.get("supplier_offer")
                case_engineering = engineering_specs(notes)
            except (ValueError, TypeError, AttributeError):
                pass
        # Supplier availability is deliberately short-lived. A final-model
        # case may still be selectable when its vendor offer has gone stale,
        # but only when the operational case record has a sourced price. In
        # that case hide the stale offer and use the sourced case price.
        if supplier_offer:
            try:
                observed = datetime.fromisoformat(supplier_offer["observed_at"])
                if datetime.utcnow() - observed > timedelta(hours=8):
                    live_price = (asset_case.price_new or asset_case.price or asset_case.rrp) if asset_case else None
                    if live_price and float(live_price) > 0:
                        supplier_offer = None
                        fallback_price = float(live_price)
                    else:
                        continue
            except (KeyError, TypeError, ValueError):
                live_price = (asset_case.price_new or asset_case.price or asset_case.rrp) if asset_case else None
                if live_price and float(live_price) > 0:
                    supplier_offer = None
                    fallback_price = float(live_price)
                else:
                    continue
        case_images = c.images or ([live.image_url] if live and live.image_url else [])
        if not case_images and asset_case:
            published_asset = final_asset_by_case_id.get(asset_case.id)
            case_images = [url for url in (published_asset.source_image_refs if published_asset else []) if isinstance(url, str) and url.startswith(("https://", "http://"))]
        output.append({
            "id": c.id,
            "asset_subject_id": asset_case.id if asset_case else None,
            "name": c.name,
            "brand": c.brand,
            "form_factor": c.form_factor,
            "images": case_images,
            "rrp_gbp": fallback_price or c.rrp_gbp,
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
            "price_updated_at": asset_case.updated_at if fallback_price and asset_case else c.updated_at,
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
    slots = curated_slots(await public_playbook_slots(playbook_id, db), definition)
    if definition:
        segment = (await db.execute(select(CuratedBuildSegment).where(
            CuratedBuildSegment.customer_type == definition["segment"],
            CuratedBuildSegment.budget_level == definition["tier"],
        ))).scalar_one_or_none()
        # Automatic upsells are drawn from the active curated catalogue. A
        # candidate must have a current market median above the cell's default
        # component; compatibility and the live build budget are checked again
        # when the customer selects it and when pricing the build.
        slot_by_id = {slot["slot_id"]: slot for slot in slots}
        defaults = {slot["slot_id"]: slot.get("default_variant_id") for slot in slots}
        rows = (await db.execute(
            select(CatalogueVariant, Listing)
            .join(Listing, Listing.id == CatalogueVariant.listing_id)
            .where(
                CatalogueVariant.slot_id.in_(slot_by_id),
                CatalogueVariant.curated_for_builds.is_(True),
                CatalogueVariant.status == "active",
                Listing.status == "active",
            )
        )).all() if slot_by_id else []
        def scorer_listing_id(listing: Listing) -> str:
            external_id = listing.external_id or ""
            return external_id.split("|")[1] if external_id.startswith("ebay_v1|") and "|" in external_id else external_id

        listing_ids = {scorer_listing_id(listing) for _, listing in rows}
        score_rows = (await db.execute(
            select(GemRadarScoredListing.listing_id, GemRadarScoredListing.market_median_price)
            .where(GemRadarScoredListing.listing_id.in_(listing_ids))
            .order_by(GemRadarScoredListing.scored_at.desc(), GemRadarScoredListing.id.desc())
        )).all() if listing_ids else []
        medians = {}
        for listing_id, median in score_rows:
            medians.setdefault(listing_id, median)
        by_variant = {variant.id: listing for variant, listing in rows}
        median_by_variant = {variant.id: medians.get(scorer_listing_id(listing)) for variant, listing in rows}
        for slot in slots:
            slot["upgrade_budget_ceiling"] = round(float(segment.budget_max) * 1.2, 2) if segment and segment.budget_max else None
            base_id = defaults.get(slot["slot_id"])
            base_median = median_by_variant.get(base_id)
            baseline = next((item for values in slot["variants_by_tier"].values() for item in values if item["id"] == base_id), None)
            if baseline is None:
                continue
            choices = [baseline]
            if base_median is not None and float(base_median) > 0:
                for variant, listing in rows:
                    if variant.slot_id != slot["slot_id"] or variant.id == base_id:
                        continue
                    median = median_by_variant.get(variant.id)
                    if median is None or float(median) <= float(base_median):
                        continue
                    choices.append({
                        "id": variant.id,
                        "automatic_upsell": True,
                        "market_median_price": float(median),
                        "baseline_market_median_price": float(base_median),
                        "title": listing.title,
                        "display_price": variant.display_price,
                        "gem_score": listing.gem_score,
                        "images": listing.image_urls or [],
                        "customer_option": {
                            "capacity_gb": listing.ram_gb if slot["slot_type"] == "ram" else listing.storage_gb,
                            "memory_type": listing.ram_type,
                            "interface": ('NVMe' if 'nvme' in (listing.storage_type or '').lower() else 'SATA' if 'sata' in (listing.storage_type or '').lower() and 'hdd' not in (listing.storage_type or '').lower() else None),
                        },
                        "description": listing.description,
                        "specifications": engineering_specs(listing.raw_specs),
                        "price_updated_at": variant.updated_at,
                        "last_seen_at": variant.last_seen_at,
                        "availability": variant.status,
                    })
            slot["variants_by_tier"] = {"budget": [], "mid": choices, "high": []}
    return slots


class ProductCopyRequest(BaseModel):
    variant_id: int | None = Field(default=None, gt=0)
    case_id: int | None = Field(default=None, gt=0)
    baseline_variant_id: int | None = Field(default=None, gt=0)
    curated_build_id: str | None = Field(default=None, max_length=120)
    candidate_index: int | None = Field(default=None, ge=0, le=100)


@router.post("/product-copy")
async def public_product_copy(body: ProductCopyRequest, db: AsyncSession = Depends(get_db)):
    """Return cached, grounded sales copy; generate once on first request if missing."""
    from app.services.catalogue_marketing_copy import ensure_product_copy
    try:
        return await ensure_product_copy(
            db, variant_id=body.variant_id, case_id=body.case_id,
            baseline_variant_id=body.baseline_variant_id,
            curated_build_id=body.curated_build_id, candidate_index=body.candidate_index,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail="Product details are temporarily unavailable. Please try again.") from exc


@router.get('/curated-builds')
async def public_curated_builds(db: AsyncSession = Depends(get_db)):
    from app.services.curated_build_policy import definitions, curated_slots
    from app.services.ship_naming import enrich_curated_build_with_ship_name
    
    playbooks = await public_list_playbooks(db)
    cases = await public_list_cases(db)
    by_name = {p['name']: p for p in playbooks}
    catalogue = {p['id']: await public_playbook_slots(p['id'], db) for p in playbooks}
    result = []
    cell_segments = (await db.execute(select(CuratedBuildSegment))).scalars().all()
    segment_by_cell = {(row.customer_type.casefold(), row.budget_level.casefold()): row for row in cell_segments}
    for definition in definitions()['builds']:
        pb = by_name.get(definition['segment'])
        slots = curated_slots(catalogue.get(pb['id'], []) if pb else [], definition)
        chosen = [next((v for values in s['variants_by_tier'].values() for v in values if v['id'] == s['default_variant_id']), None) for s in slots]
        # Cases are resolved from case_catalogue below, not from component
        # variants. The playbook slot is retained for the configurator shape,
        # but an empty case variant list must not make every curated build
        # appear incomplete.
        missing = [s['slot_type'] for s, v in zip(slots, chosen) if v is None and s['slot_type'] != 'case']
        if not cases:
            missing.append('case')
        parts = sum(float(v['display_price']) for v in chosen if v) + (min(float(c['rrp_gbp']) for c in cases) if cases else 0)
        build_data = {
            **definition, 
            'playbook_id': pb['id'] if pb else None, 
            'missing_components': missing,
            'price_gbp': round((parts + LABOUR_COST) * (1 + OVERHEAD_RATE), 2) if not missing else None
        }
        cell = segment_by_cell.get((definition['segment'].casefold(), definition['tier'].casefold()))
        upgrade_options = (cell.approved_upgrades or []) if cell and cell.is_live else []
        build_data['upgrade_options'] = upgrade_options
        result.append(enrich_curated_build_with_ship_name(build_data))
    return result


@router.get('/software-options')
async def public_software_options(
    playbook_id: int,
    curated_build_id: str | None = None,
    budget_tier: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Return approved software choices and this build's Playbook recommendation."""
    playbook = await db.get(Playbook, playbook_id)
    if not playbook:
        raise HTTPException(status_code=404, detail="Playbook not found")
    from app.services.software_catalogue import (
        SOFTWARE_CATALOGUE,
        effective_software_profile_for_playbook,
    )
    from app.services.product_software import (
        software_profile_for_curated_cell_from_db,
        software_profile_for_playbook_cell_from_db,
    )
    try:
        if curated_build_id:
            profile = await software_profile_for_curated_cell_from_db(
                db, curated_build_id, playbook.name, playbook.software_profile
            )
        elif budget_tier:
            profile = await software_profile_for_playbook_cell_from_db(
                db, playbook.name, budget_tier, playbook.software_profile
            )
        else:
            profile = effective_software_profile_for_playbook(playbook.name, playbook.software_profile)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "profile": profile,
        "apps": SOFTWARE_CATALOGUE,
        "estimate_basis": "Indicative internal minutes saved by avoiding app search and setup; not benchmarked or guaranteed.",
    }


@router.get('/playbooks/{playbook_id}/custom-slots')
async def public_custom_slots(playbook_id: int, db: AsyncSession = Depends(get_db)):
    """Full selection from the same published component base as curated builds."""
    base = await public_playbook_slots(playbook_id, db)
    playbook = await db.get(Playbook, playbook_id)
    requirements = playbook.requirements if playbook and isinstance(playbook.requirements, dict) else {}
    gpu_optional = requirements.get("gpu_required") is False
    pool = {}
    for pb in await public_list_playbooks(db):
        for slot in await public_playbook_slots(pb['id'], db):
            bucket = pool.setdefault(slot['slot_type'], {})
            for values in slot['variants_by_tier'].values():
                for variant in values:
                    bucket[variant['id']] = variant
    return [{
        **slot,
        'is_required': not (gpu_optional and slot['slot_type'] == 'gpu'),
        'variants_by_tier': {'budget': [], 'mid': list(pool.get(slot['slot_type'], {}).values()), 'high': []},
    } for slot in base]


# Analytics endpoints for curated journey
from app.schemas.buying_flow import SessionAnalyticsEvent

@router.post('/analytics/event')
async def track_analytics_event(
    event: SessionAnalyticsEvent,
    db: AsyncSession = Depends(get_db),
):
    """
    Track an analytics event from the curated journey.
    
    Events include: budget_chosen, customer_type_picked, playbook_tier_shown,
    case_chosen, rgb_tweaked, ar_opened, drop_off.
    
    This endpoint logs anonymous journey events for later analysis.
    """
    # TODO: Store in analytics table or send to analytics service
    # For now, just log the event
    import structlog
    log = structlog.get_logger(__name__)
    
    log.info(
        "curated_journey.analytics_event",
        event_type=event.event_type,
        curated_build_id=event.curated_build_id,
        metadata=event.metadata,
        has_buying_flow=event.buying_flow is not None,
    )
    
    return {"status": "tracked", "event_type": event.event_type}
