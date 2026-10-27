"""Deprecated tag-to-membership bridge; the ranked Curated range owns membership."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalogue import CatalogueVariant
from app.models.listing import Listing


async def sync_search_tags_to_catalogue(db: AsyncSession, listings: list, tags: list[str]) -> int:
    """Accept legacy source-tag notifications without changing the managed range."""
    # Membership is owned by bestseller_catalogue_sync, not extension tags.
    # Legacy callers remain valid while the separate Custom range is retired.
    return 0
