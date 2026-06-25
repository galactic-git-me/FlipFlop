"""
Multi-source component price search.

Searches Vinted, Gumtree, Amazon, Temu, AliExpress for component listings.
Returns lowest price found for a given component model across all sources.
"""
from __future__ import annotations
import asyncio
from dataclasses import dataclass
from typing import TypedDict
import structlog

log = structlog.get_logger(__name__)

_GUMTREE_PAGE_COUNT = 1


@dataclass
class ComponentListing:
    """A component listing from any source."""
    title: str
    price: float
    source: str  # "vinted", "gumtree", "amazon", "temu", "aliexpress"
    url: str
    image_url: str | None = None
    condition: str | None = None  # "used", "new", etc.


async def search_component_all_sources(
    component_name: str,
    min_price: float = 5.0,
    max_price: float = 2500.0,
) -> list[ComponentListing]:
    """
    Search all sources for a component.
    Returns listings sorted by price (lowest first).
    """
    vinted_task = _search_vinted(component_name, min_price, max_price)
    gumtree_task = _search_gumtree(component_name, min_price, max_price)
    amazon_task = _search_amazon(component_name, min_price, max_price)
    temu_task = _search_temu(component_name, min_price, max_price)
    aliexpress_task = _search_aliexpress(component_name, min_price, max_price)

    vinted, gumtree, amazon, temu, aliexpress = await asyncio.gather(
        vinted_task, gumtree_task, amazon_task, temu_task, aliexpress_task,
        return_exceptions=True,
    )

    results = []
    for result in [vinted, gumtree, amazon, temu, aliexpress]:
        if isinstance(result, list):
            results.extend(result)
        elif isinstance(result, Exception):
            log.warning("component_search.source_error", error=str(result))

    return sorted(results, key=lambda x: x.price)


async def _search_vinted(
    component_name: str,
    min_price: float,
    max_price: float,
) -> list[ComponentListing]:
    """Search Vinted for component listings."""
    try:
        from app.scrapers.vinted_scraper import fetch_vinted_listings
        rows = await fetch_vinted_listings(
            search_terms=[component_name],
            min_price=int(min_price),
            max_price=int(max_price),
        )
        return [
            ComponentListing(
                title=row.get("title", ""),
                price=float(row.get("price", 0)),
                source="vinted",
                url=row.get("url", ""),
                image_url=row.get("image_urls", [None])[0] if row.get("image_urls") else None,
                condition="used",
            )
            for row in rows
            if min_price <= float(row.get("price", 0)) <= max_price
        ]
    except Exception as exc:
        log.warning("component_search.vinted_error", error=str(exc))
        return []


async def _search_gumtree(
    component_name: str,
    min_price: float,
    max_price: float,
) -> list[ComponentListing]:
    """Search Gumtree for component listings."""
    try:
        from app.services.playwright_scraper import scrape_gumtree_playwright
        rows = await scrape_gumtree_playwright([component_name], _GUMTREE_PAGE_COUNT, int(max_price))
        return [
            ComponentListing(
                title=row.get("title", ""),
                price=float(row.get("price", 0)),
                source="gumtree",
                url=row.get("url", ""),
                image_url=row.get("image_url"),
            )
            for row in rows
            if min_price <= float(row.get("price", 0)) <= max_price
        ]
    except Exception as exc:
        log.warning("component_search.gumtree_error", error=str(exc))
        return []


async def _search_amazon(
    component_name: str,
    min_price: float,
    max_price: float,
) -> list[ComponentListing]:
    """Search Amazon for component listings."""
    # Placeholder: would use upgrade_parts._fetch_amazon infrastructure
    log.debug("component_search.amazon_placeholder", term=component_name)
    return []


async def _search_temu(
    component_name: str,
    min_price: float,
    max_price: float,
) -> list[ComponentListing]:
    """Search Temu for component listings."""
    # Placeholder: would use upgrade_parts._fetch_temu infrastructure
    log.debug("component_search.temu_placeholder", term=component_name)
    return []


async def _search_aliexpress(
    component_name: str,
    min_price: float,
    max_price: float,
) -> list[ComponentListing]:
    """Search AliExpress for component listings."""
    # Placeholder: would use upgrade_parts._fetch_aliexpress infrastructure
    log.debug("component_search.aliexpress_placeholder", term=component_name)
    return []
