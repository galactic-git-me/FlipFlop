"""
Public catalogue endpoints — no auth required.
Consumed by the customer website (Subsystem 3).
"""
from collections import defaultdict
from datetime import datetime, timedelta
import json
import re

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.catalogue import CaseCatalogue, CatalogueVariant, PlaybookSlot
from app.models.configurator import ConfiguratorCatalogueVisibility
from app.models.listing import Listing
from app.models.playbook import Playbook
from app.models.curated_build_segment import CuratedBuildSegment
from app.models.case import Case
from app.models.gem_radar_scored_listing import GemRadarScoredListing
from app.models.gem_radar_observation import GemRadarListingObservation
from app.models.component_3d_asset import AssetSubjectType, Component3DAsset, Component3DAssetStatus
from app.models.gem_radar_intelligence import PreferredComponent
from app.models.growth import AnalyticsEvent
from app.services.playbook_pricing import LABOUR_COST, OVERHEAD_RATE
from app.schemas.payment import PlaybookBuildConfig
from app.services.studio_fit import engineering_specs

router = APIRouter(prefix="/public", tags=["public"])


@router.post("/playbooks/{playbook_id}/delivery-quotes")
async def playbook_delivery_quotes(
    playbook_id: int, build_config: PlaybookBuildConfig,
    db: AsyncSession = Depends(get_db),
):
    """Live, exact-specification Playbook quotes, also accepted by checkout.

    Reuse the existing validation and snapshot path so browse and payment
    cannot acquire different commercial rules.
    """
    if playbook_id != build_config.playbook_id:
        raise HTTPException(422, "The selected build belongs to a different Playbook")
    from app.services.playbook_delivery import quote_playbook_delivery
    return await quote_playbook_delivery(db, build_config)

_TIER_ORDER = ("budget", "mid", "high")
_TIER_LABELS = {"budget": "Value", "mid": "Balanced", "high": "Performance"}


def _variant_has_matching_final_model(variant: CatalogueVariant, asset: Component3DAsset | None) -> bool:
    if variant and variant.status == "active" and asset and asset.category != "case":
        return bool(asset.is_active and asset.status == Component3DAssetStatus.FINAL and asset.glb_ref)
    media = variant.asset_media_review or {}
    model_images = media.get("model_image_urls") or (
        media.get("image_urls") if len(media.get("image_urls") or []) <= 4 else []
    )
    return bool(
        media.get("status") in {"approved", "auto_included"}
        and media.get("image_urls")
        and model_images
        and asset
        and asset.source_image_refs == model_images
    )


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
                CatalogueVariant.curated_for_builds.is_(True),
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
    return await _published_playbook_slots(playbook_id, db)


async def _published_playbook_slots(playbook_id: int, db: AsyncSession, *, full_curated_range: bool = False):
    """
    Customer-visible slots for a playbook, with active variants grouped by tier.
    Exposes display pricing, product media and whitelisted engineering data.
    """
    from app.services.curated_media import media_urls
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
    free_software_slots={slot.id for slot in slots if slot.slot_type=='os_secondary'}

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

    # Visibility grants permission to display a product, never availability.
    # Hidden, sold or removed offers cannot enter a purchasable catalogue.
    if slot_ids:
        status_filter = CatalogueVariant.status == "active"
        variants_result = await db.execute(
            select(CatalogueVariant, Listing)
            .join(Listing, CatalogueVariant.listing_id == Listing.id)
            .where(
                CatalogueVariant.slot_id.in_(slot_ids),
                status_filter,
                CatalogueVariant.curated_for_builds.is_(True),
                Listing.status == "active",
                CatalogueVariant.display_price >= 0,
            )
            .order_by(CatalogueVariant.slot_id, CatalogueVariant.display_price)
        )
        all_rows = [
            (variant,listing) for variant,listing in variants_result.all()
            if variant.display_price>0 or (variant.slot_id in free_software_slots
                and isinstance(listing.raw_specs,dict)
                and isinstance(listing.raw_specs.get('playbook_free_software'),dict)
                and listing.raw_specs['playbook_free_software'].get('kind')=='official_free_os_download')
        ]
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
    if curated_slot_ids and not full_curated_range:
        all_rows = [
            (v, l) for v, l in all_rows
            if v.slot_id not in curated_slot_ids or v.id in visible_variant_ids
        ]

    # Storefront components need automatically included listing media and an
    # exact published model matching the separately selected reference photos.
    variant_ids = [variant.id for variant, _ in all_rows]
    if variant_ids:
        from app.services.shared_variant_assets import final_assets_by_variant, approved_model_photos
        from app.services.playbook_mvp import mvp_mode
        ready_asset_by_variant = await final_assets_by_variant(db, [variant for variant, _ in all_rows])
        all_rows = [
            (variant, listing) for variant, listing in all_rows
            if ready_asset_by_variant.get(variant.id) or (mvp_mode(playbook) and (approved_model_photos(variant) or variant.slot_id in {slot.id for slot in slots if slot.slot_type.startswith("os")}))
        ]

    def source_listing_id(listing: Listing) -> str:
        external_id = listing.external_id or ""
        return external_id.split("|", 1)[1] if external_id.startswith("ebay_v1|") and "|" in external_id else external_id

    source_ids = list(dict.fromkeys(source_listing_id(listing) for _, listing in all_rows if source_listing_id(listing)))
    scored_media = (await db.execute(
        select(GemRadarScoredListing).where(GemRadarScoredListing.listing_id.in_(source_ids) if source_ids else False)
        .order_by(GemRadarScoredListing.scored_at.desc(), GemRadarScoredListing.id.desc())
    )).scalars().all()
    observation_media = (await db.execute(
        select(GemRadarListingObservation).where(GemRadarListingObservation.listing_id.in_(source_ids) if source_ids else False)
        .order_by(GemRadarListingObservation.observed_at.desc(), GemRadarListingObservation.id.desc())
    )).scalars().all()
    latest_scored: dict[str, GemRadarScoredListing] = {}
    latest_observations: dict[str, GemRadarListingObservation] = {}
    for media in scored_media:
        latest_scored.setdefault(media.listing_id, media)
    for media in observation_media:
        latest_observations.setdefault(media.listing_id, media)

    def included_media(variant: CatalogueVariant, listing: Listing, kind: str) -> list[str]:
        approved_photo = (variant.asset_media_review or {}).get("main_photo_approved_url")
        if kind == "images" and approved_photo:
            return media_urls([approved_photo])
        if kind == "images" and mvp_mode(playbook):
            return media_urls(approved_model_photos(variant))
        listing_id = source_listing_id(listing)
        specs = listing.raw_specs if isinstance(listing.raw_specs, dict) else {}
        capture = specs.get("playbook_product_capture") or {}
        values = []
        if kind == "images":
            values.extend(listing.image_urls or [])
            if capture.get("url") == listing.url:
                values.extend(capture.get("product_image_urls") or [])
            for row in (latest_scored.get(listing_id), latest_observations.get(listing_id)):
                if row:
                    values.extend(row.image_urls or [])
                    if row.image_url:
                        values.append(row.image_url)
        else:
            for row in (latest_scored.get(listing_id), latest_observations.get(listing_id)):
                if row:
                    values.extend(row.video_urls or [])
        media = variant.asset_media_review or {}
        values.extend(media.get("image_urls" if kind == "images" else "video_urls") or [])
        return media_urls(values)

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
            "official_free_software": bool(v.slot_id in free_software_slots and v.display_price==0
                and isinstance(l.raw_specs,dict) and isinstance(l.raw_specs.get('playbook_free_software'),dict)
                and l.raw_specs['playbook_free_software'].get('kind')=='official_free_os_download'),
            "gem_score": l.gem_score,
            "images": included_media(v, l, "images"),
            "videos": included_media(v, l, "videos"),
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
    # The importer uses ASIN first and CPK only as a fallback. Once reconciled,
    # retain the exact CaseCatalogue id on the operational case so similar
    # CPK/title families cannot make unrelated chooser entries inherit a rank.
    live_by_catalogue_id = {}
    for row in live_cases:
        identity = (row.sourcing_3d_evidence or {}).get("amazon_top100_identity") or {}
        catalogue_id = identity.get("catalogue_id")
        if catalogue_id:
            current = live_by_catalogue_id.get(int(catalogue_id))
            if current is None or (row.bestseller_rank or 10**9) < (current.bestseller_rank or 10**9):
                live_by_catalogue_id[int(catalogue_id)] = row
    # The operational cases table owns Amazon rank. Match exact names first,
    # then token containment for Amazon titles that include extra marketing copy.
    def live_for(catalogue_case):
        reconciled = live_by_catalogue_id.get(catalogue_case.id)
        if reconciled:
            return reconciled
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

    def stale_offer_fallback_case(live_case, asset_case):
        if asset_case:
            return asset_case
        if (live_case and live_case.source_site == "Amazon"
                and live_case.bestseller_rank is not None
                and 1 <= live_case.bestseller_rank <= 100
                and (live_case.sourcing_3d_evidence or {}).get("amazon_top100_identity")):
            return live_case
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
        # Supplier availability is deliberately short-lived. A case remains
        # selectable after its vendor offer expires when its linked operational
        # Amazon bestseller row has a sourced price; hide the stale offer and
        # fall back to that price rather than dropping the case from the chooser.
        if supplier_offer:
            try:
                observed = datetime.fromisoformat(supplier_offer["observed_at"])
                if datetime.utcnow() - observed > timedelta(hours=8):
                    price_case = stale_offer_fallback_case(live, asset_case)
                    live_price = (price_case.price_new or price_case.price or price_case.rrp) if price_case else None
                    if live_price and float(live_price) > 0:
                        supplier_offer = None
                        fallback_price = float(live_price)
                    else:
                        continue
            except (KeyError, TypeError, ValueError):
                price_case = stale_offer_fallback_case(live, asset_case)
                live_price = (price_case.price_new or price_case.price or price_case.rrp) if price_case else None
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
            "asset_subject_name": asset_case.name if asset_case else None,
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
    segment = None
    if definition:
        segment = (await db.execute(select(CuratedBuildSegment).where(
            CuratedBuildSegment.customer_type == definition["segment"],
            CuratedBuildSegment.budget_level == definition["tier"],
        ))).scalar_one_or_none()
        from app.services.curated_publication import publication_snapshot, PublicationError
        try:
            snapshot = publication_snapshot(definition, segment,
                await public_playbook_slots(playbook_id, db), await public_list_cases(db))
        except PublicationError as exc:
            raise HTTPException(404, str(exc)) from exc
        slots = snapshot['slots']
    else:
        # Unscoped curated catalogues must not bypass the cell publication gate.
        raise HTTPException(404, 'Choose a published curated Playbook cell')
    if definition:
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
                        "images": media_urls(listing.image_urls or []),
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
    from app.services.curated_media import media_urls
    
    cell_segments = (await db.execute(select(CuratedBuildSegment).where(CuratedBuildSegment.is_live.is_(True)))).scalars().all()
    if not cell_segments:
        return []
    playbooks = await public_list_playbooks(db)
    cases = await public_list_cases(db)
    by_name = {p['name']: p for p in playbooks}
    catalogue = {p['id']: await public_playbook_slots(p['id'], db) for p in playbooks}
    result = []
    segment_by_cell = {(row.customer_type.casefold(), row.budget_level.casefold()): row for row in cell_segments}
    approved_rows = (await db.execute(text("""
        WITH latest AS (
            SELECT DISTINCT ON (category, asin) category, asin, title, url,
                image_url, rank, cpk, captured_at
            FROM amazon_bestseller_observations
            ORDER BY category, asin, captured_at DESC
        )
        SELECT a.category, COALESCE(a.cpk, 'asin:' || a.asin) AS cpk,
            a.title, a.url, a.image_url AS reference_image_url, r.selected_media,
            m.listing_id,
            COALESCE(m.title, a.title) AS listing_title,
            COALESCE(m.url, a.url) AS listing_url,
            COALESCE(m.image_url, a.image_url) AS listing_image_url,
            COALESCE(m.source, 'amazon') AS listing_source
        FROM latest a
        JOIN curated_bestseller_reviews r
            ON r.category = a.category AND r.cpk = COALESCE(a.cpk, 'asin:' || a.asin)
            AND r.status = 'approved'
        LEFT JOIN LATERAL (
            SELECT s.listing_id, s.source, s.title, s.url, COALESCE(
                CASE WHEN s.image_url ~* '^https?://' AND s.image_url NOT LIKE '%._RC' THEN s.image_url END,
                o.image_url
            ) AS image_url
            FROM gem_radar_scored_listings s
            LEFT JOIN LATERAL (
                SELECT image_url FROM gem_radar_listing_observations
                WHERE listing_id = s.listing_id
                  AND image_url ~* '^https?://' AND image_url NOT LIKE '%._RC'
                ORDER BY observed_at DESC, id DESC LIMIT 1
            ) o ON true
            WHERE s.delivered_price > 0 AND s.cpk = a.cpk AND s.category IN (
                CASE a.category WHEN 'storage' THEN 'ssd'
                    WHEN 'cooler' THEN 'cooling' ELSE a.category END,
                a.category
            )
            ORDER BY (COALESCE(
                CASE WHEN s.image_url ~* '^https?://' AND s.image_url NOT LIKE '%._RC' THEN s.image_url END,
                o.image_url
            ) IS NOT NULL) DESC, s.scored_at DESC
            LIMIT 1
        ) m ON true
    """))).mappings().all()
    approved_images_by_match: dict[tuple[str, str], list[dict]] = defaultdict(list)
    approved_videos_by_match: dict[tuple[str, str], list[dict]] = defaultdict(list)
    listing_match: dict[str, tuple[str, str]] = {}
    for row in approved_rows:
        pair = (str(row["category"]), str(row["cpk"]))
        if row["listing_id"]:
            listing_match[str(row["listing_id"])] = pair
        for url, title, source, href in (
            (row["reference_image_url"], row["title"], "Amazon product image", row["url"]),
            (row["listing_image_url"], row["listing_title"], f"Approved {row['listing_source']} listing", row["listing_url"]),
        ):
            if not url or any(item["url"] == url for item in approved_images_by_match[pair]):
                continue
            approved_images_by_match[pair].append({"url": url, "title": title, "source": source, "href": href})
    if listing_match:
        media_rows = (await db.execute(text("""
            SELECT o.listing_id, o.image_url, o.image_urls, o.video_urls, l.image_urls AS catalogue_image_urls
            FROM gem_radar_listing_observations o
            LEFT JOIN listings l ON l.external_id = o.listing_id
            WHERE o.listing_id = ANY(:listing_ids)
        """), {"listing_ids": list(listing_match)})).mappings().all()
        for media_row in media_rows:
            pair = listing_match.get(str(media_row["listing_id"]))
            if not pair:
                continue
            images = list(media_row["image_urls"] or [])
            images.extend(media_row["catalogue_image_urls"] or [])
            if media_row["image_url"]:
                images.append(media_row["image_url"])
            for url in dict.fromkeys(images):
                if isinstance(url, str) and url.startswith(("https://", "http://")) and not any(item["url"] == url for item in approved_images_by_match[pair]):
                    approved_images_by_match[pair].append({"url": url, "title": "Product listing photo", "source": "Approved marketplace listing", "href": None})
            for url in dict.fromkeys(media_row["video_urls"] or []):
                if isinstance(url, str) and url.startswith(("https://", "http://")) and not any(item["url"] == url for item in approved_videos_by_match[pair]):
                    approved_videos_by_match[pair].append({"url": url, "title": "Product listing video", "source": "Approved marketplace listing", "href": None})
    # Curated Playbook galleries include every captured photo and video for an
    # owner-approved exact product match. Per-photo curation is not a gate.
    for definition in definitions()['builds']:
        pb = by_name.get(definition['segment'])
        cell = segment_by_cell.get((definition['segment'].casefold(), definition['tier'].casefold()))
        if not pb or not cell:
            continue
        from app.services.curated_publication import publication_snapshot, PublicationError
        try:
            snapshot = publication_snapshot(definition, cell, catalogue.get(pb['id'], []), cases)
        except PublicationError:
            continue
        build_data = {**definition, 'components': snapshot['components'],
            'playbook_id': pb['id'], 'missing_components': [],
            'price_gbp': snapshot['price_gbp'], 'default_case_id': snapshot['default_case_id'],
            'default_slot_selections': snapshot['default_slot_selections']}
        upgrade_options = (cell.approved_upgrades or []) if cell and cell.is_live else []
        build_data['upgrade_options'] = upgrade_options
        listing_images = []
        if cell:
            for identity in (cell.bestseller_components or {}).values():
                if not isinstance(identity, dict):
                    continue
                listing_images.extend(approved_images_by_match.get((str(identity.get('category') or ''), str(identity.get('cpk') or '')), []))
        listing_images = [image for image in listing_images if media_urls([image.get('url')])]
        build_data['listing_images'] = list({image['url']: image for image in listing_images}.values())
        build_data['listing_videos'] = [video for identity in (cell.bestseller_components or {}).values() if isinstance(identity, dict)
            for video in approved_videos_by_match.get((str(identity.get('category') or ''), str(identity.get('cpk') or '')), [])] if cell else []
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
    """Start empty and select from the one approved Curated component range."""
    base = await _published_playbook_slots(playbook_id, db, full_curated_range=True)
    playbook = await db.get(Playbook, playbook_id)
    requirements = playbook.requirements if playbook and isinstance(playbook.requirements, dict) else {}
    gpu_optional = requirements.get("gpu_required") is False
    pool = {}
    for slot in base:
        bucket = pool.setdefault(slot['slot_type'], {})
        for values in slot['variants_by_tier'].values():
            for variant in values:
                bucket[variant['id']] = variant
    return [{
        **slot,
        'default_variant_id': None,
        'is_required': not (gpu_optional and slot['slot_type'] == 'gpu'),
        'variants_by_tier': {'budget': [], 'mid': list(pool.get(slot['slot_type'], {}).values()), 'high': []},
    } for slot in base if slot['slot_type'] not in {'storage_secondary','os_secondary'}]


# Analytics endpoints for curated journey
from app.schemas.buying_flow import SessionAnalyticsEvent

_CURATED_ANALYTICS_FIELDS={
    'curated_build_view': {'segment','tier'},
    'case_selected': {'case_id'},
    'component_selected': {'role','variant_id'},
    'build_added_to_cart': {'component_count'},
    'delivery_mode_selected': {'delivery_mode'},
    'checkout_started': {'delivery_mode'},
    'budget_chosen': {'budget_min','budget_max'},
    'customer_type_picked': {'customer_type'},
    'playbook_tier_shown': {'tier'},
    'case_chosen': {'case_id'},
    'rgb_tweaked': {'rgb_value'},
    'ar_opened': set(),
    'drop_off': {'step'},
}


def _safe_curated_analytics_metadata(event_type, metadata):
    """Store only small, non-identifying fields used by the Playbook funnel."""
    allowed=_CURATED_ANALYTICS_FIELDS.get(event_type,set())
    result={}
    for key in allowed:
        value=metadata.get(key)
        if isinstance(value,bool):
            result[key]=value
        elif isinstance(value,int) and not isinstance(value,bool) and abs(value)<1_000_000:
            result[key]=value
        elif isinstance(value,float) and value==value and abs(value)<1_000_000:
            result[key]=value
        elif isinstance(value,str) and len(value)<=80 and '@' not in value:
            result[key]=value
    return result

@router.post('/analytics/event')
async def track_analytics_event(
    event: SessionAnalyticsEvent,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Persist consented, pseudonymous journey signals for cell-level review."""
    if request.cookies.get('flipflop.cookie-consent.v1')!='accepted':
        return {'status':'ignored','reason':'analytics_consent_required'}
    allowed_fields=_CURATED_ANALYTICS_FIELDS.get(event.event_type)
    if allowed_fields is None:
        raise HTTPException(422,'Unsupported curated journey event')
    if not event.session_id or not re.fullmatch(r'[A-Za-z0-9-]{16,120}',event.session_id):
        raise HTTPException(422,'A valid short-lived analytics session ID is required')
    build_id=event.curated_build_id
    from app.services.curated_build_policy import definitions
    if build_id and build_id not in {row['id'] for row in definitions()['builds']}:
        raise HTTPException(422,'Unknown curated Playbook cell')
    if event.event_type in {'curated_build_view','case_selected','component_selected','build_added_to_cart','delivery_mode_selected','checkout_started'} and not build_id:
        raise HTTPException(422,'This event requires a curated Playbook cell')
    metadata=_safe_curated_analytics_metadata(event.event_type,event.metadata)
    db.add(AnalyticsEvent(source='curated_journey',event_name=event.event_type,
        session_id=event.session_id,path=f'/curated/{build_id}' if build_id else '/curated',
        utm={},properties={'curated_build_id':build_id,'metadata':metadata}))
    await db.flush()
    return {'status':'tracked','event_type':event.event_type}
