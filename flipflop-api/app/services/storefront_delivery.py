"""Delivery options shared by storefront checkout and server-side pricing."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.app_settings import AppSettings


async def estimate_component_sourcing_days(db: AsyncSession, variant_ids: list[int]) -> tuple[int | None, str | None]:
    """Return the slowest selected component's current, exact-URL delivery evidence."""
    if not variant_ids:
        return None, None

    from app.models.catalogue import CatalogueVariant
    from app.models.listing import Listing
    from app.models.gem_radar_scored_listing import GemRadarScoredListing

    rows = (await db.execute(
        select(CatalogueVariant.id, Listing.url, Listing.source_name)
        .join(Listing, Listing.id == CatalogueVariant.listing_id)
        .where(CatalogueVariant.id.in_(set(variant_ids)))
    )).all()
    urls = list({str(row.url).strip() for row in rows if row.url})
    scraped_by_url = {}
    if urls:
        cutoff = datetime.utcnow() - timedelta(days=14)
        scraped = (await db.execute(
            select(GemRadarScoredListing)
            .where(GemRadarScoredListing.url.in_(urls), GemRadarScoredListing.scored_at >= cutoff)
            .order_by(GemRadarScoredListing.scored_at.desc())
        )).scalars().all()
        for item in scraped:
            key = (item.url or "").strip()
            if key not in scraped_by_url:
                scraped_by_url[key] = item

    estimates: list[int] = []
    used_scrape = False
    for row in rows:
        item = scraped_by_url.get((row.url or "").strip())
        if item is not None and item.delivery_working_days is not None:
            days = int(item.delivery_working_days)
            used_scrape = True
        else:
            supplier = (row.source_name or "").casefold()
            if "vinted" in supplier or "ebay" in supplier:
                days = 7
            elif "amazon" in supplier and item is not None and item.prime_eligible:
                days = 1
            else:
                days = 3
        estimates.append(max(0, days))
    return max(estimates) if estimates else None, "scraped_listing" if used_scrape else "vendor_default"


async def apply_component_delivery_estimate(db: AsyncSession, choice: dict, variant_ids: list[int]) -> dict:
    """Apply sourcing evidence to a configured end-to-end customer promise."""
    if not variant_ids or choice.get("fulfilment_type") not in {"curated", "custom"}:
        return choice
    from app.models.catalogue import CatalogueVariant
    from app.models.listing import Listing

    sources = (await db.execute(
        select(Listing.source_name)
        .join(CatalogueVariant, CatalogueVariant.listing_id == Listing.id)
        .where(CatalogueVariant.id.in_(set(variant_ids)))
    )).scalars().all()
    if choice.get("delivery_option") != "flexible" and any(
        name and any(v in name.casefold() for v in ("ebay", "vinted")) for name in sources
    ):
        raise ValueError("eBay and Vinted sourcing require Flexible delivery")

    sourcing_days, source = await estimate_component_sourcing_days(db, variant_ids)
    choice = dict(choice)
    configured_days = int(choice.get("delivery_days") or 0)
    choice["supplier_delivery_days"] = sourcing_days
    choice["delivery_estimate_source"] = source or "configured_fulfilment_default"
    choice["delivery_days"] = max(configured_days, sourcing_days or 0)
    choice["promise"] = f"Estimated delivery within {choice['delivery_days']} working days."
    return choice


def add_working_days(start: datetime, days: int) -> datetime:
    current = start
    remaining = max(0, days)
    while remaining:
        current += timedelta(days=1)
        if current.weekday() < 5:
            remaining -= 1
    return current


async def load_delivery_settings(db: AsyncSession) -> AppSettings:
    settings = (await db.execute(select(AppSettings).where(AppSettings.name == "default"))).scalar_one_or_none()
    if settings:
        return settings
    settings = AppSettings(name="default")
    db.add(settings)
    await db.flush()
    return settings


async def delivery_choice(db: AsyncSession, fulfilment_type: str, speedy: bool, flexible: bool = False) -> dict:
    settings = await load_delivery_settings(db)
    now = datetime.now(ZoneInfo("Europe/London"))
    speedy_fee = float(settings.speedy_delivery_price_gbp if settings.speedy_delivery_price_gbp is not None else 49.0) if speedy else 0.0
    if fulfilment_type == "prebuilt":
        if speedy:
            cutoff_hour = int(settings.speedy_prebuilt_cutoff_hour if settings.speedy_prebuilt_cutoff_hour is not None else 14)
            before_cutoff = (now.hour, now.minute) < (cutoff_hour, 0)
            cutoff = f"{cutoff_hour:02d}:00"
            promise = f"Target delivery within 1 working day. Orders before {cutoff} UK time dispatch the same day; later orders dispatch the next working day."
            return {"fulfilment_type": fulfilment_type, "speedy_delivery": True, "fee_gbp": speedy_fee,
                    "delivery_option": "fast_track", "promise": promise, "delivery_days": 1, "same_day_dispatch": before_cutoff}
        days = int(settings.standard_prebuilt_days if settings.standard_prebuilt_days is not None else 3)
        return {"fulfilment_type": fulfilment_type, "speedy_delivery": False, "fee_gbp": 0.0,
                "delivery_option": "standard", "promise": f"Estimated delivery within {days} working days.", "delivery_days": days, "same_day_dispatch": False}

    if flexible:
        days = int(settings.flexible_curated_custom_days if settings.flexible_curated_custom_days is not None else 10)
        return {"fulfilment_type": fulfilment_type, "speedy_delivery": False, "delivery_option": "flexible", "fee_gbp": 0.0,
                "promise": f"Estimated delivery within {days} working days.", "delivery_days": days, "same_day_dispatch": False}
    days = int(settings.speedy_curated_custom_days if settings.speedy_curated_custom_days is not None else 3) if speedy else int(settings.standard_curated_custom_days if settings.standard_curated_custom_days is not None else 5)
    return {"fulfilment_type": fulfilment_type, "speedy_delivery": speedy, "delivery_option": "fast_track" if speedy else "standard", "fee_gbp": speedy_fee,
            "promise": f"Estimated delivery within {days} working days.", "delivery_days": days, "same_day_dispatch": False}


def checkout_metadata(choice: dict) -> dict[str, str]:
    return {
        "delivery_type": str(choice["fulfilment_type"]),
        "speedy_delivery": "true" if choice["speedy_delivery"] else "false",
        "delivery_option": str(choice.get("delivery_option", "standard")),
        "delivery_fee_gbp": f"{float(choice['fee_gbp']):.2f}",
        "delivery_promise": str(choice["promise"]),
        "delivery_days": "" if choice["delivery_days"] is None else str(choice["delivery_days"]),
        "same_day_dispatch": "true" if choice["same_day_dispatch"] else "false",
        "delivery_estimate_source": str(choice.get("delivery_estimate_source", "configured_fulfilment_default")),
        "supplier_delivery_days": "" if choice.get("supplier_delivery_days") is None else str(choice["supplier_delivery_days"]),
    }
