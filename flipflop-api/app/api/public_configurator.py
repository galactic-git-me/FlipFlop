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
from app.services.configurator_compatibility import evaluate_configuration

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
        if subject.category:
            generic = (
                await db.execute(
                    select(Component3DAsset).where(
                        Component3DAsset.subject_type == AssetSubjectType.CATEGORY_GENERIC,
                        Component3DAsset.category == subject.category,
                        Component3DAsset.is_active == True,  # noqa: E712
                        Component3DAsset.status.in_(_SERVABLE),
                    )
                )
            ).scalar_one_or_none()

        results.append(
            {
                "query": subject.model_dump(),
                "asset": _asset_payload(generic, "category_generic")
                if generic and generic.glb_ref
                else None,
            }
        )

    return {"results": results}


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
