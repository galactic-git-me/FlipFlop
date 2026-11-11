"""Public deterministic PC part compatibility endpoint."""
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.catalogue import CatalogueVariant
from app.models.component_manual import ComponentManual
from app.models.gem_radar_listing_cpk import GemRadarListingCpk
from app.models.gem_radar_observation import GemRadarListingObservation
from app.models.gem_radar_scored_listing import GemRadarScoredListing
from app.models.listing import Listing, ListingStatus
from app.services.pc_parts_compatibility import evaluate_pc_parts_compatibility
from app.services.component_manual_library import matching_manuals

router = APIRouter(prefix="/public/pc-parts-compatibility", tags=["pc-parts-compatibility"])


class CompatibilityCheckRequest(BaseModel):
    parts: dict[str, dict[str, Any]] = Field(default_factory=dict, max_length=20)
    case: dict[str, Any] = Field(default_factory=dict)
    gpu_required: bool = True


@router.post("/check")
async def check_pc_parts_compatibility(body: CompatibilityCheckRequest) -> dict[str, Any]:
    """Check supplied, source-backed engineering facts without storing them."""
    return evaluate_pc_parts_compatibility(body.parts, body.case, gpu_required=body.gpu_required)


def _vendor_name(source: str | None, url: str | None, seller: str | None) -> str:
    value = (source or "").strip().casefold()
    if not value and url:
        value = (urlsplit(url).hostname or "").removeprefix("www.").split(".")[0].casefold()
    if not value:
        value = seller or "Other"
    labels = {
        "amazon": "Amazon", "ebay": "eBay", "overclockers": "Overclockers UK",
        "scan": "Scan", "awd_it": "AWD-IT", "computer_orbit": "Computer Orbit",
        "bargain_hardware": "Bargain Hardware", "cex": "CeX", "newegg": "Newegg",
    }
    return labels.get(value, value.replace("_", " ").replace("-", " ").title())


@router.get("/components/{variant_id}/product-info")
async def get_component_product_info(variant_id: int, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Return fresh vendor offers, captured price history and an exact guide match."""
    row = (await db.execute(
        select(CatalogueVariant, Listing)
        .join(Listing, Listing.id == CatalogueVariant.listing_id)
        .where(
            CatalogueVariant.id == variant_id,
            CatalogueVariant.status == "active",
            Listing.status == ListingStatus.active,
            (CatalogueVariant.curated_for_builds.is_(True) | CatalogueVariant.custom_for_builds.is_(True)),
        )
    )).first()
    if not row:
        raise HTTPException(404, "Active public component not found")
    variant, listing = row

    external_id = str(listing.external_id)
    if external_id.startswith("ebay_v1|") and "|" in external_id:
        external_id = external_id.split("|", 1)[1]
    cpk = (await db.execute(
        select(GemRadarListingCpk.cpk).where(GemRadarListingCpk.listing_id == external_id).limit(1)
    )).scalar_one_or_none()
    if not cpk:
        cpk = (await db.execute(
            select(GemRadarScoredListing.cpk).where(
                GemRadarScoredListing.listing_id == external_id,
                GemRadarScoredListing.cpk.is_not(None),
            ).order_by(GemRadarScoredListing.scored_at.desc()).limit(1)
        )).scalar_one_or_none()

    related_ids = {external_id}
    if cpk:
        related_ids.update((await db.execute(
            select(GemRadarListingCpk.listing_id).where(GemRadarListingCpk.cpk == cpk)
        )).scalars().all())
        related_ids.update((await db.execute(
            select(GemRadarScoredListing.listing_id).where(GemRadarScoredListing.cpk == cpk)
        )).scalars().all())

    cutoff = datetime.utcnow() - timedelta(days=180)
    observations = (await db.execute(
        select(GemRadarListingObservation)
        .where(
            GemRadarListingObservation.listing_id.in_(related_ids),
            GemRadarListingObservation.observed_at >= cutoff,
            GemRadarListingObservation.delivered_price > 0,
            GemRadarListingObservation.condition_normalised == "new",
        )
        .order_by(GemRadarListingObservation.observed_at.desc())
        .limit(3000)
    )).scalars().all()

    # The newest seen price for each distinct offer avoids allowing repeat
    # scans of one URL to outweigh other vendor listings in the display.
    latest_offer: dict[str, GemRadarListingObservation] = {}
    history_by_day: dict[tuple[str, str], list[float]] = defaultdict(list)
    for observation in observations:
        vendor = _vendor_name(observation.source, None, observation.seller_name)
        latest_offer.setdefault(observation.listing_id, observation)
        history_by_day[(observation.observed_at.date().isoformat(), vendor)].append(float(observation.delivered_price))

    latest_by_vendor: dict[str, list[GemRadarListingObservation]] = defaultdict(list)
    for offer in latest_offer.values():
        vendor = _vendor_name(offer.source, None, offer.seller_name)
        if offer.observed_at >= datetime.utcnow() - timedelta(days=30):
            latest_by_vendor[vendor].append(offer)

    ids_with_urls = list(latest_offer)
    scored_rows = (await db.execute(
        select(GemRadarScoredListing.listing_id, GemRadarScoredListing.url)
        .where(GemRadarScoredListing.listing_id.in_(ids_with_urls), GemRadarScoredListing.url.is_not(None))
        .order_by(GemRadarScoredListing.scored_at.desc())
    )).all() if ids_with_urls else []
    urls: dict[str, str] = {}
    for listing_id, url in scored_rows:
        urls.setdefault(listing_id, url)

    vendor_prices = []
    for vendor, offers in sorted(latest_by_vendor.items()):
        best = min(offers, key=lambda item: (item.delivered_price, -item.observed_at.timestamp()))
        vendor_prices.append({
            "vendor": vendor,
            "price_gbp": round(float(best.delivered_price), 2),
            "item_price_gbp": round(float(best.item_price), 2),
            "postage_gbp": round(float(best.postage_price or 0), 2),
            "observed_at": best.observed_at.isoformat(),
            "url": urls.get(best.listing_id),
            "seller": best.seller_name,
        })

    history = [
        {"date": day, "vendor": vendor, "price_gbp": round(sum(prices) / len(prices), 2)}
        for (day, vendor), prices in sorted(history_by_day.items())
    ]

    raw_specs = listing.raw_specs if isinstance(listing.raw_specs, dict) else {}
    identity = raw_specs.get("identity") if isinstance(raw_specs.get("identity"), dict) else {}
    manuals = (await db.execute(select(ComponentManual).where(ComponentManual.is_active.is_(True)))).scalars().all()
    manual_identity = {
        "component_name": listing.title,
        "component_key": listing.title,
        "model": identity.get("model") or raw_specs.get("model"),
        "model_number": identity.get("model_number") or raw_specs.get("model_number"),
        "mpn": identity.get("mpn") or raw_specs.get("mpn"),
        "manufacturer_part_number": identity.get("manufacturer_part_number") or raw_specs.get("manufacturer_part_number"),
        "gtin": identity.get("gtin") or raw_specs.get("gtin"),
    }
    guide_match = matching_manuals([manual_identity], manuals)
    guide = guide_match[0] if guide_match else None

    return {
        "variant_id": variant.id,
        "title": listing.title,
        "cpk": cpk,
        "prices": vendor_prices,
        "history": history,
        "history_days": 180,
        "guide": guide,
    }
