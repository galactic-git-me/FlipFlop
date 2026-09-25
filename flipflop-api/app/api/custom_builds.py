"""Custom component catalogue administration and storefront availability."""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.catalogue import CatalogueVariant, PlaybookSlot
from app.models.custom_build_settings import CustomBuildSettings
from app.models.listing import Classification, Listing
from app.routes.admin_auth import get_current_admin

router = APIRouter(prefix="/custom-builds", tags=["custom-builds"], dependencies=[Depends(get_current_admin)])
public_router = APIRouter(prefix="/public/custom-builds", tags=["public-custom-builds"])
REQUIRED_SLOTS = {"cpu", "gpu", "motherboard", "ram", "storage", "psu", "case"}


class MembershipBody(BaseModel):
    custom_for_builds: bool


class LiveBody(BaseModel):
    is_live: bool


def _item(variant: CatalogueVariant, listing: Listing, slot: PlaybookSlot) -> dict:
    return {
        "id": variant.id,
        "listing_id": variant.listing_id,
        "slot_type": slot.slot_type,
        "title": listing.title,
        "image_url": listing.image_urls[0] if listing.image_urls else None,
        "source_price": listing.price,
        "price": variant.custom_display_price if variant.custom_display_price is not None else variant.display_price,
        "proposed_price": variant.custom_proposed_price,
        "custom_cost_snapshot": variant.custom_cost_snapshot,
        "custom_for_builds": variant.custom_for_builds,
        "sale_status": variant.custom_sale_status,
        "listing_status": listing.status.value if hasattr(listing.status, "value") else listing.status,
        "catalogue_status": variant.status,
        "last_seen_at": listing.last_seen_at.isoformat() if listing.last_seen_at else None,
        "url": listing.url,
    }


async def _rows(db: AsyncSession):
    return (await db.execute(
        select(CatalogueVariant, Listing, PlaybookSlot)
        .join(Listing, CatalogueVariant.listing_id == Listing.id)
        .join(PlaybookSlot, CatalogueVariant.slot_id == PlaybookSlot.id)
        .where(or_(
            CatalogueVariant.custom_for_builds.is_(True),
            and_(
                Listing.classification.in_((Classification.gem, Classification.amazing_gem)),
                Listing.listing_type == "buy_it_now",
                or_(Listing.condition.is_(None), Listing.condition.notin_(("for_parts", "parts_only", "untested"))),
                ~Listing.title.ilike("%for parts%"), ~Listing.title.ilike("%parts only%"),
                ~Listing.title.ilike("%not working%"), ~Listing.title.ilike("%spares or repair%"),
                ~Listing.external_id.ilike("%206450130546%"),
                CatalogueVariant.status != "hidden",
            ),
        )).order_by(CatalogueVariant.auto_published_at.desc())
    )).all()


async def _settings(db: AsyncSession) -> CustomBuildSettings:
    settings = await db.get(CustomBuildSettings, 1)
    if settings is None:
        settings = CustomBuildSettings(id=1, is_live=False)
        db.add(settings)
        await db.flush()
    return settings


def _refresh_availability(variant: CatalogueVariant, listing: Listing) -> None:
    title = (listing.title or "").lower()
    clean_listing = (
        listing.listing_type == "buy_it_now"
        and listing.classification in (Classification.gem, Classification.amazing_gem)
        and listing.condition not in ("for_parts", "parts_only", "untested")
        and not any(term in title for term in ("for parts", "parts only", "not working", "spares or repair"))
    )
    available = variant.status == "active" and listing.status.value == "active" and clean_listing
    variant.custom_sale_status = "on_sale" if available else "out_of_stock"


@router.get("")
async def get_custom_catalogue(db: AsyncSession = Depends(get_db)):
    items = []
    seen_listings: set[int] = set()
    for variant, listing, slot in sorted(await _rows(db), key=lambda row: (not row[0].custom_for_builds, -row[0].id)):
        if listing.id in seen_listings:
            continue
        seen_listings.add(listing.id)
        if variant.custom_for_builds:
            _refresh_availability(variant, listing)
            if variant.custom_cost_snapshot is None:
                variant.custom_cost_snapshot = listing.price
                if variant.custom_display_price is None:
                    variant.custom_display_price = variant.display_price
            elif variant.custom_display_price is not None:
                delta = listing.price - variant.custom_cost_snapshot
                proposed = round(max(0, variant.custom_display_price + delta), 2)
                variant.custom_proposed_price = proposed if abs(proposed - variant.custom_display_price) >= 0.01 else None
        items.append(_item(variant, listing, slot))
    settings = await _settings(db)
    return {"items": items, "is_live": settings.is_live}


@router.patch("/variants/{variant_id}/catalogue")
async def set_custom_membership(variant_id: int, body: MembershipBody, db: AsyncSession = Depends(get_db)):
    variant = await db.get(CatalogueVariant, variant_id)
    if not variant:
        raise HTTPException(status_code=404, detail="Catalogue component not found")
    variant.custom_for_builds = body.custom_for_builds
    variant.updated_at = datetime.utcnow().isoformat()
    listing = await db.get(Listing, variant.listing_id)
    if body.custom_for_builds and listing:
        variant.custom_cost_snapshot = listing.price
        variant.custom_display_price = variant.custom_display_price if variant.custom_display_price is not None else variant.display_price
        _refresh_availability(variant, listing)
    elif not body.custom_for_builds:
        variant.custom_sale_status = "out_of_stock"
    return {"id": variant.id, "custom_for_builds": variant.custom_for_builds, "sale_status": variant.custom_sale_status}


@router.post("/variants/{variant_id}/approve-price")
async def approve_component_price(variant_id: int, db: AsyncSession = Depends(get_db)):
    variant = await db.get(CatalogueVariant, variant_id)
    if not variant or variant.custom_proposed_price is None:
        raise HTTPException(status_code=409, detail="No proposed custom-build price is available")
    listing = await db.get(Listing, variant.listing_id)
    variant.custom_display_price = variant.custom_proposed_price
    variant.custom_proposed_price = None
    variant.custom_cost_snapshot = listing.price if listing else variant.custom_cost_snapshot
    return {"id": variant.id, "price": variant.custom_display_price, "custom_cost_snapshot": variant.custom_cost_snapshot}


@router.post("/variants/{variant_id}/dismiss-price")
async def dismiss_component_price(variant_id: int, db: AsyncSession = Depends(get_db)):
    variant = await db.get(CatalogueVariant, variant_id)
    if not variant or variant.custom_proposed_price is None:
        raise HTTPException(status_code=409, detail="No proposed custom-build price is available")
    listing = await db.get(Listing, variant.listing_id)
    variant.custom_proposed_price = None
    variant.custom_cost_snapshot = listing.price if listing else variant.custom_cost_snapshot
    return {"id": variant.id, "dismissed": True, "custom_cost_snapshot": variant.custom_cost_snapshot}


@router.post("/go-live")
async def set_custom_catalogue_live(body: LiveBody, db: AsyncSession = Depends(get_db)):
    settings = await _settings(db)
    if body.is_live:
        available_by_slot: set[str] = set()
        has_pending_prices = False
        for variant, listing, slot in await _rows(db):
            if variant.custom_for_builds:
                _refresh_availability(variant, listing)
                has_pending_prices = has_pending_prices or variant.custom_proposed_price is not None
                if variant.custom_sale_status == "on_sale":
                    available_by_slot.add(slot.slot_type)
        missing = sorted(REQUIRED_SLOTS - available_by_slot)
        if missing:
            raise HTTPException(status_code=409, detail=f"Add an available custom component for: {', '.join(missing)}")
        if has_pending_prices:
            raise HTTPException(status_code=409, detail="Approve or dismiss the proposed component price changes before publishing")
    settings.is_live = body.is_live
    settings.updated_at = datetime.utcnow()
    return {"is_live": settings.is_live}


@public_router.get("/catalogue")
async def public_custom_catalogue(db: AsyncSession = Depends(get_db)):
    settings = await db.get(CustomBuildSettings, 1)
    if not settings or not settings.is_live:
        return {"is_live": False, "components": []}
    components = []
    seen_listings: set[int] = set()
    for variant, listing, slot in sorted(await _rows(db), key=lambda row: (not row[0].custom_for_builds, -row[0].id)):
        if not variant.custom_for_builds:
            continue
        if listing.id in seen_listings:
            continue
        seen_listings.add(listing.id)
        _refresh_availability(variant, listing)
        if variant.custom_sale_status != "on_sale":
            continue
        components.append({
            "id": variant.id,
            "category": slot.slot_type,
            "title": listing.title,
            "price": variant.custom_display_price if variant.custom_display_price is not None else variant.display_price,
            "image_url": listing.image_urls[0] if listing.image_urls else None,
        })
    return {"is_live": True, "components": components}
