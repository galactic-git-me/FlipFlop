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


def _get_vinted_search_terms(component_name: str) -> list[str]:
    """Convert component model names to simple marketplace search terms."""
    name_lower = component_name.lower()

    # CPU: Extract socket type (AM4, AM5, LGA1700) and return generic term
    if "cpu" in name_lower or "processor" in name_lower:
        if "am4" in name_lower:
            return ["AM4 CPU"]
        elif "am5" in name_lower:
            return ["AM5 CPU"]
        elif "lga" in name_lower:
            return ["Intel CPU"]
        return ["CPU"]

    # Motherboard: Extract socket and return generic term
    if "motherboard" in name_lower or "mobo" in name_lower:
        if "am4" in name_lower:
            return ["AM4 motherboard"]
        elif "am5" in name_lower:
            return ["AM5 motherboard"]
        elif "lga" in name_lower:
            return ["Intel motherboard"]
        return ["motherboard"]

    # RAM: Extract generation and return generic term
    if "ram" in name_lower or "ddr" in name_lower:
        if "ddr5" in name_lower:
            return ["DDR5 RAM"]
        elif "ddr4" in name_lower:
            return ["DDR4 RAM"]
        return ["RAM"]

    # SSD/NVMe: Generic storage terms
    if "ssd" in name_lower or "nvme" in name_lower or "m.2" in name_lower:
        if "nvme" in name_lower or "m.2" in name_lower:
            return ["NVME drive"]
        return ["SSD"]

    # GPU: Generic graphics card terms
    if "gpu" in name_lower or "graphics" in name_lower or "rtx" in name_lower or "gtx" in name_lower:
        return ["graphics card"]

    # PSU: Generic power supply terms
    if "psu" in name_lower or "power supply" in name_lower:
        return ["power supply"]

    # Cooler: Generic cooler terms
    if "cooler" in name_lower or "heatsink" in name_lower or "aio" in name_lower:
        return ["CPU cooler"]

    # Fallback: Use component name as-is
    return [component_name]


@dataclass
class ComponentListing:
    """A component listing from any source."""
    title: str
    price: float
    source: str  # "vinted", "gumtree", "amazon", "temu", "aliexpress"
    url: str
    image_url: str | None = None
    condition: str | None = None  # "used", "new", etc.
    estimated_delivery_days: int | None = None  # Days to delivery


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
    """Search Vinted for component listings using flexible search terms."""
    try:
        from app.scrapers.vinted_scraper import fetch_vinted_listings

        # Convert specific model names to general Vinted search terms
        # (e.g., "16GB DDR4 3200MHz Kit" → ["DDR4 RAM", "16GB RAM"])
        search_terms = _get_vinted_search_terms(component_name)

        rows = await fetch_vinted_listings(
            search_terms=search_terms,
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
                estimated_delivery_days=row.get("estimated_delivery_days"),
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
    """Search Gumtree for component listings using flexible search terms."""
    try:
        from app.services.playwright_scraper import scrape_gumtree_playwright

        # Use the same search term conversion as Vinted
        search_terms = _get_vinted_search_terms(component_name)

        rows = await scrape_gumtree_playwright(search_terms, int(min_price), int(max_price))
        return [
            ComponentListing(
                title=row.get("title", ""),
                price=float(row.get("price", 0)),
                source="gumtree",
                url=row.get("url", ""),
                image_url=row.get("image_url"),
                estimated_delivery_days=row.get("estimated_delivery_days"),
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
    """Search Amazon for component listings using Playwright."""
    try:
        from app.scrapers.amazon_scraper import fetch_amazon_listings

        # Convert component name to search terms
        search_terms = _get_vinted_search_terms(component_name)

        rows = await fetch_amazon_listings(
            search_terms=search_terms,
            min_price=min_price,
            max_price=max_price,
        )
        return [
            ComponentListing(
                title=row.get("title", ""),
                price=float(row.get("price", 0)),
                source="amazon",
                url=row.get("url", ""),
                image_url=row.get("image_urls", [None])[0] if row.get("image_urls") else None,
                condition=row.get("condition", "new"),
                estimated_delivery_days=row.get("estimated_delivery_days"),
            )
            for row in rows
            if min_price <= float(row.get("price", 0)) <= max_price
        ]
    except Exception as exc:
        log.warning("component_search.amazon_error", error=str(exc))
        return []


async def _search_temu(
    component_name: str,
    min_price: float,
    max_price: float,
) -> list[ComponentListing]:
    """Search Temu for component listings using Apify."""
    try:
        from app.scrapers.temu_scraper import scrape_temu_components

        result = await scrape_temu_components()
        listings = result.get("listings", [])

        return [
            ComponentListing(
                title=listing.get("title", ""),
                price=float(listing.get("price_gbp", 0)),
                source="temu",
                url=listing.get("source_url", ""),
                image_url=None,
                condition="new",
                estimated_delivery_days=listing.get("estimated_delivery_days"),
            )
            for listing in listings
            if min_price <= float(listing.get("price_gbp", 0)) <= max_price
        ]
    except Exception as exc:
        log.warning("component_search.temu_error", error=str(exc))
        return []


async def _search_aliexpress(
    component_name: str,
    min_price: float,
    max_price: float,
) -> list[ComponentListing]:
    """Search AliExpress for component listings using Playwright."""
    try:
        from app.scrapers.aliexpress_scraper import fetch_aliexpress_listings

        # Convert component name to search terms
        search_terms = _get_vinted_search_terms(component_name)

        rows = await fetch_aliexpress_listings(
            search_terms=search_terms,
            min_price=min_price,
            max_price=max_price,
        )
        return [
            ComponentListing(
                title=row.get("title", ""),
                price=float(row.get("price", 0)),
                source="aliexpress",
                url=row.get("url", ""),
                image_url=row.get("image_urls", [None])[0] if row.get("image_urls") else None,
                condition=row.get("condition", "new"),
                estimated_delivery_days=row.get("estimated_delivery_days"),
            )
            for row in rows
            if min_price <= float(row.get("price", 0)) <= max_price
        ]
    except Exception as exc:
        log.warning("component_search.aliexpress_error", error=str(exc))
        return []
