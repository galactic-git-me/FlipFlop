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
    """Convert component model names to Vinted search terms that actually find listings."""
    name_lower = component_name.lower()
    terms = []

    # GPU/Graphics cards
    if any(x in name_lower for x in ["rtx", "gtx", "radeon", "gpu", "graphics card"]):
        if "3060" in name_lower:
            terms.extend(["RTX 3060", "3060 12GB", "graphics card"])
        elif "3070" in name_lower:
            terms.extend(["RTX 3070", "3070 8GB"])
        elif "3080" in name_lower:
            terms.extend(["RTX 3080", "3080 10GB"])
        else:
            terms.extend(["graphics card", "GPU", "RTX", "GTX"])

    # CPU/Processors
    elif any(x in name_lower for x in ["core i", "ryzen", "cpu"]):
        if "i5" in name_lower or "ryzen 5" in name_lower:
            terms.extend(["CPU", "Intel Core i5", "AMD Ryzen 5"])
        elif "i7" in name_lower or "ryzen 7" in name_lower:
            terms.extend(["CPU", "Intel Core i7", "AMD Ryzen 7"])
        else:
            terms.extend(["CPU", "processor"])

    # RAM
    elif any(x in name_lower for x in ["ddr4", "ddr5", "ram"]):
        if "16gb" in name_lower:
            terms.extend(["16GB RAM", "DDR4 RAM", "DDR5 RAM"])
        elif "32gb" in name_lower:
            terms.extend(["32GB RAM", "DDR4 RAM", "DDR5 RAM"])
        elif "64gb" in name_lower:
            terms.extend(["64GB RAM", "DDR4 kit", "DDR5 kit"])
        elif "8gb" in name_lower:
            terms.extend(["8GB RAM", "DDR4 RAM", "DDR5 RAM"])
        else:
            terms.extend(["RAM", "DDR4 RAM", "DDR5 RAM"])

    # SSDs/Storage
    elif any(x in name_lower for x in ["ssd", "nvme", "m.2"]):
        if "nvme" in name_lower or "m.2" in name_lower:
            terms.extend(["NVMe SSD", "M.2 SSD"])
        if "500gb" in name_lower:
            terms.extend(["500GB SSD"])
        elif "1tb" in name_lower or "2tb" in name_lower:
            terms.extend(["SSD 1TB", "SSD 2TB"])
        else:
            terms.extend(["SSD", "NVMe SSD"])

    # PSU/Power supplies
    elif any(x in name_lower for x in ["psu", "power supply", "650w", "750w", "850w"]):
        for wattage in ["650w", "750w", "850w", "1000w", "1200w"]:
            if wattage in name_lower:
                terms.append(f"power supply {wattage}")
        if not terms:
            terms.extend(["power supply", "PSU"])

    # Motherboards
    elif any(x in name_lower for x in ["motherboard", "mobo", "atx", "am4", "am5", "lga"]):
        terms.extend(["motherboard", "mobo"])
        if "am4" in name_lower:
            terms.append("AM4 motherboard")
        elif "am5" in name_lower:
            terms.append("AM5 motherboard")
        elif "lga" in name_lower:
            terms.append("Intel motherboard")

    # CPU Coolers
    elif any(x in name_lower for x in ["cooler", "heatsink", "aio"]):
        terms.extend(["CPU cooler", "cooler"])

    # Fallback: use generic terms
    if not terms:
        terms = [component_name, "PC component"]

    return terms[:3]  # Return top 3 most relevant terms


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
