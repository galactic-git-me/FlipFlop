"""
Public configurator endpoints — no auth required.
Consumed by the theflipflop.shop storefront 3D configurator:

  - 3D asset resolution with the honest fallback chain
    (exact VARIANT/CASE asset → CATEGORY_GENERIC placeholder → none)
  - Live compatibility evaluation (Commerce PRD Ch.12.3/12.4)
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.component_3d_asset import (
    Component3DAsset,
    Component3DAssetStatus,
    AssetSubjectType,
)
from app.models.catalogue import CatalogueVariant
from app.models.listing import Listing
from app.services.configurator_compatibility import evaluate_configuration
from app.services.component_family_classifier import classify_family

router = APIRouter(prefix="/public", tags=["public-configurator"])

# Only these lifecycle states are ever served to customers.
_SERVABLE = (Component3DAssetStatus.VALIDATED, Component3DAssetStatus.FINAL)


def _asset_payload(asset: Component3DAsset, fallback_level: str) -> dict:
    return {
        "asset_id": asset.id,
        "subject_type": asset.subject_type.value,
        "subject_id": asset.subject_id,
        "category": asset.category,
        "status": asset.status.value,
        "version": asset.version,
        "glb_ref": asset.glb_ref,
        "preview_image_ref": asset.preview_image_ref,
        "anchor_manifest": asset.anchor_manifest_json,
        "dimensions_mm": asset.dimensions_mm,
        "scale_validated": asset.scale_validated,
        "fallback_level": fallback_level,  # exact | category_generic
    }


class AssetSubjectQuery(BaseModel):
    subject_type: str = Field(pattern="^(case|variant)$")
    subject_id: int
    category: str | None = None  # slot category for placeholder fallback


class AssetResolveRequest(BaseModel):
    subjects: list[AssetSubjectQuery] = Field(max_length=50)


@router.post("/assets/resolve")
async def resolve_assets(body: AssetResolveRequest, db: AsyncSession = Depends(get_db)):
    """Bulk-resolve servable 3D assets for cases/variants.

    Per subject the response is either the exact active asset, the active
    generic placeholder for its category, or {"asset": null} — the frontend
    then renders its own last-resort placeholder. A different product's model
    is never substituted (honest-fallback rule)."""
    results = []
    for subject in body.subjects:
        stype = (
            AssetSubjectType.CASE
            if subject.subject_type == "case"
            else AssetSubjectType.VARIANT
        )
        exact = (
            await db.execute(
                select(Component3DAsset).where(
                    Component3DAsset.subject_type == stype,
                    Component3DAsset.subject_id == subject.subject_id,
                    Component3DAsset.is_active == True,  # noqa: E712
                    Component3DAsset.status.in_(_SERVABLE),
                )
            )
        ).scalar_one_or_none()

        if exact and exact.glb_ref:
            results.append(
                {"query": subject.model_dump(), "asset": _asset_payload(exact, "exact")}
            )
            continue

        generic = None
        fallback_level = "category_generic"
        if subject.category:
            # Bucket-level generic first (e.g. "gpu_large_triple_fan") — a
            # closer visual match than the whole-category placeholder. Only
            # applies to VARIANT subjects, since a family bucket is derived
            # from the variant's own listing title.
            family_key = None
            if stype == AssetSubjectType.VARIANT:
                variant_row = (
                    await db.execute(
                        select(CatalogueVariant, Listing)
                        .join(Listing, CatalogueVariant.listing_id == Listing.id)
                        .where(CatalogueVariant.id == subject.subject_id)
                    )
                ).first()
                if variant_row:
                    _, listing = variant_row
                    family_key = classify_family(subject.category, listing.title or "")

            if family_key:
                generic = (
                    await db.execute(
                        select(Component3DAsset).where(
                            Component3DAsset.subject_type == AssetSubjectType.CATEGORY_GENERIC,
                            Component3DAsset.category == subject.category,
                            Component3DAsset.family_key == family_key,
                            Component3DAsset.is_active == True,  # noqa: E712
                            Component3DAsset.status.in_(_SERVABLE),
                        )
                    )
                ).scalar_one_or_none()
                if generic and generic.glb_ref:
                    fallback_level = "family_generic"

            if not (generic and generic.glb_ref):
                # Plain whole-category generic — the original, coarser
                # fallback, used when no family-specific asset exists yet
                # (library still being built out) or the title didn't
                # classify confidently.
                generic = (
                    await db.execute(
                        select(Component3DAsset).where(
                            Component3DAsset.subject_type == AssetSubjectType.CATEGORY_GENERIC,
                            Component3DAsset.category == subject.category,
                            Component3DAsset.family_key.is_(None),
                            Component3DAsset.is_active == True,  # noqa: E712
                            Component3DAsset.status.in_(_SERVABLE),
                        )
                    )
                ).scalar_one_or_none()
                fallback_level = "category_generic"

        results.append(
            {
                "query": subject.model_dump(),
                "asset": _asset_payload(generic, fallback_level)
                if generic and generic.glb_ref
                else None,
            }
        )

    return {"results": results}


class BuildSceneComponent(BaseModel):
    category: str = Field(pattern="^(motherboard|cpu|gpu|ram|storage|cooling|psu|fan)$")
    variant_id: int
    label: str | None = None


class BuildSceneRequest(BaseModel):
    case_id: int
    components: list[BuildSceneComponent] = Field(default_factory=list, max_length=30)


_MOUNT_CATEGORY = {
    "motherboard": "Motherboard",
    "gpu": "GPU",
    "psu": "PSU",
    "cooling": "CPUCooler",
    "storage": "Storage",
    "fan": "CaseFan",
}

# Relative-to-motherboard offsets are only used for components whose physical
# mount is not represented by the current case manifest schema. They are
# deliberately labelled approximate in the response and must not be used for AR
# clearance claims.
_BOARD_RELATIVE_MM = {
    "cpu": (0.0, 0.0, 12.0),
    "ram": (42.0, 0.0, 18.0),
}


@router.post("/build-scene")
async def compose_build_scene(body: BuildSceneRequest, db: AsyncSession = Depends(get_db)):
    """Resolve a case plus interchangeable component assets into one scene manifest.

    The browser keeps this manifest stable while replacing individual component
    groups, so a selection change does not reload the whole viewer.
    """
    subjects = [AssetSubjectQuery(subject_type="case", subject_id=body.case_id, category="case")]
    subjects.extend(
        AssetSubjectQuery(subject_type="variant", subject_id=item.variant_id, category=item.category)
        for item in body.components
    )
    resolved = await resolve_assets(AssetResolveRequest(subjects=subjects), db)
    case_asset = resolved["results"][0]["asset"]
    if not case_asset:
        raise HTTPException(status_code=404, detail="No approved 3D asset is available for this case")

    anchor = case_asset.get("anchor_manifest") or {}
    mounts = anchor.get("mounts") or []
    motherboard_mount = next((m for m in mounts if m.get("category") == "Motherboard"), None)

    def find_mount(category: str, occurrence: int = 0) -> dict | None:
        mount_category = _MOUNT_CATEGORY.get(category)
        matches = [m for m in mounts if m.get("category") == mount_category]
        return matches[occurrence] if occurrence < len(matches) else (matches[0] if matches else None)

    component_entries = []
    fan_occurrence = 0
    for requested, result in zip(body.components, resolved["results"][1:]):
        asset = result["asset"]
        if not asset:
            component_entries.append({
                "category": requested.category,
                "variant_id": requested.variant_id,
                "label": requested.label,
                "asset": None,
                "placement": None,
            })
            continue
        occurrence = fan_occurrence if requested.category == "fan" else 0
        mount = find_mount(requested.category, occurrence)
        if requested.category == "fan":
            fan_occurrence += 1
        approximate = False
        if not mount and requested.category in _BOARD_RELATIVE_MM and motherboard_mount:
            base = motherboard_mount.get("position_mm", (0, 0, 0))
            offset = _BOARD_RELATIVE_MM[requested.category]
            mount = {
                "id": f"motherboard-relative-{requested.category}",
                "position_mm": [base[i] + offset[i] for i in range(3)],
                "rotation_deg": motherboard_mount.get("rotation_deg", (0, 0, 0)),
            }
            approximate = True
        component_entries.append({
            "category": requested.category,
            "variant_id": requested.variant_id,
            "label": requested.label,
            "asset": asset,
            "placement": {
                "mount_id": mount.get("id") if mount else None,
                "position_mm": mount.get("position_mm", (0, 0, 0)) if mount else (0, 0, 0),
                "rotation_deg": mount.get("rotation_deg", (0, 0, 0)) if mount else (0, 0, 0),
                "approximate": approximate or mount is None,
            },
            "argb": {
                "supported": requested.category in {"fan", "ram", "gpu", "cooling"},
                "zone_id": f"{requested.category}-{requested.variant_id}",
                "mesh_name_patterns": ["rgb", "argb", "led", "light", "glow"],
            },
        })

    envelope = anchor.get("case_envelope_mm") or case_asset.get("dimensions_mm")
    return {
        "schema_version": 1,
        "case": {"case_id": body.case_id, "asset": case_asset},
        "components": component_entries,
        "case_envelope_mm": envelope,
        "ar": {
            "ready": bool(case_asset.get("scale_validated") and envelope),
            "reason": None if case_asset.get("scale_validated") and envelope else "AR requires a scale-validated case model with real dimensions",
        },
    }


class CompatibilityEvaluateRequest(BaseModel):
    playbook_id: int
    selections: dict[int, int] = Field(
        default_factory=dict,
        description="Partial selection map {slot_id: variant_id}",
    )
    case_id: int | None = None


@router.post("/compatibility/evaluate")
async def compatibility_evaluate(
    body: CompatibilityEvaluateRequest, db: AsyncSession = Depends(get_db)
):
    """Per-slot, per-variant {is_compatible, reason} for the given partial
    selection. Greyed-out-not-hidden UX: the frontend keeps incompatible
    variants visible with the returned reason (Commerce PRD 12.3)."""
    result = await evaluate_configuration(
        db,
        playbook_id=body.playbook_id,
        selections={int(k): int(v) for k, v in body.selections.items()},
        case_id=body.case_id,
    )
    if not result["slots"]:
        raise HTTPException(
            status_code=404, detail="Playbook not found or has no visible slots"
        )
    return result


class BuildPriceRequest(BaseModel):
    playbook_id: int
    slot_selections: dict[int, int]  # slot_id -> variant_id
    case_id: int | None = None


@router.post("/build-price")
async def calculate_build_price(
    body: BuildPriceRequest, db: AsyncSession = Depends(get_db)
):
    """Calculate final build price with proportional margin distribution.

    Returns:
      - Components with final display prices
      - Build total (components + case)
      - Margin breakdown
    """
    from app.models.listing import Listing as ListingModel
    from app.models.catalogue import CatalogueVariant as VariantModel

    # Get selected variants
    variant_ids = list(body.slot_selections.values())
    if not variant_ids:
        raise HTTPException(status_code=400, detail="No components selected")

    result = await db.execute(
        select(VariantModel, ListingModel)
        .join(ListingModel, VariantModel.listing_id == ListingModel.id)
        .where(VariantModel.id.in_(variant_ids))
    )
    rows = result.all()

    if not rows:
        raise HTTPException(status_code=404, detail="Variants not found")

    # Sum costs
    base_cost = sum(l.price for _, l in rows)

    # Use display prices as the final price
    # (admin has already set display_price = proportionally distributed price)
    total_component_price = sum(v.display_price for v, _ in rows)

    # Add case if selected
    case_price = 0.0
    if body.case_id:
        from app.models.catalogue import CaseCatalogue
        case_result = await db.execute(
            select(CaseCatalogue).where(CaseCatalogue.id == body.case_id)
        )
        case = case_result.scalar_one_or_none()
        if case:
            case_price = case.rrp_gbp

    total_price = total_component_price + case_price

    return {
        "components": [
            {
                "variant_id": v.id,
                "display_price": v.display_price,
            }
            for v, _ in rows
        ],
        "case_price": case_price,
        "total": total_price,
        "margin": total_component_price - base_cost,
    }
