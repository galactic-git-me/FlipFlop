"""Legacy from-scratch builder API backed by the single Curated catalogue."""
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
        "image_url": (variant.asset_media_review or {}).get("main_photo_approved_url") or (listing.image_urls[0] if listing.image_urls else None),
        "source_price": listing.price or 0,
        "price": variant.display_price,
        "proposed_price": None,
        "custom_cost_snapshot": variant.custom_cost_snapshot,
        "custom_for_builds": variant.curated_for_builds,
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
        .where(CatalogueVariant.curated_for_builds.is_(True),
            CatalogueVariant.status.in_(("active", "pending_review")),
        ).order_by(CatalogueVariant.auto_published_at.desc())
    )).all()


async def _settings(db: AsyncSession) -> CustomBuildSettings:
    settings = await db.get(CustomBuildSettings, 1)
    if settings is None:
        settings = CustomBuildSettings(id=1, is_live=False)
        db.add(settings)
        await db.flush()
    return settings


def _refresh_availability(variant: CatalogueVariant, listing: Listing) -> None:
    from app.services.shared_variant_assets import approved_model_photos
    title = (listing.title or "").lower()
    clean_listing = (
        listing.listing_type == "buy_it_now"
        and variant.curated_for_builds
        and listing.condition not in ("for_parts", "parts_only", "untested")
        and not any(term in title for term in ("for parts", "parts only", "not working", "spares or repair"))
    )
    available = (variant.status == "active" and getattr(listing.status, "value", listing.status) == "active"
        and clean_listing and (listing.price or 0) > 0 and variant.display_price > 0
        and not (listing.raw_specs or {}).get("catalogue_deleted")
        and (listing_is_software(listing) or bool(approved_model_photos(variant))))
    variant.custom_sale_status = "on_sale" if available else "out_of_stock"


def listing_is_software(listing):
    specs = listing.raw_specs or {}
    return bool(specs.get("gamers_outlet") or specs.get("royalcdkeys") or specs.get("playbook_free_software"))


@router.get("")
async def get_custom_catalogue(db: AsyncSession = Depends(get_db)):
    items = []
    seen_listings: set[int] = set()
    for variant, listing, slot in sorted(await _rows(db), key=lambda row: (not row[0].curated_for_builds, -row[0].id)):
        if listing.id in seen_listings:
            continue
        seen_listings.add(listing.id)
        _refresh_availability(variant, listing)
        items.append(_item(variant, listing, slot))
    settings = await _settings(db)
    return {"items": items, "is_live": settings.is_live}


@router.patch("/variants/{variant_id}/catalogue")
async def set_custom_membership(variant_id: int, body: MembershipBody, db: AsyncSession = Depends(get_db)):
    raise HTTPException(410, "There is one Curated catalogue. Its range is managed from Amazon rankings and Playbook requirements.")


@router.post("/variants/{variant_id}/approve-price")
async def approve_component_price(variant_id: int, db: AsyncSession = Depends(get_db)):
    raise HTTPException(410, "Separate Custom catalogue prices have been retired. Use the Curated catalogue.")


@router.post("/variants/{variant_id}/dismiss-price")
async def dismiss_component_price(variant_id: int, db: AsyncSession = Depends(get_db)):
    raise HTTPException(410, "Separate Custom catalogue prices have been retired. Use the Curated catalogue.")


@router.post("/go-live")
async def set_custom_catalogue_live(body: LiveBody, db: AsyncSession = Depends(get_db)):
    settings = await _settings(db)
    if body.is_live:
        available_by_slot: set[str] = set()
        has_pending_prices = False
        for variant, listing, slot in await _rows(db):
            if variant.curated_for_builds:
                _refresh_availability(variant, listing)
                has_pending_prices = False
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
    for variant, listing, slot in sorted(await _rows(db), key=lambda row: (not row[0].curated_for_builds, -row[0].id)):
        if not variant.curated_for_builds:
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
            "price": variant.display_price,
            "image_url": (variant.asset_media_review or {}).get("main_photo_approved_url") or (listing.image_urls[0] if listing.image_urls else None),
        })
    return {"is_live": True, "components": components}
