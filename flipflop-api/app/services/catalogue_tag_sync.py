"""Carry explicit extension search tags onto already reviewed catalogue rows."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalogue import CatalogueVariant
from app.models.listing import Listing


async def sync_search_tags_to_catalogue(db: AsyncSession, listings: list, tags: list[str]) -> int:
    """Set catalogue eligibility flags for exact-URL matches without publishing.

    New Gem Radar candidates remain review-only. This bridge only updates a
    catalogue row already connected to the same listing URL; `status` is never
    changed, so a tag cannot bypass review or publication controls.
    """
    normalised = {str(tag).strip().casefold() for tag in tags}
    curated = bool(normalised & {"curated", "top10bestsellers", "top-10-bestsellers"})
    custom = bool(normalised & {"custom", "allbestsellers", "all-bestsellers"})
    if not (curated or custom):
        return 0
    urls = {str(item.url).strip() for item in listings if getattr(item, "url", None)}
    if not urls:
        return 0
    matches = (await db.execute(
        select(CatalogueVariant).join(Listing, Listing.id == CatalogueVariant.listing_id)
        .where(Listing.url.in_(urls))
    )).scalars().all()
    for variant in matches:
        if curated:
            variant.curated_for_builds = True
        if custom:
            variant.custom_for_builds = True
    return len(matches)
