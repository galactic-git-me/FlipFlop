"""
Admin API for configurator management.

Endpoints:
  GET  /configurator/playbooks/{playbook_id}/slots-with-variants
  GET  /configurator/visibility/{playbook_id}
  POST /configurator/visibility
  PATCH /configurator/visibility/{visibility_id}
  POST /configurator/research-market-price
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.catalogue import PlaybookSlot, CatalogueVariant
from app.models.listing import Listing
from app.models.configurator import ConfiguratorCatalogueVisibility
from app.models.gem_radar_scored_listing import GemRadarScoredListing
from app.services.market_research import research_build_price
from app.routes.admin_auth import get_current_admin

router = APIRouter(prefix="/configurator", tags=["configurator-admin"], dependencies=[Depends(get_current_admin)])


class VisibilityCreate(BaseModel):
    playbook_slot_id: int
    catalogue_variant_id: int
    is_publicly_visible: bool
    display_order: int = 0


class VisibilityOut(BaseModel):
    id: int
    playbook_slot_id: int
    catalogue_variant_id: int
    is_publicly_visible: bool
    display_order: int

    class Config:
        from_attributes = True


class ResearchMarketPriceRequest(BaseModel):
    playbook_id: int
    playbook_name: str
    specs: str


class ResearchMarketPriceResponse(BaseModel):
    suggested_price: float
    reasoning: str
    sources_analyzed: int


@router.get("/playbooks/{playbook_id}/slots-with-variants")
async def get_slots_with_variants(playbook_id: int, db: AsyncSession = Depends(get_db)):
    """Get all slots and their available variants for a playbook.

    Queries gem_radar_scored_listings (GEM/SUPER_GEM only) instead of
    the legacy listings table, to show all actively-scored gems from the
    extension rather than just CatalogueVariant rows.
    """
    # Get slots
    slots_result = await db.execute(
        select(PlaybookSlot).where(PlaybookSlot.playbook_id == playbook_id)
    )
    slots = slots_result.scalars().all()

    if not slots:
        raise HTTPException(status_code=404, detail="Playbook has no slots")

    # Map slot_type -> gem_radar categories (plural because gem_radar uses detailed categories)
    slot_to_categories = {
        "cpu": ("cpu",),
        "gpu": ("gpu",),
        "ram": ("ram",),
        "storage": ("ssd", "hdd"),
    }

    result = []
    for slot in slots:
        categories = slot_to_categories.get(slot.slot_type, ())
        if not categories:
            # Slot type not mappable to gem_radar categories, skip it
            result.append({
                "id": slot.id,
                "slot_type": slot.slot_type,
                "tier_names": slot.tier_names,
                "variants": [],
            })
            continue

        # Get GEM/SUPER_GEM listings from gem_radar for this category, ranked by deal score
        variants_result = await db.execute(
            select(GemRadarScoredListing)
            .where(
                GemRadarScoredListing.category.in_(categories),
                GemRadarScoredListing.classification.in_(("GEM", "SUPER_GEM")),
            )
            .order_by(desc(GemRadarScoredListing.deal_score))
        )
        scored_listings = variants_result.scalars().all()

        # Tier the gems by deal_score: SUPER_GEM=high, GEM with high score=mid, GEM=budget
        variants = []
        for gem in scored_listings:
            # Use classification as tier proxy
            if gem.classification == "SUPER_GEM":
                tier = "high"
            elif gem.classification == "GEM" and gem.deal_score >= 8.5:
                tier = "mid"
            else:
                tier = "budget"

            variants.append({
                "id": gem.listing_id,  # Use listing_id as the unique identifier
                "listing_id": gem.listing_id,
                "title": gem.title,
                "display_price": gem.delivered_price,
                "tier": tier,
                "status": "active",
                "source": gem.source,
                "deal_score": gem.deal_score,
                "classification": gem.classification,
            })

        slot_data = {
            "id": slot.id,
            "slot_type": slot.slot_type,
            "tier_names": slot.tier_names,
            "variants": variants,
        }
        result.append(slot_data)

    return result


@router.get("/visibility/{playbook_id}")
async def get_visibility(playbook_id: int, db: AsyncSession = Depends(get_db)):
    """Get visibility settings for all variants in a playbook."""
    # Get all slots for this playbook
    slots_result = await db.execute(
        select(PlaybookSlot.id).where(PlaybookSlot.playbook_id == playbook_id)
    )
    slot_ids = [row[0] for row in slots_result.all()]

    if not slot_ids:
        raise HTTPException(status_code=404, detail="Playbook not found")

    # Get visibility records for these slots
    vis_result = await db.execute(
        select(ConfiguratorCatalogueVisibility).where(
            ConfiguratorCatalogueVisibility.playbook_slot_id.in_(slot_ids)
        )
    )
    records = vis_result.scalars().all()

    return [
        {
            "id": r.id,
            "catalogue_variant_id": r.catalogue_variant_id,
            "playbook_slot_id": r.playbook_slot_id,
            "is_publicly_visible": r.is_publicly_visible,
            "display_order": r.display_order,
        }
        for r in records
    ]


@router.post("/visibility")
async def create_or_update_visibility(
    body: VisibilityCreate, db: AsyncSession = Depends(get_db)
):
    """Create or update visibility for a variant in a slot."""
    # Check if record exists
    existing_result = await db.execute(
        select(ConfiguratorCatalogueVisibility).where(
            ConfiguratorCatalogueVisibility.playbook_slot_id == body.playbook_slot_id,
            ConfiguratorCatalogueVisibility.catalogue_variant_id == body.catalogue_variant_id,
        )
    )
    existing = existing_result.scalar_one_or_none()

    if existing:
        # Update
        existing.is_publicly_visible = body.is_publicly_visible
        existing.display_order = body.display_order
        db.add(existing)
    else:
        # Create
        new_vis = ConfiguratorCatalogueVisibility(
            playbook_slot_id=body.playbook_slot_id,
            catalogue_variant_id=body.catalogue_variant_id,
            is_publicly_visible=body.is_publicly_visible,
            display_order=body.display_order,
        )
        db.add(new_vis)

    await db.commit()
    return {"ok": True, "visibility": body.model_dump()}


@router.patch("/visibility/{visibility_id}")
async def update_visibility(
    visibility_id: int, body: VisibilityCreate, db: AsyncSession = Depends(get_db)
):
    """Update visibility settings."""
    result = await db.execute(
        select(ConfiguratorCatalogueVisibility).where(
            ConfiguratorCatalogueVisibility.id == visibility_id
        )
    )
    vis = result.scalar_one_or_none()

    if not vis:
        raise HTTPException(status_code=404, detail="Visibility record not found")

    vis.is_publicly_visible = body.is_publicly_visible
    vis.display_order = body.display_order
    db.add(vis)
    await db.commit()

    return {
        "id": vis.id,
        "is_publicly_visible": vis.is_publicly_visible,
        "display_order": vis.display_order,
    }


@router.post("/research-market-price", response_model=ResearchMarketPriceResponse)
async def research_market_price(
    body: ResearchMarketPriceRequest, db: AsyncSession = Depends(get_db)
):
    """Research market price for a build using LLM + eBay data."""
    result = await research_build_price(
        db=db,
        playbook_name=body.playbook_name,
        specs=body.specs,
    )
    return result


class CalculatePricingRequest(BaseModel):
    playbook_id: int
    slot_selections: dict[int, int]  # slot_id -> variant_id
    market_price: float | None = None
    min_margin: float = 150.0


class ComponentPricing(BaseModel):
    variant_id: int
    base_price: float
    margin_share: float
    display_price: float


class CalculatePricingResponse(BaseModel):
    market_price: float
    total_base_cost: float
    total_margin: float
    total_price: float
    components: list[ComponentPricing]


@router.post("/calculate-pricing", response_model=CalculatePricingResponse)
async def calculate_pricing(
    body: CalculatePricingRequest, db: AsyncSession = Depends(get_db)
):
    """
    Calculate component prices with proportional margin distribution.

    If market_price is not provided, uses medial comp price.
    Ensures minimum margin, distributes proportionally.
    """
    # Get selected variants
    variant_ids = list(body.slot_selections.values())
    if not variant_ids:
        raise HTTPException(status_code=400, detail="No components selected")

    result = await db.execute(
        select(CatalogueVariant, Listing)
        .join(Listing, CatalogueVariant.listing_id == Listing.id)
        .where(CatalogueVariant.id.in_(variant_ids))
    )
    rows = result.all()

    if not rows:
        raise HTTPException(status_code=404, detail="Variants not found")

    # Sum base costs
    base_cost = sum(l.price for _, l in rows)

    # Use provided market price or estimate from components
    if body.market_price is None:
        body.market_price = base_cost * 1.5  # Default: 1.5x cost

    # Calculate total margin needed
    total_margin = max(body.min_margin, body.market_price - base_cost)
    total_price = base_cost + total_margin

    # Distribute margin proportionally by base cost
    components = []
    for variant, listing in rows:
        base_price = listing.price
        proportion = base_price / base_cost if base_cost > 0 else 1 / len(rows)
        margin_share = total_margin * proportion
        display_price = base_price + margin_share

        components.append(
            ComponentPricing(
                variant_id=variant.id,
                base_price=base_price,
                margin_share=margin_share,
                display_price=display_price,
            )
        )

    return CalculatePricingResponse(
        market_price=body.market_price,
        total_base_cost=base_cost,
        total_margin=total_margin,
        total_price=total_price,
        components=components,
    )
